from __future__ import annotations

import gzip
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

from sports_skills._espn_base import normalize_odds

logger = logging.getLogger("sports_skills.football")


# ============================================================
# Configuration & League Mappings
# ============================================================

LEAGUES = {
    "premier-league": {
        "espn": "eng.1",
        "understat": "EPL",
        "fpl": True,
        "transfermarkt": "premier-league",
        "openfootball": {"file": "en.1", "season_format": "aug"},
        "name": "Premier League",
        "country": "England",
    },
    "la-liga": {
        "espn": "esp.1",
        "understat": "La_Liga",
        "fpl": None,
        "transfermarkt": "laliga",
        "openfootball": {"file": "es.1", "season_format": "aug"},
        "name": "La Liga",
        "country": "Spain",
    },
    "bundesliga": {
        "espn": "ger.1",
        "understat": "Bundesliga",
        "fpl": None,
        "transfermarkt": "1-bundesliga",
        "openfootball": {"file": "de.1", "season_format": "aug"},
        "name": "Bundesliga",
        "country": "Germany",
    },
    "serie-a": {
        "espn": "ita.1",
        "understat": "Serie_A",
        "fpl": None,
        "transfermarkt": "serie-a",
        "openfootball": {"file": "it.1", "season_format": "aug"},
        "name": "Serie A",
        "country": "Italy",
    },
    "ligue-1": {
        "espn": "fra.1",
        "understat": "Ligue_1",
        "fpl": None,
        "transfermarkt": "ligue-1",
        "openfootball": {"file": "fr.1", "season_format": "aug"},
        "name": "Ligue 1",
        "country": "France",
    },
    "championship": {
        "espn": "eng.2",
        "understat": None,
        "fpl": None,
        "transfermarkt": "championship",
        "openfootball": {"file": "en.2", "season_format": "aug"},
        "name": "Championship",
        "country": "England",
    },
    "eredivisie": {
        "espn": "ned.1",
        "understat": None,
        "fpl": None,
        "transfermarkt": "eredivisie",
        "openfootball": {"file": "nl.1", "season_format": "aug"},
        "name": "Eredivisie",
        "country": "Netherlands",
    },
    "primeira-liga": {
        "espn": "por.1",
        "understat": None,
        "fpl": None,
        "transfermarkt": "primeira-liga",
        "openfootball": {"file": "pt.1", "season_format": "aug"},
        "name": "Primeira Liga",
        "country": "Portugal",
    },
    "serie-a-brazil": {
        "espn": "bra.1",
        "understat": None,
        "fpl": None,
        "transfermarkt": "campeonato-brasileiro-serie-a",
        "openfootball": {"file": "br.1", "season_format": "jan"},
        "name": "Serie A Brazil",
        "country": "Brazil",
    },
    "mls": {
        "espn": "usa.1",
        "understat": None,
        "fpl": None,
        "transfermarkt": "major-league-soccer",
        "openfootball": {"file": "mls", "season_format": "jan"},
        "name": "MLS",
        "country": "USA",
    },
    # ---- Additional men's leagues ----
    "liga-mx": {
        "espn": "mex.1",
        "understat": None,
        "fpl": None,
        "transfermarkt": "liga-mx",
        "season_format": "jan",
        "name": "Liga MX",
        "country": "Mexico",
    },
    "liga-argentina": {
        "espn": "arg.1",
        "understat": None,
        "fpl": None,
        "transfermarkt": "superliga",
        "season_format": "jan",
        "name": "Liga Profesional Argentina",
        "country": "Argentina",
    },
    "scottish-premiership": {
        "espn": "sco.1",
        "understat": None,
        "fpl": None,
        "transfermarkt": "scottish-premiership",
        "name": "Scottish Premiership",
        "country": "Scotland",
    },
    "belgian-pro-league": {
        "espn": "bel.1",
        "understat": None,
        "fpl": None,
        "transfermarkt": "jupiler-pro-league",
        "name": "Belgian Pro League",
        "country": "Belgium",
    },
    "super-lig": {
        "espn": "tur.1",
        "understat": None,
        "fpl": None,
        "transfermarkt": "super-lig",
        "name": "Turkish Super Lig",
        "country": "Turkey",
    },
    "j-league": {
        "espn": "jpn.1",
        "understat": None,
        "fpl": None,
        "transfermarkt": "j1-league",
        "season_format": "jan",
        "name": "J.League",
        "country": "Japan",
    },
    "a-league": {
        "espn": "aus.1",
        "understat": None,
        "fpl": None,
        "transfermarkt": "a-league-men",
        "name": "A-League Men",
        "country": "Australia",
    },
    # ---- Women's leagues ----
    "nwsl": {
        "espn": "usa.nwsl",
        "understat": None,
        "fpl": None,
        "transfermarkt": "nwsl",
        "season_format": "jan",
        "name": "NWSL",
        "country": "USA",
    },
    "wsl": {
        "espn": "eng.w.1",
        "understat": None,
        "fpl": None,
        "transfermarkt": "womens-super-league",
        "name": "Women's Super League",
        "country": "England",
    },
    "liga-f": {
        "espn": "esp.w.1",
        "understat": None,
        "fpl": None,
        "transfermarkt": "liga-f",
        "name": "Liga F",
        "country": "Spain",
    },
    "premiere-ligue-feminine": {
        "espn": "fra.w.1",
        "understat": None,
        "fpl": None,
        "transfermarkt": "premiere-ligue",
        "name": "Premiere Ligue",
        "country": "France",
    },
    "a-league-women": {
        "espn": "aus.w.1",
        "understat": None,
        "fpl": None,
        "transfermarkt": "a-league-women",
        "name": "A-League Women",
        "country": "Australia",
    },
    "womens-champions-league": {
        "espn": "uefa.wchampions",
        "understat": None,
        "fpl": None,
        "transfermarkt": None,
        "name": "UEFA Women's Champions League",
        "country": "Europe",
    },
    "womens-world-cup": {
        "espn": "fifa.wwc",
        "understat": None,
        "fpl": None,
        "transfermarkt": None,
        "name": "FIFA Women's World Cup",
        "country": "International",
    },
    # ---- European & international competitions ----
    "champions-league": {
        "espn": "uefa.champions",
        "understat": None,
        "fpl": None,
        "transfermarkt": None,
        "name": "Champions League",
        "country": "Europe",
    },
    "europa-league": {
        "espn": "uefa.europa",
        "understat": None,
        "fpl": None,
        "transfermarkt": None,
        "name": "Europa League",
        "country": "Europe",
    },
    "conference-league": {
        "espn": "uefa.europa.conf",
        "understat": None,
        "fpl": None,
        "transfermarkt": None,
        "name": "Conference League",
        "country": "Europe",
    },
    "european-championship": {
        "espn": "uefa.euro",
        "understat": None,
        "fpl": None,
        "transfermarkt": None,
        "name": "European Championship",
        "country": "Europe",
    },
    "copa-libertadores": {
        "espn": "conmebol.libertadores",
        "understat": None,
        "fpl": None,
        "transfermarkt": None,
        "name": "Copa Libertadores",
        "country": "South America",
    },
    "world-cup": {
        "espn": "fifa.world",
        "understat": None,
        "fpl": None,
        "transfermarkt": None,
        "name": "FIFA World Cup",
        "country": "International",
    },
    "international-friendly": {
        "espn": "fifa.friendly",
        "understat": None,
        "fpl": None,
        "transfermarkt": None,
        "name": "International Friendly",
        "country": "International",
    },
}

ESPN_TO_SLUG = {v["espn"]: k for k, v in LEAGUES.items() if v.get("espn")}

STATUS_MAP = {
    "SCHEDULED": "not_started",
    "TIMED": "not_started",
    "IN_PLAY": "live",
    "PAUSED": "halftime",
    "FINISHED": "closed",
    "POSTPONED": "postponed",
    "SUSPENDED": "suspended",
    "CANCELLED": "cancelled",
    "AWARDED": "closed",
    "LIVE": "live",
}

