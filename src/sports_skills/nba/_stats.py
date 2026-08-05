"""NBA Stats (stats.nba.com) connector — direct HTTP, stdlib only.

Covers the analytics layer ESPN's public endpoints do not provide: league game
logs back to the 1940s, career stats, advanced box scores, shot-chart
coordinates, and play-by-play v3. Same role the nflverse backend plays for NFL,
but consumed directly rather than through a third-party package.

Request shapes replicate the parameter sets stats.nba.com actually requires —
several endpoints reject requests that omit even blank-valued keys.
"""

from __future__ import annotations

import functools
import json
import logging
import re
import unicodedata
import urllib.parse
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sports_skills._espn_base import (
    RateLimiter,
    _cache_get,
    _cache_set,
    _http_fetch,
)
from sports_skills._premium import UPGRADE_MARKER

logger = logging.getLogger("sports_skills.nba._stats")

_STATS_BASE = "https://stats.nba.com/stats"

# stats.nba.com requires browser-shaped headers and refuses generic clients —
# the inverse of ESPN's site.api policy (which rejects browser-shaped strings
# from non-browsers). Each host gets the headers its edge accepts; do not unify
# with the shared ESPN User-Agent. `br` is deliberately absent from
# Accept-Encoding: _http_fetch can only decode gzip with the stdlib.
_STATS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    # The client-hint trio must accompany a Chrome User-Agent — Chrome always
    # sends it, so its absence is treated as a bot signal and the request is
    # silently tarpitted. Keep the version in step with the UA above.
    "Sec-Ch-Ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Fetch-Dest": "empty",
}

# stats.nba.com throttles by client and volume; stay far under its radar.
_stats_rate_limiter = RateLimiter(max_tokens=1, refill_rate=0.5)

# Fail fast: a tarpitted connection would otherwise hold an agent for minutes.
_TIMEOUT = 12

