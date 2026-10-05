"""Sleeper public API connector — NFL fantasy trending adds/drops.

Sleeper's read-only public API (https://docs.sleeper.com) needs no key. A
trending row carries only a Sleeper player ID and a count; names, teams and
positions come from Sleeper's NFL player catalog, a multi-megabyte payload
Sleeper asks clients to fetch at most once a day. Player IDs stay in Sleeper's
own namespace: no ESPN or nflverse mapping is attempted.

The catalog, trimmed to IDs, names, teams and positions, is kept in memory and
on disk (``$XDG_CACHE_HOME/sports-skills/sleeper/``) so separate CLI processes
share one fetch a day. Trending results are cached in-process only.
"""

from __future__ import annotations

import contextlib
import datetime
import functools
import json
import logging
import os
import re
import tempfile
import urllib.parse
from typing import Any

from sports_skills import _replay
from sports_skills._espn_base import (
    _USER_AGENT,
    RateLimiter,
    _cache_get,
    _cache_set,
    _http_fetch,
)

logger = logging.getLogger("sports_skills.nfl._sleeper")

_PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl"

_TREND_TYPES = ("add", "drop")
_MAX_LOOKBACK_HOURS = 168
_MAX_LIMIT = 100

# Trends move through the day; the catalog changes slowly and Sleeper asks for
# at most one fetch a day.
_TRENDING_TTL = 300
_CATALOG_TTL = 86400
_CATALOG_KEY = "sleeper:players:nfl"
_CATALOG_TIMEOUT = 60
_CATALOG_FIELDS = ("name", "team", "position")
# A catalog object counts as a player record only if it carries at least one of
# these keys, each null or a string. Error envelopes and wrapped catalogs do not.
_PLAYER_KEYS = ("full_name", "first_name", "last_name", "team", "position")
# Bump when the on-disk record changes shape; older files then read as a miss.
_CATALOG_CACHE_SCHEMA = 1
_CATALOG_CACHE_FILE = "players-nfl.json"

_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

_sleeper_rate_limiter = RateLimiter(max_tokens=2, refill_rate=2.0)

_DIGITS = re.compile(r"[0-9]+")

_NOTE = (
    "count is the add/drop tally Sleeper's trending API reports for the player over "
    "the lookback window. It is a popularity signal among Sleeper users, not a "
    "projection, ranking, or betting edge."
)


class _SleeperError(Exception):
    """A request cannot be built, or Sleeper's response is not the expected shape."""


def _guard(fn):
    """Return connector errors as data instead of raising.

    These functions are called by autonomous agents, so a bad parameter, an
    upstream failure, or a changed response shape has to arrive as a readable
    message rather than an unhandled traceback.
    """

    @functools.wraps(fn)
    def wrapper(request_data: dict[str, Any]) -> dict[str, Any]:
        try:
            return fn(request_data)
        except _SleeperError as exc:
            return {"error": True, "message": str(exc)}
        except Exception as exc:  # noqa: BLE001 — surface, never crash the agent
            logger.debug("sleeper call failed", exc_info=True)
            return {
                "error": True,
                "message": f"Sleeper backend error ({type(exc).__name__}): {exc}",
            }

    return wrapper


def _utcnow() -> datetime.datetime:
    """Current UTC time (a seam for tests)."""
    return datetime.datetime.now(datetime.timezone.utc)


def _timestamp() -> str:
    return _utcnow().strftime(_TIMESTAMP_FORMAT)


def _trend_type(value: Any) -> str:
    if isinstance(value, str) and value.strip().lower() in _TREND_TYPES:
        return value.strip().lower()
    raise _SleeperError(f"trend_type must be 'add' or 'drop'; got {value!r}.")


def _bounded_int(name: str, value: Any, maximum: int) -> int:
    """A whole number in ``1..maximum``.

    Digit strings are accepted because the CLI passes some integers as text.
    Booleans and floats (even ``24.0``) are refused rather than coerced.
    """
    number = None
    if isinstance(value, int) and not isinstance(value, bool):
        number = value
    elif isinstance(value, str) and _DIGITS.fullmatch(value.strip()):
        number = int(value.strip())
    if number is None or not 1 <= number <= maximum:
        raise _SleeperError(f"{name} must be a whole number from 1 to {maximum}; got {value!r}.")
    return number


def _fetch_error(what: str, err: dict[str, Any]) -> dict[str, Any]:
    """Keep ``status_code`` and replay flags; say which Sleeper request failed."""
    out = dict(err)
    out["message"] = f"Sleeper {what} request failed: {err.get('message') or 'unknown error'}"
    return out