ESPN_STATUS_MAP = {
    "STATUS_SCHEDULED": "not_started",
    "STATUS_IN_PROGRESS": "live",
    "STATUS_HALFTIME": "halftime",
    "STATUS_FINAL": "closed",
    "STATUS_FULL_TIME": "closed",
    "STATUS_POSTPONED": "postponed",
    "STATUS_CANCELED": "cancelled",
    "STATUS_SUSPENDED": "suspended",
    "STATUS_FIRST_HALF": "1st_half",
    "STATUS_SECOND_HALF": "2nd_half",
    "STATUS_END_PERIOD": "halftime",
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
# Rate Limiters (Token Bucket)
# ============================================================


class _RateLimiter:
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


_espn_rate_limiter = _RateLimiter(max_tokens=2, refill_rate=2.0)
_understat_rate_limiter = _RateLimiter(max_tokens=1, refill_rate=0.5)
_fpl_rate_limiter = _RateLimiter(max_tokens=10, refill_rate=10.0 / 60.0)
_tm_rate_limiter = _RateLimiter(max_tokens=2, refill_rate=2.0 / 60.0)


# ============================================================
# HTTP Helpers — Retry, Error Handling, Request Functions
# ============================================================

_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# HTTP status codes worth retrying (transient server/infra errors)
_RETRYABLE_CODES = {429, 500, 502, 503, 504}

# Default retry config
_MAX_RETRIES = 2  # up to 2 retries (3 total attempts)
_RETRY_BASE_DELAY = 1.0  # 1s, 2s (exponential)
_RETRY_MAX_DELAY = 4.0  # cap delay at 4s


def _is_retryable(exc):
    """Check if an exception is worth retrying (transient failures only)."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in _RETRYABLE_CODES
    # Timeouts, connection resets, DNS failures — all transient
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
                # Client error (400, 401, 403, 404) — don't retry
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

        # Exponential backoff before retry
        if attempt < max_retries:
            delay = min(_RETRY_BASE_DELAY * (2**attempt), _RETRY_MAX_DELAY)
            # Extra backoff for 429 rate limits
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


def _espn_request(
    league_slug, resource="scoreboard", params=None, max_retries=_MAX_RETRIES
):
    """ESPN public API (no auth required). Rate-limited, cached.

    Set max_retries=0 for exploratory requests (e.g. probing multiple leagues).
    """
    cache_key = (
        f"espn:{league_slug}:{resource}:{json.dumps(params or {}, sort_keys=True)}"
    )
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    url = (
        f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_slug}/{resource}"
    )
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


def _espn_web_request(league_slug, resource, params=None):
    """ESPN web API (standings, season lists). Different host from site API."""
    cache_key = (
        f"espn_web:{league_slug}:{resource}:{json.dumps(params or {}, sort_keys=True)}"
    )
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    url = (
        f"https://site.web.api.espn.com/apis/v2/sports/soccer/{league_slug}/{resource}"
    )
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


def _espn_summary(league_slug, event_id, max_retries=_MAX_RETRIES):
    """ESPN match summary endpoint (rich data: stats, lineups, player stats).

    Returns parsed JSON dict on success, None on failure.
    Set max_retries=0 for exploratory requests (e.g. probing multiple leagues).
    """
    if not league_slug or not event_id:
        return None
    cache_key = f"espn_summary:{league_slug}:{event_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached if cached else None
    url = (
        f"https://site.web.api.espn.com/apis/site/v2/sports/soccer"
        f"/{league_slug}/summary?event={event_id}"
    )
    headers = {"User-Agent": _USER_AGENT}
    raw, err = _http_fetch(
        url, headers=headers, rate_limiter=_espn_rate_limiter, max_retries=max_retries
    )
    if err:
        logger.debug(
            "ESPN summary failed for %s/%s: %s",
            league_slug,
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


def _understat_html(url):
    """Fetch Understat HTML page (for embedded match_info parsing).

    Returns HTML string on success, None on failure.
    """
    cache_key = f"ustat_html:{url}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached if cached else None
    headers = {"User-Agent": _USER_AGENT}
    raw, err = _http_fetch(url, headers=headers, rate_limiter=_understat_rate_limiter)
    if err:
        logger.debug("Understat HTML failed for %s: %s", url, err.get("message", ""))
        _cache_set(cache_key, "", ttl=60)
        return None
    try:
        html = raw.decode()
        _cache_set(cache_key, html, ttl=600)
        return html
    except Exception:
        _cache_set(cache_key, "", ttl=60)
        return None


def _understat_api(path, ttl=300):
    """Fetch JSON from Understat AJAX API (requires X-Requested-With header).

    Returns parsed JSON on success, None on failure.
    """
    cache_key = f"ustat_api:{path}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached if cached else None
    url = f"https://understat.com{path}"
    headers = {
        "User-Agent": _USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
        "Accept-Encoding": "gzip, deflate",
    }
    raw, err = _http_fetch(
        url, headers=headers, rate_limiter=_understat_rate_limiter, decode_gzip=True
    )
    if err:
        logger.debug("Understat API failed for %s: %s", path, err.get("message", ""))
        _cache_set(cache_key, "", ttl=60)
        return None
    try:
        data = json.loads(raw.decode())
        _cache_set(cache_key, data, ttl=ttl)
        return data
    except (json.JSONDecodeError, ValueError):
        _cache_set(cache_key, "", ttl=60)
        return None


def _fpl_request(endpoint, ttl=300):
    """FPL API (fantasy.premierleague.com). No auth, cached, rate-limited.

    Returns parsed JSON on success, None on failure.
    """
    cache_key = f"fpl:{endpoint}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached if cached else None
    url = f"https://fantasy.premierleague.com/api{endpoint}"
    headers = {"User-Agent": _USER_AGENT}
    raw, err = _http_fetch(url, headers=headers, rate_limiter=_fpl_rate_limiter)
    if err:
        logger.debug("FPL request failed for %s: %s", endpoint, err.get("message", ""))
        _cache_set(cache_key, "", ttl=60)
        return None
    try:
        data = json.loads(raw.decode())
        _cache_set(cache_key, data, ttl=ttl)
        return data
    except (json.JSONDecodeError, ValueError):
        _cache_set(cache_key, "", ttl=60)
        return None


def _tm_request(endpoint, ttl=3600):
    """Transfermarkt ceapi (no auth, JSON). Cached, conservative rate limit.

    Returns parsed JSON on success, None on failure.
    """
    cache_key = f"tm:{endpoint}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached if cached else None
    url = f"https://www.transfermarkt.com{endpoint}"
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    raw, err = _http_fetch(url, headers=headers, rate_limiter=_tm_rate_limiter)
    if err:
        logger.debug(
            "Transfermarkt request failed for %s: %s", endpoint, err.get("message", "")
        )
        _cache_set(cache_key, "", ttl=60)
        return None
    try:
        data = json.loads(raw.decode())
        _cache_set(cache_key, data, ttl=ttl)
        return data
    except (json.JSONDecodeError, ValueError):
        _cache_set(cache_key, "", ttl=60)
        return None


# ============================================================
# Season Detection (ESPN-based, with date fallback)
# ============================================================


def _estimate_current_season(slug, league):
    """Estimate the current season from the system date when ESPN is unavailable.

    Calendar-year leagues (season_format "jan"): Brazil, MLS, J-League, etc.
      → season year = current year (season runs ~Jan-Dec).
    European leagues (season_format "aug"): EPL, La Liga, Bundesliga, etc.
      → season year = current year if month >= 8, else previous year
        (season runs ~Aug of year N to May/Jun of year N+1).
    Tournaments without openfootball config (Champions League, World Cup, etc.)
      → same "aug" heuristic as European leagues.
    """
    now = datetime.utcnow()
    of_cfg = league.get("openfootball") or {}
    season_format = league.get("season_format") or of_cfg.get("season_format", "aug")

    if season_format == "jan":
        year = now.year
    else:
        year = now.year if now.month >= 8 else now.year - 1

    name = league.get("name", slug)
    if season_format == "jan":
        display = f"{year} {name}"
        start = f"{year}-01-01T00:00Z"
        end = f"{year}-12-31T23:59Z"
    else:
        display = f"{year}-{str(year + 1)[-2:]} {name}"
        start = f"{year}-08-01T00:00Z"
        end = f"{year + 1}-06-30T23:59Z"

    return {
        "year": year,
        "start_date": start,
        "end_date": end,
        "display_name": display,
        "calendar": [],
        "slug": slug,
        "estimated": True,
    }


def _detect_current_season(slug, espn_slug):
    """Detect current season year/dates for a league using ESPN scoreboard.

    Falls back to date-based estimation when ESPN is unavailable so that
    callers always receive usable season data.
    """
    if not espn_slug:
        return None
    cache_key = f"season_detect:{espn_slug}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached if cached else None

    league = LEAGUES.get(slug) or {}
    data = _espn_request(espn_slug, "scoreboard")

    if data.get("error"):
        fallback = _estimate_current_season(slug, league)
        _cache_set(cache_key, fallback, ttl=300)
        return fallback

    leagues = data.get("leagues", [])
    if not leagues:
        fallback = _estimate_current_season(slug, league)
        _cache_set(cache_key, fallback, ttl=300)
        return fallback

    league_info = leagues[0]
    season = league_info.get("season", {})
    if not season:
        fallback = _estimate_current_season(slug, league)
        _cache_set(cache_key, fallback, ttl=300)
        return fallback

    result = {
        "year": season.get("year"),
        "start_date": season.get("startDate", ""),
        "end_date": season.get("endDate", ""),
        "display_name": season.get("displayName", ""),
        "calendar": league_info.get("calendar", []),
        "slug": slug,
    }
    _cache_set(cache_key, result, ttl=3600)
    return result


def _resolve_espn_event(event_id, params):
    """Resolve event ID to (espn_league_slug, espn_event_id) tuple.

    Tries multiple strategies to determine which ESPN league the event belongs to.
    """
    eid = _resolve_event_id(event_id)
    # 1. Explicit league hint
    league_slug = (
        params.get("league_slug")
        or params.get("command_attribute", {}).get("league_slug", "")
        or params.get("competition_id")
        or params.get("command_attribute", {}).get("competition_id", "")
    )
    if league_slug:
        league, slug = _resolve_competition(league_slug)
        if league and league.get("espn"):
            return league["espn"], eid
    # 2. Extract from season_id
    season_id = params.get("season_id") or params.get("command_attribute", {}).get(
        "season_id", ""
    )
    if season_id:
        league, slug, year = _resolve_season(season_id)
        if league and league.get("espn"):
            return league["espn"], eid
    # 3. From event_value context (workflow pipelines pass this)
    event_value = params.get("event_value", {})
    comp_id = event_value.get("sport:competition", {}).get("@id", "")
    if comp_id:
        comp_slug = comp_id.replace("urn:machina:competition:", "")
        league = LEAGUES.get(comp_slug)
        if league and league.get("espn"):
            return league["espn"], eid
    # 4. Try all leagues as last resort (skip retries when probing)
    for slug, league in LEAGUES.items():
        espn_slug = league.get("espn")
        if not espn_slug:
            continue
        summary = _espn_summary(espn_slug, eid, max_retries=0)
        if summary and summary.get("header"):
            # Use actual league from response, not the probed slug
            real_espn = (
                summary.get("header", {}).get("league", {}).get("slug", espn_slug)
            )
            resolved = ESPN_TO_SLUG.get(real_espn)
            if resolved and LEAGUES.get(resolved, {}).get("espn"):
                return LEAGUES[resolved]["espn"], eid
            return espn_slug, eid
    return None, eid


# ============================================================
# openfootball/football.json Fallback
# ============================================================

_OPENFOOTBALL_BASE = (
    "https://raw.githubusercontent.com/openfootball/football.json/master"
)


def _openfootball_season_path(league, year):
    """Build the GitHub raw URL path for an openfootball season file."""
    of = league.get("openfootball")
    if not of:
        return None
    file_name = of["file"]
    if of["season_format"] == "aug":
        # European leagues: {year}-{YY}/xx.1.json  (e.g. 2025-26)
        return (
            f"{_OPENFOOTBALL_BASE}/{year}-{(int(year) + 1) % 100:02d}/{file_name}.json"
        )
    else:
        # Calendar-year leagues (MLS, Brazil): {year}/xx.json
        return f"{_OPENFOOTBALL_BASE}/{year}/{file_name}.json"


def _openfootball_fetch(slug, year):
    """Fetch and cache openfootball data for a league season."""
    league = LEAGUES.get(slug)
    if not league:
        return None
    url = _openfootball_season_path(league, year)
    if not url:
        return None
    cache_key = f"openfootball:{slug}:{year}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached if cached else None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "sports-skills/0.2"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        _cache_set(cache_key, data, ttl=3600)
        return data
    except Exception:
        _cache_set(cache_key, "", ttl=300)
        return None


def _normalize_openfootball_match(match, slug, year):
    """Normalize an openfootball match to Machina event format."""
    league = LEAGUES.get(slug, {})
    score = match.get("score") or {}
    ft = score.get("ft") or []
    has_score = len(ft) == 2
    status = "closed" if has_score else "not_started"
    date_str = match.get("date", "")
    time_str = match.get("time", "")
    start_time = f"{date_str}T{time_str}:00Z" if date_str and time_str else date_str
    return {
        "id": "",
        "status": status,
        "start_time": start_time,
        "matchday": None,
        "round": "",
        "round_name": match.get("round", ""),
        "competition": {"id": slug, "name": league.get("name", "")},
        "season": {"id": f"{slug}-{year}", "name": str(year), "year": str(year)},
        "venue": {"id": "", "name": "", "city": "", "country": ""},
        "competitors": [
            {
                "team": {
                    "id": "",
                    "name": match.get("team1", ""),
                    "short_name": "",
                    "abbreviation": "",
                },
                "qualifier": "home",
                "score": ft[0] if has_score else 0,
            },
            {
                "team": {
                    "id": "",
                    "name": match.get("team2", ""),
                    "short_name": "",
                    "abbreviation": "",
                },
                "qualifier": "away",
                "score": ft[1] if has_score else 0,
            },
        ],
        "scores": {
            "home": ft[0] if has_score else 0,
            "away": ft[1] if has_score else 0,
        },
        "source": "openfootball",
    }


def _openfootball_get_schedule(slug, year):
    """Get full season schedule from openfootball as normalized events."""
    data = _openfootball_fetch(slug, year)
    if not data:
        return []
    return [
        _normalize_openfootball_match(m, slug, year) for m in data.get("matches", [])
    ]


def _openfootball_get_teams(slug, year):
    """Extract unique team names from openfootball season data."""
    data = _openfootball_fetch(slug, year)
    if not data:
        return []
    seen = set()
    teams = []
    for m in data.get("matches", []):
        for key in ("team1", "team2"):
            name = m.get(key, "")
            if name and name not in seen:
                seen.add(name)
                teams.append(
                    {
                        "id": "",
                        "name": name,
                        "short_name": name,
                        "abbreviation": "",
                        "crest": "",
                        "country": "",
                        "country_code": "",
                        "venue": "",
                        "founded": None,
                        "colors": "",
                        "website": "",
                    }
                )
    teams.sort(key=lambda t: t["name"])
    return teams


def _openfootball_get_standings(slug, year):
    """Compute standings from openfootball results."""
    data = _openfootball_fetch(slug, year)
    if not data:
        return []
    table = {}
    for m in data.get("matches", []):
        score = m.get("score") or {}
        ft = score.get("ft")
        if not ft or len(ft) != 2:
            continue
        t1, t2 = m.get("team1", ""), m.get("team2", "")
        for team in (t1, t2):
            if team and team not in table:
                table[team] = {
                    "played": 0,
                    "won": 0,
                    "drawn": 0,
                    "lost": 0,
                    "goals_for": 0,
                    "goals_against": 0,
                    "points": 0,
                }
        if t1 and t2:
            g1, g2 = ft[0], ft[1]
            table[t1]["played"] += 1
            table[t2]["played"] += 1
            table[t1]["goals_for"] += g1
            table[t1]["goals_against"] += g2
            table[t2]["goals_for"] += g2
            table[t2]["goals_against"] += g1
            if g1 > g2:
                table[t1]["won"] += 1
                table[t1]["points"] += 3
                table[t2]["lost"] += 1
            elif g2 > g1:
                table[t2]["won"] += 1
                table[t2]["points"] += 3
                table[t1]["lost"] += 1
            else:
                table[t1]["drawn"] += 1
                table[t1]["points"] += 1
                table[t2]["drawn"] += 1
                table[t2]["points"] += 1
    entries = []
    for name, s in table.items():
        s["goal_difference"] = s["goals_for"] - s["goals_against"]
        entries.append({"team": {"id": "", "name": name}, **s})
    entries.sort(key=lambda e: (-e["points"], -e["goal_difference"], -e["goals_for"]))
    for i, e in enumerate(entries):
        e["position"] = i + 1
    return entries


# ============================================================
# Understat HTML Parsing
# ============================================================


def _decode_understat_json(raw):
    """Decode Understat's hex-escaped JSON (\\xNN sequences)."""
    try:
        decoded = re.sub(
            r"\\x([0-9a-fA-F]{2})",
            lambda m: chr(int(m.group(1), 16)),
            raw,
        )
        return json.loads(decoded)
    except (json.JSONDecodeError, ValueError):
        return None


def _extract_understat_var(html, var_name):
    """Extract a JSON.parse('...') variable from Understat HTML."""
    pattern = r"var\s+" + re.escape(var_name) + r"\s*=\s*JSON\.parse\('(.+?)'\)"
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return None
    return _decode_understat_json(match.group(1))


# ============================================================
# Team Name Matching (fuzzy cross-source)
# ============================================================


def _normalize_name(name):
    """Normalize team name for comparison."""
    n = name.lower().strip()
    n = n.replace("-", " ")
    n = n.replace(".", "")
    for token in [" fc", " cf", " sc", " ac", "fc ", "sc ", " afc", " ssc"]:
        n = n.replace(token, " ")
    for old, new in [
        ("á", "a"),
        ("à", "a"),
        ("â", "a"),
        ("ã", "a"),
        ("é", "e"),
        ("è", "e"),
        ("ê", "e"),
        ("í", "i"),
        ("ì", "i"),
        ("ó", "o"),
        ("ò", "o"),
        ("ô", "o"),
        ("õ", "o"),
        ("ú", "u"),
        ("ù", "u"),
        ("ü", "u"),
        ("ñ", "n"),
        ("ç", "c"),
        ("ö", "o"),
        ("ä", "a"),
        ("ß", "ss"),
    ]:
        n = n.replace(old, new)
    return " ".join(n.split())


_ABBREV = {
    "man": "manchester",
    "utd": "united",
    "spurs": "tottenham",
    "wolves": "wolverhampton",
    "nottm": "nottingham",
    "sheff": "sheffield",
    "inter": "internazionale",
    "barca": "barcelona",
    "psg": "paris",
    "gladbach": "monchengladbach",
    "atletico": "atletico",
}


def _expand_abbrev(words):
    """Expand common abbreviations in a word set."""
    expanded = set()
    for w in words:
        expanded.add(w)
        if w in _ABBREV:
            expanded.add(_ABBREV[w])
    return expanded


def _teams_match(name1, name2):
    """Check if two team names likely refer to the same team."""
    if not name1 or not name2:
        return False
    n1 = _normalize_name(name1)
    n2 = _normalize_name(name2)
    if n1 == n2:
        return True
    if n1 in n2 or n2 in n1:
        return True
    words1 = _expand_abbrev(set(w for w in n1.split() if len(w) > 2))
    words2 = _expand_abbrev(set(w for w in n2.split() if len(w) > 2))
    if words1 and words2:
        overlap = words1 & words2
        min_size = min(
            len(set(w for w in n1.split() if len(w) > 2)),
            len(set(w for w in n2.split() if len(w) > 2)),
        )
        if min_size > 0 and len(overlap) >= min_size:
            return True
    return False


# ============================================================
# Cross-Source Event Resolution
# ============================================================


def _find_understat_match_id(match_info):
    """Find Understat match ID by matching date + home team name via AJAX API."""
    understat_league = match_info.get("understat_league")
    if not understat_league:
        return None
    date_str = match_info.get("date", "")
    home_team = match_info.get("home_team", "")
    season_year = match_info.get("season_year", "")
    if not date_str or not home_team or not season_year:
        return None
    cache_key = f"ustat_mid:{understat_league}:{date_str}:{_normalize_name(home_team)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached if cached else None
    # Fetch season match index via Understat AJAX API
    season_key = f"ustat_dates:{understat_league}:{season_year}"
    matches = _cache_get(season_key)
    if matches is None:
        league_data = _understat_api(
            f"/getLeagueData/{understat_league}/{season_year}", ttl=3600
        )
        matches = league_data.get("dates", []) if league_data else []
        _cache_set(season_key, matches, ttl=3600)
    for m in matches:
        m_date = m.get("datetime", "")[:10]
        m_home = m.get("h", {}).get("title", "")
        if m_date == date_str and _teams_match(home_team, m_home):
            mid = str(m.get("id", ""))
            _cache_set(cache_key, mid, ttl=86400)
            return mid
    _cache_set(cache_key, "", ttl=3600)
    return None


def _get_understat_match(match_id):
    """Fetch Understat match data (shots, rosters, match_info) via AJAX API."""
    if not match_id:
        return None
    cache_key = f"ustat_match:{match_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached if cached else None
    # Fetch shots + rosters via AJAX API
    api_data = _understat_api(f"/getMatchData/{match_id}", ttl=300)
    shots = (
        api_data.get("shots", {"h": [], "a": []}) if api_data else {"h": [], "a": []}
    )
    rosters = (
        api_data.get("rosters", {"h": {}, "a": {}}) if api_data else {"h": {}, "a": {}}
    )
    # Fetch match_info from HTML page (still embedded as JSON.parse)
    match_info = None
    html = _understat_html(f"https://understat.com/match/{match_id}")
    if html:
        match_info = _extract_understat_var(html, "match_info")
    data = {
        "shots": shots,
        "rosters": rosters,
        "match_info": match_info or {},
    }
    is_finished = match_info.get("isResult", False) if match_info else False
    _cache_set(cache_key, data, ttl=86400 if is_finished else 300)
    return data


# ============================================================
# ID Resolvers
# ============================================================


def _resolve_competition(competition_id):
    if not competition_id:
        return None, None
    cid = str(competition_id)
    if cid.startswith("urn:machina:competition:"):
        slug = cid.replace("urn:machina:competition:", "")
        return LEAGUES.get(slug), slug
    if cid in LEAGUES:
        return LEAGUES[cid], cid
    for slug, league in LEAGUES.items():
        if league.get("espn") == cid:
            return league, slug
    return None, cid


def _resolve_season(season_id):
    if not season_id:
        return None, None, None
    sid = str(season_id)
    if sid.startswith("urn:machina:season:"):
        sid = sid.replace("urn:machina:season:", "")
    parts = sid.rsplit("-", 1)
    if len(parts) == 2 and parts[1].isdigit():
        slug = parts[0]
        year = int(parts[1])
        league = LEAGUES.get(slug)
        if league:
            return league, slug, year
    for slug, league in LEAGUES.items():
        if sid.startswith(slug):
            remainder = sid[len(slug) :].lstrip("-")
            if remainder.isdigit():
                return league, slug, int(remainder)
    return None, sid, None


def _resolve_team_id(team_id):
    if not team_id:
        return None
    tid = str(team_id)
    if tid.startswith("urn:machina:team:"):
        tid = tid.replace("urn:machina:team:", "")
    return tid


def _resolve_event_id(event_id):
    if not event_id:
        return None
    eid = str(event_id)
    if eid.startswith("urn:machina:event:"):
        eid = eid.replace("urn:machina:event:", "")
    if eid.startswith("urn:machina:sport_event:"):
        eid = eid.replace("urn:machina:sport_event:", "")
    return eid


def _resolve_player_id(player_id):
    if not player_id:
        return None
    pid = str(player_id)
    if pid.startswith("urn:machina:player:"):
        pid = pid.replace("urn:machina:player:", "")
    return pid


# ============================================================
# Helpers
# ============================================================


def _slugify(name):
    return name.lower().replace(" ", "-").replace(".", "").replace("'", "")


# ============================================================
# ESPN Summary Normalizers
# ============================================================


def _espn_home_away_map(summary):
    """Build team_id → homeAway mapping from ESPN summary header."""
    header = summary.get("header", {})
    comps = header.get("competitions", [{}])
    competitors = comps[0].get("competitors", []) if comps else []
    return {c.get("id", ""): c.get("homeAway", "") for c in competitors}


def _map_espn_event_type(text):
    """Map ESPN event type text to normalized type."""
    t = text.lower()
    if "own goal" in t:
        return "own_goal"
    if "penalty" in t and "goal" in t:
        return "penalty_goal"
    if "penalty" in t and ("miss" in t or "saved" in t):
        return "penalty_missed"
    if "goal" in t:
        return "goal"
    if "yellow" in t and "red" in t:
        return "yellow_red_card"
    if "red" in t:
        return "red_card"
    if "yellow" in t:
        return "yellow_card"
    if "substitution" in t:
        return "substitution"
    return t or "unknown"


def _normalize_espn_summary_statistics(summary):
    """Extract team statistics from ESPN summary boxscore."""
    ha_map = _espn_home_away_map(summary)
    teams = []
    for team_data in summary.get("boxscore", {}).get("teams", []):
        team = team_data.get("team", {})
        team_id = team.get("id", "")
        stats_raw = team_data.get("statistics", [])
        sd = {s.get("name", ""): s.get("displayValue", "0") for s in stats_raw}
        teams.append(
            {
                "team": {
                    "id": team_id,
                    "name": team.get("displayName", ""),
                    "abbreviation": team.get("abbreviation", ""),
                },
                "qualifier": ha_map.get(team_id, ""),
                "statistics": {
                    "ball_possession": sd.get("possessionPct", "0"),
                    "shots_total": sd.get("shotsTotal", "0"),
                    "shots_on_target": sd.get("shotsOnTarget", "0"),
                    "shots_off_target": sd.get("shotsOffTarget", "0"),
                    "shots_blocked": sd.get("shotsBlocked", "0"),
                    "corner_kicks": sd.get("wonCorners", "0"),
                    "free_kicks": "0",
                    "fouls": sd.get("foulsCommitted", "0"),
                    "offsides": sd.get("offsides", "0"),
                    "yellow_cards": sd.get("yellowCards", "0"),
                    "red_cards": sd.get("redCards", "0"),
                    "passes_total": sd.get("totalPasses", "0"),
                    "passes_accurate": sd.get("completedPasses", "0"),
                    "tackles": sd.get("tackles", "0"),
                    "crosses": "0",
                    "goalkeeper_saves": sd.get("saves", "0"),
                },
            }
        )
    return teams


def _normalize_espn_summary_timeline(summary):
    """Extract timeline events from ESPN summary."""
    timeline = []
    events = summary.get("keyEvents", [])
    if not events:
        header = summary.get("header", {})
        comps = header.get("competitions", [{}])
        events = comps[0].get("details", []) if comps else []
    for ev in events:
        type_obj = ev.get("type", {})
        type_text = (
            type_obj.get("text", "") if isinstance(type_obj, dict) else str(type_obj)
        )
        mapped_type = _map_espn_event_type(type_text)
        clock = ev.get("clock", {})
        minute_raw = clock.get("displayValue", "0'").replace("'", "").replace("+", " ")
        try:
            minute = int(minute_raw.split()[0]) if minute_raw.strip() else 0
        except ValueError:
            minute = 0
        team_data = ev.get("team", {})
        athletes = ev.get("athletesInvolved") or []
        if not athletes:
            # Fallback: ESPN uses participants[].athlete for some leagues
            participants = ev.get("participants") or []
            athletes = [
                p.get("athlete") or {} for p in participants if p.get("athlete")
            ]
        entry = {
            "id": str(ev.get("id", ev.get("sequenceNumber", ""))),
            "type": mapped_type,
            "minute": minute,
            "period": "",
            "datetime": "",
            "team": {
                "id": team_data.get("id", ""),
                "name": team_data.get("displayName", team_data.get("name", "")),
            }
            if team_data
            else None,
            "player": {
                "id": athletes[0].get("id", "") if athletes else "",
                "name": athletes[0].get("displayName", "") if athletes else "",
            }
            if athletes
            else None,
        }
        if mapped_type == "substitution" and len(athletes) > 1:
            entry["player_in"] = {
                "id": athletes[0].get("id", ""),
                "name": athletes[0].get("displayName", ""),
            }
            entry["player_out"] = {
                "id": athletes[1].get("id", ""),
                "name": athletes[1].get("displayName", ""),
            }
        timeline.append(entry)
    timeline.sort(key=lambda e: e["minute"])
    return timeline


def _normalize_espn_summary_lineups(summary):
    """Extract lineup/formation data from ESPN summary."""
    ha_map = _espn_home_away_map(summary)
    formations = {}
    for f in summary.get("boxscore", {}).get("form", []):
        tid = f.get("team", {}).get("id", "")
        formations[tid] = f.get("formationSummary", "")
    lineups = []
    for roster in summary.get("rosters", []):
        team = roster.get("team", {})
        team_id = team.get("id", "")
        starting, bench = [], []
        for p in roster.get("roster", []):
            athlete = p.get("athlete", {})
            pos = p.get("position", {})
            jersey = p.get("jersey", "")
            info = {
                "id": athlete.get("id", ""),
                "name": athlete.get("displayName", ""),
                "position": pos.get("name", ""),
                "shirt_number": int(jersey) if jersey and jersey.isdigit() else None,
            }
            (starting if p.get("starter") else bench).append(info)
        if starting or bench:
            lineups.append(
                {
                    "team": {
                        "id": team_id,
                        "name": team.get("displayName", ""),
                        "abbreviation": team.get("abbreviation", ""),
                    },
                    "qualifier": ha_map.get(team_id, ""),
                    "formation": formations.get(team_id, ""),
                    "starting": starting,
                    "bench": bench,
                }
            )
    return lineups


def _normalize_espn_summary_players(summary):
    """Extract player-level statistics from ESPN summary rosters."""
    ha_map = _espn_home_away_map(summary)
    teams = []
    for roster in summary.get("rosters", []):
        team = roster.get("team", {})
        team_id = team.get("id", "")
        players = []
        for p in roster.get("roster", []):
            athlete = p.get("athlete", {})
            pos = p.get("position", {})
            stats = p.get("stats", [])
            jersey = p.get("jersey", "")
            stat_dict = {}
            for s in stats:
                stat_dict[s.get("name", "")] = s.get(
                    "value", s.get("displayValue", "0")
                )
            players.append(
                {
                    "id": athlete.get("id", ""),
                    "name": athlete.get("displayName", ""),
                    "short_name": athlete.get("shortName", ""),
                    "position": pos.get("name", ""),
                    "position_abbreviation": pos.get("abbreviation", ""),
                    "shirt_number": jersey,
                    "starter": p.get("starter", False),
                    "subbed_in": p.get("subbedIn", False),
                    "subbed_out": p.get("subbedOut", False),
                    "sub_minute": p.get("subMinute"),
                    "statistics": stat_dict,
                }
            )
        if players:
            teams.append(
                {
                    "team": {
                        "id": team_id,
                        "name": team.get("displayName", ""),
                        "abbreviation": team.get("abbreviation", ""),
                    },
                    "qualifier": ha_map.get(team_id, ""),
                    "players": players,
                }
            )
    return teams


# ============================================================
# Understat Normalizers
# ============================================================


def _normalize_understat_xg(shots_data, match_info_data):
    """Normalize Understat shot-level xG data."""
    home_shots = shots_data.get("h", [])
    away_shots = shots_data.get("a", [])
    home_xg = sum(float(s.get("xG", 0)) for s in home_shots)
    away_xg = sum(float(s.get("xG", 0)) for s in away_shots)
    # Fallback to match_info xG totals when no shot-level data
    if not home_shots and not away_shots and match_info_data:
        home_xg = float(match_info_data.get("h_xg", 0))
        away_xg = float(match_info_data.get("a_xg", 0))
    teams = []
    if match_info_data:
        # match_info uses flat keys: team_h/team_a for names, h/a for team IDs
        for side, qualifier in [("h", "home"), ("a", "away")]:
            teams.append(
                {
                    "team": {
                        "id": str(match_info_data.get(side, "")),
                        "name": match_info_data.get(f"team_{side}", ""),
                    },
                    "qualifier": qualifier,
                    "xg": round(home_xg if side == "h" else away_xg, 3),
                }
            )
    shots = []
    for shot in sorted(home_shots + away_shots, key=lambda s: int(s.get("minute", 0))):
        shots.append(
            {
                "id": shot.get("id", ""),
                "minute": int(shot.get("minute", 0)),
                "result": shot.get("result", ""),
                "xg": round(float(shot.get("xG", 0)), 4),
                "player": {
                    "id": shot.get("player_id", ""),
                    "name": shot.get("player", ""),
                },
                "assist": shot.get("player_assisted", ""),
                "situation": shot.get("situation", ""),
                "shot_type": shot.get("shotType", ""),
                "last_action": shot.get("lastAction", ""),
                "coordinates": {
                    "x": float(shot.get("X", 0)),
                    "y": float(shot.get("Y", 0)),
                },
                "qualifier": "home" if shot.get("h_a") == "h" else "away",
            }
        )
    return {"teams": teams, "shots": shots}


def _normalize_understat_players(rosters_data, match_info_data):
    """Normalize Understat player-level xG data."""
    teams = []
    for side, qualifier in [("h", "home"), ("a", "away")]:
        # match_info uses flat keys: h/a for team IDs, team_h/team_a for names
        team_id = str(match_info_data.get(side, "")) if match_info_data else ""
        team_name = match_info_data.get(f"team_{side}", "") if match_info_data else ""
        roster = rosters_data.get(side, {})
        players = []
        for pid, p in roster.items():
            players.append(
                {
                    "id": p.get("player_id", pid),
                    "name": p.get("player", ""),
                    "position_order": int(p.get("positionOrder", 99)),
                    "minutes": int(p.get("time", 0)),
                    "goals": int(p.get("goals", 0)),
                    "own_goals": int(p.get("own_goals", 0)),
                    "assists": int(p.get("assists", 0)),
                    "shots": int(p.get("shots", 0)),
                    "key_passes": int(p.get("key_passes", 0)),
                    "xg": round(float(p.get("xG", 0)), 3),
                    "xa": round(float(p.get("xA", 0)), 3),
                    "xg_chain": round(float(p.get("xGChain", 0)), 3),
                    "xg_buildup": round(float(p.get("xGBuildup", 0)), 3),
                    "yellow_card": int(p.get("yellow_card", 0)),
                    "red_card": int(p.get("red_card", 0)),
                }
            )
        players.sort(key=lambda x: x["position_order"])
        if players:
            teams.append(
                {
                    "team": {
                        "id": team_id,
                        "name": team_name,
                    },
                    "qualifier": qualifier,
                    "players": players,
                }
            )
    return teams


# ============================================================
# ESPN Event & Standings Normalizers
# ============================================================


def _parse_espn_score(score):
    """Parse ESPN score (can be string, int, or $ref dict)."""
    if isinstance(score, dict):
        return int(float(score.get("value", score.get("displayValue", 0))))
    try:
        return int(score) if score is not None else 0
    except (ValueError, TypeError):
        return 0


def _normalize_espn_event(espn_event, league_slug=""):
    """Normalize ESPN scoreboard event to Machina event format."""
    comp = espn_event.get("competitions", [{}])[0]
    competitors = comp.get("competitors", [])
    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), {})
    status_type = comp.get("status", {}).get("type", {}).get("name", "")
    season = espn_event.get("season", {})
    season_year = str(season.get("year", ""))
    hs = _parse_espn_score(home.get("score"))
    as_ = _parse_espn_score(away.get("score"))
    venue = comp.get("venue", {})
    return {
        "id": str(espn_event.get("id", "")),
        "status": ESPN_STATUS_MAP.get(status_type, "not_started"),
        "start_time": comp.get("date", espn_event.get("date", "")),
        "matchday": None,
        "round": "",
        "round_name": espn_event.get("week", {}).get("text", ""),
        "competition": {
            "id": league_slug,
            "name": LEAGUES.get(league_slug, {}).get("name", ""),
        },
        "season": {
            "id": f"{league_slug}-{season_year}" if season_year else "",
            "name": season_year,
            "year": season_year,
        },
        "venue": {
            "id": str(venue.get("id", "")),
            "name": venue.get("fullName", ""),
            "city": venue.get("address", {}).get("city", ""),
            "country": venue.get("address", {}).get("country", ""),
        },
        "competitors": [
            {
                "team": {
                    "id": str(home.get("team", {}).get("id", "")),
                    "name": home.get("team", {}).get("displayName", ""),
                    "short_name": home.get("team", {}).get("shortDisplayName", ""),
                    "abbreviation": home.get("team", {}).get("abbreviation", ""),
                },
                "qualifier": "home",
                "score": hs,
            },
            {
                "team": {
                    "id": str(away.get("team", {}).get("id", "")),
                    "name": away.get("team", {}).get("displayName", ""),
                    "short_name": away.get("team", {}).get("shortDisplayName", ""),
                    "abbreviation": away.get("team", {}).get("abbreviation", ""),
                },
                "qualifier": "away",
                "score": as_,
            },
        ],
        "scores": {
            "home": hs,
            "away": as_,
        },
        "odds": normalize_odds(comp.get("odds", [])),
        "referees": [],
    }


