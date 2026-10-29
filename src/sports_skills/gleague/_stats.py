"""NBA G League via NBA Stats (stats.nba.com) with ``LeagueID=20``.

Reuses the NBA Stats transport (headers, rate limiter, cache, no retries), error
guard and lookups from ``sports_skills.nba._stats``. The NBA public functions are
not called: they send ``LeagueID=00``. Unlike the NBA reader, a missing result set,
a payload naming another league, or a row from another league's game is an error,
never a silent fallback; a well-formed table with no rows is an empty success.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from sports_skills._shaping import parse_limit, shape_rows
from sports_skills.nba._stats import (
    _GAME_LOG_IDENTITY,
    _MEASURE_TYPES,
    _PER_MODES,
    _PLAYER_GAME_LOG_IDENTITY,
    _PLAYER_OR_TEAM,
    _SHOT_IDENTITY,
    _TEAM_STATS_IDENTITY,
    _current_season_year,
    _fold,
    _guard,
    _iso_date,
    _lookup,
    _matchup_sides,
    _NbaStatsError,
    _normalize_box_team,
    _request,
    _team_warnings,
)

LEAGUE_ID = "20"

# The player index changes rarely; hold it far longer than game data.
_PLAYERS_TTL = 21600

_GAME_ID = re.compile(r"20[0-9]{8}")

_SEASON_TYPES = {"regular": "Regular Season", "playoffs": "Playoffs", "preseason": "Pre Season", "showcase": "Showcase"}

# The NBA's aliases minus the play-in (type 5), which the G League does not have.
_SEASON_TYPE_ALIASES = {
    "regular_season": "regular",
    "reg": "regular",
    "2": "regular",
    "playoff": "playoffs",
    "postseason": "playoffs",
    "post_season": "playoffs",
    "4": "playoffs",
    "pre_season": "preseason",
    "1": "preseason",
}

# The verified upstream enum is "Showcase", not "Showcase Cup".
_SHOWCASE = {"showcase", "showcase_cup", "tournament", "tip_off_tournament"}

_STAT_CATEGORIES = (
    "PTS", "REB", "AST", "STL", "BLK", "TOV", "EFF", "MIN", "OREB", "DREB",
    "FGM", "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT",
)  # fmt: skip

_LEADER_IDENTITY = ("player_id", "rank", "player", "team")


def _season_str(season: Any) -> str:
    """Starting year (2025, "2025") or "2025-26" -> "2025-26"; anything else is an error."""
    if season is None:
        season = _current_season_year()
    text = str(season).strip() if isinstance(season, (int, str)) and not isinstance(season, bool) else ""
    match = re.fullmatch(r"([0-9]{4})(?:-([0-9]{2}))?", text)
    if match:
        year = int(match.group(1))
        end = f"{(year + 1) % 100:02d}"
        if match.group(2) in (None, end):
            return f"{year}-{end}"
    raise _NbaStatsError(
        f"Invalid season {season!r}. Pass the starting year (2025 for 2025-26; the ESPN-backed "
        "commands use the ending year) or the 'YYYY-YY' form (e.g. '2025-26')."
    )


def _season_type(value: Any) -> str:
    if value is not None:
        key = str(value).strip().lower().replace(" ", "_").replace("-", "_")
        if key in _SHOWCASE:
            return "Showcase"
        value = _SEASON_TYPE_ALIASES.get(key, value)
    return _lookup(_SEASON_TYPES, value, "regular", "season_type")


def _game_id(value: Any) -> str:
    """The 10-digit official G League game id ("20..."); refused before any request otherwise."""
    text = value if isinstance(value, str) else str(value) if type(value) is int else ""
    if not (text.isascii() and _GAME_ID.fullmatch(text)):
        raise _NbaStatsError(
            f"Invalid G League game id {value!r}. Expected the 10-digit official id starting with 20 "
            "(e.g. '2022500001') from get_nbastats_game_log; NBA (00...), WNBA (10...) and ESPN event "
            "ids are not G League game ids."
        )
    return text


def _person_id(value: Any) -> str:
    text = value.strip() if isinstance(value, str) else str(value) if type(value) is int else ""
    if not (text.isascii() and text.isdigit()):
        raise _NbaStatsError(f"Invalid player_id {value!r}. Expected an NBA.com person id (digits).")
    return text


def _table(data: Any, name: str) -> list[dict[str, Any]]:
    """Rows of the named result set with lowercase keys.

    The payload must say it answers for the G League; a missing or malformed table is an error.
    Handles both ``resultSets`` (a list) and leagueleaders' singular ``resultSet``.
    """
    if not isinstance(data, dict):
        raise _NbaStatsError("stats.nba.com returned an unexpected payload")
    parameters = data.get("parameters")
    league = parameters.get("LeagueID") if isinstance(parameters, dict) else None
    if str(league) != LEAGUE_ID:
        raise _NbaStatsError(f"stats.nba.com answered for LeagueID {league!r}, not the G League ({LEAGUE_ID})")
    sets = data.get("resultSets")
    if sets is None and isinstance(data.get("resultSet"), dict):
        sets = [data["resultSet"]]
    chosen = (
        next((s for s in sets if isinstance(s, dict) and s.get("name") == name), None)
        if isinstance(sets, list)
        else None
    )
    headers = chosen.get("headers") if chosen else None
    rows = chosen.get("rowSet") if chosen else None
    if not (
        isinstance(headers, list)
        and bool(headers)
        and all(isinstance(h, str) and h for h in headers)
        and len({h.lower() for h in headers}) == len(headers)
        and isinstance(rows, list)
        and all(isinstance(r, list) and len(r) == len(headers) for r in rows)
    ):
        raise _NbaStatsError(f"stats.nba.com response has no well-formed {name} table")
    keys = [str(h).lower() for h in headers]
    return [dict(zip(keys, row)) for row in rows]


def _check_games(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        game_id = str(row.get("game_id"))
        if not _GAME_ID.fullmatch(game_id):
            raise _NbaStatsError(f"stats.nba.com returned game id {game_id!r}, which is not a G League game")


def _all_players() -> list[dict[str, Any]]:
    data = _request(
        "commonallplayers",
        {"IsOnlyCurrentSeason": 0, "LeagueID": LEAGUE_ID, "Season": _season_str(None)},
        ttl=_PLAYERS_TTL,
    )
    return _table(data, "CommonAllPlayers")


def _resolve_player(player_id: Any, player: Any) -> tuple[str, str]:
    """``(person_id, display_name)`` from an id, or a name matched against the G League registry."""
    if player_id is not None:
        person_id = _person_id(player_id)
        return person_id, person_id
    if not player:
        raise _NbaStatsError("Pass player_id or player (a name to search for).")
    needle = _fold(str(player).strip())
    matches = [row for row in _all_players() if needle in _fold(row.get("display_first_last", ""))]
    if not matches:
        raise _NbaStatsError(f"No G League player matched {player!r}. Try find_nba_player to search the registry.")
    if len(matches) > 1:
        names = ", ".join(str(m.get("display_first_last")) for m in matches[:6])
        raise _NbaStatsError(
            f"{player!r} matched {len(matches)} players ({names}"
            + (", …" if len(matches) > 6 else "")
            + "). Pass player_id, or a more specific name."
        )
    return str(matches[0].get("person_id")), str(matches[0].get("display_first_last"))


def _team_game_log(season: str, season_type: str, mode: str = "T") -> list[dict[str, Any]]:
    data = _request(
        "leaguegamelog",
        {
            "Counter": 0,
            "DateFrom": "",
            "DateTo": "",
            "Direction": "ASC",
            "LeagueID": LEAGUE_ID,
            "PlayerOrTeam": mode,
            "Season": season,
            "SeasonType": season_type,
            "Sorter": "DATE",
        },
    )
    rows = _table(data, "LeagueGameLog")
    _check_games(rows)
    return rows


def _team(raw_team: Any) -> str | None:
    return None if raw_team is None else str(raw_team).strip().upper()


# ============================================================
# Public connector functions
# ============================================================


@_guard
def find_nba_player(request_data: dict[str, Any]) -> dict[str, Any]:
    name = request_data.get("params", {}).get("name")
    if not name:
        raise _NbaStatsError("name is required")
    needle = _fold(str(name).strip())
    matches = [
        {
            "player_id": str(row.get("person_id", "")),
            "name": row.get("display_first_last"),
            "is_active": row.get("rosterstatus") == 1,
            "team": row.get("team_abbreviation") or None,
            "from_year": row.get("from_year"),
            "to_year": row.get("to_year"),
        }
        for row in _all_players()
        if needle in _fold(row.get("display_first_last", ""))
    ]
    return {"provider": "nba-stats", "league_id": LEAGUE_ID, "query": name, "players": matches, "count": len(matches)}


@_guard
def get_nbastats_game_log(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    season = _season_str(params.get("season"))
    season_type = _season_type(params.get("season_type"))
    raw_team = params.get("team")
    team = _team(raw_team)
    raw_player = params.get("player")
    mode = params.get("player_or_team")
    if mode is None and raw_player is not None:
        mode = "player"
    if _lookup(_PLAYER_OR_TEAM, mode, "team", "player_or_team") == "P":
        return _player_games(params, season, season_type, raw_team, team, raw_player)
    if raw_player is not None:
        raise _NbaStatsError("player selects player rows; pass player_or_team='player' (or omit it) with player.")

    rows = _team_game_log(season, season_type)
    if team is not None:
        rows = [r for r in rows if str(r.get("team_abbreviation", "")).upper() == team]
    total = len(rows)
    rows, shaping = shape_rows(rows, params, identity=_GAME_LOG_IDENTITY)
    result = {
        "provider": "nba-stats",
        "league_id": LEAGUE_ID,
        "season": season,
        "season_type": season_type,
        "team": team,
        "games": rows,
        "count": len(rows),
        **shaping,
    }
    warnings = _team_warnings(team, raw_team, total)
    if warnings:
        result["warnings"] = warnings
    return result


def _player_games(params, season, season_type, raw_team, team, raw_player) -> dict[str, Any]:
    """Player games in the NBA row form; one player or the entire G League."""
    person_id = display = None
    if raw_player is None:
        rows = _team_game_log(season, season_type, mode="P")
    else:
        text = str(raw_player).strip()
        person_id, display = (
            _resolve_player(text, None) if text.isascii() and text.isdigit() else _resolve_player(None, text)
        )
        data = _request(
            "playergamelog",
            {
                "DateFrom": "",
                "DateTo": "",
                "LeagueID": LEAGUE_ID,
                "PlayerID": person_id,
                "Season": season,
                "SeasonType": season_type,
            },
        )
        rows = _table(data, "PlayerGameLog")
        _check_games(rows)
    for row in rows:
        if person_id is not None and str(row.get("player_id")) != person_id:
            raise _NbaStatsError(f"stats.nba.com returned player {row.get('player_id')!r} for player {person_id!r}")
        try:
            row["game_date"] = datetime.strptime(str(row.get("game_date")), "%b %d, %Y").strftime("%Y-%m-%d")
        except ValueError:
            pass
        row["team_abbreviation"] = str(row.get("matchup") or "").split(" ")[0] or None
    rows.sort(key=lambda r: (str(r.get("game_date")), str(r.get("game_id"))))
    if team is not None:
        rows = [r for r in rows if str(r.get("team_abbreviation", "")).upper() == team]
    for row in rows:
        row["opponent"], row["home_away"] = _matchup_sides(row.get("matchup"))
    total = len(rows)
    rows, shaping = shape_rows(rows, params, identity=_PLAYER_GAME_LOG_IDENTITY)
    result = {
        "provider": "nba-stats",
        "league_id": LEAGUE_ID,
        "season": season,
        "season_type": season_type,
        "player_or_team": "player",
        "team": team,
        "games": rows,
        "count": len(rows),
        **shaping,
    }
    if person_id is not None:
        result.update(player_id=person_id, player=display)
    warnings = _team_warnings(team, raw_team, total)
    if person_id is not None and not total and team is None:
        warnings.append(f"player {display!r} has no {season_type} games in {season}")
    if warnings:
        result["warnings"] = warnings
    return result


@_guard
def get_nbastats_player_career(request_data: dict[str, Any]) -> dict[str, Any]:
    """Regular-season G League rows only: the college, Showcase and playoff tables are not read."""
    params = request_data.get("params", {})
    per_mode = _lookup(_PER_MODES, params.get("per_mode"), "totals", "per_mode")
    person_id, display = _resolve_player(params.get("player_id"), params.get("player"))
    data = _request("playercareerstats", {"LeagueID": LEAGUE_ID, "PerMode": per_mode, "PlayerID": person_id})
    seasons = _table(data, "SeasonTotalsRegularSeason")
    career = _table(data, "CareerTotalsRegularSeason")
    for row in seasons + career:
        if str(row.get("league_id")) != LEAGUE_ID or str(row.get("player_id")) != person_id:
            raise _NbaStatsError(
                f"stats.nba.com returned a career row for league {row.get('league_id')!r}, "
                f"player {row.get('player_id')!r}; expected G League player {person_id!r}"
            )
    return {
        "provider": "nba-stats",
        "league_id": LEAGUE_ID,
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
    season_type = _season_type(params.get("season_type"))
    measure = _lookup(_MEASURE_TYPES, params.get("measure"), "base", "measure")
    per_mode = _lookup(_PER_MODES, params.get("per_mode"), "totals", "per_mode")
    raw_team = params.get("team")
    team = _team(raw_team)

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
            "LeagueID": LEAGUE_ID,
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
    rows = _table(data, "LeagueDashTeamStats")
    # This table names teams without abbreviating them; the same season's G League game log
    # (cached) supplies them. A team with no game-log rows keeps a null abbreviation.
    abbreviations = {str(r.get("team_id")): r.get("team_abbreviation") for r in _team_game_log(season, season_type)}
    for row in rows:
        row["team_abbreviation"] = abbreviations.get(str(row.get("team_id")))
    if team is not None:
        wanted = str(raw_team).strip()
        rows = [
            r
            for r in rows
            if (r["team_abbreviation"] is not None and str(r["team_abbreviation"]).upper() == team)
            or str(r.get("team_id")) == wanted
            or str(r.get("team_name", "")).casefold() == wanted.casefold()
        ]
    total = len(rows)
    rows, shaping = shape_rows(rows, params, identity=_TEAM_STATS_IDENTITY)
    result = {
        "provider": "nba-stats",
        "league_id": LEAGUE_ID,
        "season": season,
        "season_type": season_type,
        "measure": measure,
        "per_mode": per_mode,
        "team": team,
        "teams": rows,
        "count": len(rows),
        **shaping,
    }
    warnings = _team_warnings(team, raw_team, total)
    if warnings:
        result["warnings"] = warnings
    return result


@_guard
def get_nbastats_shot_chart(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    season = _season_str(params.get("season"))
    season_type = _season_type(params.get("season_type"))
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
            "LeagueID": LEAGUE_ID,
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
    rows = _table(data, "Shot_Chart_Detail")
    _check_games(rows)
    if any(str(row.get("player_id")) != person_id for row in rows):
        raise _NbaStatsError(f"stats.nba.com returned shots for another or missing player, not {person_id!r}")
    total = len(rows)
    shots = [
        {
            "game_id": r.get("game_id"),
            "game_date": _iso_date(r.get("game_date")),
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
    shots, shaping = shape_rows(shots, params, identity=_SHOT_IDENTITY)
    result = {
        "provider": "nba-stats",
        "league_id": LEAGUE_ID,
        "player_id": person_id,
        "player": display,
        "season": season,
        "season_type": season_type,
        "shots": shots,
        "count": len(shots),
        **shaping,
    }
    if limit is not None and total > len(shots):
        result["truncated"] = True
        result["warnings"] = [f"results truncated to limit={int(limit)} of {total} shots"]
    return result


@_guard
def get_nbastats_play_by_play(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    game_id = _game_id(params.get("game_id"))
    limit = parse_limit(params["limit"]) if params.get("limit") is not None else None

    data = _request("playbyplayv3", {"EndPeriod": 0, "GameID": game_id, "StartPeriod": 0})
    game = data.get("game") if isinstance(data, dict) else None
    actions = game.get("actions") if isinstance(game, dict) else None
    if (
        not isinstance(game, dict)
        or str(game.get("gameId")) != game_id
        or not isinstance(actions, list)
        or not all(isinstance(a, dict) for a in actions)
    ):
        raise _NbaStatsError(f"stats.nba.com has no play-by-play for G League game {game_id!r}")
    total = len(actions)
    if limit is not None:
        actions = actions[:limit]
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
    result = {"provider": "nba-stats", "league_id": LEAGUE_ID, "game_id": game_id, "plays": plays, "count": len(plays)}
    if limit is not None and total > len(plays):
        result["truncated"] = True
        result["warnings"] = [f"results truncated to limit={limit} of {total} actions"]
    return result


@_guard
def get_nbastats_advanced_boxscore(request_data: dict[str, Any]) -> dict[str, Any]:
    game_id = _game_id(request_data.get("params", {}).get("game_id"))
    data = _request(
        "boxscoreadvancedv3",
        {"EndPeriod": 0, "EndRange": 0, "GameID": game_id, "RangeType": 0, "StartPeriod": 0, "StartRange": 0},
    )
    box = data.get("boxScoreAdvanced") if isinstance(data, dict) else None
    sides = [box.get("homeTeam"), box.get("awayTeam")] if isinstance(box, dict) else []
    if (
        not isinstance(box, dict)
        or str(box.get("gameId")) != game_id
        or not all(
            isinstance(s, dict)
            and isinstance(s.get("players"), list)
            and all(isinstance(p, dict) for p in s["players"])
            for s in sides
        )
    ):
        raise _NbaStatsError(f"No advanced box score for G League game_id {game_id!r}")
    home, away = (_normalize_box_team(side) for side in sides)
    for team in (home, away):
        # G League tricodes have no verified ESPN spelling.
        team.pop("team_abbreviation_espn")
        # boxscoreadvancedv3 sends minutes inside statistics, not beside it.
        for player in team["players"]:
            if player["minutes"] is None:
                player["minutes"] = player["stats"].get("minutes")
    return {"provider": "nba-stats", "league_id": LEAGUE_ID, "game_id": game_id, "home": home, "away": away}


@_guard
def get_nbastats_leaders(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    season = _season_str(params.get("season"))
    season_type = _season_type(params.get("season_type"))
    per_mode = _lookup(_PER_MODES, params.get("per_mode"), "per_game", "per_mode")
    category = str(params.get("stat_category") or "PTS").strip().upper()
    if category not in _STAT_CATEGORIES:
        raise _NbaStatsError(
            f"Invalid stat_category {params.get('stat_category')!r}. Valid values: {', '.join(_STAT_CATEGORIES)}"
        )

    data = _request(
        "leagueleaders",
        {
            "ActiveFlag": "",
            "LeagueID": LEAGUE_ID,
            "PerMode": per_mode,
            "Scope": "S",
            "Season": season,
            "SeasonType": season_type,
            "StatCategory": category,
        },
    )
    rows = _table(data, "LeagueLeaders")
    rows, shaping = shape_rows(rows, params, identity=_LEADER_IDENTITY)
    return {
        "provider": "nba-stats",
        "league_id": LEAGUE_ID,
        "season": season,
        "season_type": season_type,
        "per_mode": per_mode,
        "stat_category": category,
        "leaders": rows,
        "count": len(rows),
        **shaping,
    }