# ESPN and NBA.com disagree on six team abbreviations. Both spellings are
# accepted everywhere a team filter exists; rows carry both systems so results
# can be joined against the ESPN-backed functions in this module.
_ESPN_TO_NBA = {"GS": "GSW", "NO": "NOP", "NY": "NYK", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS"}
_NBA_TO_ESPN = {v: k for k, v in _ESPN_TO_NBA.items()}

_SEASON_TYPES = {
    "regular": "Regular Season",
    "playoffs": "Playoffs",
    "preseason": "Pre Season",
    "playin": "PlayIn",
}

_MEASURE_TYPES = {
    "base": "Base",
    "advanced": "Advanced",
    "four_factors": "Four Factors",
    "misc": "Misc",
    "scoring": "Scoring",
    "opponent": "Opponent",
    "defense": "Defense",
}

_PER_MODES = {"totals": "Totals", "per_game": "PerGame", "per_36": "Per36Minutes"}


class _NbaStatsError(Exception):
    """A request cannot be built or served as asked."""


def _guard(fn):
    """Return connector errors as data instead of raising.

    These functions are called by autonomous agents, so a bad parameter or an
    upstream failure has to arrive as a readable message rather than an
    unhandled traceback.
    """

    @functools.wraps(fn)
    def wrapper(request_data: dict[str, Any]) -> dict[str, Any]:
        try:
            return fn(request_data)
        except _NbaStatsThrottled as exc:
            return {
                "error": True,
                "message": str(exc),
                UPGRADE_MARKER: "rate_limited",
            }
        except _NbaStatsError as exc:
            return {"error": True, "message": str(exc)}
        except Exception as exc:  # noqa: BLE001 — surface, never crash the agent
            logger.debug("nba-stats call failed", exc_info=True)
            return {
                "error": True,
                "message": f"NBA Stats backend error ({type(exc).__name__}): {exc}",
            }

    return wrapper


def _current_season_year() -> int:
    """The season identified by its starting year (Oct-June)."""
    now = datetime.now()
    return now.year if now.month >= 10 else now.year - 1


def _season_str(season: Any) -> str:
    """Coerce a season into stats.nba.com's "2024-25" form.

    Accepts the starting year (2024 or "2024") or the already-formatted string.
    """
    if season is None:
        season = _current_season_year()
    text = str(season).strip()
    if re.fullmatch(r"\d{4}-\d{2}", text):
        return text
    if re.fullmatch(r"\d{4}", text):
        year = int(text)
        return f"{year}-{(year + 1) % 100:02d}"
    raise _NbaStatsError(
        f"Invalid season {season!r}. Pass the starting year (e.g. 2024) or the "
        "NBA form (e.g. '2024-25')."
    )


def _normalize_team(team: Any) -> str | None:
    """Translate a team abbreviation to NBA.com's spelling (accepts ESPN's)."""
    if team is None:
        return None
    value = str(team).strip().upper()
    return _ESPN_TO_NBA.get(value, value)


def _lookup(mapping: Mapping[str, str], value: Any, default: str, what: str) -> str:
    if value is None:
        return mapping[default]
    key = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    if key not in mapping:
        raise _NbaStatsError(f"Invalid {what} {value!r}. Valid values: {', '.join(sorted(mapping))}")
    return mapping[key]


class _NbaStatsThrottled(_NbaStatsError):
    """stats.nba.com is tarpitting this client — a per-IP reputation state."""


def _request(endpoint: str, params: dict[str, Any], ttl: int = 600) -> dict[str, Any]:
    """Fetch one stats.nba.com endpoint. Rate-limited and cached.

    ``max_retries=0`` is deliberate: this host throttles by silently letting
    connections time out once a client's per-IP request volume trips its bot
    heuristics, and retrying a tarpitted request only extends the penalty.
    Long cache TTLs keep the request volume low in the first place.
    """
    query = urllib.parse.urlencode(params)
    url = f"{_STATS_BASE}/{endpoint}?{query}"
    cache_key = f"nbastats:{endpoint}:{query}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    raw, err = _http_fetch(
        url,
        headers=_STATS_HEADERS,
        rate_limiter=_stats_rate_limiter,
        timeout=_TIMEOUT,
        max_retries=0,
        decode_gzip=True,
    )
    if err:
        message = str(err.get("message", ""))
        if "timed out" in message.lower() or "timeout" in message.lower():
            raise _NbaStatsThrottled(
                "stats.nba.com did not answer. It throttles by client and volume "
                "(datacenter IPs and busy callers get silently tarpitted), so wait "
                "a while before retrying — repeated retries extend the penalty. "
                "Recent responses may still be cached; the ESPN-backed and "
                "get_live_* commands in this module are unaffected."
            )
        raise _NbaStatsError(err.get("message", "request failed"))
    try:
        data = json.loads(raw.decode())
    except (json.JSONDecodeError, ValueError) as exc:
        raise _NbaStatsError("stats.nba.com returned invalid JSON") from exc
    _cache_set(cache_key, data, ttl=ttl)
    return data


def _records(data: dict[str, Any], name: str | None = None) -> list[dict[str, Any]]:
    """Turn a classic resultSets payload into records with lowercase keys."""
    sets = data.get("resultSets") or []
    chosen = None
    if name is not None:
        for rs in sets:
            if rs.get("name") == name:
                chosen = rs
                break
    if chosen is None and sets:
        chosen = sets[0]
    if not chosen:
        return []
    headers = [str(h).lower() for h in chosen.get("headers", [])]
    return [dict(zip(headers, row)) for row in chosen.get("rowSet", [])]


def _with_espn_abbreviation(rows: list[dict[str, Any]], key: str = "team_abbreviation") -> None:
    """Annotate rows with the ESPN spelling next to NBA.com's (in place)."""
    for row in rows:
        abbr = row.get(key)
        if abbr:
            row["team_abbreviation_espn"] = _NBA_TO_ESPN.get(str(abbr), str(abbr))


def _team_warnings(team: str | None, raw_team: Any, count: int) -> list[str]:
    """Explain an empty team filter rather than returning a bare empty list."""
    if team is None or count:
        return []
    note = f"team {team!r} matched no rows"
    if str(raw_team).strip().upper() != team:
        note += f" (normalized from {str(raw_team).strip().upper()!r})"
    return [note]


# ============================================================
# Player registry
# ============================================================

# The full player index changes rarely; hold it far longer than game data.
_PLAYERS_TTL = 21600


def _all_players() -> list[dict[str, Any]]:
    data = _request(
        "commonallplayers",
        {"IsOnlyCurrentSeason": 0, "LeagueID": "00", "Season": _season_str(None)},
        ttl=_PLAYERS_TTL,
    )
    return _records(data, "CommonAllPlayers")