def _normalize_espn_standings(espn_data, league_slug=""):
    """Normalize ESPN standings response to Machina format."""
    groups = []
    for child in espn_data.get("children", []):
        standings = child.get("standings", {})
        entries = []
        for entry in standings.get("entries", []):
            team = entry.get("team", {})
            sd = {s.get("name", ""): s.get("value", 0) for s in entry.get("stats", [])}
            entries.append(
                {
                    "position": int(sd.get("rank", 0)),
                    "team": {
                        "id": str(team.get("id", "")),
                        "name": team.get("displayName", ""),
                        "short_name": team.get("shortDisplayName", ""),
                        "abbreviation": team.get("abbreviation", ""),
                        "crest": team.get("logos", [{}])[0].get("href", "")
                        if team.get("logos")
                        else "",
                    },
                    "played": int(sd.get("gamesPlayed", 0)),
                    "won": int(sd.get("wins", 0)),
                    "drawn": int(sd.get("ties", 0)),
                    "lost": int(sd.get("losses", 0)),
                    "goals_for": int(sd.get("pointsFor", 0)),
                    "goals_against": int(sd.get("pointsAgainst", 0)),
                    "goal_difference": int(sd.get("pointDifferential", 0)),
                    "points": int(sd.get("points", 0)),
                    "form": "",
                }
            )
        groups.append(
            {
                "name": child.get("name", "TOTAL"),
                "type": "TOTAL",
                "entries": entries,
            }
        )
    return groups


