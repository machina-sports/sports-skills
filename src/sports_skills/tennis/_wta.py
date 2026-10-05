"""WTA public API (api.wtatennis.com) — tournament entry lists and player match results.

Keyed by the WTA's own numeric ids, which are unrelated to the ESPN athlete and
event ids used by the rest of the tennis module. The API is public but
undocumented: field meanings here are read from its payloads, and a field whose
meaning is not evident is passed through raw rather than interpreted.
"""

from __future__ import annotations

import datetime
import functools
import json
import logging
import math
import re
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

logger = logging.getLogger("sports_skills.tennis.wta")

_API_BASE = "https://api.wtatennis.com/tennis"
_PROVIDER = "WTA (api.wtatennis.com)"

_wta_rate_limiter = RateLimiter(max_tokens=2, refill_rate=1.0)

_TIMEOUT = 15
_CACHE_TTL = 600

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 200

# Open Era start; an earlier year is not a meaningful WTA query.
_MIN_YEAR = 1968

# Positive decimal without leading zeros, ASCII digits only (``\d`` would also
# admit non-ASCII digits). "08001" is rejected rather than rewritten to "8001".
_ID_RE = re.compile(r"[1-9][0-9]{0,9}")
_INT_RE = re.compile(r"-?[0-9]{1,6}")

# Format is derived from how many players stand on each side, never from a
# provider code. Codes (event_type_code, s_d_flag, qpm_flag, winner) stay raw.
_FORMATS = {1: "singles", 2: "doubles"}

_ENTRY_NOTE = (
    "Entry list as published by the WTA when it was retrieved (see source). It changes as players "
    "withdraw, qualify, or enter late, so it is not a final draw."
)
_EMPTY_ENTRY_NOTE = (
    "The WTA API returned no events for this tournament and year: the entry list may not be "
    "published yet, or this tournament_id/year pair may not exist."
)
_RESULTS_NOTE = (
    "A bounded window of the player's most recent WTA results: one request for at most `limit` "
    "matches (with `year`, from that tournament year only). It is not the full career history and "
    "carries no total count; has_more says only whether the provider had at least one further match "
    "beyond this window. tournament_start_date is the tournament's start date, not the date a match "
    "was played."
)
_RESULTS_ORDERING = (
    "As delivered by the WTA API for sort=desc (newest first); the connector does not re-sort. "
    "Matches within one tournament are not guaranteed to be in the order they were played."
)
_LIVE_SOURCE_NOTE = (
    "fetched_at is when this connector obtained the response from the WTA API (a cached response "
    "keeps its original fetch time); served_at is when this result was returned. Neither says when "
    "the WTA last updated the data or when any match was played."
)
_REPLAY_SOURCE_NOTE = (
    "Served with SPORTS_SKILLS_REPLAY={mode}: the response may come from a local recording whose "
    "original fetch time is not known here, so fetched_at is null. served_at is when it was served "
    "locally; it is not the freshness of the data or of any event."
)


class _WtaError(Exception):
    """A request cannot be built or served as asked."""

    def __init__(self, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.extra = extra


def _guard(fn):
    """Return connector errors as data instead of raising.

    These functions are called by autonomous agents, so a bad parameter, an
    upstream failure, or an unexpected payload has to arrive as a readable
    message rather than an unhandled traceback.
    """

    @functools.wraps(fn)
    def wrapper(request_data: dict[str, Any]) -> dict[str, Any]:
        try:
            return fn(request_data)
        except _WtaError as exc:
            return {"error": True, "message": str(exc), **exc.extra}
        except Exception as exc:  # noqa: BLE001 — surface, never crash the agent
            logger.debug("WTA call failed", exc_info=True)
            return {"error": True, "message": f"WTA backend error ({type(exc).__name__}): {exc}"}

    return wrapper


# ============================================================
# Validation
# ============================================================


def _native_id(value: Any) -> str | None:
    """A positive WTA numeric id (decimal, no leading zeros) as a string, or None."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    text = str(value)
    return text if _ID_RE.fullmatch(text) else None


def _payload_id(value: Any) -> str | None:
    """An id field from a provider payload, which may be space-padded (e.g. " 847")."""
    return _native_id(value.strip() if isinstance(value, str) else value)


def _parse_id(value: Any, name: str) -> str:
    if value is None or value == "":
        raise _WtaError(f"{name} is required: the WTA's numeric id (e.g. 901), not an ESPN id.")
    native = _native_id(value)
    if native is None:
        raise _WtaError(
            f"Invalid {name} {value!r}: must be a positive WTA numeric id (digits only, no leading zeros)."
        )
    return native


def _as_int(value: Any) -> int | None:
    """``value`` as a whole number, or None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) and value.is_integer() else None
    if isinstance(value, str) and _INT_RE.fullmatch(value.strip()):
        return int(value)
    return None