def _fold(text: Any) -> str:
    """Lowercase and strip diacritics for name matching.

    The registry stores accented names ("Nikola Jokić", "Luka Dončić"), which
    the ASCII spellings people actually type would never substring-match.
    """
    normalized = unicodedata.normalize("NFKD", str(text))
    return normalized.encode("ascii", "ignore").decode().lower()


def _resolve_player(player_id: Any, player: Any) -> tuple[str, str]:
    """Return ``(person_id, display_name)`` from an id or a name query."""
    if player_id is not None:
        return str(player_id), str(player_id)
    if not player:
        raise _NbaStatsError("Pass player_id or player (a name to search for).")
    needle = _fold(str(player).strip())
    matches = [
        row
        for row in _all_players()
        if needle in _fold(row.get("display_first_last", ""))
    ]
    if not matches:
        raise _NbaStatsError(
            f"No NBA player matched {player!r}. Try find_nba_player to search the registry."
        )
    if len(matches) > 1:
        names = ", ".join(str(m.get("display_first_last")) for m in matches[:6])
        raise _NbaStatsError(
            f"{player!r} matched {len(matches)} players ({names}"
            + (", …" if len(matches) > 6 else "")
            + "). Pass player_id, or a more specific name."
        )
    row = matches[0]
    return str(row.get("person_id")), str(row.get("display_first_last"))


# ============================================================
# Public connector functions
# ============================================================