def _parse_espn_roster(espn_league, team_id):
    """Fetch and parse roster from ESPN ``/teams/{id}/roster`` endpoint.

    Returns a list of player dicts with ``espn_athlete_id``.  Falls back to
    an empty list on any failure so callers never break.
    """
    data = _espn_request(espn_league, f"teams/{team_id}/roster", max_retries=0)
    if not data or data.get("error"):
        return []
    athletes = data.get("athletes", [])
    players = []
    for ath in athletes:
        # Flat format: each element is an athlete dict
        if isinstance(ath, dict) and ath.get("id"):
            pos = ath.get("position", {})
            players.append(
                {
                    "id": str(ath.get("id", "")),
                    "name": ath.get("displayName", ath.get("fullName", "")),
                    "position": pos.get("abbreviation", pos.get("name", ""))
                    if isinstance(pos, dict)
                    else str(pos),
                    "shirt_number": ath.get("jersey", ""),
                    "age": ath.get("age"),
                    "nationality": ath.get("citizenship", ""),
                    "espn_athlete_id": str(ath.get("id", "")),
                }
            )
    return players


def _normalize_espn_team(espn_team):
    """Normalize ESPN team object to Machina format."""
    return {
        "id": str(espn_team.get("id", "")),
        "name": espn_team.get("displayName", ""),
        "short_name": espn_team.get("shortDisplayName", ""),
        "abbreviation": espn_team.get("abbreviation", ""),
        "crest": espn_team.get("logos", [{}])[0].get("href", "")
        if espn_team.get("logos")
        else "",
        "country": "",
        "country_code": "",
        "venue": "",
        "founded": None,
        "colors": "",
        "website": "",
    }


