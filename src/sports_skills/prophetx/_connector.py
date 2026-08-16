"""ProphetX betting exchange — public read-only market data endpoints.

Wraps the ProphetX public trade API for tournament/event/market discovery.
No authentication required; this module never sends credentials and only
issues GET requests. Uses stdlib only (urllib, json, threading).

This is the KEYLESS public surface — it is distinct from the authenticated
ProphetX Affiliate API (Machina connector, separate track). Do not add
Authorization headers or write operations here.

Upstream behavior verified live (2026-08-13, re-verified 2026-08-16):
- Envelope varies by endpoint: ``{"next": int, "data": {"tournaments": [...]}}``,
  ``{"next": "<epoch>_<id>", "data": [...]}`` (a bare list), ``{"data": {"markets":
  [...]}}`` with no ``next``, and a literal ``{}`` body for empty results.
- Errors: ``{"error": "<msg>", "error_code": <int>}`` with HTTP 400/404.
- ``selections`` on markets/marketLines are OPTIONAL: when a public order book
  is exposed they carry American odds, stake, and price levels; when the book
  is empty or suspended (common on in-play and low-activity markets) they come
  back ``[null, null]``. Availability varies per market — 2026-08-13 probes
  saw all-null selections on a live game, 2026-08-16 probes saw populated
  moneyline/spread/total books on pre-game markets. Always check the
  ``selections_available`` flag; normalize odds only when actually present,
  and never invent them.
- Event ``status`` values observed: ``not_started``, ``live``. End of
  pagination: ``next`` is null/absent on the final page.
- No rate-limit headers observed; throttle conservatively anyway (CloudFront +
  KrakenD in front; fail closed on 403).
"""

import json
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# ============================================================
# Configuration
# ============================================================

BASE_URL = "https://cash.api.prophetx.co/trade/public/api"

# Read-only guard: this module must never authenticate or write.
_ALLOWED_METHOD = "GET"

# Upstream default page size is 10; cursor pagination via `next`.
_PAGE_LIMIT = 50

# Bounded fan-out caps for composite commands (search/todays): these commands
# chain tournaments -> events -> markets, so caps keep request counts small.
_MAX_TOURNAMENT_PAGES = 4
_MAX_EVENT_PAGES_PER_TOURNAMENT = 3
_MAX_TOURNAMENTS_SCANNED = 12
_MAX_MARKET_EVENTS = 5

# Sport ids observed on /v1/tournaments (sport is a nested object per tournament).
SPORT_CODES = {
    "soccer": 1,
    "basketball": 2,
    "baseball": 3,
    "ice-hockey": 4,
    "tennis": 5,
    "american-football": 16,
}

