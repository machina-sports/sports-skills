"""TheSportsDB metadata connector — team logos, player photos, and search.

Wraps the TheSportsDB free API (key=3) for metadata enrichment.
Uses stdlib only (urllib, json, threading). No API key purchase required.
"""

import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("sports_skills.metadata")

# ============================================================
# Configuration
# ============================================================

BASE_URL = "https://www.thesportsdb.com/api/v1/json/3"
_USER_AGENT = "sports-skills/1.0"

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


class _RateLimiter:
    def __init__(self, max_tokens=5, refill_rate=5.0):
        self.max_tokens = max_tokens
        self.tokens = max_tokens
        self.refill_rate = refill_rate
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self, timeout=10.0):
        deadline = time.monotonic() + timeout
        while True:
            with self.lock:
                now = time.monotonic()
                elapsed = now - self.last_refill
                self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
                self.last_refill = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.1)


_limiter = _RateLimiter()

# ============================================================
# HTTP Fetching
# ============================================================


def _http_fetch(url, retries=2):
    """Fetch JSON from a URL with retry logic."""
    _limiter.acquire()

    cached = _cache_get(url)
    if cached is not None:
        return cached

    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                _cache_set(url, data)
                return data
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                last_err = e
                time.sleep(min(2 ** attempt, 4))
                continue
            return {"error": True, "message": f"HTTP {e.code}: {e.reason}"}
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(min(2 ** attempt, 4))
                continue

    return {"error": True, "message": f"Request failed after {retries + 1} attempts: {last_err}"}


# ============================================================
# API Functions
# ============================================================


def search_teams(request_data):
    """Search teams by name.

    Params:
        query: Team name or partial name to search for.
    """
    params = request_data.get("params", {})
    query = params.get("query", "")
    if not query:
        return {"error": True, "message": "query parameter is required"}

    url = f"{BASE_URL}/searchteams.php?t={urllib.parse.quote(query)}"
    data = _http_fetch(url)
    if data.get("error"):
        return data

    teams_raw = data.get("teams") or []
    teams = []
    for t in teams_raw:
        teams.append({
            "team_id": t.get("idTeam"),
            "name": t.get("strTeam"),
            "short_name": t.get("strTeamShort"),
            "sport": t.get("strSport"),
            "league": t.get("strLeague"),
            "country": t.get("strCountry"),
            "stadium": t.get("strStadium"),
            "logo": t.get("strBadge"),
            "banner": t.get("strBanner"),
        })
    return {"teams": teams, "count": len(teams)}


def search_players(request_data):
    """Search players by name.

    Params:
        query: Player name or partial name to search for.
    """
    params = request_data.get("params", {})
    query = params.get("query", "")
    if not query:
        return {"error": True, "message": "query parameter is required"}

    url = f"{BASE_URL}/searchplayers.php?p={urllib.parse.quote(query)}"
    data = _http_fetch(url)
    if data.get("error"):
        return data

    players_raw = data.get("player") or []
    players = []
    for p in players_raw:
        players.append({
            "player_id": p.get("idPlayer"),
            "name": p.get("strPlayer"),
            "team": p.get("strTeam"),
            "sport": p.get("strSport"),
            "nationality": p.get("strNationality"),
            "position": p.get("strPosition"),
            "photo": p.get("strThumb"),
            "cutout": p.get("strCutout"),
        })
    return {"players": players, "count": len(players)}


def get_team_logo(request_data):
    """Get team logo URL by team name.

    Params:
        team_name: Name of the team to look up.
        sport: Sport to filter by (default: Soccer).
    """
    params = request_data.get("params", {})
    team_name = params.get("team_name", "")
    sport = params.get("sport", "Soccer")
    if not team_name:
        return {"error": True, "message": "team_name parameter is required"}

    url = f"{BASE_URL}/searchteams.php?t={urllib.parse.quote(team_name)}"
    data = _http_fetch(url)
    if data.get("error"):
        return data

    teams = data.get("teams") or []
    for t in teams:
        if sport and t.get("strSport", "").lower() != sport.lower():
            continue
        return {
            "team_id": t.get("idTeam"),
            "team_name": t.get("strTeam"),
            "sport": t.get("strSport"),
            "logo_url": t.get("strBadge"),
        }

    # Fallback: return first result regardless of sport filter
    if teams:
        t = teams[0]
        return {
            "team_id": t.get("idTeam"),
            "team_name": t.get("strTeam"),
            "sport": t.get("strSport"),
            "logo_url": t.get("strBadge"),
        }

    return {"error": True, "message": f"No team found for '{team_name}'"}


def get_team_info(request_data):
    """Get detailed team information.

    Params:
        team_name: Name of the team to look up.
    """
    params = request_data.get("params", {})
    team_name = params.get("team_name", "")
    if not team_name:
        return {"error": True, "message": "team_name parameter is required"}

    url = f"{BASE_URL}/searchteams.php?t={urllib.parse.quote(team_name)}"
    data = _http_fetch(url)
    if data.get("error"):
        return data

    teams = data.get("teams") or []
    if not teams:
        return {"error": True, "message": f"No team found for '{team_name}'"}

    t = teams[0]
    return {
        "team_id": t.get("idTeam"),
        "name": t.get("strTeam"),
        "short_name": t.get("strTeamShort"),
        "sport": t.get("strSport"),
        "league": t.get("strLeague"),
        "country": t.get("strCountry"),
        "stadium": t.get("strStadium"),
        "capacity": t.get("intStadiumCapacity"),
        "description": t.get("strDescriptionEN"),
        "logo": t.get("strBadge"),
        "banner": t.get("strBanner"),
        "jersey": t.get("strEquipment"),
        "website": t.get("strWebsite"),
        "year_formed": t.get("intFormedYear"),
    }


def get_player_photo(request_data):
    """Get player photo URL by player name.

    Params:
        player_name: Name of the player to look up.
    """
    params = request_data.get("params", {})
    player_name = params.get("player_name", "")
    if not player_name:
        return {"error": True, "message": "player_name parameter is required"}

    url = f"{BASE_URL}/searchplayers.php?p={urllib.parse.quote(player_name)}"
    data = _http_fetch(url)
    if data.get("error"):
        return data

    players = data.get("player") or []
    if not players:
        return {"error": True, "message": f"No player found for '{player_name}'"}

    p = players[0]
    return {
        "player_id": p.get("idPlayer"),
        "player_name": p.get("strPlayer"),
        "team": p.get("strTeam"),
        "sport": p.get("strSport"),
        "photo_url": p.get("strThumb"),
        "cutout_url": p.get("strCutout"),
    }