# ============================================================
# Match Context (ESPN-based, for cross-source resolution)
# ============================================================


def _get_match_context(espn_league, espn_event_id, summary=None):
    """Build match context from ESPN for cross-source resolution (no fd needed)."""
    if not summary:
        summary = _espn_summary(espn_league, espn_event_id)
    if not summary:
        return None
    header = summary.get("header", {})
    comps = header.get("competitions", [{}])
    comp = comps[0] if comps else {}
    competitors = comp.get("competitors", [])
    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
    away = next((c for c in competitors if c.get("homeAway") == "away"), {})
    slug = ESPN_TO_SLUG.get(espn_league, "")
    league_info = LEAGUES.get(slug, {})
    return {
        "slug": slug,
        "espn_league": espn_league,
        "understat_league": league_info.get("understat"),
        "date": comp.get("date", "")[:10],
        "home_team": home.get("team", {}).get("displayName", ""),
        "away_team": away.get("team", {}).get("displayName", ""),
        "season_year": str(header.get("season", {}).get("year", "")),
    }


# ============================================================
# FPL Helpers (Fantasy Premier League API)
# ============================================================

_FPL_POSITION_MAP = {1: "Goalkeeper", 2: "Defender", 3: "Midfielder", 4: "Forward"}
_FPL_STATUS_MAP = {
    "a": "available",
    "d": "doubtful",
    "i": "injured",
    "s": "suspended",
    "u": "unavailable",
    "n": "not_in_squad",
}


def _map_fpl_position(element_type):
    return _FPL_POSITION_MAP.get(element_type, "Unknown")


def _map_fpl_injury_status(fpl_status):
    return _FPL_STATUS_MAP.get(fpl_status, fpl_status)


def _get_fpl_bootstrap():
    """Fetch FPL bootstrap-static (all players/teams/gameweeks). Cached 15min."""
    return _fpl_request("/bootstrap-static/", ttl=900)


def _build_fpl_team_map(bootstrap):
    """Build {team_id: team_data} from FPL bootstrap teams array."""
    if not bootstrap:
        return {}
    return {t["id"]: t for t in bootstrap.get("teams", [])}


def _normalize_fpl_player_enrichment(fpl_player):
    """Extract enrichment fields from FPL player data."""
    return {
        "fpl_id": fpl_player.get("id"),
        "code": fpl_player.get("code"),
        "web_name": fpl_player.get("web_name", ""),
        "status": _map_fpl_injury_status(fpl_player.get("status", "a")),
        "news": fpl_player.get("news", ""),
        "chance_of_playing_this_round": fpl_player.get("chance_of_playing_this_round"),
        "chance_of_playing_next_round": fpl_player.get("chance_of_playing_next_round"),
        "form": fpl_player.get("form", "0.0"),
        "now_cost": fpl_player.get("now_cost"),
        "selected_by_percent": fpl_player.get("selected_by_percent", "0.0"),
        "total_points": fpl_player.get("total_points", 0),
        "points_per_game": fpl_player.get("points_per_game", "0.0"),
        "expected_goals": fpl_player.get("expected_goals", "0.00"),
        "expected_assists": fpl_player.get("expected_assists", "0.00"),
        "expected_goal_involvements": fpl_player.get(
            "expected_goal_involvements", "0.00"
        ),
        "expected_goals_conceded": fpl_player.get("expected_goals_conceded", "0.00"),
        "ict_index": fpl_player.get("ict_index", "0.0"),
        "influence": fpl_player.get("influence", "0.0"),
        "creativity": fpl_player.get("creativity", "0.0"),
        "threat": fpl_player.get("threat", "0.0"),
        "minutes": fpl_player.get("minutes", 0),
        "goals_scored": fpl_player.get("goals_scored", 0),
        "assists": fpl_player.get("assists", 0),
        "clean_sheets": fpl_player.get("clean_sheets", 0),
        "penalties_order": fpl_player.get("penalties_order"),
        "corners_and_indirect_freekicks_order": fpl_player.get(
            "corners_and_indirect_freekicks_order"
        ),
        "direct_freekicks_order": fpl_player.get("direct_freekicks_order"),
    }


def _normalize_fpl_player_as_profile(fpl_player, team_map=None):
    """Convert FPL player to Machina player profile format."""
    if team_map is None:
        bootstrap = _get_fpl_bootstrap()
        team_map = _build_fpl_team_map(bootstrap) if bootstrap else {}
    team = team_map.get(fpl_player.get("team"), {})
    return {
        "id": str(fpl_player.get("code", fpl_player.get("id", ""))),
        "name": f"{fpl_player.get('first_name', '')} {fpl_player.get('second_name', '')}".strip(),
        "first_name": fpl_player.get("first_name", ""),
        "last_name": fpl_player.get("second_name", ""),
        "date_of_birth": "",
        "nationality": "",
        "position": _map_fpl_position(fpl_player.get("element_type")),
        "shirt_number": fpl_player.get("squad_number"),
        "team": {
            "id": str(team.get("code", team.get("id", ""))),
            "name": team.get("name", ""),
        },
    }


def _enrich_team_players_fpl(players):
    """Enrich player list with FPL data (in-place). Matches by name."""
    bootstrap = _get_fpl_bootstrap()
    if not bootstrap:
        return
    fpl_by_name = {}
    for p in bootstrap.get("elements", []):
        full_name = f"{p.get('first_name', '')} {p.get('second_name', '')}".strip()
        web_name = p.get("web_name", "")
        if full_name:
            fpl_by_name[full_name.lower()] = p
        if web_name:
            fpl_by_name[web_name.lower()] = p
    for player in players:
        pname = player.get("name", "").lower()
        fpl_p = fpl_by_name.get(pname)
        if not fpl_p:
            for fname, fp in fpl_by_name.items():
                if _teams_match(pname, fname):
                    fpl_p = fp
                    break
        if fpl_p:
            player["fpl_data"] = _normalize_fpl_player_enrichment(fpl_p)


def _build_missing_players_from_fpl(bootstrap, season_id):
    """Build missing players list from FPL bootstrap data grouped by team."""
    team_map = _build_fpl_team_map(bootstrap)
    missing_by_team = {}
    for player in bootstrap.get("elements", []):
        status = player.get("status", "a")
        if status in ("d", "i", "s", "u", "n"):
            team_id = player.get("team")
            team_info = team_map.get(team_id, {})
            team_name = team_info.get("name", "Unknown")
            if team_name not in missing_by_team:
                missing_by_team[team_name] = {
                    "team": {
                        "id": str(team_info.get("code", team_id)),
                        "name": team_name,
                        "short_name": team_info.get("short_name", ""),
                    },
                    "players": [],
                }
            missing_by_team[team_name]["players"].append(
                {
                    "id": str(player.get("code", player.get("id", ""))),
                    "name": f"{player.get('first_name', '')} {player.get('second_name', '')}".strip(),
                    "web_name": player.get("web_name", ""),
                    "position": _map_fpl_position(player.get("element_type")),
                    "status": _map_fpl_injury_status(status),
                    "news": player.get("news", ""),
                    "chance_of_playing_this_round": player.get(
                        "chance_of_playing_this_round"
                    ),
                    "chance_of_playing_next_round": player.get(
                        "chance_of_playing_next_round"
                    ),
                    "news_added": player.get("news_added", ""),
                }
            )
    teams = sorted(missing_by_team.values(), key=lambda t: t["team"]["name"])
    return {"season_id": season_id, "teams": teams}


def _build_leaders_from_fpl(bootstrap):
    """Build top scorers list from FPL bootstrap (sorted by goals desc)."""
    team_map = _build_fpl_team_map(bootstrap)
    scorers = []
    for p in bootstrap.get("elements", []):
        goals = p.get("goals_scored", 0)
        if goals > 0:
            team = team_map.get(p.get("team"), {})
            scorers.append(
                {
                    "player": {
                        "id": str(p.get("code", p.get("id", ""))),
                        "name": f"{p.get('first_name', '')} {p.get('second_name', '')}".strip(),
                        "first_name": p.get("first_name", ""),
                        "last_name": p.get("second_name", ""),
                        "nationality": "",
                        "position": _map_fpl_position(p.get("element_type")),
                        "date_of_birth": "",
                    },
                    "team": {
                        "id": str(team.get("code", team.get("id", ""))),
                        "name": team.get("name", ""),
                        "short_name": team.get("short_name", ""),
                        "abbreviation": team.get("short_name", ""),
                        "crest": "",
                    },
                    "goals": goals,
                    "assists": p.get("assists", 0),
                    "penalties": 0,
                    "played_matches": p.get("starts", 0),
                }
            )
    scorers.sort(key=lambda s: (-s["goals"], -s["assists"]))
    return scorers[:30]


# ============================================================
# Transfermarkt Helpers (ceapi)
# ============================================================


def _tm_market_value(tm_player_id):
    """Fetch market value development for a Transfermarkt player ID. Cached 24hr."""
    if not tm_player_id:
        return None
    return _tm_request(f"/ceapi/marketValueDevelopment/graph/{tm_player_id}", ttl=86400)


def _tm_transfer_history(tm_player_id):
    """Fetch transfer history for a Transfermarkt player ID. Cached 24hr."""
    if not tm_player_id:
        return None
    return _tm_request(f"/ceapi/transferHistory/list/{tm_player_id}", ttl=86400)


def _resolve_tm_player_id(params):
    """Resolve Transfermarkt player ID from explicit params."""
    return (
        str(
            params.get("tm_player_id")
            or params.get("command_attribute", {}).get("tm_player_id", "")
        )
        or None
    )


def _normalize_tm_market_value(entry):
    """Normalize a single Transfermarkt market value data point."""
    return {
        "value": entry.get("y", 0),
        "currency": "EUR",
        "date": entry.get("datum_mw", ""),
        "formatted": entry.get("mw", ""),
        "age": entry.get("age", ""),
        "club": entry.get("verein", ""),
    }


def _normalize_tm_transfer(transfer, tm_player_id=""):
    """Normalize a Transfermarkt transfer record."""
    from_club = (
        transfer.get("from", {}) if isinstance(transfer.get("from"), dict) else {}
    )
    to_club = transfer.get("to", {}) if isinstance(transfer.get("to"), dict) else {}
    return {
        "player_tm_id": tm_player_id,
        "date": transfer.get("dateUnformatted", transfer.get("date", "")),
        "season": transfer.get("season", ""),
        "from_team": {
            "name": from_club.get("clubName", ""),
            "image": from_club.get("clubImage", from_club.get("clubEmblem-1x", "")),
        },
        "to_team": {
            "name": to_club.get("clubName", ""),
            "image": to_club.get("clubImage", to_club.get("clubEmblem-1x", "")),
        },
        "fee": transfer.get("fee", ""),
        "market_value": transfer.get("marketValue", ""),
    }


# ============================================================
# Command Functions (20 total)
# ESPN primary, openfootball fallback
# ============================================================


def get_current_season(request_data):
    """Detect current season for a competition using ESPN.

    Falls back to date-based estimation when ESPN is unavailable.
    """
    params = request_data.get("params", {})
    competition_id = params.get("competition_id") or params.get(
        "command_attribute", {}
    ).get("competition_id", "")
    league, slug = _resolve_competition(competition_id)
    if not league:
        return {"error": True, "message": f"Unknown competition: {competition_id}"}
    espn_slug = league.get("espn")
    if not espn_slug:
        return {"error": True, "message": f"No ESPN coverage for {slug}"}
    season = _detect_current_season(slug, espn_slug)
    if not season:
        return {"error": True, "message": "Could not detect current season"}
    result = {
        "competition": {"id": slug, "name": league["name"]},
        "season": {
            "id": f"{slug}-{season['year']}",
            "name": season["display_name"],
            "year": str(season["year"]),
            "start_date": season["start_date"],
            "end_date": season["end_date"],
        },
        "calendar_dates": len(season.get("calendar", [])),
    }
    if season.get("estimated"):
        result["estimated"] = True
    return result