# Friendly aliases -> canonical ProphetX sport codes.
SPORT_ALIASES = {
    "football": "american-football",
    "nfl": "american-football",
    "cfb": "american-football",
    "nba": "basketball",
    "wnba": "basketball",
    "cbb": "basketball",
    "mlb": "baseball",
    "nhl": "ice-hockey",
    "hockey": "ice-hockey",
    "epl": "soccer",
    "ucl": "soccer",
    "laliga": "soccer",
    "bundesliga": "soccer",
    "seriea": "soccer",
    "ligue1": "soccer",
    "mls": "soccer",
    "worldcup": "soccer",
    "atp": "tennis",
    "wta": "tennis",
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
# Rate Limiter (Token Bucket) — conservative: no published limits upstream
# ============================================================


class _RateLimiter:
    def __init__(self, max_tokens=4, refill_rate=2.0):
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


_rate_limiter = _RateLimiter(max_tokens=4, refill_rate=2.0)


# ============================================================
# HTTP Helpers
# ============================================================

_USER_AGENT = "sports-skills/0.1 (Python; stdlib)"

# Retry only transient statuses; 403 is treated as WAF/blocked -> fail closed.
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 2


def _request(endpoint, params=None, ttl=60):
    """Make a GET request to the ProphetX public API. Cached, throttled, retried.

    Returns parsed JSON on success, or ``{"error": True, "status_code": ...,
    "message": ...}`` on failure. Never raises; never sends credentials.
    """
    cache_key = f"prophetx:{endpoint}:{json.dumps(params or {}, sort_keys=True)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    url = f"{BASE_URL}{endpoint}"
    if params:
        clean = {k: v for k, v in params.items() if v is not None and v != ""}
        if clean:
            url += "?" + urllib.parse.urlencode(clean, doseq=True)

    last_error = None
    for attempt in range(_MAX_RETRIES + 1):
        _rate_limiter.acquire()
        req = urllib.request.Request(url, method=_ALLOWED_METHOD)
        req.add_header("User-Agent", _USER_AGENT)
        req.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                try:
                    data = json.loads(resp.read().decode())
                except (ValueError, UnicodeDecodeError) as parse_err:
                    return {"error": True, "message": f"Malformed JSON from upstream: {parse_err}"}
                _cache_set(cache_key, data, ttl=ttl)
                return data
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode() if e.fp else ""
            except Exception:
                pass
            message = body or str(e.reason)
            try:
                parsed = json.loads(body) if body else {}
                if isinstance(parsed, dict) and parsed.get("error"):
                    message = f"{parsed.get('error')} (error_code={parsed.get('error_code')})"
            except ValueError:
                pass
            last_error = {"error": True, "status_code": e.code, "message": message}
            if e.code == 403:
                # WAF/blocked: fail closed immediately, do not hammer.
                last_error["message"] = f"Access blocked upstream (403). Not retrying. {message}"
                return last_error
            if e.code not in _RETRYABLE_STATUSES or attempt == _MAX_RETRIES:
                return last_error
            retry_after = e.headers.get("Retry-After") if e.headers else None
            _backoff(attempt, retry_after)
        except Exception as e:
            last_error = {"error": True, "message": str(e)}
            if attempt == _MAX_RETRIES:
                return last_error
            _backoff(attempt, None)

    return last_error or {"error": True, "message": "Request failed"}


def _backoff(attempt, retry_after):
    """Exponential backoff with jitter; honors Retry-After when parseable."""
    if retry_after:
        try:
            time.sleep(min(10.0, float(retry_after)))
            return
        except (TypeError, ValueError):
            pass
    time.sleep(min(10.0, (0.5 * (2**attempt)) + random.uniform(0, 0.25)))


# ============================================================
# Response Helpers
# ============================================================


def _success(data, message=""):
    return {"status": True, "data": data, "message": message}


def _error(message, data=None):
    return {"status": False, "data": data, "message": message}


def _check_error(response):
    if isinstance(response, dict) and response.get("error"):
        code = response.get("status_code", "unknown")
        msg = response.get("message", "Unknown error")
        return _error(f"API error ({code}): {msg}")
    return None


def _unwrap(response, key):
    """Tolerate every observed envelope shape and return (items, next_cursor).

    Shapes seen live: ``{"data": {"<key>": [...]}}``, ``{"data": [...]}``,
    a literal ``{}`` for empty, plus schema drift where fields go missing.
    Returns ``(None, None)`` when the payload doesn't match any known shape
    (schema drift -> caller fails closed instead of mis-parsing).
    """
    if not isinstance(response, dict):
        return None, None
    next_cursor = response.get("next")
    data = response.get("data")
    if data is None:
        # Empty body `{}` observed for tournaments without events.
        return ([], next_cursor) if not response or "data" in response else (None, None)
    if isinstance(data, list):
        return data, next_cursor
    if isinstance(data, dict):
        items = data.get(key)
        if items is None:
            return [], next_cursor
        if isinstance(items, list):
            return items, next_cursor
        return None, None
    return None, None


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# Odds Helpers
# ============================================================


def _american_to_probability(odds):
    """Implied probability from American odds. Returns None when not derivable."""
    try:
        value = float(odds)
    except (TypeError, ValueError):
        return None
    if value == 0:
        return None
    if value > 0:
        return round(100.0 / (value + 100.0), 4)
    return round(-value / (-value + 100.0), 4)


def _normalize_selection(selection):
    """Normalize one order-book selection, preserving raw payload.

    Public responses frequently carry ``selections: [null, null]`` (empty
    book). When populated, odds/stake keys are extracted defensively and the
    full raw object is preserved — never invent fields that aren't there.
    Selections may arrive as a flat dict or a list of price levels.
    """
    if selection is None:
        return None
    if isinstance(selection, list):
        levels = [_normalize_selection(level) for level in selection]
        return [level for level in levels if level is not None] or None
    if not isinstance(selection, dict):
        return None
    odds = selection.get("odds")
    normalized = {
        "odds_american": odds if isinstance(odds, (int, float)) else None,
        "implied_probability": _american_to_probability(odds),
        "line_id": selection.get("line_id") or selection.get("lineID") or selection.get("lineId"),
        "stake": selection.get("stake"),
        "available_stake": selection.get("available_stake") or selection.get("availableStake"),
        "_raw": selection,
    }
    return normalized


# ============================================================
# Normalizers (provider-neutral fields + _raw)
# ============================================================


def _normalize_tournament(tournament):
    sport = tournament.get("sport") or {}
    category = tournament.get("category") or {}
    return {
        "id": tournament.get("id"),
        "name": tournament.get("name", ""),
        "sport": sport.get("name", ""),
        "sport_id": sport.get("id"),
        "category": category.get("name", ""),
        "source_url": f"{BASE_URL}/v1/tournaments",
        "_raw": tournament,
    }


def _normalize_event(event, tournament=None):
    competitors = []
    home_name = ""
    away_name = ""
    for competitor in event.get("competitors") or []:
        seq = competitor.get("seq")
        name = competitor.get("displayName") or competitor.get("name", "")
        competitors.append(
            {
                "id": competitor.get("id"),
                "name": name,
                "abbreviation": competitor.get("abbreviation", ""),
                "seq": seq,
                # Observed convention: seq 0 = home (matches venue), seq 1 = away.
                "home": seq == 0,
            }
        )
        if seq == 0:
            home_name = name
        elif seq == 1:
            away_name = name

    tournament_ref = event.get("tournament") or {}
    tournament_id = tournament_ref.get("id") or (tournament or {}).get("id")
    venue = event.get("venue") or {}
    return {
        "id": event.get("id"),
        "name": event.get("name", ""),
        "tournament_id": tournament_id,
        "tournament": tournament_ref.get("name") or (tournament or {}).get("name", ""),
        "scheduled": event.get("scheduled", ""),
        "status": event.get("status", ""),
        "home": home_name,
        "away": away_name,
        "competitors": competitors,
        "venue": venue.get("name", ""),
        "source_url": f"{BASE_URL}/v1/tournaments/{tournament_id}/events"
        if tournament_id
        else f"{BASE_URL}/v1/tournaments",
        "retrieved_at": _now_iso(),
        "_raw": event,
    }


def _normalize_outcome(outcome, selections=None):
    normalized = {
        "id": outcome.get("id"),
        "name": outcome.get("displayName") or outcome.get("name", ""),
        "competitor_id": outcome.get("competitorId"),
        "line": outcome.get("line"),
        "display_line": outcome.get("displayLine"),
        "line_id": outcome.get("lineID") or outcome.get("lineId"),
    }
    odds = outcome.get("odds")
    if isinstance(odds, (int, float)) and odds != 0:
        normalized["odds_american"] = odds
        normalized["implied_probability"] = _american_to_probability(odds)
    if selections is not None:
        normalized["selections"] = selections
    return normalized


def _normalize_market(market, event_id=None, api_version="v1"):
    """Normalize a market from /v1 or /v2 event-markets payloads.

    ``market["id"]`` is the market-TYPE id (e.g. 219 = Moneyline on any event),
    not unique per event — ``market_key`` combines event and type for a stable
    per-event identity.
    """
    sport_event_id = market.get("sportEventId") or event_id
    raw_selections = market.get("selections")
    selections_by_index = []
    if isinstance(raw_selections, list):
        selections_by_index = [_normalize_selection(sel) for sel in raw_selections]

    outcomes = []
    for index, outcome in enumerate(market.get("outcomes") or []):
        selection = selections_by_index[index] if index < len(selections_by_index) else None
        outcomes.append(_normalize_outcome(outcome, selections=selection))

    market_lines = []
    for line in market.get("marketLines") or []:
        line_selections = line.get("selections")
        line_outcomes = []
        normalized_line_selections = []
        if isinstance(line_selections, list):
            normalized_line_selections = [_normalize_selection(sel) for sel in line_selections]
        for index, outcome in enumerate(line.get("outcomes") or []):
            selection = normalized_line_selections[index] if index < len(normalized_line_selections) else None
            line_outcomes.append(_normalize_outcome(outcome, selections=selection))
        market_lines.append(
            {
                "id": line.get("id"),
                "name": line.get("name", ""),
                "line": line.get("line"),
                # Upstream flags the PRIMARY line of a multi-line market
                # (e.g. the fixed run line / fixed total) as favourite.
                "favourite": bool(line.get("favourite")),
                "outcomes": line_outcomes,
                "_raw": line,
            }
        )

    has_selections = any(sel is not None for sel in selections_by_index) or any(
        outcome.get("selections") for line in market_lines for outcome in line["outcomes"]
    )

    return {
        "id": market.get("id"),
        "market_key": f"{sport_event_id}:{market.get('id')}",
        "event_id": sport_event_id,
        "name": market.get("name", ""),
        "type": market.get("type", ""),
        "subtype": market.get("subType", ""),
        "category": market.get("categoryName", ""),
        "status": market.get("status", ""),
        "total_stake": market.get("totalStake", 0),
        "outcomes": outcomes,
        "market_lines": market_lines,
        "selections_available": has_selections,
        "api_version": api_version,
        "source_url": f"{BASE_URL}/{api_version}/events/{sport_event_id}/markets",
        "retrieved_at": _now_iso(),
        "_raw": market,
    }


# ============================================================
# Paged fetch helpers
# ============================================================


def _fetch_tournaments_paged(max_items, ttl=600):
    """Collect /v1/tournaments pages following the integer `next` cursor.

    Returns (tournaments, next_cursor, error): error only when the FIRST page
    fails; next_cursor lets callers resume past ``max_items``.
    """
    tournaments = []
    cursor = None
    for _ in range(_MAX_TOURNAMENT_PAGES):
        if len(tournaments) >= max_items:
            break
        params = {"limit": min(_PAGE_LIMIT, max_items - len(tournaments))}
        if cursor is not None:
            params["next"] = cursor
        response = _request("/v1/tournaments", params=params, ttl=ttl)
        err = _check_error(response)
        if err:
            if tournaments:
                return tournaments, cursor, None
            return [], None, err
        page, cursor = _unwrap(response, "tournaments")
        if page is None:
            if tournaments:
                return tournaments, None, None
            return [], None, _error("Unexpected tournaments payload shape (schema drift)")
        tournaments.extend(page)
        if not cursor or not page:
            break
    return tournaments[:max_items], cursor, None


def _fetch_events_paged(tournament_id, max_items, ttl=60):
    """Collect /v1/tournaments/{id}/events pages following the string cursor."""
    events = []
    cursor = None
    for _ in range(_MAX_EVENT_PAGES_PER_TOURNAMENT):
        if len(events) >= max_items:
            break
        params = {"limit": min(_PAGE_LIMIT, max_items - len(events))}
        if cursor:
            params["next"] = cursor
        response = _request(f"/v1/tournaments/{tournament_id}/events", params=params, ttl=ttl)
        err = _check_error(response)
        if err:
            if events:
                return events, None
            return [], err
        page, cursor = _unwrap(response, "events")
        if page is None:
            if events:
                return events, None
            return [], _error("Unexpected events payload shape (schema drift)")
        events.extend(page)
        if not cursor or not page:
            break
    return events[:max_items], None


def _fetch_event_markets(event_id, api_version="v1", ttl=30):
    """Fetch one event's markets; v2 falls back to v1 on failure.

    Returns (markets, used_version, error).
    """
    version = "v2" if str(api_version).lower() == "v2" else "v1"
    response = _request(f"/{version}/events/{event_id}/markets", ttl=ttl)
    err = _check_error(response)
    markets = None
    if not err:
        markets, _ = _unwrap(response, "markets")
    if (err or markets is None) and version == "v2":
        # Tested fallback: keep v1 compatibility when v2 errors or drifts.
        response = _request(f"/v1/events/{event_id}/markets", ttl=ttl)
        err = _check_error(response)
        if err:
            return None, "v1", err
        markets, _ = _unwrap(response, "markets")
        version = "v1"
    if err:
        return None, version, err
    if markets is None:
        return None, version, _error("Unexpected markets payload shape (schema drift)")
    return markets, version, None


def _resolve_sport(sport):
    """Resolve a sport code/alias to (canonical_code, sport_id). None when unknown."""
    if not sport:
        return None, None
    code = str(sport).strip().lower().replace("_", "-").replace(" ", "-")
    code = SPORT_ALIASES.get(code, code)
    sport_id = SPORT_CODES.get(code)
    if sport_id is None:
        return None, None
    return code, sport_id


def _parse_scheduled(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


# ============================================================
# Commands — Public Endpoints
# ============================================================


def get_tournaments(request_data):
    """Get available tournaments (leagues/competitions).

    Params:
        limit (int): Max tournaments (default: 50; upstream page default is 10)
        sport (str): Filter by sport code ('soccer', 'tennis', 'basketball',
            'baseball', 'ice-hockey', 'american-football', or aliases like
            'nfl', 'mlb', 'nhl', 'epl')
        next (int): Pagination cursor from a previous response
    """
    try:
        params = request_data.get("params", {})
        limit = min(int(params.get("limit", 50)), 200)
        sport = params.get("sport")
        sport_id = None
        if sport:
            code, sport_id = _resolve_sport(sport)
            if code is None:
                valid = sorted(set(SPORT_CODES) | set(SPORT_ALIASES))
                return _error(f"Unknown sport '{sport}'. Valid codes: {', '.join(valid)}")

        if params.get("next") is not None:
            response = _request(
                "/v1/tournaments",
                params={"limit": limit, "next": params["next"]},
                ttl=600,
            )
            err = _check_error(response)
            if err:
                return err
            tournaments, cursor = _unwrap(response, "tournaments")
            if tournaments is None:
                return _error("Unexpected tournaments payload shape (schema drift)")
        else:
            tournaments, cursor, err = _fetch_tournaments_paged(limit)
            if err:
                return err

        if sport_id is not None:
            tournaments = [t for t in tournaments if (t.get("sport") or {}).get("id") == sport_id]

        normalized = [_normalize_tournament(t) for t in tournaments]
        data = {"tournaments": normalized, "count": len(normalized)}
        if cursor is not None:
            data["next"] = cursor
        return _success(data, f"Retrieved {len(normalized)} tournaments")
    except Exception as e:
        return _error(f"Error fetching tournaments: {str(e)}")


def get_events(request_data):
    """Get events for a tournament.

    Params:
        tournament_id (int): Tournament ID (required)
        limit (int): Max events (default: 50)
        status (str): Client-side filter by event status (e.g. 'not_started')
    """
    try:
        params = request_data.get("params", {})
        tournament_id = params.get("tournament_id")
        if tournament_id in (None, ""):
            return _error("tournament_id is required")
        try:
            tournament_id = int(tournament_id)
        except (TypeError, ValueError):
            return _error(f"tournament_id must be an integer, got '{tournament_id}'")

        limit = min(int(params.get("limit", 50)), 200)
        events, err = _fetch_events_paged(tournament_id, limit)
        if err:
            return err

        status = params.get("status")
        if status:
            events = [e for e in events if e.get("status") == status]

        normalized = [_normalize_event(e) for e in events]
        return _success(
            {"events": normalized, "count": len(normalized), "tournament_id": tournament_id},
            f"Retrieved {len(normalized)} events",
        )
    except Exception as e:
        return _error(f"Error fetching events: {str(e)}")


def get_markets(request_data):
    """Get markets for an event.

    Params:
        event_id (int): Event ID (required)
        api_version (str): 'v1' (default) or 'v2' (richer: subType, category,
            marketLines/alt lines, player props). v2 falls back to v1 on failure.
        market_type (str): Client-side filter by type (e.g. 'moneyline', 'spread', 'total')
    """
    try:
        params = request_data.get("params", {})
        event_id = params.get("event_id")
        if event_id in (None, ""):
            return _error("event_id is required")
        try:
            event_id = int(event_id)
        except (TypeError, ValueError):
            return _error(f"event_id must be an integer, got '{event_id}'")

        api_version = str(params.get("api_version", "v1")).lower()
        if api_version not in ("v1", "v2"):
            return _error("api_version must be 'v1' or 'v2'")

        markets, used_version, err = _fetch_event_markets(event_id, api_version)
        if err:
            return err

        market_type = params.get("market_type")
        if market_type:
            markets = [m for m in markets if m.get("type") == market_type]

        normalized = [_normalize_market(m, event_id=event_id, api_version=used_version) for m in markets]
        message = f"Retrieved {len(normalized)} markets"
        if used_version != api_version:
            message += f" (fell back from {api_version} to {used_version})"
        return _success(
            {
                "markets": normalized,
                "count": len(normalized),
                "event_id": event_id,
                "api_version": used_version,
            },
            message,
        )
    except Exception as e:
        return _error(f"Error fetching markets: {str(e)}")


def get_market(request_data):
    """Get one market from an event's markets payload.

    There is no per-market upstream endpoint — this filters the event-markets
    response by market id or market_key.

    Params:
        event_id (int): Event ID (required)
        market_id (str|int): Market id (e.g. 219) or market_key (e.g. '19742:219') (required)
        api_version (str): 'v1' (default) or 'v2'
    """
    try:
        params = request_data.get("params", {})
        event_id = params.get("event_id")
        market_id = params.get("market_id")
        if event_id in (None, ""):
            return _error("event_id is required")
        if market_id in (None, ""):
            return _error("market_id is required")
        try:
            event_id = int(event_id)
        except (TypeError, ValueError):
            return _error(f"event_id must be an integer, got '{event_id}'")

        result = get_markets(
            {
                "params": {
                    "event_id": event_id,
                    "api_version": params.get("api_version", "v1"),
                }
            }
        )
        if not result.get("status"):
            return result

        wanted = str(market_id)
        for market in result["data"]["markets"]:
            if str(market.get("id")) == wanted or market.get("market_key") == wanted:
                return _success(market, f"Retrieved market {wanted} for event {event_id}")
        return _error(f"Market '{wanted}' not found in event {event_id}")
    except Exception as e:
        return _error(f"Error fetching market: {str(e)}")


def search_markets(request_data):
    """Search markets by sport and/or keyword across upcoming events.

    Bounded fan-out: scans up to a handful of tournaments/events per call and
    fetches markets for the soonest matching events only.

    Params:
        query (str): Keyword matched against event name/competitors/tournament
        sport (str): Sport code or alias ('soccer', 'nfl', 'mlb', 'epl', ...)
        status (str): Market status filter — 'open' (default; matches upstream
            'active'/'open'), any raw upstream status value, or 'all' to disable
        limit (int): Max markets returned (default: 50)
        api_version (str): 'v1' (default) or 'v2'
    """
    try:
        params = request_data.get("params", {})
        query = (params.get("query") or "").strip().lower()
        sport = params.get("sport")
        status = params.get("status", "open")
        limit = min(int(params.get("limit", 50)), 200)
        api_version = str(params.get("api_version", "v1")).lower()

        if sport:
            tournaments_result = get_tournaments({"params": {"limit": 200, "sport": sport}})
        else:
            tournaments_result = get_tournaments({"params": {"limit": 200}})
        if not tournaments_result.get("status"):
            return tournaments_result
        tournaments = tournaments_result["data"]["tournaments"]

        if query:

            def tournament_rank(t):
                return 0 if query in t["name"].lower() else 1

            tournaments = sorted(tournaments, key=tournament_rank)
        tournaments = tournaments[:_MAX_TOURNAMENTS_SCANNED]

        candidate_events = []
        first_error = None
        for tournament in tournaments:
            events, err = _fetch_events_paged(tournament["id"], _PAGE_LIMIT)
            if err:
                first_error = first_error or err
                continue
            for event in events:
                normalized = _normalize_event(event, tournament=tournament)
                haystack = " ".join(
                    [
                        normalized["name"],
                        normalized["tournament"],
                        normalized["home"],
                        normalized["away"],
                    ]
                ).lower()
                if query and query not in haystack:
                    continue
                candidate_events.append(normalized)

        if not candidate_events:
            if first_error and not query:
                return first_error
            return _success(
                {"markets": [], "count": 0, "events_scanned": 0},
                "No matching events found",
            )

        candidate_events.sort(key=lambda e: e.get("scheduled") or "9999")
        selected_events = candidate_events[:_MAX_MARKET_EVENTS]

        markets = []
        for event in selected_events:
            event_markets, used_version, err = _fetch_event_markets(event["id"], api_version)
            if err:
                continue
            for market in event_markets:
                market_status = market.get("status")
                if status in ("open", "active"):
                    if market_status not in ("active", "open"):
                        continue
                elif status and status != "all" and market_status != status:
                    continue
                normalized = _normalize_market(market, event_id=event["id"], api_version=used_version)
                normalized["event_name"] = event["name"]
                normalized["event_scheduled"] = event["scheduled"]
                normalized["tournament"] = event["tournament"]
                markets.append(normalized)
                if len(markets) >= limit:
                    break
            if len(markets) >= limit:
                break

        return _success(
            {
                "markets": markets,
                "count": len(markets),
                "events_scanned": len(selected_events),
            },
            f"Retrieved {len(markets)} markets across {len(selected_events)} events",
        )
    except Exception as e:
        return _error(f"Error searching markets: {str(e)}")


def get_todays_events(request_data):
    """Get today's events (UTC) across tournaments, optionally by sport.

    Params:
        sport (str): Sport code or alias ('soccer', 'nfl', 'mlb', 'epl', ...)
        limit (int): Max events (default: 50)
    """
    try:
        params = request_data.get("params", {})
        sport = params.get("sport")
        limit = min(int(params.get("limit", 50)), 200)

        if sport:
            tournaments_result = get_tournaments({"params": {"limit": 200, "sport": sport}})
        else:
            tournaments_result = get_tournaments({"params": {"limit": 200}})
        if not tournaments_result.get("status"):
            return tournaments_result
        tournaments = tournaments_result["data"]["tournaments"][:_MAX_TOURNAMENTS_SCANNED]

        today = datetime.now(timezone.utc).date()
        events_today = []
        first_error = None
        scanned = 0
        for tournament in tournaments:
            events, err = _fetch_events_paged(tournament["id"], _PAGE_LIMIT)
            if err:
                first_error = first_error or err
                continue
            scanned += 1
            for event in events:
                scheduled = _parse_scheduled(event.get("scheduled"))
                if scheduled is None or scheduled.date() != today:
                    continue
                events_today.append(_normalize_event(event, tournament=tournament))

        if not events_today and first_error and scanned == 0:
            return first_error

        events_today.sort(key=lambda e: e.get("scheduled") or "")
        events_today = events_today[:limit]
        return _success(
            {"events": events_today, "count": len(events_today), "date": today.isoformat()},
            f"Retrieved {len(events_today)} events for {today.isoformat()}",
        )
    except Exception as e:
        return _error(f"Error fetching today's events: {str(e)}")


def get_sports_config(request_data):
    """Get available sport codes, aliases, and their live tournaments.

    Sport codes: 'soccer', 'tennis', 'basketball', 'baseball', 'ice-hockey',
    'american-football'. Aliases: 'nfl', 'nba', 'mlb', 'nhl', 'epl', 'mls', etc.

    No params required.
    """
    try:
        tournaments_result = get_tournaments({"params": {"limit": 200}})
        if not tournaments_result.get("status"):
            return tournaments_result

        by_sport = {}
        for tournament in tournaments_result["data"]["tournaments"]:
            sport_id = tournament.get("sport_id")
            code = next((c for c, sid in SPORT_CODES.items() if sid == sport_id), None)
            if code is None:
                code = (tournament.get("sport") or "unknown").lower().replace(" ", "-")
            entry = by_sport.setdefault(
                code,
                {"sport": code, "sport_id": sport_id, "name": tournament.get("sport", ""), "tournaments": []},
            )
            entry["tournaments"].append({"id": tournament["id"], "name": tournament["name"]})

        sports = sorted(by_sport.values(), key=lambda s: s["sport"])
        aliases = {alias: target for alias, target in sorted(SPORT_ALIASES.items())}
        return _success(
            {"sports": sports, "aliases": aliases, "count": len(sports)},
            f"Retrieved {len(sports)} sports",
        )
    except Exception as e:
        return _error(f"Error fetching sports config: {str(e)}")
