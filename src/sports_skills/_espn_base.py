"""Shared ESPN HTTP infrastructure for US sports modules.

Provides caching, rate limiting, retry logic, and parameterized
ESPN API request functions. Used by nfl, nba, nhl, mlb, wnba modules.
"""

from __future__ import annotations

import datetime
import gzip
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("sports_skills._espn_base")


# ============================================================
# ESPN Status Map (common across all US sports)
# ============================================================

ESPN_STATUS_MAP = {
    "STATUS_SCHEDULED": "not_started",
    "STATUS_IN_PROGRESS": "live",
    "STATUS_HALFTIME": "halftime",
    "STATUS_FINAL": "closed",
    "STATUS_FULL_TIME": "closed",
    "STATUS_POSTPONED": "postponed",
    "STATUS_CANCELED": "cancelled",
    "STATUS_SUSPENDED": "suspended",
    "STATUS_END_PERIOD": "period_break",
    "STATUS_DELAYED": "delayed",
    "STATUS_RAIN_DELAY": "delayed",
    "STATUS_FIRST_HALF": "1st_half",
    "STATUS_SECOND_HALF": "2nd_half",
}


# ============================================================
# Module-Level Cache (TTL-based)
# ============================================================

_cache = {}
_cache_lock = threading.Lock()


def _cache_get(key):
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if time.monotonic() > expiry:
            del _cache[key]
            return None
        return value


def _cache_set(key, value, ttl=300):
    with _cache_lock:
        if len(_cache) > 500:
            now = time.monotonic()
            expired = [k for k, (_, exp) in _cache.items() if now > exp]
            for k in expired:
                del _cache[k]
        _cache[key] = (value, time.monotonic() + ttl)


# ============================================================
# Rate Limiter (Token Bucket)
# ============================================================


class RateLimiter:
    def __init__(self, max_tokens=9, refill_rate=9.0 / 60.0):
        self.max_tokens = max_tokens
        self.tokens = max_tokens
        self.refill_rate = refill_rate
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self):
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now
            if self.tokens >= 1:
                self.tokens -= 1
                return
        time.sleep(max(0, (1 - self.tokens) / self.refill_rate))
        self.acquire()


_espn_rate_limiter = RateLimiter(max_tokens=2, refill_rate=2.0)


# ============================================================
# HTTP Helpers — Retry, Error Handling
# ============================================================

_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

_RETRYABLE_CODES = {429, 500, 502, 503, 504}

_MAX_RETRIES = 2
_RETRY_BASE_DELAY = 1.0
_RETRY_MAX_DELAY = 4.0