def get_competitions(request_data):
    """List available competitions with current season info."""
    competitions = []
    for slug, league in LEAGUES.items():
        comp = {
            "id": slug,
            "name": league["name"],
            "category": {"id": _slugify(league["country"]), "name": league["country"]},
            "type": "LEAGUE",
        }
        espn_slug = league.get("espn")
        if espn_slug:
            season_info = _detect_current_season(slug, espn_slug)
            if season_info:
                cs = {
                    "year": str(season_info["year"]),
                    "start_date": season_info["start_date"],
                    "end_date": season_info["end_date"],
                }
                if season_info.get("estimated"):
                    cs["estimated"] = True
                comp["current_season"] = cs
        competitions.append(comp)
    return {"competitions": competitions}


def get_competition_seasons(request_data):
    """Get available seasons for a competition."""
    params = request_data.get("params", {})
    competition_id = params.get("competition_id") or params.get(
        "command_attribute", {}
    ).get("competition_id", "")
    league, slug = _resolve_competition(competition_id)
    if not league:
        return {
            "competition": {},
            "seasons": [],
            "error": True,
            "message": f"Unknown competition: {competition_id}",
        }
    comp_info = {
        "id": slug,
        "name": league["name"],
        "category": {"id": _slugify(league["country"]), "name": league["country"]},
        "type": "LEAGUE",
    }
    espn_slug = league.get("espn")
    if not espn_slug:
        return {
            "competition": comp_info,
            "seasons": [],
            "message": "No ESPN coverage for this competition",
        }
    data = _espn_web_request(espn_slug, "standings")
    if data.get("error"):
        season = _detect_current_season(slug, espn_slug)
        if season:
            return {
                "competition": comp_info,
                "seasons": [
                    {
                        "id": f"{slug}-{season['year']}",
                        "name": season["display_name"],
                        "year": str(season["year"]),
                        "start_date": season["start_date"],
                        "end_date": season["end_date"],
                        "current_matchday": None,
                    }
                ],
            }
        return {"competition": comp_info, "seasons": []}
    seasons = []
    for s in data.get("seasons", []):
        year = str(s.get("year", ""))
        seasons.append(
            {
                "id": f"{slug}-{year}",
                "name": s.get("displayName", year),
                "year": year,
                "start_date": s.get("startDate", ""),
                "end_date": s.get("endDate", ""),
                "current_matchday": None,
            }
        )
    return {"competition": comp_info, "seasons": seasons}


def get_season_schedule(request_data):
    """Get full season match schedule."""
    params = request_data.get("params", {})
    season_id = params.get("season_id") or params.get("command_attribute", {}).get(
        "season_id", ""
    )
    league, slug, year = _resolve_season(season_id)
    if not league or not year:
        return {
            "schedules": [],
            "error": True,
            "message": f"Unknown season: {season_id}",
        }
    espn_slug = league.get("espn")
    if not espn_slug:
        return {"schedules": [], "message": "No ESPN coverage for this competition"}
    standings_data = _espn_web_request(espn_slug, "standings", {"season": str(year)})
    team_ids = []
    if not standings_data.get("error"):
        for child in standings_data.get("children", []):
            for entry in child.get("standings", {}).get("entries", []):
                tid = entry.get("team", {}).get("id")
                if tid:
                    team_ids.append(str(tid))
    if not team_ids:
        data = _espn_request(espn_slug, "scoreboard")
        return {
            "schedules": [
                _normalize_espn_event(e, slug) for e in data.get("events", [])
            ]
        }
    all_events = {}
    expected_total = len(team_ids) * (len(team_ids) - 1)
    for tid in team_ids:
        data = _espn_request(espn_slug, f"teams/{tid}/schedule", {"season": str(year)})
        if not data.get("error"):
            for e in data.get("events", []):
                eid = e.get("id", "")
                if eid and eid not in all_events:
                    all_events[eid] = _normalize_espn_event(e, slug)
        if len(all_events) >= expected_total:
            break
    if all_events:
        return {
            "schedules": sorted(
                all_events.values(), key=lambda e: e.get("start_time", "")
            )
        }
    # openfootball fallback
    of_events = _openfootball_get_schedule(slug, year)
    if of_events:
        return {"schedules": of_events, "source": "openfootball"}
    return {"schedules": []}


def get_season_standings(request_data):
    """Get season standings."""
    params = request_data.get("params", {})
    season_id = params.get("season_id") or params.get("command_attribute", {}).get(
        "season_id", ""
    )
    league, slug, year = _resolve_season(season_id)
    if not league:
        return {
            "standings": [],
            "error": True,
            "message": f"Unknown season: {season_id}",
        }
    espn_slug = league.get("espn")
    if not espn_slug:
        return {"standings": [], "message": "No ESPN coverage for this competition"}
    espn_params = {"season": str(year)} if year else {}
    data = _espn_web_request(espn_slug, "standings", espn_params)
    if not data.get("error"):
        standings = _normalize_espn_standings(data, slug)
        if standings:
            return {"standings": standings}
    # openfootball fallback: compute standings from results
    of_entries = _openfootball_get_standings(slug, year)
    if of_entries:
        league_name = league.get("name", "")
        return {
            "standings": [{"group": league_name, "entries": of_entries}],
            "source": "openfootball",
        }
    return {"standings": []}


def get_season_leaders(request_data):
    """Get top scorers/leaders. fd primary, FPL fallback for PL."""
    params = request_data.get("params", {})
    season_id = params.get("season_id") or params.get("command_attribute", {}).get(
        "season_id", ""
    )
    league, slug, year = _resolve_season(season_id)
    if not league:
        return {"leaders": [], "error": True, "message": f"Unknown season: {season_id}"}
    # FPL (PL only)
    if league.get("fpl"):
        bootstrap = _get_fpl_bootstrap()
        if bootstrap:
            leaders = _build_leaders_from_fpl(bootstrap)
            if leaders:
                return {"leaders": leaders}
    return {
        "leaders": [],
        "message": "Season leaders available for Premier League only (via FPL)",
    }


def get_season_teams(request_data):
    """Get teams in a season."""
    params = request_data.get("params", {})
    season_id = params.get("season_id") or params.get("command_attribute", {}).get(
        "season_id", ""
    )
    league, slug, year = _resolve_season(season_id)
    if not league:
        return {"teams": [], "error": True, "message": f"Unknown season: {season_id}"}
    espn_slug = league.get("espn")
    if not espn_slug:
        return {"teams": [], "message": "No ESPN coverage for this competition"}
    data = _espn_web_request(
        espn_slug, "standings", {"season": str(year)} if year else {}
    )
    if data.get("error"):
        return {"teams": []}
    teams = []
    seen = set()
    for child in data.get("children", []):
        for entry in child.get("standings", {}).get("entries", []):
            team = entry.get("team", {})
            tid = str(team.get("id", ""))
            if tid and tid not in seen:
                seen.add(tid)
                teams.append(_normalize_espn_team(team))
    if teams:
        return {"teams": teams}
    # openfootball fallback: extract team names from match data
    of_teams = _openfootball_get_teams(slug, year)
    if of_teams:
        return {"teams": of_teams, "source": "openfootball"}
    return {"teams": []}


def search_team(request_data):
    """Search for a team by name across all leagues (or a specific one)."""
    params = request_data.get("params", {})
    query = params.get("query") or params.get("command_attribute", {}).get("query", "")
    if not query:
        return {"results": [], "error": True, "message": "Missing query"}
    competition_id = params.get("competition_id") or params.get(
        "command_attribute", {}
    ).get("competition_id", "")
    leagues_to_search = []
    if competition_id:
        league, slug = _resolve_competition(competition_id)
        if league:
            leagues_to_search.append((slug, league))
        else:
            return {
                "results": [],
                "error": True,
                "message": f"Unknown competition: {competition_id}",
            }
    else:
        leagues_to_search = list(LEAGUES.items())
    results = []
    for slug, league in leagues_to_search:
        espn_slug = league.get("espn")
        if not espn_slug:
            continue
        season = _detect_current_season(slug, espn_slug)
        if not season:
            continue
        year = season["year"]
        season_id = f"{slug}-{year}"
        teams_data = get_season_teams(
            {
                "params": {
                    "season_id": season_id,
                    **{k: v for k, v in params.items() if k.startswith("fd_")},
                }
            }
        )
        for team in teams_data.get("teams", []):
            team_name = team.get("name", "")
            if _teams_match(query, team_name):
                results.append(
                    {
                        "team": team,
                        "competition": {"id": slug, "name": league["name"]},
                        "season": {"id": season_id, "year": str(year)},
                    }
                )
    return {"results": results}


def get_team_profile(request_data):
    """Get team profile with squad/roster. FPL enrichment for PL teams."""
    params = request_data.get("params", {})
    team_id = params.get("team_id") or params.get("command_attribute", {}).get(
        "team_id", ""
    )
    tid = _resolve_team_id(team_id)
    if not tid:
        return {"team": {}, "players": [], "error": True, "message": "Missing team_id"}
    league_slug = params.get("league_slug") or params.get("command_attribute", {}).get(
        "league_slug", ""
    )
    result = None
    if not result:
        leagues_to_try = []
        if league_slug:
            league, _ = _resolve_competition(league_slug)
            if league and league.get("espn"):
                leagues_to_try.append(league["espn"])
        if not leagues_to_try:
            leagues_to_try = [lg["espn"] for lg in LEAGUES.values() if lg.get("espn")]
        # Skip retries when probing multiple leagues (ESPN returns 500 for wrong league)
        probe_retries = 0 if len(leagues_to_try) > 1 else _MAX_RETRIES
        for espn_slug in leagues_to_try:
            data = _espn_request(espn_slug, f"teams/{tid}", max_retries=probe_retries)
            if data.get("error"):
                continue
            team_data = data.get("team", data)
            if team_data.get("id") or team_data.get("displayName"):
                # Use the team's actual league for roster (ESPN resolves IDs globally)
                roster_slug = (
                    team_data.get("leagueAbbrev")
                    or (team_data.get("defaultLeague") or {}).get("slug")
                    or espn_slug
                )
                result = {
                    "team": _normalize_espn_team(team_data),
                    "players": _parse_espn_roster(roster_slug, tid),
                    "manager": {},
                    "venue": {
                        "id": "",
                        "name": team_data.get("venue", {}).get("fullName", "")
                        if isinstance(team_data.get("venue"), dict)
                        else "",
                    },
                }
                break
    if not result:
        return {"team": {}, "players": [], "error": True, "message": "Team not found"}
    # FPL enrichment for PL teams
    if league_slug == "premier-league" and result.get("players"):
        _enrich_team_players_fpl(result["players"])
    elif not league_slug and result.get("players"):
        # Auto-detect PL by checking team name against FPL bootstrap
        bootstrap = _get_fpl_bootstrap()
        if bootstrap:
            team_name = result.get("team", {}).get("name", "")
            for fpl_team in bootstrap.get("teams", []):
                if _teams_match(team_name, fpl_team.get("name", "")):
                    _enrich_team_players_fpl(result["players"])
                    break
    return result


def get_daily_schedule(request_data):
    """Get all matches for a specific date across all leagues."""
    params = request_data.get("params", {})
    date = params.get("date") or params.get("command_attribute", {}).get("date", "")
    if not date:
        date = datetime.utcnow().strftime("%Y-%m-%d")
    date_key = date.replace("-", "")
    events = []
    seen = set()
    for slug, league in LEAGUES.items():
        espn_slug = league.get("espn")
        if not espn_slug:
            continue
        data = _espn_request(espn_slug, "scoreboard", {"dates": date_key})
        if data.get("error"):
            continue
        for e in data.get("events", []):
            eid = e.get("id", "")
            if eid and eid not in seen:
                seen.add(eid)
                events.append(_normalize_espn_event(e, slug))
    if events:
        return {"date": date, "events": events}
    # openfootball fallback: scan all leagues for matches on this date
    for slug, league in LEAGUES.items():
        of = league.get("openfootball")
        if not of:
            continue
        # Determine which year to use based on date
        d_year = int(date[:4])
        if of["season_format"] == "aug":
            # European: season spans Aug Y to May Y+1
            d_month = int(date[5:7])
            year = str(d_year - 1) if d_month < 7 else str(d_year)
        else:
            year = str(d_year)
        data = _openfootball_fetch(slug, year)
        if not data:
            continue
        for m in data.get("matches", []):
            if m.get("date") == date:
                events.append(_normalize_openfootball_match(m, slug, year))
    return {"date": date, "events": events}