def _parse_trending(raw: bytes) -> list[dict[str, Any]]:
    try:
        payload = json.loads(raw)
    except ValueError:
        raise _SleeperError("Sleeper trending response was not valid JSON.") from None
    if not isinstance(payload, list):
        raise _SleeperError(
            f"Sleeper trending response was a JSON {type(payload).__name__}, expected a list."
        )
    rows = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise _SleeperError(f"Sleeper trending item {index} is not an object: {item!r}.")
        player_id = item.get("player_id")
        count = item.get("count")
        if isinstance(player_id, bool) or not isinstance(player_id, (str, int)) or not str(player_id).strip():
            raise _SleeperError(f"Sleeper trending item {index} has no usable player_id: {player_id!r}.")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise _SleeperError(f"Sleeper trending item {index} has no usable count: {count!r}.")
        rows.append({"player_id": str(player_id).strip(), "count": count})
    return rows


def _fetch_trending(url: str, cache_key: str, use_cache: bool) -> dict[str, Any]:
    """``{"rows", "fetched_at"}`` or an error dict. Cached only on success."""
    if use_cache:
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached
    raw, err = _http_fetch(url, headers={"User-Agent": _USER_AGENT}, rate_limiter=_sleeper_rate_limiter)
    if err:
        return _fetch_error("trending", err)
    entry = {"rows": _parse_trending(raw), "fetched_at": _timestamp()}
    if use_cache:
        _cache_set(cache_key, entry, ttl=_TRENDING_TTL)
    return entry


def _text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _catalog_fields(entry: dict[str, Any]) -> dict[str, Any]:
    """Name/team/position of one catalog entry. Team defenses have no full_name."""
    name = _text(entry.get("full_name"))
    if name is None:
        parts = [p for p in (_text(entry.get("first_name")), _text(entry.get("last_name"))) if p]
        name = " ".join(parts) or None
    return {"name": name, "team": _text(entry.get("team")), "position": _text(entry.get("position"))}


def _catalog_cache_path() -> str:
    """On-disk catalog location, following the cricsheet cache convention."""
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "sports-skills", "sleeper", _CATALOG_CACHE_FILE)


def _valid_index(index: Any) -> bool:
    """True if ``index`` is a non-empty mapping of entries exactly as ``_load_catalog`` builds them."""
    if not isinstance(index, dict) or not index:
        return False
    for entry in index.values():
        if not isinstance(entry, dict) or set(entry) != set(_CATALOG_FIELDS):
            return False
        # _load_catalog never stores an entry with nothing known.
        if all(value is None for value in entry.values()):
            return False
        # Each field is None or a stripped, non-empty string.
        if any(value is not None and _text(value) != value for value in entry.values()):
            return False
    return True


def _read_disk_catalog() -> tuple[dict[str, Any], float] | None:
    """``(catalog, seconds_left)`` from disk, or None.

    Missing, unreadable, corrupt, wrong-schema, future-dated and expired files
    are all misses, so expired data is never served as current. The lifetime
    counts from the original ``fetched_at``, not from when the file was read.
    """
    try:
        with open(_catalog_cache_path(), encoding="utf-8") as f:
            record = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict):
        return None
    schema = record.get("schema")
    if isinstance(schema, bool) or schema != _CATALOG_CACHE_SCHEMA or not _valid_index(record.get("index")):
        return None
    fetched_at = record.get("fetched_at")
    try:
        fetched = datetime.datetime.strptime(fetched_at, _TIMESTAMP_FORMAT)
    except (TypeError, ValueError):
        return None
    age = (_utcnow() - fetched.replace(tzinfo=datetime.timezone.utc)).total_seconds()
    if not 0 <= age < _CATALOG_TTL:
        return None
    return {"index": record["index"], "fetched_at": fetched_at}, _CATALOG_TTL - age


def _write_disk_catalog(catalog: dict[str, Any]) -> None:
    """Best effort: a failure is logged at debug level and the call still succeeds.

    Written to a temporary file and renamed into place, so a reader never sees
    a partial file; on failure the temporary file is removed and any previous
    cache file is left as it was.
    """
    path = _catalog_cache_path()
    directory = os.path.dirname(path)
    record = {"schema": _CATALOG_CACHE_SCHEMA, "fetched_at": catalog["fetched_at"], "index": catalog["index"]}
    tmp = None
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".players-nfl.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(record, f, separators=(",", ":"))
        os.replace(tmp, path)
    except OSError:
        logger.debug("could not write Sleeper catalog cache %s", path, exc_info=True)
        if tmp is not None:
            with contextlib.suppress(OSError):
                os.remove(tmp)