@_guard
def find_nba_player(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    name = params.get("name")
    if not name:
        raise _NbaStatsError("name is required")
    needle = _fold(str(name).strip())
    matches = []
    for row in _all_players():
        if needle in _fold(row.get("display_first_last", "")):
            matches.append(
                {
                    "player_id": str(row.get("person_id", "")),
                    "name": row.get("display_first_last"),
                    "is_active": row.get("rosterstatus") == 1,
                    "team": row.get("team_abbreviation") or None,
                    "from_year": row.get("from_year"),
                    "to_year": row.get("to_year"),
                }
            )
    return {
        "provider": "nba-stats",
        "query": name,
        "players": matches,
        "count": len(matches),
    }


@_guard
def get_nbastats_game_log(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    season = _season_str(params.get("season"))
    season_type = _lookup(_SEASON_TYPES, params.get("season_type"), "regular", "season_type")
    raw_team = params.get("team")
    team = _normalize_team(raw_team)

    data = _request(
        "leaguegamelog",
        {
            "Counter": 0,
            "DateFrom": "",
            "DateTo": "",
            "Direction": "ASC",
            "LeagueID": "00",
            "PlayerOrTeam": "T",
            "Season": season,
            "SeasonType": season_type,
            "Sorter": "DATE",
        },
    )
    rows = _records(data, "LeagueGameLog")
    if team is not None:
        rows = [r for r in rows if str(r.get("team_abbreviation", "")).upper() == team]
    _with_espn_abbreviation(rows)

    result = {
        "provider": "nba-stats",
        "season": season,
        "season_type": season_type,
        "team": team,
        "games": rows,
        "count": len(rows),
    }
    warnings = _team_warnings(team, raw_team, len(rows))
    if warnings:
        result["warnings"] = warnings
    return result


@_guard
def get_nbastats_player_career(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    per_mode = _lookup(_PER_MODES, params.get("per_mode"), "totals", "per_mode")
    person_id, display = _resolve_player(params.get("player_id"), params.get("player"))

    data = _request(
        "playercareerstats",
        {"LeagueID": "00", "PerMode": per_mode, "PlayerID": person_id},
    )
    seasons = _records(data, "SeasonTotalsRegularSeason")
    _with_espn_abbreviation(seasons)
    career = _records(data, "CareerTotalsRegularSeason")

    return {
        "provider": "nba-stats",
        "player_id": person_id,
        "player": display,
        "per_mode": per_mode,
        "seasons": seasons,
        "career_totals": career[0] if career else None,
        "count": len(seasons),
    }


@_guard
def get_nbastats_team_stats(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    season = _season_str(params.get("season"))
    season_type = _lookup(_SEASON_TYPES, params.get("season_type"), "regular", "season_type")
    measure = _lookup(_MEASURE_TYPES, params.get("measure"), "base", "measure")
    per_mode = _lookup(_PER_MODES, params.get("per_mode"), "totals", "per_mode")
    raw_team = params.get("team")
    team = _normalize_team(raw_team)

    # This endpoint rejects requests missing any of these keys, even blank ones.
    data = _request(
        "leaguedashteamstats",
        {
            "Conference": "",
            "DateFrom": "",
            "DateTo": "",
            "Division": "",
            "GameScope": "",
            "GameSegment": "",
            "LastNGames": 0,
            "LeagueID": "00",
            "Location": "",
            "MeasureType": measure,
            "Month": 0,
            "OpponentTeamID": 0,
            "Outcome": "",
            "PORound": "",
            "PaceAdjust": "N",
            "PerMode": per_mode,
            "Period": 0,
            "PlayerExperience": "",
            "PlayerPosition": "",
            "PlusMinus": "N",
            "Rank": "N",
            "Season": season,
            "SeasonSegment": "",
            "SeasonType": season_type,
            "ShotClockRange": "",
            "StarterBench": "",
            "TeamID": "",
            "TwoWay": "",
            "VsConference": "",
            "VsDivision": "",
        },
    )
    rows = _records(data, "LeagueDashTeamStats")
    # This table names teams rather than abbreviating them; match on either.
    if team is not None:
        wanted_name = None
        for abbr, name in _team_names().items():
            if abbr == team:
                wanted_name = name
                break
        rows = [
            r
            for r in rows
            if str(r.get("team_abbreviation", "")).upper() == team
            or (wanted_name and r.get("team_name") == wanted_name)
        ]
    for row in rows:
        abbr = _name_to_abbr(row.get("team_name"))
        if abbr:
            row.setdefault("team_abbreviation", abbr)
    _with_espn_abbreviation(rows)

    result = {
        "provider": "nba-stats",
        "season": season,
        "season_type": season_type,
        "measure": measure,
        "per_mode": per_mode,
        "team": team,
        "teams": rows,
        "count": len(rows),
    }
    warnings = _team_warnings(team, raw_team, len(rows))
    if warnings:
        result["warnings"] = warnings
    return result


# NBA.com's canonical franchise names by abbreviation — used to filter tables
# that carry names but not abbreviations.
_TEAM_NAMES = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets", "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers",
    "LAC": "LA Clippers", "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat", "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans", "NYK": "New York Knicks", "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings", "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors", "UTA": "Utah Jazz", "WAS": "Washington Wizards",
}


def _team_names() -> dict[str, str]:
    return _TEAM_NAMES


def _name_to_abbr(name: Any) -> str | None:
    for abbr, full in _TEAM_NAMES.items():
        if full == name:
            return abbr
    return None


@_guard
def get_nbastats_shot_chart(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    season = _season_str(params.get("season"))
    season_type = _lookup(_SEASON_TYPES, params.get("season_type"), "regular", "season_type")
    person_id, display = _resolve_player(params.get("player_id"), params.get("player"))
    limit = params.get("limit")

    data = _request(
        "shotchartdetail",
        {
            "AheadBehind": "",
            "ClutchTime": "",
            "ContextFilter": "",
            "ContextMeasure": "FGA",
            "DateFrom": "",
            "DateTo": "",
            "EndPeriod": "",
            "EndRange": "",
            "GameID": "",
            "GameSegment": "",
            "LastNGames": 0,
            "LeagueID": "00",
            "Location": "",
            "Month": 0,
            "OpponentTeamID": 0,
            "Outcome": "",
            "Period": 0,
            "PlayerID": person_id,
            "PlayerPosition": "",
            "PointDiff": "",
            "Position": "",
            "RangeType": "",
            "RookieYear": "",
            "Season": season,
            "SeasonSegment": "",
            "SeasonType": season_type,
            "StartPeriod": "",
            "StartRange": "",
            "TeamID": 0,
            "VsConference": "",
            "VsDivision": "",
        },
    )
    rows = _records(data, "Shot_Chart_Detail")
    total = len(rows)
    if limit is not None:
        rows = rows[: int(limit)]

    shots = [
        {
            "game_id": r.get("game_id"),
            "game_date": r.get("game_date"),
            "period": r.get("period"),
            "minutes_remaining": r.get("minutes_remaining"),
            "seconds_remaining": r.get("seconds_remaining"),
            "action_type": r.get("action_type"),
            "shot_type": r.get("shot_type"),
            "shot_zone": r.get("shot_zone_basic"),
            "shot_area": r.get("shot_zone_area"),
            "shot_distance": r.get("shot_distance"),
            "loc_x": r.get("loc_x"),
            "loc_y": r.get("loc_y"),
            "made": r.get("shot_made_flag") == 1,
        }
        for r in rows
    ]
    result = {
        "provider": "nba-stats",
        "player_id": person_id,
        "player": display,
        "season": season,
        "season_type": season_type,
        "shots": shots,
        "count": len(shots),
    }
    if limit is not None and total > len(shots):
        result["truncated"] = True
        result["warnings"] = [f"results truncated to limit={int(limit)} of {total} shots"]
    return result


@_guard
def get_nbastats_play_by_play(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    game_id = params.get("game_id")
    if not game_id:
        raise _NbaStatsError(
            "game_id is required — the 10-digit NBA game id from get_nbastats_game_log "
            "(e.g. '0022400061'), not an ESPN event id."
        )
    limit = params.get("limit")

    data = _request(
        "playbyplayv3",
        {"EndPeriod": 0, "GameID": str(game_id), "StartPeriod": 0},
    )
    actions = (data.get("game") or {}).get("actions") or []
    total = len(actions)
    if limit is not None:
        actions = actions[: int(limit)]

    plays = [
        {
            "action_number": a.get("actionNumber"),
            "period": a.get("period"),
            "clock": a.get("clock"),
            "team": a.get("teamTricode") or None,
            "player": a.get("playerNameI") or None,
            "action_type": a.get("actionType"),
            "sub_type": a.get("subType") or None,
            "description": a.get("description"),
            "score_home": a.get("scoreHome"),
            "score_away": a.get("scoreAway"),
            "shot_value": a.get("shotValue") or None,
            "loc_x": a.get("xLegacy"),
            "loc_y": a.get("yLegacy"),
        }
        for a in actions
    ]
    result = {
        "provider": "nba-stats",
        "game_id": str(game_id),
        "plays": plays,
        "count": len(plays),
    }
    if limit is not None and total > len(plays):
        result["truncated"] = True
        result["warnings"] = [f"results truncated to limit={int(limit)} of {total} actions"]
    return result


def _normalize_box_team(side: dict[str, Any]) -> dict[str, Any]:
    abbr = side.get("teamTricode", "")
    players = [
        {
            "player_id": str(p.get("personId", "")),
            "name": f"{p.get('firstName', '')} {p.get('familyName', '')}".strip(),
            "position": p.get("position") or None,
            "minutes": p.get("minutes"),
            "stats": p.get("statistics") or {},
        }
        for p in side.get("players") or []
    ]
    return {
        "team_id": str(side.get("teamId", "")),
        "team": abbr,
        "team_abbreviation_espn": _NBA_TO_ESPN.get(abbr, abbr),
        "team_name": f"{side.get('teamCity', '')} {side.get('teamName', '')}".strip(),
        "stats": side.get("statistics") or {},
        "players": players,
    }


@_guard
def get_nbastats_advanced_boxscore(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    game_id = params.get("game_id")
    if not game_id:
        raise _NbaStatsError(
            "game_id is required — the 10-digit NBA game id from get_nbastats_game_log "
            "(e.g. '0022400061'), not an ESPN event id."
        )

    data = _request(
        "boxscoreadvancedv3",
        {
            "EndPeriod": 0,
            "EndRange": 0,
            "GameID": str(game_id),
            "RangeType": 0,
            "StartPeriod": 0,
            "StartRange": 0,
        },
    )
    box = data.get("boxScoreAdvanced") or {}
    if not box:
        raise _NbaStatsError(f"No advanced box score for game_id {game_id!r}")

    return {
        "provider": "nba-stats",
        "game_id": str(box.get("gameId", game_id)),
        "home": _normalize_box_team(box.get("homeTeam") or {}),
        "away": _normalize_box_team(box.get("awayTeam") or {}),
    }