# --- Event Details (ESPN summary primary) ---


def get_event_summary(request_data):
    """Get match summary with basic info and scores."""
    params = request_data.get("params", {})
    event_id = params.get("event_id") or params.get("command_attribute", {}).get(
        "event_id", ""
    )
    eid = _resolve_event_id(event_id)
    if not eid:
        return {
            "event": {},
            "statistics": {},
            "error": True,
            "message": "Missing event_id",
        }
    # ESPN primary
    espn_league, espn_eid = _resolve_espn_event(eid, params)
    if espn_league:
        summary = _espn_summary(espn_league, espn_eid)
        if summary and summary.get("header"):
            slug = ESPN_TO_SLUG.get(espn_league, "")
            header = summary["header"]
            comps = header.get("competitions", [{}])
            comp = comps[0] if comps else {}
            event_data = {
                "id": espn_eid,
                "competitions": [comp],
                "season": header.get("season", {}),
                "date": comp.get("date", ""),
                "week": header.get("week", {}),
            }
            event = _normalize_espn_event(event_data, slug)
            return {"event": event, "statistics": {}}
    return {
        "event": {},
        "statistics": {},
        "error": True,
        "message": "Could not resolve event",
    }


def get_event_lineups(request_data):
    """Get match lineups from ESPN summary."""
    params = request_data.get("params", {})
    event_id = params.get("event_id") or params.get("command_attribute", {}).get(
        "event_id", ""
    )
    eid = _resolve_event_id(event_id)
    if not eid:
        return {"lineups": [], "error": True, "message": "Missing event_id"}
    # ESPN primary
    espn_league, espn_eid = _resolve_espn_event(eid, params)
    if espn_league:
        summary = _espn_summary(espn_league, espn_eid)
        if summary:
            lineups = _normalize_espn_summary_lineups(summary)
            if lineups:
                return {"lineups": lineups}
    return {"lineups": []}


def get_event_statistics(request_data):
    """Get match team statistics from ESPN summary."""
    params = request_data.get("params", {})
    event_id = params.get("event_id") or params.get("command_attribute", {}).get(
        "event_id", ""
    )
    eid = _resolve_event_id(event_id)
    if not eid:
        return {"teams": [], "error": True, "message": "Missing event_id"}
    espn_league, espn_eid = _resolve_espn_event(eid, params)
    if espn_league:
        summary = _espn_summary(espn_league, espn_eid)
        if summary:
            teams = _normalize_espn_summary_statistics(summary)
            if teams:
                return {"teams": teams}
    return {"teams": []}


def get_event_timeline(request_data):
    """Get match timeline/key events from ESPN summary."""
    params = request_data.get("params", {})
    event_id = params.get("event_id") or params.get("command_attribute", {}).get(
        "event_id", ""
    )
    eid = _resolve_event_id(event_id)
    if not eid:
        return {"timeline": [], "error": True, "message": "Missing event_id"}
    espn_league, espn_eid = _resolve_espn_event(eid, params)
    if espn_league:
        summary = _espn_summary(espn_league, espn_eid)
        if summary:
            timeline = _normalize_espn_summary_timeline(summary)
            if timeline:
                return {"timeline": timeline}
    return {"timeline": []}


def get_team_schedule(request_data):
    """Get schedule for a specific team."""
    params = request_data.get("params", {})
    team_id = params.get("team_id") or params.get("command_attribute", {}).get(
        "team_id", ""
    )
    tid = _resolve_team_id(team_id)
    if not tid:
        return {"team": {}, "events": [], "error": True, "message": "Missing team_id"}
    competition_id = params.get("competition_id") or params.get(
        "command_attribute", {}
    ).get("competition_id", "")
    # Resolve competition_id to a slug for filtering
    comp_filter_slug = None
    if competition_id:
        _, comp_filter_slug = _resolve_competition(competition_id)
    # ESPN path: try with league hint first
    league_slug = params.get("league_slug") or params.get("command_attribute", {}).get(
        "league_slug", ""
    )
    season_year = params.get("season_year") or params.get("command_attribute", {}).get(
        "season_year", ""
    )
    leagues_to_try = []
    if league_slug:
        league, _ = _resolve_competition(league_slug)
        if league and league.get("espn"):
            leagues_to_try.append((_, league))
    if not leagues_to_try:
        leagues_to_try = [(s, lg) for s, lg in LEAGUES.items() if lg.get("espn")]
    # When probing multiple leagues, skip retries (ESPN returns 500 for wrong league)
    probe_retries = 0 if len(leagues_to_try) > 1 else _MAX_RETRIES
    for slug, league in leagues_to_try:
        espn_slug = league["espn"]
        espn_params = {"season": str(season_year)} if season_year else {}
        # Fetch past results
        data = _espn_request(
            espn_slug, f"teams/{tid}/schedule", espn_params, max_retries=probe_retries
        )
        if data.get("error"):
            continue
        events_raw = data.get("events", [])
        # Fetch upcoming fixtures (ESPN requires fixture=true separately)
        fixture_params = {**espn_params, "fixture": "true"}
        fixture_data = _espn_request(
            espn_slug,
            f"teams/{tid}/schedule",
            fixture_params,
            max_retries=probe_retries,
        )
        if not fixture_data.get("error"):
            fixture_events = fixture_data.get("events", [])
            # Merge, dedup by event ID
            seen_ids = {e.get("id", "") for e in events_raw}
            for fe in fixture_events:
                if fe.get("id", "") not in seen_ids:
                    events_raw.append(fe)
                    seen_ids.add(fe.get("id", ""))
        if not events_raw:
            continue
        events = [_normalize_espn_event(e, slug) for e in events_raw]
        if comp_filter_slug:
            events = [
                e
                for e in events
                if e.get("competition", {}).get("id") == comp_filter_slug
            ]
        events.sort(key=lambda e: e.get("start_time", ""))
        team_data = {}
        if events and events[0].get("competitors"):
            for comp in events[0]["competitors"]:
                if comp.get("team", {}).get("id") == tid:
                    team_data = comp["team"]
                    break
        return {"team": team_data, "events": events}
    return {"team": {}, "events": [], "message": "Team schedule not found"}


def get_head_to_head(request_data):
    """Get head-to-head history (unavailable — use get_team_schedule for both teams instead)."""
    return {
        "teams": [],
        "events": [],
        "message": "Head-to-head history is unavailable. Use get_team_schedule for both teams and compare.",
    }


# --- Enrichment (Understat + ESPN) ---


def get_event_xg(request_data):
    """Get expected goals (xG) data from Understat (5 top leagues)."""
    params = request_data.get("params", {})
    event_id = params.get("event_id") or params.get("command_attribute", {}).get(
        "event_id", ""
    )
    eid = _resolve_event_id(event_id)
    if not eid:
        return {
            "event_id": event_id,
            "teams": [],
            "shots": [],
            "error": True,
            "message": "Missing event_id",
        }
    # Build match context from ESPN
    match_ctx = None
    espn_league, espn_eid = _resolve_espn_event(eid, params)
    if espn_league:
        summary = _espn_summary(espn_league, espn_eid)
        if summary:
            match_ctx = _get_match_context(espn_league, espn_eid, summary)
    if not match_ctx:
        return {
            "event_id": event_id,
            "teams": [],
            "shots": [],
            "message": "Could not resolve match",
        }
    if not match_ctx.get("understat_league"):
        return {
            "event_id": event_id,
            "teams": [],
            "shots": [],
            "message": (
                f"xG data not available for {match_ctx.get('slug', 'this league')}. "
                "Understat covers: EPL, La Liga, Bundesliga, Serie A, Ligue 1"
            ),
        }
    understat_id = _find_understat_match_id(match_ctx)
    if not understat_id:
        return {
            "event_id": event_id,
            "teams": [],
            "shots": [],
            "message": "Match not found on Understat",
        }
    udata = _get_understat_match(understat_id)
    if not udata:
        return {
            "event_id": event_id,
            "teams": [],
            "shots": [],
            "message": "Could not fetch Understat data",
        }
    result = _normalize_understat_xg(udata["shots"], udata["match_info"])
    result["event_id"] = event_id
    result["source"] = "understat"
    return result


def get_event_players_statistics(request_data):
    """Get player-level match statistics from ESPN + Understat xG."""
    params = request_data.get("params", {})
    event_id = params.get("event_id") or params.get("command_attribute", {}).get(
        "event_id", ""
    )
    eid = _resolve_event_id(event_id)
    if not eid:
        return {
            "event_id": event_id,
            "teams": [],
            "error": True,
            "message": "Missing event_id",
        }
    # ESPN primary for player stats
    espn_league, espn_eid = _resolve_espn_event(eid, params)
    summary = None
    if espn_league:
        summary = _espn_summary(espn_league, espn_eid)
    if summary:
        teams = _normalize_espn_summary_players(summary)
        if teams:
            # Enrich with Understat xG if available
            match_ctx = _get_match_context(espn_league, espn_eid, summary)
            if match_ctx and match_ctx.get("understat_league"):
                understat_id = _find_understat_match_id(match_ctx)
                if understat_id:
                    udata = _get_understat_match(understat_id)
                    if udata:
                        uteams = _normalize_understat_players(
                            udata["rosters"], udata["match_info"]
                        )
                        _merge_understat_player_xg(teams, uteams)
            return {"event_id": event_id, "teams": teams}
    return {
        "event_id": event_id,
        "teams": [],
        "message": "Player statistics not available",
    }


def _merge_understat_player_xg(espn_teams, ustat_teams):
    """Merge Understat xG data into ESPN player statistics (in-place)."""
    for espn_t in espn_teams:
        qualifier = espn_t.get("qualifier", "")
        ustat_t = next(
            (u for u in ustat_teams if u.get("qualifier") == qualifier), None
        )
        if not ustat_t:
            continue
        ustat_players = {p["name"].lower(): p for p in ustat_t.get("players", [])}
        for ep in espn_t.get("players", []):
            ep_name = ep.get("name", "").lower()
            up = ustat_players.get(ep_name)
            if not up:
                for uname, upl in ustat_players.items():
                    if _teams_match(ep_name, uname):
                        up = upl
                        break
            if up:
                ep["statistics"]["xg"] = str(up.get("xg", 0))
                ep["statistics"]["xa"] = str(up.get("xa", 0))
                ep["statistics"]["xg_chain"] = str(up.get("xg_chain", 0))
                ep["statistics"]["xg_buildup"] = str(up.get("xg_buildup", 0))
                ep["statistics"]["key_passes"] = str(up.get("key_passes", 0))


def get_missing_players(request_data):
    """Get injured/missing/doubtful players. FPL source for PL."""
    params = request_data.get("params", {})
    season_id = params.get("season_id") or params.get("command_attribute", {}).get(
        "season_id", ""
    )
    league, slug, year = _resolve_season(season_id)
    if not league:
        return {
            "season_id": season_id,
            "teams": [],
            "error": True,
            "message": f"Unknown season: {season_id}",
        }
    # FPL path (PL only)
    if league.get("fpl"):
        bootstrap = _get_fpl_bootstrap()
        if bootstrap:
            return _build_missing_players_from_fpl(bootstrap, season_id)
    return {
        "season_id": season_id,
        "teams": [],
        "message": "Missing player data only available for Premier League (via FPL)",
    }


def get_season_transfers(request_data):
    """Get season transfers. Transfermarkt ceapi when tm_player_ids provided."""
    params = request_data.get("params", {})
    season_id = params.get("season_id") or params.get("command_attribute", {}).get(
        "season_id", ""
    )
    tm_player_ids = params.get("tm_player_ids") or params.get(
        "command_attribute", {}
    ).get("tm_player_ids", [])
    if not tm_player_ids:
        return {
            "season_id": season_id,
            "transfers": [],
            "message": "Transfers require tm_player_ids parameter (list of Transfermarkt player IDs)",
        }
    league, slug, year = _resolve_season(season_id)
    all_transfers = []
    for tm_id in tm_player_ids[:50]:
        history = _tm_transfer_history(str(tm_id))
        if not history:
            continue
        transfers_raw = history.get("transfers", history.get("transferHistory", []))
        if isinstance(transfers_raw, list):
            for t in transfers_raw:
                normalized = _normalize_tm_transfer(t, str(tm_id))
                if year and normalized.get("date"):
                    try:
                        t_year = int(normalized["date"][:4])
                        if abs(t_year - year) > 1:
                            continue
                    except (ValueError, TypeError):
                        pass
                all_transfers.append(normalized)
    return {"season_id": season_id, "transfers": all_transfers}


