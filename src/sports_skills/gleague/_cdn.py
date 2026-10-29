"""NBA G League live box scores and play-by-play from the official G League CDN (cdn-gleague.nba.com).

The payloads have cdn.nba.com's liveData shape, so the pure NBA normalizers are
reused once a payload is checked to describe the requested G League game. One
attempt, the project's standard CDN headers, and no fallback: a refusal (403/429)
is returned as an error, never replaced by ESPN or NBA data.
"""

import json

from sports_skills import _espn_base
from sports_skills._shaping import parse_limit
from sports_skills.gleague._stats import LEAGUE_ID, _game_id
from sports_skills.nba._cdn import _CDN_HEADERS, _normalize_cdn_boxscore, _normalize_cdn_playbyplay
from sports_skills.nba._stats import _guard

_CDN_BASE = "https://cdn-gleague.nba.com/static/json/liveData"
_PLAYER_STAT_FIELDS = {
    "minutes",
    "points",
    "reboundsTotal",
    "assists",
    "steals",
    "blocks",
    "turnovers",
    "fieldGoalsMade",
    "fieldGoalsAttempted",
    "threePointersMade",
    "threePointersAttempted",
    "freeThrowsMade",
    "freeThrowsAttempted",
    "plusMinusPoints",
}


def _box_ok(game):
    sides = [game.get("homeTeam"), game.get("awayTeam")]
    return all(
        isinstance(s, dict)
        and s.get("teamId")
        and "score" in s
        and isinstance(s.get("statistics"), dict)
        and isinstance(s.get("periods"), list)
        and isinstance(s.get("players"), list)
        and all(isinstance(p, dict) for p in s["periods"])
        and all(
            isinstance(p, dict)
            and p.get("personId")
            and isinstance(p.get("statistics"), dict)
            and _PLAYER_STAT_FIELDS.issubset(p["statistics"])
            and all(p["statistics"][key] is not None for key in _PLAYER_STAT_FIELDS)
            for p in s["players"]
        )
        for s in sides
    )


def _pbp_ok(game):
    actions = game.get("actions")
    return isinstance(actions, list) and all(isinstance(a, dict) for a in actions)


def _fetch(kind, game_id, valid):
    """``(payload, None)`` for a payload describing ``game_id``, else ``(None, error dict)``."""
    cache_key = f"gleague_cdn:{kind}:{game_id}"
    cached = _espn_base._cache_get(cache_key)
    if cached is not None:
        return cached, None
    raw, err = _espn_base._http_fetch(
        f"{_CDN_BASE}/{kind}/{kind}_{game_id}.json",
        headers=_CDN_HEADERS,
        max_retries=0,
        decode_gzip=True,
    )
    if err:
        return None, err
    try:
        data = json.loads(raw.decode())
    except ValueError:
        return None, {"error": True, "message": "G League CDN returned invalid JSON"}
    game = data.get("game") if isinstance(data, dict) else None
    if not isinstance(game, dict) or str(game.get("gameId")) != game_id or not valid(game):
        return None, {"error": True, "message": f"G League CDN has no {kind} for game {game_id!r}"}
    _espn_base._cache_set(cache_key, data, ttl=15)
    return data, None


@_guard
def get_live_boxscore(request_data):
    """Box score for one G League game, in the NBA get_live_boxscore shape."""
    game_id = _game_id(request_data.get("params", {}).get("game_id"))
    data, err = _fetch("boxscore", game_id, _box_ok)
    if err:
        return err
    result = _normalize_cdn_boxscore(data)
    # The NBA normalizer reads the CDN's "0"/"1" flags with bool(), so "0" reads as true.
    for team, side in zip(result["teams"], ("homeTeam", "awayTeam")):
        for player, raw in zip(team["players"], data["game"][side]["players"]):
            player["starter"] = raw.get("starter") in ("1", 1)
            if "on_court" in player:
                player["on_court"] = raw.get("oncourt") in ("1", 1)
    return {"provider": "nba-cdn", "league_id": LEAGUE_ID, **result}


@_guard
def get_live_playbyplay(request_data):
    """Play-by-play for one G League game, most recent first, in the NBA get_live_playbyplay shape."""
    params = request_data.get("params", {})
    game_id = _game_id(params.get("game_id"))
    limit = parse_limit(params.get("limit", 25))
    scoring_only = params.get("scoring_only", False)
    if isinstance(scoring_only, str):
        scoring_only = scoring_only.lower() in ("true", "1", "yes")
    data, err = _fetch("playbyplay", game_id, _pbp_ok)
    if err:
        return err
    actions = list(reversed(_normalize_cdn_playbyplay(data)["actions"]))
    if scoring_only:
        actions = [a for a in actions if a.get("scoring_play")]
    actions = actions[:limit]
    return {
        "provider": "nba-cdn",
        "league_id": LEAGUE_ID,
        "game_id": game_id,
        "actions": actions,
        "count": len(actions),
        "order": "most_recent_first",
    }
