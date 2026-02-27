"""NBA CDN connector — real-time live data from cdn.nba.com.

Provides live scoreboard, box scores, and play-by-play directly from
the NBA's CDN. No API keys required. Preferred over ESPN for live
in-game data due to faster update frequency.
"""

import json
import logging

from sports_skills._espn_base import (
    _USER_AGENT,
    _cache_get,
    _cache_set,
    _http_fetch,
)

logger = logging.getLogger("sports_skills.nba.cdn")

_CDN_BASE = "https://cdn.nba.com/static/json/liveData"

_CDN_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
}

_NBA_STATUS_MAP = {
    1: "not_started",
    2: "live",
    3: "closed",
}


# ============================================================
# CDN HTTP Helper
# ============================================================


def _cdn_fetch(path, cache_key, ttl=30):
    """Fetch JSON from the NBA CDN with caching.

    Args:
        path: Path after the CDN base URL.
        cache_key: Cache key for this request.
        ttl: Cache TTL in seconds (short for live data).

    Returns:
        Parsed JSON dict on success, or error dict on failure.
    """
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    url = f"{_CDN_BASE}/{path}"
    raw, err = _http_fetch(url, headers=_CDN_HEADERS, decode_gzip=True)
    if err:
        return err

    try:
        data = json.loads(raw.decode())
        _cache_set(cache_key, data, ttl=ttl)
        return data
    except (json.JSONDecodeError, ValueError):
        return {"error": True, "message": "NBA CDN returned invalid JSON"}


# ============================================================
# Normalizers
# ============================================================


def _normalize_cdn_game(game):
    """Normalize a single game from the CDN scoreboard."""
    home = game.get("homeTeam", {})
    away = game.get("awayTeam", {})
    status_code = game.get("gameStatus", 1)

    competitors = []
    for team_data, home_away in [(home, "home"), (away, "away")]:
        periods = []
        for p in team_data.get("periods", []):
            periods.append(int(p.get("score", 0)))
        competitors.append({
            "team": {
                "id": str(team_data.get("teamId", "")),
                "name": f"{team_data.get('teamCity', '')} {team_data.get('teamName', '')}".strip(),
                "abbreviation": team_data.get("teamTricode", ""),
            },
            "home_away": home_away,
            "score": str(team_data.get("score", 0)),
            "period_scores": periods,
            "record": f"{team_data.get('wins', 0)}-{team_data.get('losses', 0)}",
            "winner": (
                status_code == 3
                and int(team_data.get("score", 0)) > int(
                    (away if home_away == "home" else home).get("score", 0)
                )
            ),
        })

    # Game leaders
    leaders = {}
    gl = game.get("gameLeaders", {})
    for side in ("homeLeaders", "awayLeaders"):
        leader = gl.get(side, {})
        if leader.get("name"):
            leaders[side.replace("Leaders", "")] = {
                "id": str(leader.get("personId", "")),
                "name": leader.get("name", ""),
                "jersey": leader.get("jerseyNum", ""),
                "position": leader.get("position", ""),
                "points": leader.get("points", 0),
                "rebounds": leader.get("rebounds", 0),
                "assists": leader.get("assists", 0),
            }

    result = {
        "id": game.get("gameId", ""),
        "game_code": game.get("gameCode", ""),
        "status": _NBA_STATUS_MAP.get(status_code, str(status_code)),
        "status_text": game.get("gameStatusText", ""),
        "period": game.get("period", 0),
        "game_clock": game.get("gameClock", ""),
        "game_time_utc": game.get("gameTimeUTC", ""),
        "competitors": competitors,
    }
    if leaders:
        result["leaders"] = leaders

    return result


def _parse_minutes(iso_duration):
    """Convert ISO 8601 duration (e.g. PT32M15.00S) to MM:SS string."""
    if not iso_duration or not isinstance(iso_duration, str):
        return ""
    # Strip PT prefix
    s = iso_duration
    if s.startswith("PT"):
        s = s[2:]
    minutes = 0
    seconds = 0
    if "M" in s:
        parts = s.split("M")
        try:
            minutes = int(parts[0])
        except ValueError:
            pass
        s = parts[1] if len(parts) > 1 else ""
    if s.endswith("S"):
        s = s[:-1]
    if s:
        try:
            seconds = int(float(s))
        except ValueError:
            pass
    return f"{minutes}:{seconds:02d}"