def get_player_profile(request_data):
    """Get player profile. FPL for PL, Transfermarkt enrichment."""
    params = request_data.get("params", {})
    player_id = params.get("player_id") or params.get("command_attribute", {}).get(
        "player_id", ""
    )
    fpl_id = params.get("fpl_id") or params.get("command_attribute", {}).get(
        "fpl_id", ""
    )
    pid = _resolve_player_id(player_id)
    player = {}
    # FPL enrichment
    if fpl_id:
        bootstrap = _get_fpl_bootstrap()
        if bootstrap:
            for fp in bootstrap.get("elements", []):
                if str(fp.get("id")) == str(fpl_id) or str(fp.get("code")) == str(
                    fpl_id
                ):
                    if not player:
                        player = _normalize_fpl_player_as_profile(fp)
                    player["fpl_data"] = _normalize_fpl_player_enrichment(fp)
                    break
    elif not player and pid:
        # Try to find in FPL by matching code (FPL code == PL player code)
        bootstrap = _get_fpl_bootstrap()
        if bootstrap:
            for fp in bootstrap.get("elements", []):
                if str(fp.get("code")) == str(pid):
                    player = _normalize_fpl_player_as_profile(fp)
                    player["fpl_data"] = _normalize_fpl_player_enrichment(fp)
                    break
    # ESPN profile fallback — when player_id (ESPN athlete ID) is provided
    if not player and pid:
        _espn_profile_slugs = [
            "eng.1", "esp.1", "ger.1", "ita.1", "fra.1", "bra.1", "usa.1",
            "ned.1", "por.1", "mex.1", "arg.1", "eng.2", "sco.1", "bel.1",
        ]
        for slug in _espn_profile_slugs:
            url = (
                f"https://site.api.espn.com/apis/common/v3/sports/soccer"
                f"/{slug}/athletes/{pid}"
            )
            raw, err = _http_fetch(
                url, headers={"User-Agent": _USER_AGENT},
                rate_limiter=_espn_rate_limiter, max_retries=0,
            )
            if err:
                continue
            try:
                data = json.loads(raw.decode())
            except (json.JSONDecodeError, ValueError):
                continue
            ath = data.get("athlete", {})
            if ath.get("id"):
                pos = ath.get("position", {})
                team_info = ath.get("team", {})
                player = {
                    "id": str(ath.get("id", "")),
                    "espn_athlete_id": str(ath.get("id", "")),
                    "name": ath.get("displayName", ath.get("fullName", "")),
                    "first_name": ath.get("firstName", ""),
                    "last_name": ath.get("fullName", "").split()[-1]
                    if ath.get("fullName")
                    else "",
                    "position": pos.get("displayName", pos.get("name", ""))
                    if isinstance(pos, dict)
                    else str(pos),
                    "shirt_number": ath.get("jersey", ""),
                    "age": ath.get("age"),
                    "nationality": ath.get("citizenship", ""),
                    "height": ath.get("displayHeight", ""),
                    "weight": ath.get("displayWeight", ""),
                    "team": team_info.get("displayName", ""),
                    "team_id": str(team_info.get("id", "")),
                    "league": slug,
                    "photo": ath.get("headshot", {}).get("href", "")
                    if isinstance(ath.get("headshot"), dict)
                    else "",
                }
                break
    # Transfermarkt enrichment
    tm_id = _resolve_tm_player_id(params)
    if tm_id:
        mv_data = _tm_market_value(tm_id)
        if mv_data and isinstance(mv_data, dict):
            mv_list = mv_data.get("list", mv_data.get("marketValueDevelopment", []))
            if isinstance(mv_list, list) and mv_list:
                player["market_value"] = _normalize_tm_market_value(mv_list[-1])
                player["market_value_history"] = [
                    _normalize_tm_market_value(entry) for entry in mv_list
                ]
        th_data = _tm_transfer_history(tm_id)
        if th_data and isinstance(th_data, dict):
            th_list = th_data.get("transfers", th_data.get("transferHistory", []))
            if isinstance(th_list, list) and th_list:
                player["transfer_history"] = [
                    _normalize_tm_transfer(t, tm_id) for t in th_list
                ]
    if not player:
        return {
            "player": {},
            "message": "Player not found. Provide player_id, fpl_id, or tm_player_id.",
        }
    return {"player": player}


def get_player_season_stats(request_data):
    """Get player season gamelog with per-match stats via ESPN overview endpoint.

    Returns appearances, goals, assists, shots, shots on target, fouls,
    offsides, and cards for each match in the current season.
    """
    params = request_data.get("params", {})
    player_id = params.get("player_id") or params.get("command_attribute", {}).get(
        "player_id", ""
    )
    league_slug = params.get("league_slug") or params.get("command_attribute", {}).get(
        "league_slug", "eng.1"
    )

    if not player_id:
        return {"error": True, "message": "player_id is required (ESPN athlete ID)"}

    cache_key = f"football_player_season:{player_id}:{league_slug}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    url = (
        f"https://site.web.api.espn.com/apis/common/v3/sports/soccer"
        f"/{league_slug}/athletes/{player_id}/overview"
    )
    headers = {"User-Agent": _USER_AGENT}
    raw, err = _http_fetch(url, headers=headers, rate_limiter=_espn_rate_limiter)
    if err:
        return err

    try:
        data = json.loads(raw.decode())
    except (json.JSONDecodeError, ValueError):
        return {"error": True, "message": "ESPN returned invalid JSON"}

    # Parse gameLog from overview
    game_log = data.get("gameLog", {})
    stats_blocks = game_log.get("statistics", [])
    if not stats_blocks:
        return {
            "player_id": str(player_id),
            "league": league_slug,
            "matches": [],
            "message": "No season statistics available for this player.",
        }

    stat_block = stats_blocks[0]
    labels = stat_block.get("labels", [])
    names = stat_block.get("names", [])
    display_names = stat_block.get("displayNames", [])

    # Build per-match entries
    matches = []
    events_data = stat_block.get("events", [])
    events_meta = game_log.get("events", {})

    for ev in events_data:
        event_id = str(ev.get("eventId", ""))
        stats_raw = ev.get("stats", [])

        # Map stats to named keys
        stats = {}
        for i, val in enumerate(stats_raw):
            key = names[i] if i < len(names) else (labels[i] if i < len(labels) else f"stat_{i}")
            stats[key] = val

        match_entry = {"event_id": event_id, "stats": stats}

        # Add event metadata (links) if available
        meta = events_meta.get(event_id, {})
        if meta:
            for link in meta.get("links", []):
                if "summary" in link.get("rel", []):
                    match_entry["link"] = link.get("href", "")
                    break

        matches.append(match_entry)

    result = {
        "player_id": str(player_id),
        "league": league_slug,
        "stat_columns": labels,
        "stat_names": names,
        "stat_display_names": display_names,
        "matches": matches,
        "count": len(matches),
    }
    _cache_set(cache_key, result, ttl=600)
    return result


# ============================================================
# Player Search (Transfermarkt + ESPN)
# ============================================================


def _tm_search_players(query, limit=5):
    """Search Transfermarkt quick-search page for players.

    Returns a list of dicts with tm_player_id, name, position, club, etc.
    Parses the HTML search results page (no JSON API available for search).
    """
    import html as html_mod

    encoded_query = urllib.parse.quote_plus(query)
    url = (
        f"https://www.transfermarkt.com/schnellsuche/ergebnis/"
        f"schnellsuche?query={encoded_query}"
    )
    raw, err = _http_fetch(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": "text/html"},
        rate_limiter=_tm_rate_limiter,
        max_retries=1,
    )
    if err or not raw:
        logger.debug("TM search failed for %r: %s", query, err)
        return []

    page = raw.decode("utf-8", errors="replace")

    results = []
    # Each player row has an inline-table with player link + club,
    # followed by a <td> with the position.
    for m in re.finditer(
        r'<table class="inline-table">(.*?)</table>\s*</td>\s*<td[^>]*>([^<]*)</td>',
        page,
        re.DOTALL,
    ):
        block = m.group(1)
        position = m.group(2).strip()

        player_link = re.search(
            r'href="/([^"]+)/profil/spieler/(\d+)"[^>]*>([^<]+)</a>', block
        )
        if not player_link:
            continue
        slug, tm_id, name = player_link.groups()
        name = html_mod.unescape(name.strip())

        club_link = re.search(
            r'<a title="([^"]+)" href="/[^"]+/startseite/verein/(\d+)">', block
        )
        club_name = html_mod.unescape(club_link.group(1)) if club_link else ""
        club_id = club_link.group(2) if club_link else ""

        results.append(
            {
                "name": name,
                "tm_player_id": tm_id,
                "position": position,
                "club": club_name,
                "tm_club_id": club_id,
            }
        )
        if len(results) >= limit:
            break

    return results


def _espn_search_players(query, limit=5):
    """Search ESPN for football/soccer players by name.

    Returns a list of dicts with espn_athlete_id, name, league, team info.
    """
    encoded_query = urllib.parse.quote_plus(query)
    url = (
        f"https://site.api.espn.com/apis/common/v3/search"
        f"?query={encoded_query}&type=player&sport=soccer&limit={limit}"
    )
    raw, err = _http_fetch(
        url,
        headers={"User-Agent": _USER_AGENT},
        rate_limiter=_espn_rate_limiter,
        max_retries=1,
    )
    if err or not raw:
        logger.debug("ESPN search failed for %r: %s", query, err)
        return []

    try:
        data = json.loads(raw.decode())
    except (json.JSONDecodeError, ValueError):
        return []

    results = []
    for item in data.get("items", []):
        if item.get("type") != "player":
            continue
        league_rels = item.get("leagueRelationships", [])
        league_slug = ""
        league_name = ""
        if league_rels:
            core = league_rels[0].get("core", {})
            league_slug = core.get("slug", "")
            league_name = core.get("displayName", "")
        results.append(
            {
                "espn_athlete_id": item.get("id", ""),
                "name": item.get("displayName", ""),
                "league": league_slug,
                "league_name": league_name,
            }
        )
        if len(results) >= limit:
            break

    return results


def search_player(request_data):
    """Search for a football player by name.

    Searches Transfermarkt and ESPN simultaneously to return player IDs
    that can be used with get_player_profile and get_season_transfers.
    """
    params = request_data.get("params", {})
    query = params.get("query") or params.get("command_attribute", {}).get("query", "")
    if not query:
        return {"results": [], "error": True, "message": "Missing query"}
    limit = 5

    # Search both sources
    tm_results = _tm_search_players(query, limit=limit)
    espn_results = _espn_search_players(query, limit=limit)

    # Merge: pair TM and ESPN results by name similarity
    merged = []
    used_espn = set()

    for tm in tm_results:
        entry = {
            "name": tm["name"],
            "tm_player_id": tm["tm_player_id"],
            "position": tm["position"],
            "club": tm["club"],
            "tm_club_id": tm["tm_club_id"],
            "espn_athlete_id": "",
            "league": "",
            "league_name": "",
        }
        # Try to match with an ESPN result
        tm_lower = _normalize_name(tm["name"])
        for i, espn in enumerate(espn_results):
            if i in used_espn:
                continue
            espn_lower = _normalize_name(espn["name"])
            if tm_lower == espn_lower or tm_lower in espn_lower or espn_lower in tm_lower:
                entry["espn_athlete_id"] = espn["espn_athlete_id"]
                entry["league"] = espn["league"]
                entry["league_name"] = espn["league_name"]
                used_espn.add(i)
                break
        merged.append(entry)

    # Add unmatched ESPN results
    for i, espn in enumerate(espn_results):
        if i in used_espn:
            continue
        merged.append(
            {
                "name": espn["name"],
                "tm_player_id": "",
                "position": "",
                "club": "",
                "tm_club_id": "",
                "espn_athlete_id": espn["espn_athlete_id"],
                "league": espn["league"],
                "league_name": espn["league_name"],
            }
        )

    return {"results": merged[:limit]}
