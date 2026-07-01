"""Esports data — Dota 2 (OpenDota) + League of Legends esports (Leaguepedia).

Public, keyless sources. Stdlib only (urllib, json, threading).

  OpenDota    https://api.opendota.com/api  — Dota 2 pro matches, leagues, teams.
              Keyless. Free tier ~60 req/min, 50k calls/month per IP.
  Leaguepedia https://lol.fandom.com/api.php (Cargo) — structured LoL esports data.
              Keyless, CC-BY-SA (attribute Leaguepedia). Aggressively rate-limited:
              the throttle arrives INSIDE an HTTP-200 body as
              {"error":{"code":"ratelimited"}} — we detect it and cache hard.

No keyless bookmaker odds exist for esports. For implied-probability signals use
the `kalshi` (get_esports_odds) and `polymarket` (get_esports_events) skills.
"""

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

OPENDOTA_BASE = "https://api.opendota.com/api"
LEAGUEPEDIA_URL = "https://lol.fandom.com/api.php"

# Leaguepedia/Fandom require a descriptive, contact-bearing User-Agent.
_USER_AGENT = "sports-skills/0.1 (+https://sports-skills.sh; +https://machina.gg)"


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
            for k in [k for k, (_, exp) in _cache.items() if now > exp]:
                del _cache[k]
        _cache[key] = (value, time.monotonic() + ttl)


# ============================================================
# Rate Limiters (Token Bucket)
# ============================================================


class _RateLimiter:
    def __init__(self, max_tokens, refill_rate):
        self.max_tokens = max_tokens
        self.tokens = max_tokens
        self.refill_rate = refill_rate
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self):
        with self.lock:
            now = time.monotonic()
            self.tokens = min(
                self.max_tokens,
                self.tokens + (now - self.last_refill) * self.refill_rate,
            )
            self.last_refill = now
            if self.tokens >= 1:
                self.tokens -= 1
                return
        time.sleep(max(0, (1 - self.tokens) / self.refill_rate))
        self.acquire()


# OpenDota free tier ~60/min. Leaguepedia throttles hard — stay well under 1 req/2s.
_opendota_rl = _RateLimiter(max_tokens=2, refill_rate=1.0)
_leaguepedia_rl = _RateLimiter(max_tokens=1, refill_rate=0.4)


# ============================================================
# Response Helpers
# ============================================================


def _success(data, message=""):
    return {"status": True, "data": data, "message": message}


def _error(message, data=None):
    return {"status": False, "data": data, "message": message}


def _safe_float(value, default=None):
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


# ============================================================
# HTTP Helpers
# ============================================================


def _http_get_json(url, rate_limiter, ttl):
    cached = _cache_get(url)
    if cached is not None:
        return cached
    rate_limiter.acquire()
    req = urllib.request.Request(url)
    req.add_header("User-Agent", _USER_AGENT)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            _cache_set(url, data, ttl=ttl)
            return data
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"error": True, "status_code": e.code, "message": body}
    except Exception as e:
        return {"error": True, "message": str(e)}


def _opendota_get(path, params=None, ttl=300):
    url = f"{OPENDOTA_BASE}{path}"
    if params:
        clean = {k: v for k, v in params.items() if v is not None and v != ""}
        if clean:
            url += "?" + urllib.parse.urlencode(clean, doseq=True)
    return _http_get_json(url, _opendota_rl, ttl)


def _leaguepedia_get(params, ttl=1800):
    query = {"action": "cargoquery", "format": "json", **params}
    url = f"{LEAGUEPEDIA_URL}?" + urllib.parse.urlencode(query, doseq=True)
    return _http_get_json(url, _leaguepedia_rl, ttl)


def _http_error(response):
    if isinstance(response, dict) and response.get("error") is True:
        code = response.get("status_code", "?")
        return _error(f"HTTP error ({code}): {str(response.get('message', ''))[:200]}")
    return None


# ============================================================
# OpenDota (Dota 2)
# ============================================================