def _parse_year(value: Any, required: bool) -> int | None:
    if value is None or value == "":
        if required:
            raise _WtaError("year is required (e.g. 2025).")
        return None
    year = _as_int(value)
    latest = datetime.datetime.now(datetime.timezone.utc).year + 1
    if year is None or not _MIN_YEAR <= year <= latest:
        raise _WtaError(f"Invalid year {value!r}: must be a whole year between {_MIN_YEAR} and {latest}.")
    return year


def _parse_limit(value: Any) -> int:
    if value is None or value == "":
        return _DEFAULT_LIMIT
    limit = _as_int(value)
    if limit is None or not 1 <= limit <= _MAX_LIMIT:
        raise _WtaError(f"Invalid limit {value!r}: must be a whole number between 1 and {_MAX_LIMIT}.")
    return limit


# ============================================================
# Fetch
# ============================================================


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch(path: str, rows_key: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """GET one WTA API path whose payload holds a ``rows_key`` list.

    Returns ``(url, payload, source)``. Rate-limited and cached for ten minutes;
    a cached hit keeps its original fetch time. The cache is skipped while
    record/replay is active, so every call reaches ``_http_fetch`` and the
    replay directory.
    """
    url = f"{_API_BASE}/{path}"
    mode = _replay.mode()
    use_cache = mode == _replay.OFF
    cache_key = f"wta:{path}"
    if use_cache:
        cached = _cache_get(cache_key)
        if cached is not None:
            payload, fetched_at = cached
            return url, payload, _source(url, mode, fetched_at)

    raw, err = _http_fetch(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
        rate_limiter=_wta_rate_limiter,
        timeout=_TIMEOUT,
    )
    if err:
        extra = {k: err[k] for k in ("status_code", "replay_miss", "replay_error") if k in err}
        raise _WtaError(f"WTA API request failed for {url}: {err.get('message') or 'unknown error'}", **extra)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise _WtaError(f"WTA API returned invalid JSON for {url}") from None
    if not isinstance(payload, dict) or not isinstance(payload.get(rows_key), list):
        raise _WtaError(
            f"WTA API returned an unexpected response shape for {url}: expected an object with a "
            f"'{rows_key}' list. The provider format may have changed."
        )

    fetched_at = _now_iso()
    if use_cache:
        _cache_set(cache_key, (payload, fetched_at), ttl=_CACHE_TTL)
    return url, payload, _source(url, mode, fetched_at)


def _source(url: str, mode: str, fetched_at: str) -> dict[str, Any]:
    """Provenance block. ``fetched_at`` is a live fetch time only in off/record
    mode; replay and fill may serve a recording, so they report ``served_at`` only."""
    live = mode in (_replay.OFF, _replay.RECORD)
    return {
        "provider": _PROVIDER,
        "url": url,
        "replay_mode": mode,
        "fetched_at": fetched_at if live else None,
        "served_at": _now_iso(),
        "note": _LIVE_SOURCE_NOTE if live else _REPLAY_SOURCE_NOTE.format(mode=mode),
    }


# ============================================================
# Normalizers
# ============================================================


def _text(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    text = str(value).strip()
    return text or None


def _flag(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _seed(value: Any) -> int | str | None:
    """Seeds are numeric strings on entry lists and ints on results; keep anything else raw."""
    number = _as_int(value)
    return number if number is not None else _text(value)


def _iso_date(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()[:10]
    try:
        datetime.datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return None
    return text


def _person(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    player_id = _native_id(raw.get("id"))
    if player_id is None:
        return None
    name = _text(raw.get("fullName"))
    if name is None:
        parts = [_text(raw.get("firstName")), _text(raw.get("lastName"))]
        name = " ".join(p for p in parts if p) or None
    return {"id": player_id, "name": name, "country_code": _text(raw.get("countryCode"))}


def _normalize_entry(raw: Any) -> dict[str, Any] | None:
    """One singles player or doubles team on an entry list, or None if malformed."""
    if not isinstance(raw, dict) or not isinstance(raw.get("players"), list) or not raw["players"]:
        return None
    players = [_person(p) for p in raw["players"]]
    if any(p is None for p in players):
        return None
    return {
        "players": players,
        "seed": _seed(raw.get("seed")),
        "entry_type": _text(raw.get("entryType")),
        "eliminated": _flag(raw.get("eliminated")),
        "winner": _flag(raw.get("winner")),
        "runner_up": _flag(raw.get("runnerUp")),
    }


def _normalize_event(raw: Any) -> tuple[dict[str, Any] | None, int]:
    """One event (e.g. singles, doubles) of an entry list and the number of rows skipped as malformed."""
    if not isinstance(raw, dict) or not isinstance(raw.get("eventPlayers"), list):
        return None, 1
    entries = []
    skipped = 0
    for raw_entry in raw["eventPlayers"]:
        entry = _normalize_entry(raw_entry)
        if entry is None:
            skipped += 1
        else:
            entries.append(entry)
    sizes = {len(e["players"]) for e in entries}
    description = _text(raw.get("description"))
    return {
        "event_type_code": _text(raw.get("eventTypeCode")),
        # The provider sends the literal string "null" for an absent description.
        "description": None if description == "null" else description,
        # Derived from team sizes, not from event_type_code.
        "format": _FORMATS.get(sizes.pop()) if len(sizes) == 1 else None,
        "entries": entries,
        "count": len(entries),
    }, skipped


def _normalize_match(raw: Any) -> dict[str, Any] | None:
    """One match row of a player's history, or None if it has no usable tournament date."""
    if not isinstance(raw, dict):
        return None
    tournament = raw.get("tournament") if isinstance(raw.get("tournament"), dict) else {}
    group = tournament.get("tournamentGroup") if isinstance(tournament.get("tournamentGroup"), dict) else {}

    start = _iso_date(tournament.get("startDate")) or _iso_date(raw.get("StartDate"))
    if start is None:
        return None
    year = _as_int(tournament.get("year")) or _as_int(raw.get("tourn_year")) or int(start[:4])

    # The provider's side-numbered winner code is passed through raw: no public
    # source documents which side it names relative to the requested player.
    winner_code = raw.get("winner")
    if isinstance(winner_code, bool) or not isinstance(winner_code, (int, str)):
        winner_code = None

    scores = raw.get("scores")
    score = " ".join(scores.split()) if isinstance(scores, str) else ""
    partner = _person(raw.get("partner"))
    opponents = [p for p in (_person(raw.get("opponent")), _person(raw.get("opponent_partner"))) if p]
    side_size = 2 if partner else 1

    return {
        "tournament_start_date": start,
        "tournament": {
            "id": _native_id(group.get("id")) or _payload_id(raw.get("tourn_nbr")),
            "name": _text(group.get("name")) or _text(raw.get("TournamentName")),
            "title": _text(tournament.get("title")),
            "level": _text(tournament.get("level")) or _text(raw.get("TournamentLevel")),
            "year": year,
            "end_date": _iso_date(tournament.get("endDate")),
            "surface": _text(tournament.get("surface")) or _text(raw.get("Surface")),
            "in_outdoor": _text(tournament.get("inOutdoor")),
            "city": _text(tournament.get("city")),
            "country": _text(tournament.get("country")) or _text(raw.get("Country")),
        },
        "round": _text(raw.get("round_name")),
        # Derived from participant count; null when the two sides differ in size.
        "format": _FORMATS[side_size] if len(opponents) == side_size else None,
        "match_type_code": _text(raw.get("s_d_flag")),
        "draw_code": _text(raw.get("qpm_flag")),
        "partner": partner,
        "opponents": opponents,
        # Provider score string with whitespace collapsed; its orientation is not documented.
        "score": score or None,
        "winner_code": winner_code,
        "player_seed": _seed(raw.get("seed_1")),
        "opponent_seed": _seed(raw.get("seed_2")),
        "player_entry_type": _text(raw.get("entry_type_1")),
        "opponent_entry_type": _text(raw.get("entry_type_2")),
        "reason_code": _text(raw.get("reason_code")),
    }


def _skipped_warning(skipped: int, what: str) -> str:
    return f"Skipped {skipped} malformed {what} row(s) from the WTA API."


# ============================================================
# Command Functions
# ============================================================


@_guard
def get_wta_entry_list(request_data: dict[str, Any]) -> dict[str, Any]:
    """Entry list (singles and doubles) for one WTA tournament edition."""
    params = request_data.get("params", {})
    tournament_id = _parse_id(params.get("tournament_id"), "tournament_id")
    year = _parse_year(params.get("year"), required=True)

    url, payload, source = _fetch(f"tournaments/{tournament_id}/{year}/players", "events")

    events = []
    skipped = 0
    for raw_event in payload["events"]:
        event, event_skipped = _normalize_event(raw_event)
        skipped += event_skipped
        if event is not None:
            events.append(event)

    entry_count = sum(e["count"] for e in events)
    if skipped and not entry_count:
        raise _WtaError(
            f"WTA API returned {skipped} entry-list row(s) for {url}, none in a recognised shape. "
            "The provider format may have changed."
        )

    result = {
        "tournament_id": tournament_id,
        "year": year,
        "events": events,
        "count": len(events),
        "entry_count": entry_count,
        "source": source,
        "note": _ENTRY_NOTE if events else _EMPTY_ENTRY_NOTE,
    }
    if skipped:
        result["skipped_rows"] = skipped
        result["warnings"] = [_skipped_warning(skipped, "entry-list")]
    return result


@_guard
def get_wta_player_results(request_data: dict[str, Any]) -> dict[str, Any]:
    """A player's most recent WTA match results (one bounded request), newest first."""
    params = request_data.get("params", {})
    player_id = _parse_id(params.get("player_id"), "player_id")
    year = _parse_year(params.get("year"), required=False)
    limit = _parse_limit(params.get("limit"))

    # The bare endpoint returns only the oldest few matches. Ask for the newest
    # page explicitly, with one extra row as a sentinel for has_more.
    query = {"page": 0, "pageSize": limit + 1, "sort": "desc"}
    if year is not None:
        query = {"year": year, **query}
    url, payload, source = _fetch(f"players/{player_id}/matches?{urllib.parse.urlencode(query)}", "matches")

    rows = payload["matches"]
    matches = []
    skipped = 0
    for raw_match in rows[:limit]:
        match = _normalize_match(raw_match)
        if match is None:
            skipped += 1
        else:
            matches.append(match)
    if skipped and not matches:
        raise _WtaError(
            f"WTA API returned {skipped} match row(s) for {url}, none in a recognised shape. "
            "The provider format may have changed."
        )

    if year is not None:
        off_year = sum(1 for m in matches if m["tournament"]["year"] != year)
        if off_year:
            raise _WtaError(
                f"WTA API returned {off_year} match row(s) outside year {year} for {url}. The provider "
                "may have ignored the year filter, so this result is inconclusive and was not returned."
            )

    result = {
        "player": _person(payload.get("player")) or {"id": player_id, "name": None, "country_code": None},
        "year": year,
        "limit": limit,
        "matches": matches,
        "count": len(matches),
        "has_more": len(rows) > limit,
        "history_complete": False,
        "ordering": _RESULTS_ORDERING,
        "source": source,
        "note": _RESULTS_NOTE,
    }
    if skipped:
        result["skipped_rows"] = skipped
        result["warnings"] = [_skipped_warning(skipped, "match")]
    return result