def _is_retryable(exc):
    """Check if an exception is worth retrying (transient failures only)."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in _RETRYABLE_CODES
    if isinstance(exc, (urllib.error.URLError, OSError, TimeoutError)):
        return True
    return False


def _http_fetch(
    url,
    headers=None,
    rate_limiter=None,
    timeout=30,
    max_retries=_MAX_RETRIES,
    decode_gzip=False,
):
    """Core HTTP fetch with retry + exponential backoff.

    Returns (data_bytes, None) on success or (None, error_dict) on failure.
    Only retries on transient errors (5xx, 429, timeouts, connection errors).
    Client errors (4xx except 429) fail immediately.
    """
    last_error = None
    for attempt in range(1 + max_retries):
        if rate_limiter:
            rate_limiter.acquire()
        req = urllib.request.Request(url)
        for key, value in (headers or {}).items():
            req.add_header(key, value)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if decode_gzip and resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return raw, None
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode() if e.fp else ""
            except Exception:
                pass
            last_error = {"error": True, "status_code": e.code, "message": body}
            if not _is_retryable(e):
                logger.debug("HTTP %d (non-retryable) for %s", e.code, url)
                return None, last_error
            logger.debug(
                "HTTP %d (retryable, attempt %d/%d) for %s",
                e.code,
                attempt + 1,
                1 + max_retries,
                url,
            )
        except Exception as e:
            last_error = {"error": True, "message": str(e)}
            if not _is_retryable(e):
                logger.debug("Non-retryable error for %s: %s", url, e)
                return None, last_error
            logger.debug(
                "Retryable error (attempt %d/%d) for %s: %s",
                attempt + 1,
                1 + max_retries,
                url,
                e,
            )

        if attempt < max_retries:
            delay = min(_RETRY_BASE_DELAY * (2**attempt), _RETRY_MAX_DELAY)
            if isinstance(last_error, dict) and last_error.get("status_code") == 429:
                delay = min(delay * 2, _RETRY_MAX_DELAY * 2)
            time.sleep(delay)

    if max_retries > 0:
        logger.warning(
            "All %d attempts failed for %s: %s",
            1 + max_retries,
            url,
            last_error.get("message", ""),
        )
    else:
        logger.debug("Request failed for %s: %s", url, last_error.get("message", ""))
    return None, last_error


# ============================================================
# ESPN API Request Functions (parameterized by sport)
# ============================================================


def espn_request(sport_path, resource="scoreboard", params=None, max_retries=_MAX_RETRIES):
    """ESPN public site API request. Rate-limited and cached.

    Args:
        sport_path: e.g. "football/nfl", "basketball/nba", "hockey/nhl"
        resource: API resource, e.g. "scoreboard", "teams", "teams/12/roster"
        params: Optional query parameters dict.
        max_retries: Set to 0 for exploratory/probing requests.
    """
    cache_key = f"espn:{sport_path}:{resource}:{json.dumps(params or {}, sort_keys=True)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/{resource}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": _USER_AGENT}
    raw, err = _http_fetch(
        url, headers=headers, rate_limiter=_espn_rate_limiter, max_retries=max_retries
    )
    if err:
        return err
    try:
        data = json.loads(raw.decode())
        _cache_set(cache_key, data, ttl=120)
        return data
    except (json.JSONDecodeError, ValueError):
        return {"error": True, "message": "ESPN returned invalid JSON"}


def espn_web_request(sport_path, resource, params=None):
    """ESPN web API (standings, season lists). Different host from site API.

    Args:
        sport_path: e.g. "football/nfl", "basketball/nba"
        resource: API resource, e.g. "standings"
        params: Optional query parameters dict.
    """
    cache_key = f"espn_web:{sport_path}:{resource}:{json.dumps(params or {}, sort_keys=True)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    url = f"https://site.web.api.espn.com/apis/v2/sports/{sport_path}/{resource}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": _USER_AGENT}
    raw, err = _http_fetch(url, headers=headers, rate_limiter=_espn_rate_limiter)
    if err:
        return err
    try:
        data = json.loads(raw.decode())
        _cache_set(cache_key, data, ttl=300)
        return data
    except (json.JSONDecodeError, ValueError):
        return {"error": True, "message": "ESPN web API returned invalid JSON"}


def espn_summary(sport_path, event_id, max_retries=_MAX_RETRIES):
    """ESPN game summary endpoint (box score, stats, play-by-play summary).

    Args:
        sport_path: e.g. "football/nfl", "basketball/nba"
        event_id: ESPN event ID.
        max_retries: Set to 0 for exploratory requests.

    Returns parsed JSON dict on success, None on failure.
    """
    if not event_id:
        return None
    cache_key = f"espn_summary:{sport_path}:{event_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached if cached else None
    url = (
        f"https://site.web.api.espn.com/apis/site/v2/sports/{sport_path}"
        f"/summary?event={event_id}"
    )
    headers = {"User-Agent": _USER_AGENT}
    raw, err = _http_fetch(
        url, headers=headers, rate_limiter=_espn_rate_limiter, max_retries=max_retries
    )
    if err:
        logger.debug(
            "ESPN summary failed for %s/%s: %s",
            sport_path,
            event_id,
            err.get("message", ""),
        )
        _cache_set(cache_key, {}, ttl=60)
        return None
    try:
        data = json.loads(raw.decode())
        _cache_set(cache_key, data, ttl=300)
        return data
    except (json.JSONDecodeError, ValueError):
        _cache_set(cache_key, {}, ttl=60)
        return None


# ============================================================
# Athlete $ref resolver (shared across NHL, MLB, WNBA, NBA)
# ============================================================

def normalize_odds(odds_list):
    """Normalize ESPN odds data from a competition into a structured format.

    ESPN scoreboard endpoints return DraftKings odds with moneyline, spread,
    and total (over/under) including opening and closing lines. This function
    extracts all available data instead of just the summary string.

    Args:
        odds_list: The ``comp.get("odds", [])`` array from an ESPN competition.

    Returns:
        A dict with structured odds if data is present, or ``None`` if the
        odds list is empty or contains no usable data.
    """
    if not odds_list:
        return None

    o = odds_list[0]  # ESPN provides one provider (DraftKings)
    if o is None:
        return None

    ml = o.get("moneyline", {})
    ps = o.get("pointSpread", {})
    tot = o.get("total", {})
    home_odds = o.get("homeTeamOdds", {})
    away_odds = o.get("awayTeamOdds", {})

    # Determine favorite
    favorite = None
    if home_odds.get("favorite"):
        favorite = "home"
    elif away_odds.get("favorite"):
        favorite = "away"

    result = {
        "provider": o.get("provider", {}).get("name", ""),
        "details": o.get("details", ""),
        "spread": o.get("spread", ""),
        "over_under": o.get("overUnder", ""),
        "favorite": favorite,
    }

    # Moneyline (closing lines) — includes draw for soccer 3-way markets
    if ml:
        result["moneyline"] = {
            "home": ml.get("home", {}).get("close", {}).get("odds", ""),
            "away": ml.get("away", {}).get("close", {}).get("odds", ""),
        }
        draw_ml = ml.get("draw", {}).get("close", {}).get("odds", "")
        if draw_ml:
            result["moneyline"]["draw"] = draw_ml

    # Spread with juice (closing lines)
    if ps:
        result["spread_line"] = {
            "home": {
                "line": ps.get("home", {}).get("close", {}).get("line", ""),
                "odds": ps.get("home", {}).get("close", {}).get("odds", ""),
            },
            "away": {
                "line": ps.get("away", {}).get("close", {}).get("line", ""),
                "odds": ps.get("away", {}).get("close", {}).get("odds", ""),
            },
        }

    # Total (over/under with juice, closing lines)
    if tot:
        result["total"] = {
            "over": {
                "line": tot.get("over", {}).get("close", {}).get("line", ""),
                "odds": tot.get("over", {}).get("close", {}).get("odds", ""),
            },
            "under": {
                "line": tot.get("under", {}).get("close", {}).get("line", ""),
                "odds": tot.get("under", {}).get("close", {}).get("odds", ""),
            },
        }

    # Opening lines (line movement)
    open_ml_home = ml.get("home", {}).get("open", {}).get("odds", "")
    open_ml_away = ml.get("away", {}).get("open", {}).get("odds", "")
    open_ml_draw = ml.get("draw", {}).get("open", {}).get("odds", "")
    open_spread_home = ps.get("home", {}).get("open", {}).get("line", "")
    open_spread_away = ps.get("away", {}).get("open", {}).get("line", "")
    open_total_over = tot.get("over", {}).get("open", {}).get("line", "")

    if any([open_ml_home, open_ml_away, open_spread_home, open_total_over]):
        result["open"] = {}
        if open_ml_home or open_ml_away:
            open_ml = {"home": open_ml_home, "away": open_ml_away}
            if open_ml_draw:
                open_ml["draw"] = open_ml_draw
            result["open"]["moneyline"] = open_ml
        if open_spread_home or open_spread_away:
            result["open"]["spread"] = {
                "home": open_spread_home,
                "away": open_spread_away,
            }
        if open_total_over:
            result["open"]["total"] = open_total_over

    return result


def _resolve_athlete_ref(ref_url: str) -> dict:
    """Follow an ESPN athlete $ref URL and return name + athlete_id.

    ESPN's core leaders API returns athlete data as a $ref link rather than
    inline. This helper fetches the ref and extracts the name and ID, with
    caching so repeated calls for the same athlete are free.

    Returns {"name": str, "id": str}. Empty strings on failure.
    """
    if not ref_url:
        return {"name": "", "id": ""}

    # Extract ID directly from URL (e.g. .../athletes/12345)
    athlete_id = ""
    match = re.search(r'/athletes/(\d+)', ref_url)
    if match:
        athlete_id = match.group(1)

    cache_key = f"athlete_ref:{ref_url}"
    cached = _cache_get(cache_key)
    if cached is not None:
        # Migrate: old cache entries are bare strings
        if isinstance(cached, str):
            return {"name": cached, "id": athlete_id}
        return cached

    headers = {"User-Agent": _USER_AGENT}
    raw, err = _http_fetch(ref_url, headers=headers, timeout=5)
    if err:
        result = {"name": "", "id": athlete_id}
        _cache_set(cache_key, result, ttl=60)
        return result

    try:
        data = json.loads(raw.decode())
        name = data.get("displayName") or data.get("fullName") or ""
        if not athlete_id:
            athlete_id = str(data.get("id", ""))
        result = {"name": name, "id": athlete_id}
        _cache_set(cache_key, result, ttl=3600)
        return result
    except (json.JSONDecodeError, ValueError):
        result = {"name": "", "id": athlete_id}
        _cache_set(cache_key, result, ttl=60)
        return result


# ============================================================
# Core API support (team/player stats, futures)
# ============================================================

CORE_LEAGUE_MAP = {
    "football/nfl": ("football", "nfl"),
    "basketball/nba": ("basketball", "nba"),
    "basketball/wnba": ("basketball", "wnba"),
    "hockey/nhl": ("hockey", "nhl"),
    "baseball/mlb": ("baseball", "mlb"),
    "football/college-football": ("football", "college-football"),
    "basketball/mens-college-basketball": ("basketball", "mens-college-basketball"),
}


def _current_year():
    """Return the current year (UTC)."""
    return datetime.datetime.utcnow().year


def _resolve_team_ref(ref_url: str) -> str:
    """Follow an ESPN team $ref URL and return the team's displayName.

    Same pattern as ``_resolve_athlete_ref`` but for team references.
    Returns empty string on any failure (safe fallback).
    """
    if not ref_url:
        return ""

    cache_key = f"team_ref:{ref_url}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    headers = {"User-Agent": _USER_AGENT}
    raw, err = _http_fetch(ref_url, headers=headers, timeout=5)
    if err:
        _cache_set(cache_key, "", ttl=60)
        return ""

    try:
        data = json.loads(raw.decode())
        name = data.get("displayName") or data.get("name") or ""
        _cache_set(cache_key, name, ttl=3600)
        return name
    except (json.JSONDecodeError, ValueError):
        _cache_set(cache_key, "", ttl=60)
        return ""


def espn_core_request(sport_path, resource_path, ttl=300):
    """ESPN Core API request. Rate-limited and cached.

    Args:
        sport_path: e.g. "football/nfl", "basketball/nba"
        resource_path: Path after the league, e.g. "seasons/2025/futures"
        ttl: Cache TTL in seconds.
    """
    mapping = CORE_LEAGUE_MAP.get(sport_path)
    if not mapping:
        return {"error": True, "message": f"Unknown sport path for core API: {sport_path}"}
    sport, league = mapping

    cache_key = f"espn_core:{sport}:{league}:{resource_path}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    url = (
        f"https://sports.core.api.espn.com/v2/sports/{sport}"
        f"/leagues/{league}/{resource_path}"
    )
    headers = {"User-Agent": _USER_AGENT}
    raw, err = _http_fetch(url, headers=headers, rate_limiter=_espn_rate_limiter)
    if err:
        return err
    try:
        data = json.loads(raw.decode())
        _cache_set(cache_key, data, ttl=ttl)
        return data
    except (json.JSONDecodeError, ValueError):
        return {"error": True, "message": "ESPN core API returned invalid JSON"}


# ============================================================
# Shared Normalizers — Injuries, Transactions, Stats, Futures, Depth Charts
# ============================================================


def normalize_injuries(data):
    """Normalize ESPN injuries response (shared across all US sports).

    Input: full response from ``espn_request(SPORT_PATH, "injuries")``.
    """
    teams = []
    for team_entry in data.get("injuries", []):
        injuries = []
        for inj in team_entry.get("injuries", []):
            athlete = inj.get("athlete", {})
            details = inj.get("details", {})
            inj_type = inj.get("type", {})
            injuries.append({
                "name": athlete.get("displayName", ""),
                "position": athlete.get("position", {}).get("abbreviation", ""),
                "status": inj.get("status", ""),
                "type": inj_type.get("description", inj_type.get("name", "")),
                "detail": details.get("detail", ""),
                "side": details.get("side", ""),
                "return_date": details.get("returnDate", ""),
            })
        teams.append({
            "team": team_entry.get("displayName", ""),
            "team_id": str(team_entry.get("id", "")),
            "injuries": injuries,
            "count": len(injuries),
        })
    return {"teams": teams, "count": len(teams)}


def normalize_transactions(data):
    """Normalize ESPN transactions response (shared across all US sports).

    Input: full response from ``espn_request(SPORT_PATH, "transactions")``.
    """
    transactions = []
    for txn in data.get("transactions", []):
        team = txn.get("team", {})
        transactions.append({
            "date": txn.get("date", ""),
            "team": team.get("displayName", ""),
            "team_abbreviation": team.get("abbreviation", ""),
            "description": txn.get("description", ""),
        })
    return {"transactions": transactions, "count": len(transactions)}


def normalize_core_stats(data):
    """Normalize ESPN core API team/player statistics.

    Input: parsed JSON from the core API statistics endpoint.
    Works for both team and player stats — same structure.
    """
    splits = data.get("splits", {})
    categories = []
    for cat in splits.get("categories", []):
        stats = []
        for stat in cat.get("stats", []):
            entry = {
                "name": stat.get("name", ""),
                "display_name": stat.get("displayName", ""),
                "abbreviation": stat.get("abbreviation", ""),
                "value": stat.get("value"),
                "display_value": stat.get("displayValue", ""),
            }
            if "rank" in stat:
                entry["rank"] = stat["rank"]
                entry["rank_display"] = stat.get("rankDisplayValue", "")
            if "perGameValue" in stat:
                entry["per_game"] = stat["perGameValue"]
                entry["per_game_display"] = stat.get("perGameDisplayValue", "")
            stats.append(entry)
        categories.append({
            "name": cat.get("displayName", cat.get("name", "")),
            "stats": stats,
        })
    return {"categories": categories, "count": len(categories)}


def normalize_futures(data, limit=25):
    """Normalize ESPN core API futures response.

    Resolves athlete/team $ref links for each book entry.

    Args:
        data: Parsed JSON from the core API futures endpoint.
        limit: Max entries per futures market.
    """
    futures = []
    for item in data.get("items", []):
        entries = []
        for future_group in item.get("futures", []):
            for book in future_group.get("books", [])[:limit]:
                athlete_ref = book.get("athlete", {})
                team_ref = book.get("team", {})
                name = ""
                athlete_id = ""
                if isinstance(athlete_ref, dict) and athlete_ref.get("$ref"):
                    resolved = _resolve_athlete_ref(athlete_ref["$ref"])
                    name = resolved["name"]
                    athlete_id = resolved["id"]
                elif isinstance(team_ref, dict) and team_ref.get("$ref"):
                    name = _resolve_team_ref(team_ref["$ref"])
                entry = {
                    "name": name,
                    "value": book.get("value", ""),
                }
                if athlete_id:
                    entry["id"] = athlete_id
                entries.append(entry)
        futures.append({
            "id": item.get("id", ""),
            "name": item.get("displayName", item.get("name", "")),
            "entries": entries,
            "count": len(entries),
        })
    return {"futures": futures, "count": len(futures)}


def normalize_depth_chart(data):
    """Normalize ESPN depth chart response (shared across NFL, NBA, MLB).

    Input: full response from ``espn_request(SPORT_PATH, "teams/{id}/depthcharts")``.
    """
    charts = []
    for chart in data.get("depthchart", []):
        positions = []
        for pos_key, pos_data in chart.get("positions", {}).items():
            pos_info = pos_data.get("position", {})
            athletes = []
            for i, ath in enumerate(pos_data.get("athletes", [])):
                athletes.append({
                    "depth": i + 1,
                    "id": str(ath.get("id", "")),
                    "name": ath.get("displayName", ""),
                })
            positions.append({
                "key": pos_key,
                "name": pos_info.get("displayName", pos_info.get("name", pos_key)),
                "abbreviation": pos_info.get("abbreviation", pos_key.upper()),
                "athletes": athletes,
            })
        charts.append({
            "name": chart.get("name", ""),
            "positions": positions,
            "count": len(positions),
        })
    return {"charts": charts, "count": len(charts)}


def _resolve_leaders(categories: list) -> list:
    """Normalize a list of ESPN core API leader categories.

    Handles the $ref athlete pattern and sport-agnostic value extraction.
    Returns a list of dicts with name, category, displayName, value, rank.
    """
    result = []
    for cat in categories:
        leaders_list = []
        for leader in cat.get("leaders", []):
            athlete = leader.get("athlete", {})
            if isinstance(athlete, dict):
                ref_url = athlete.get("$ref", "")
                name = athlete.get("displayName") or athlete.get("fullName") or ""
                athlete_id = str(athlete.get("id", ""))
                if (not name or not athlete_id) and ref_url:
                    resolved = _resolve_athlete_ref(ref_url)
                    if not name:
                        name = resolved["name"]
                    if not athlete_id:
                        athlete_id = resolved["id"]
            else:
                name = ""
                athlete_id = ""

            # Use numeric value over displayValue — displayValue can be
            # a full stat line string (e.g. MLB batting: "179-541, 53 HR...")
            raw_value = leader.get("value")
            display_value = leader.get("displayValue", "")
            if raw_value is not None:
                # Format nicely: integers as int, rates as 3dp
                try:
                    fv = float(raw_value)
                    value = str(int(fv)) if fv == int(fv) else f"{fv:.3f}"
                except (ValueError, TypeError):
                    value = display_value
            else:
                value = display_value

            leaders_list.append({
                "rank": leader.get("rank", ""),
                "id": athlete_id,
                "name": name,
                "value": value,
            })
        result.append({
            "name": cat.get("displayName", cat.get("name", "")),
            "leaders": leaders_list,
        })
    return result