def _normalize_pro_match(m):
    return {
        "match_id": m.get("match_id"),
        "start_time": m.get("start_time"),
        "duration_seconds": m.get("duration"),
        "league_id": m.get("leagueid"),
        "league_name": m.get("league_name", ""),
        "series_id": m.get("series_id"),
        "radiant": {
            "team_id": m.get("radiant_team_id"),
            "name": m.get("radiant_name", ""),
            "score": m.get("radiant_score"),
        },
        "dire": {
            "team_id": m.get("dire_team_id"),
            "name": m.get("dire_name", ""),
            "score": m.get("dire_score"),
        },
        "radiant_win": m.get("radiant_win"),
    }


def get_pro_matches(request_data):
    """Recent professional Dota 2 matches (OpenDota).

    Params:
        limit (int): Max matches (default 20, max 100).
    """
    try:
        params = request_data.get("params", {})
        limit = min(int(params.get("limit", 20)), 100)
        resp = _opendota_get("/proMatches", ttl=180)
        err = _http_error(resp)
        if err:
            return err
        matches = resp if isinstance(resp, list) else []
        normalized = [_normalize_pro_match(m) for m in matches[:limit]]
        return _success(
            {"matches": normalized, "count": len(normalized)},
            f"Retrieved {len(normalized)} pro matches",
        )
    except Exception as e:
        return _error(f"Error fetching pro matches: {e}")


def get_leagues(request_data):
    """Dota 2 leagues / tournaments (OpenDota).

    Params:
        tier (str): Filter by tier ('premium', 'professional', 'excluded').
        limit (int): Max leagues (default 50, max 200).
    """
    try:
        params = request_data.get("params", {})
        tier = str(params.get("tier") or "").lower()
        limit = min(int(params.get("limit", 50)), 200)
        resp = _opendota_get("/leagues", ttl=3600)
        err = _http_error(resp)
        if err:
            return err
        leagues = resp if isinstance(resp, list) else []
        if tier:
            leagues = [x for x in leagues if str(x.get("tier", "")).lower() == tier]
        normalized = [
            {
                "league_id": x.get("leagueid"),
                "name": x.get("name", ""),
                "tier": x.get("tier", ""),
            }
            for x in leagues[:limit]
        ]
        return _success(
            {"leagues": normalized, "count": len(normalized)},
            f"Retrieved {len(normalized)} leagues",
        )
    except Exception as e:
        return _error(f"Error fetching leagues: {e}")


def get_pro_teams(request_data):
    """Top professional Dota 2 teams by rating (OpenDota).

    Params:
        limit (int): Max teams (default 25, max 100).
    """
    try:
        params = request_data.get("params", {})
        limit = min(int(params.get("limit", 25)), 100)
        resp = _opendota_get("/teams", ttl=3600)
        err = _http_error(resp)
        if err:
            return err
        teams = resp if isinstance(resp, list) else []
        normalized = [
            {
                "team_id": t.get("team_id"),
                "name": t.get("name", ""),
                "tag": t.get("tag", ""),
                "rating": _safe_float(t.get("rating")),
                "wins": t.get("wins"),
                "losses": t.get("losses"),
                "last_match_time": t.get("last_match_time"),
                "logo_url": t.get("logo_url", ""),
            }
            for t in teams[:limit]
        ]
        return _success(
            {"teams": normalized, "count": len(normalized)},
            f"Retrieved {len(normalized)} teams",
        )
    except Exception as e:
        return _error(f"Error fetching teams: {e}")