def _normalize_cdn_boxscore(data):
    """Normalize a CDN box score response."""
    game = data.get("game", {})
    if not game:
        return {"error": True, "message": "No game data in box score response"}

    status_code = game.get("gameStatus", 1)

    game_info = {
        "id": game.get("gameId", ""),
        "game_code": game.get("gameCode", ""),
        "status": _NBA_STATUS_MAP.get(status_code, str(status_code)),
        "status_text": game.get("gameStatusText", ""),
        "period": game.get("period", 0),
        "game_clock": game.get("gameClock", ""),
        "game_time_utc": game.get("gameTimeUTC", ""),
    }

    teams = []
    for side in ("homeTeam", "awayTeam"):
        team_data = game.get(side, {})
        home_away = "home" if side == "homeTeam" else "away"

        # Team-level stats
        team_stats = {}
        raw_stats = team_data.get("statistics", {})
        for key, val in raw_stats.items():
            team_stats[key] = val

        # Player stats
        players = []
        for p in team_data.get("players", []):
            stats = p.get("statistics", {})
            player = {
                "id": str(p.get("personId", "")),
                "name": p.get("name", ""),
                "name_short": p.get("nameI", ""),
                "jersey": p.get("jerseyNum", ""),
                "position": p.get("position", ""),
                "starter": bool(p.get("starter", "")),
                "minutes": _parse_minutes(stats.get("minutes", "")),
                "points": stats.get("points", 0),
                "rebounds": stats.get("reboundsTotal", 0),
                "assists": stats.get("assists", 0),
                "steals": stats.get("steals", 0),
                "blocks": stats.get("blocks", 0),
                "turnovers": stats.get("turnovers", 0),
                "field_goals": f"{stats.get('fieldGoalsMade', 0)}-{stats.get('fieldGoalsAttempted', 0)}",
                "three_pointers": f"{stats.get('threePointersMade', 0)}-{stats.get('threePointersAttempted', 0)}",
                "free_throws": f"{stats.get('freeThrowsMade', 0)}-{stats.get('freeThrowsAttempted', 0)}",
                "plus_minus": stats.get("plusMinusPoints", 0),
            }
            # Only include on-court status if available
            on_court = p.get("oncourt")
            if on_court is not None:
                player["on_court"] = bool(on_court)
            players.append(player)

        periods = []
        for period in team_data.get("periods", []):
            periods.append(int(period.get("score", 0)))

        teams.append({
            "team": {
                "id": str(team_data.get("teamId", "")),
                "name": f"{team_data.get('teamCity', '')} {team_data.get('teamName', '')}".strip(),
                "abbreviation": team_data.get("teamTricode", ""),
            },
            "home_away": home_away,
            "score": str(team_data.get("score", 0)),
            "period_scores": periods,
            "statistics": team_stats,
            "players": players,
        })

    return {
        "game_info": game_info,
        "teams": teams,
    }


def _normalize_cdn_playbyplay(data):
    """Normalize a CDN play-by-play response."""
    game = data.get("game", {})
    if not game:
        return {"error": True, "message": "No game data in play-by-play response"}

    actions = []
    for a in game.get("actions", []):
        action = {
            "action_number": a.get("actionNumber", 0),
            "period": a.get("period", 0),
            "clock": a.get("clock", ""),
            "action_type": a.get("actionType", ""),
            "sub_type": a.get("subType", ""),
            "description": a.get("description", ""),
            "team_id": str(a.get("teamId", "")) if a.get("teamId") else "",
            "team_tricode": a.get("teamTricode", ""),
            "person_id": str(a.get("personId", "")) if a.get("personId") else "",
            "player_name": a.get("playerNameI", ""),
            "score_home": a.get("scoreHome", ""),
            "score_away": a.get("scoreAway", ""),
            "is_field_goal": bool(a.get("isFieldGoal", 0)),
            "scoring_play": bool(a.get("pointsTotal", 0)),
        }
        if a.get("shotResult"):
            action["shot_result"] = a["shotResult"]
        if a.get("pointsTotal"):
            action["points"] = a["pointsTotal"]
        if a.get("shotDistance") is not None:
            action["shot_distance"] = a["shotDistance"]
        actions.append(action)

    return {
        "game_id": game.get("gameId", ""),
        "actions": actions,
        "count": len(actions),
    }


# ============================================================
# Command Functions
# ============================================================


def get_live_scoreboard(request_data=None):
    """Get real-time NBA scoreboard from cdn.nba.com."""
    data = _cdn_fetch(
        "scoreboard/todaysScoreboard_00.json",
        cache_key="nba_cdn:scoreboard",
        ttl=30,
    )
    if data.get("error"):
        return data

    scoreboard = data.get("scoreboard", {})
    games = [_normalize_cdn_game(g) for g in scoreboard.get("games", [])]

    return {
        "games": games,
        "game_date": scoreboard.get("gameDate", ""),
        "count": len(games),
    }


def get_live_boxscore(request_data):
    """Get real-time NBA box score from cdn.nba.com."""
    params = request_data.get("params", {})
    game_id = params.get("game_id")
    if not game_id:
        return {"error": True, "message": "game_id is required"}

    data = _cdn_fetch(
        f"boxscore/boxscore_{game_id}.json",
        cache_key=f"nba_cdn:boxscore:{game_id}",
        ttl=15,
    )
    if data.get("error"):
        return data

    return _normalize_cdn_boxscore(data)


def get_live_playbyplay(request_data):
    """Get real-time NBA play-by-play from cdn.nba.com."""
    params = request_data.get("params", {})
    game_id = params.get("game_id")
    if not game_id:
        return {"error": True, "message": "game_id is required"}

    data = _cdn_fetch(
        f"playbyplay/playbyplay_{game_id}.json",
        cache_key=f"nba_cdn:playbyplay:{game_id}",
        ttl=15,
    )
    if data.get("error"):
        return data

    return _normalize_cdn_playbyplay(data)