def _load_catalog(use_cache: bool) -> tuple[dict[str, Any] | None, str | None]:
    """``({"index", "fetched_at"}, None)`` or ``(None, reason)``. Failures are not cached.

    Non-object values are skipped, but any object that is not a player record
    rejects the whole response. Records with no known name, team or position
    are left out of the index: a lookup miss reports the same nulls.
    """
    if use_cache:
        cached = _cache_get(_CATALOG_KEY)
        if cached is not None:
            return cached, None
        on_disk = _read_disk_catalog()
        if on_disk is not None:
            catalog, seconds_left = on_disk
            _cache_set(_CATALOG_KEY, catalog, ttl=seconds_left)
            return catalog, None
    raw, err = _http_fetch(
        _PLAYERS_URL,
        headers={"User-Agent": _USER_AGENT},
        rate_limiter=_sleeper_rate_limiter,
        timeout=_CATALOG_TIMEOUT,
    )
    if err:
        return None, err.get("message") or "request failed"
    try:
        payload = json.loads(raw)
    except ValueError:
        return None, "response was not valid JSON"
    if not isinstance(payload, dict) or not payload:
        return None, "response was not a non-empty object keyed by player ID"
    index = {}
    for pid, entry in payload.items():
        if not isinstance(entry, dict):
            continue
        values = [entry[key] for key in _PLAYER_KEYS if key in entry]
        if not values or not all(value is None or isinstance(value, str) for value in values):
            return None, f"entry {pid!r} is not a player record"
        fields = _catalog_fields(entry)
        if any(value is not None for value in fields.values()):
            index[str(pid)] = fields
    if not index:
        return None, "response held no player objects"
    catalog = {"index": index, "fetched_at": _timestamp()}
    if use_cache:
        _cache_set(_CATALOG_KEY, catalog, ttl=_CATALOG_TTL)
        _write_disk_catalog(catalog)
    return catalog, None


@_guard
def get_fantasy_trending(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    trend_type = _trend_type(params.get("trend_type", "add"))
    lookback_hours = _bounded_int("lookback_hours", params.get("lookback_hours", 24), _MAX_LOOKBACK_HOURS)
    limit = _bounded_int("limit", params.get("limit", 10), _MAX_LIMIT)

    # Record/replay must see every request: a memory or disk cache hit would
    # skip recording, or serve live data during a replay. Neither is written.
    mode = _replay.mode()
    use_cache = mode == _replay.OFF

    query = urllib.parse.urlencode({"lookback_hours": lookback_hours, "limit": limit})
    trending_url = f"{_PLAYERS_URL}/trending/{trend_type}?{query}"
    trending = _fetch_trending(
        trending_url, f"sleeper:trending:nfl:{trend_type}:{lookback_hours}:{limit}", use_cache
    )
    if trending.get("error"):
        return trending
    rows = trending["rows"][:limit]

    warnings = []
    catalog = None
    if not rows:
        catalog_status = "not_needed"
    else:
        catalog, reason = _load_catalog(use_cache)
        catalog_status = "loaded" if catalog else "unavailable"
        if reason:
            warnings.append(
                f"Sleeper player catalog unavailable ({reason}); names, teams and positions "
                "are unresolved. Counts and Sleeper player IDs are still valid."
            )
    index = catalog["index"] if catalog else {}

    players = []
    for rank, row in enumerate(rows, 1):
        info = index.get(row["player_id"]) or {}
        players.append(
            {
                "rank": rank,
                "sleeper_player_id": row["player_id"],
                "name": info.get("name"),
                "name_resolved": info.get("name") is not None,
                "team": info.get("team"),
                "position": info.get("position"),
                "count": row["count"],
            }
        )
    unresolved = [p["sleeper_player_id"] for p in players if not p["name_resolved"]]
    if catalog and unresolved:
        warnings.append(
            f"{len(unresolved)} Sleeper player ID(s) have no name in the player catalog: "
            f"{', '.join(unresolved)}."
        )
    if mode in (_replay.REPLAY, _replay.FILL):
        warnings.append(
            f"{_replay.MODE_ENV}={mode}: responses may come from recordings; fetched_at "
            "is when this run read them, not when they were recorded."
        )

    result = {
        "provider": "sleeper",
        "sport": "nfl",
        "trend_type": trend_type,
        "lookback_hours": lookback_hours,
        "limit": limit,
        "players": players,
        "count": len(players),
        "unresolved_count": len(unresolved),
        "catalog_status": catalog_status,
        "source": {
            "trending_url": trending_url,
            "trending_fetched_at": trending["fetched_at"],
            "players_url": _PLAYERS_URL if rows else None,
            "players_fetched_at": catalog["fetched_at"] if catalog else None,
        },
        "note": _NOTE,
    }
    if warnings:
        result["warnings"] = warnings
    return result