def get_match(request_data):
    """Detailed Dota 2 match by id (OpenDota).

    Params:
        match_id (str): Match ID (required).
    """
    try:
        params = request_data.get("params", {})
        match_id = str(params.get("match_id") or "").strip()
        if not match_id:
            return _error("match_id is required")
        resp = _opendota_get(f"/matches/{match_id}", ttl=86400)
        err = _http_error(resp)
        if err:
            return err
        if not isinstance(resp, dict) or resp.get("match_id") is None:
            return _error(f"Match not found: {match_id}")
        players = [
            {
                "account_id": p.get("account_id"),
                "name": p.get("name") or p.get("personaname", ""),
                "hero_id": p.get("hero_id"),
                "kills": p.get("kills"),
                "deaths": p.get("deaths"),
                "assists": p.get("assists"),
                "is_radiant": (p.get("player_slot") or 0) < 128,
            }
            for p in resp.get("players", [])
        ]
        data = {
            "match_id": resp.get("match_id"),
            "duration_seconds": resp.get("duration"),
            "start_time": resp.get("start_time"),
            "league_id": resp.get("leagueid"),
            "radiant_win": resp.get("radiant_win"),
            "radiant_score": resp.get("radiant_score"),
            "dire_score": resp.get("dire_score"),
            "players": players,
        }
        return _success(data, f"Retrieved match {match_id}")
    except Exception as e:
        return _error(f"Error fetching match: {e}")


# ============================================================
# Leaguepedia (LoL esports, Cargo)
# ============================================================


def _cargo_rows(resp):
    """Envelope is {"cargoquery":[{"title":{...}}]}; drop __precision helper keys."""
    rows = []
    for item in resp.get("cargoquery", []):
        title = item.get("title", {})
        rows.append({k: v for k, v in title.items() if not k.endswith("__precision")})
    return rows


def lol_cargo_query(request_data):
    """Raw Leaguepedia Cargo query for structured LoL esports data.

    Returns rows (list of dicts) exactly as Cargo returns them. You must know the
    table + field names — see references for common tables (Tournaments,
    MatchSchedule, ScoreboardGames, Players, Teams).

    Params:
        tables (str): Cargo table(s) (required, e.g. 'Tournaments').
        fields (str): Comma-separated fields (required, e.g. 'Name,DateStart,Region').
        where (str): SQL-like filter (optional).
        order_by (str): Sort clause (optional, e.g. 'DateStart DESC').
        group_by (str): Group clause (optional).
        limit (int): Max rows (default 20, max 100).
    """
    try:
        params = request_data.get("params", {})
        tables = str(params.get("tables") or "").strip()
        fields = str(params.get("fields") or "").strip()
        if not tables or not fields:
            return _error("Both 'tables' and 'fields' are required")
        query = {
            "tables": tables,
            "fields": fields,
            "limit": min(int(params.get("limit", 20)), 100),
        }
        for opt in ("where", "order_by", "group_by"):
            if params.get(opt):
                query[opt] = params[opt]
        resp = _leaguepedia_get(query)
        err = _http_error(resp)
        if err:
            return err
        # Leaguepedia returns throttling / bad-field as an in-body error on HTTP 200.
        if isinstance(resp, dict) and resp.get("error"):
            return _error(f"Leaguepedia API error: {resp['error'].get('info', 'Cargo error')}")
        rows = _cargo_rows(resp)
        return _success({"rows": rows, "count": len(rows)}, f"Retrieved {len(rows)} rows")
    except Exception as e:
        return _error(f"Error querying Leaguepedia: {e}")


def get_lol_tournaments(request_data):
    """Recent LoL esports tournaments (Leaguepedia Cargo 'Tournaments' table).

    Returns Name, DateStart, Region. For richer fields (League, Prizepool,
    DateEnd, ...) query lol_cargo_query directly — see the skill references.

    Params:
        region (str): Filter by region (e.g. 'Korea', 'Brazil', 'Europe').
        limit (int): Max tournaments (default 20, max 100).
    """
    try:
        params = request_data.get("params", {})
        # Only live-verified fields (Name/DateStart/Region, 2026-07-01). Other
        # Tournaments columns are reachable via lol_cargo_query once confirmed.
        where = None
        if params.get("region"):
            where = f"Tournaments.Region='{params['region']}'"
        return lol_cargo_query(
            {
                "params": {
                    "tables": "Tournaments",
                    "fields": "Name,DateStart,Region",
                    "where": where,
                    "order_by": "DateStart DESC",
                    "limit": params.get("limit", 20),
                }
            }
        )
    except Exception as e:
        return _error(f"Error fetching LoL tournaments: {e}")
