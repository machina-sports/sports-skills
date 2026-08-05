"""MLB Stats API (statsapi.mlb.com) connector — direct HTTP, stdlib only.

Covers the analytics layer ESPN's public endpoints do not provide: pitch-level
play-by-play (velocity, spin, plate coordinates, exit velocity, launch angle),
career splits by stat group, league leaders across dozens of categories, and
schedules back to 1901 keyed by MLB's own game ids (gamePk). Same role the
nflverse and NBA Stats backends play for their sports.

Unlike stats.nba.com, this API is genuinely open: no API key, no required
headers, no bot wall. Responses carry MLB's copyright notice, which is passed
through in every result.
"""

from __future__ import annotations

import functools
import json
import logging
import re
import unicodedata
import urllib.parse
from datetime import datetime
from typing import Any

from sports_skills._espn_base import (
    RateLimiter,
    _cache_get,
    _cache_set,
    _http_fetch,
)

logger = logging.getLogger("sports_skills.mlb._stats")

_API_BASE = "https://statsapi.mlb.com/api/v1"

_mlb_rate_limiter = RateLimiter(max_tokens=2, refill_rate=2.0)

_TIMEOUT = 15

# ESPN and MLB disagree on two team abbreviations. Both spellings are accepted
# everywhere a team filter exists; rows carry both systems so results can be
# joined against the ESPN-backed functions in this module.
_ESPN_TO_MLB = {"ARI": "AZ", "CHW": "CWS"}
_MLB_TO_ESPN = {v: k for k, v in _ESPN_TO_MLB.items()}

_GAME_TYPES = {
    "regular": "R",
    "spring": "S",
    "wildcard": "F",
    "division": "D",
    "lcs": "L",
    "worldseries": "W",
    "allstar": "A",
}

_STAT_TYPES = {"season": "season", "career": "career", "year_by_year": "yearByYear"}

_STAT_GROUPS = {"hitting": "hitting", "pitching": "pitching", "fielding": "fielding"}

# The full team map changes at most once a season; hold it far longer than
# game data.
_TEAMS_TTL = 21600


class _MlbStatsError(Exception):
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
        except _MlbStatsError as exc:
            return {"error": True, "message": str(exc)}
        except Exception as exc:  # noqa: BLE001 — surface, never crash the agent
            logger.debug("mlb-stats call failed", exc_info=True)
            return {
                "error": True,
                "message": f"MLB Stats backend error ({type(exc).__name__}): {exc}",
            }

    return wrapper


def _request(path: str, params: dict[str, Any] | None = None, ttl: int = 600) -> dict[str, Any]:
    """Fetch one statsapi.mlb.com endpoint. Rate-limited and cached."""
    query = "?" + urllib.parse.urlencode(params) if params else ""
    url = f"{_API_BASE}/{path}{query}"
    cache_key = f"mlbstats:{path}:{query}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    raw, err = _http_fetch(url, rate_limiter=_mlb_rate_limiter, timeout=_TIMEOUT)
    if err:
        raise _MlbStatsError(err.get("message", "request failed"))
    try:
        data = json.loads(raw.decode())
    except (json.JSONDecodeError, ValueError) as exc:
        raise _MlbStatsError("statsapi.mlb.com returned invalid JSON") from exc
    _cache_set(cache_key, data, ttl=ttl)
    return data


def _season_str(season: Any) -> str:
    """MLB seasons are calendar years."""
    if season is None:
        now = datetime.now()
        # The season runs roughly April-October; January-February queries almost
        # always mean the season just played.
        return str(now.year if now.month >= 3 else now.year - 1)
    text = str(season).strip()
    if re.fullmatch(r"\d{4}", text):
        return text
    raise _MlbStatsError(f"Invalid season {season!r}. Pass the year (e.g. 2024).")


def _require_game_pk(game_pk: Any) -> str:
    """Validate MLB's game id, catching ESPN event ids early.

    Passing an ESPN event id here is the natural mistake given both id systems
    live in this module, so catch it before the request and say which id system
    is expected.
    """
    if not game_pk:
        raise _MlbStatsError(
            "game_pk is required — MLB's game id from get_mlbstats_schedule "
            "(e.g. 775296), not an ESPN event id."
        )
    text = str(game_pk).strip()
    if re.fullmatch(r"4\d{8}", text):
        raise _MlbStatsError(
            f"{game_pk!r} looks like an ESPN event id. Pass the gamePk from "
            "get_mlbstats_schedule instead — join via game date plus team "
            "abbreviations; the two id systems share nothing."
        )
    if not re.fullmatch(r"\d{1,8}", text):
        raise _MlbStatsError(
            f"Invalid game_pk {game_pk!r}. Expected MLB's numeric gamePk from "
            "get_mlbstats_schedule (e.g. 775296)."
        )
    return text


def _lookup(mapping: dict[str, str], value: Any, default: str | None, what: str) -> str | None:
    if value is None:
        return mapping[default] if default else None
    key = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    if key not in mapping:
        raise _MlbStatsError(f"Invalid {what} {value!r}. Valid values: {', '.join(sorted(mapping))}")
    return mapping[key]


def _fold(text: Any) -> str:
    """Lowercase and strip diacritics for name matching."""
    normalized = unicodedata.normalize("NFKD", str(text))
    return normalized.encode("ascii", "ignore").decode().lower()


# ============================================================
# Team registry
# ============================================================


def _teams_by_abbr() -> dict[str, dict[str, Any]]:
    data = _request("teams", {"sportId": 1}, ttl=_TEAMS_TTL)
    return {
        str(t.get("abbreviation", "")).upper(): {
            "team_id": t.get("id"),
            "name": t.get("name"),
            "abbreviation": t.get("abbreviation"),
        }
        for t in data.get("teams", [])
    }


def _resolve_team(team: Any) -> dict[str, Any] | None:
    """Resolve a team abbreviation (either spelling) to the MLB team record."""
    if team is None:
        return None
    abbr = str(team).strip().upper()
    abbr = _ESPN_TO_MLB.get(abbr, abbr)
    teams = _teams_by_abbr()
    record = teams.get(abbr)
    if record is None:
        raise _MlbStatsError(
            f"Unknown team {team!r}. Valid abbreviations: {', '.join(sorted(teams))} "
            "(ESPN spellings ARI and CHW are accepted)."
        )
    return record


def _annotate_abbrs(row: dict[str, Any], abbr: Any) -> None:
    if abbr:
        text = str(abbr)
        row["team_abbreviation"] = text
        row["team_abbreviation_espn"] = _MLB_TO_ESPN.get(text, text)


# ============================================================
# Public connector functions
# ============================================================


@_guard
def find_mlb_player(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    name = params.get("name")
    if not name:
        raise _MlbStatsError("name is required")
    data = _request("people/search", {"names": str(name)})
    needle = _fold(str(name).strip())
    players = []
    for p in data.get("people", []):
        # The upstream search is fuzzy; keep its ordering but drop entries that
        # do not even fold-match, so "judge" does not return unrelated names.
        if needle not in _fold(p.get("fullName", "")):
            continue
        players.append(
            {
                "player_id": str(p.get("id", "")),
                "name": p.get("fullName"),
                "is_active": bool(p.get("active")),
                "position": (p.get("primaryPosition") or {}).get("abbreviation"),
                "bats": (p.get("batSide") or {}).get("code"),
                "throws": (p.get("pitchHand") or {}).get("code"),
                "team": (p.get("currentTeam") or {}).get("name"),
                "debut": p.get("mlbDebutDate"),
            }
        )
    return {
        "provider": "mlb-stats",
        "query": name,
        "players": players,
        "count": len(players),
        "copyright": data.get("copyright"),
    }


def _resolve_player(player_id: Any, player: Any) -> tuple[str, str]:
    """Return ``(person_id, display_name)`` from an id or a name query."""
    if player_id is not None:
        return str(player_id), str(player_id)
    if not player:
        raise _MlbStatsError("Pass player_id or player (a name to search for).")
    result = find_mlb_player({"params": {"name": player}})
    if result.get("error"):
        raise _MlbStatsError(str(result.get("message")))
    matches = result.get("players", [])
    if not matches:
        raise _MlbStatsError(
            f"No MLB player matched {player!r}. Try find_mlb_player to search the registry."
        )
    if len(matches) > 1:
        names = ", ".join(str(m.get("name")) for m in matches[:6])
        raise _MlbStatsError(
            f"{player!r} matched {len(matches)} players ({names}"
            + (", …" if len(matches) > 6 else "")
            + "). Pass player_id, or a more specific name."
        )
    return str(matches[0]["player_id"]), str(matches[0]["name"])


def _normalize_game(game: dict[str, Any]) -> dict[str, Any]:
    away, home = game.get("teams", {}).get("away", {}), game.get("teams", {}).get("home", {})
    row = {
        "game_pk": str(game.get("gamePk", "")),
        "game_date": str(game.get("gameDate", ""))[:10],
        "game_type": game.get("gameType"),
        "status": (game.get("status") or {}).get("detailedState"),
        "away_team": (away.get("team") or {}).get("name"),
        "home_team": (home.get("team") or {}).get("name"),
        "away_score": away.get("score"),
        "home_score": home.get("score"),
        "venue": (game.get("venue") or {}).get("name"),
    }
    return row


@_guard
def get_mlbstats_schedule(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    date = params.get("date")
    raw_team = params.get("team")
    game_type = _lookup(_GAME_TYPES, params.get("game_type"), None, "game_type")

    query: dict[str, Any] = {"sportId": 1}
    season = None
    if date is not None:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)):
            raise _MlbStatsError(f"Invalid date {date!r}. Use YYYY-MM-DD.")
        query["date"] = str(date)
    else:
        season = _season_str(params.get("season"))
        query["season"] = season
        if raw_team is None:
            # A full league season is ~2,430 games; require a narrower ask.
            raise _MlbStatsError(
                "Pass date=YYYY-MM-DD for a single day, or team=<abbr> with an "
                "optional season for a team's schedule."
            )
    team = _resolve_team(raw_team)
    if team is not None:
        query["teamId"] = team["team_id"]
    if game_type is not None:
        query["gameType"] = game_type

    data = _request("schedule", query)
    games = []
    for day in data.get("dates", []):
        for game in day.get("games", []):
            row = _normalize_game(game)
            if team is not None:
                _annotate_abbrs(row, team["abbreviation"])
            games.append(row)

    return {
        "provider": "mlb-stats",
        "season": season,
        "date": date,
        "team": team["abbreviation"] if team else None,
        "game_type": game_type,
        "games": games,
        "count": len(games),
        "copyright": data.get("copyright"),
    }


@_guard
def get_mlbstats_player_stats(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    stat_type = _lookup(_STAT_TYPES, params.get("stat_type"), "season", "stat_type")
    group = _lookup(_STAT_GROUPS, params.get("stat_group"), "hitting", "stat_group")
    person_id, display = _resolve_player(params.get("player_id"), params.get("player"))

    query = {"stats": stat_type, "group": group}
    if stat_type == "season":
        query["season"] = _season_str(params.get("season"))

    data = _request(f"people/{person_id}/stats", query)
    splits = []
    for block in data.get("stats", []):
        for split in block.get("splits", []):
            splits.append(
                {
                    "season": split.get("season"),
                    "team": (split.get("team") or {}).get("name"),
                    "stats": split.get("stat") or {},
                }
            )
    return {
        "provider": "mlb-stats",
        "player_id": person_id,
        "player": display,
        "stat_type": stat_type,
        "stat_group": group,
        "splits": splits,
        "count": len(splits),
        "copyright": data.get("copyright"),
    }


@_guard
def get_mlbstats_play_by_play(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    game_pk = _require_game_pk(params.get("game_pk"))
    limit = params.get("limit")

    data = _request(f"game/{game_pk}/playByPlay", None)
    all_plays = data.get("allPlays", [])
    total = len(all_plays)
    if limit is not None:
        all_plays = all_plays[: int(limit)]

    plays = []
    for p in all_plays:
        about, result = p.get("about") or {}, p.get("result") or {}
        pitches = []
        for e in p.get("playEvents", []):
            if not e.get("isPitch"):
                continue
            pd_ = e.get("pitchData") or {}
            hd = e.get("hitData") or {}
            pitch = {
                "type": ((e.get("details") or {}).get("type") or {}).get("description"),
                "call": ((e.get("details") or {}).get("call") or {}).get("description"),
                "speed_mph": pd_.get("startSpeed"),
                "spin_rpm": (pd_.get("breaks") or {}).get("spinRate"),
                "plate_x": (pd_.get("coordinates") or {}).get("pX"),
                "plate_z": (pd_.get("coordinates") or {}).get("pZ"),
            }
            if hd:
                pitch["hit"] = {
                    "exit_velocity_mph": hd.get("launchSpeed"),
                    "launch_angle": hd.get("launchAngle"),
                    "distance_ft": hd.get("totalDistance"),
                }
            pitches.append(pitch)
        plays.append(
            {
                "inning": about.get("inning"),
                "half": about.get("halfInning"),
                "batter": (p.get("matchup") or {}).get("batter", {}).get("fullName"),
                "pitcher": (p.get("matchup") or {}).get("pitcher", {}).get("fullName"),
                "event": result.get("event"),
                "description": result.get("description"),
                "rbi": result.get("rbi"),
                "away_score": result.get("awayScore"),
                "home_score": result.get("homeScore"),
                "pitches": pitches,
            }
        )

    result = {
        "provider": "mlb-stats",
        "game_pk": game_pk,
        "plays": plays,
        "count": len(plays),
        "copyright": data.get("copyright"),
    }
    if limit is not None and total > len(plays):
        result["truncated"] = True
        result["warnings"] = [f"results truncated to limit={int(limit)} of {total} plays"]
    return result


def _normalize_box_side(side: dict[str, Any]) -> dict[str, Any]:
    team = side.get("team") or {}
    abbr = team.get("abbreviation") or ""
    players = []
    for p in (side.get("players") or {}).values():
        person = p.get("person") or {}
        stats = p.get("stats") or {}
        entry = {
            "player_id": str(person.get("id", "")),
            "name": person.get("fullName"),
            "position": (p.get("position") or {}).get("abbreviation"),
            "batting": stats.get("batting") or {},
            "pitching": stats.get("pitching") or {},
        }
        if entry["batting"] or entry["pitching"]:
            players.append(entry)
    out = {
        "team_id": str(team.get("id", "")),
        "team_name": team.get("name"),
        "stats": {
            "batting": (side.get("teamStats") or {}).get("batting") or {},
            "pitching": (side.get("teamStats") or {}).get("pitching") or {},
        },
        "players": players,
    }
    _annotate_abbrs(out, abbr)
    return out


@_guard
def get_mlbstats_boxscore(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    game_pk = _require_game_pk(params.get("game_pk"))

    data = _request(f"game/{game_pk}/boxscore", None)
    teams = data.get("teams") or {}
    if not teams:
        raise _MlbStatsError(f"No box score for game_pk {game_pk!r}")

    return {
        "provider": "mlb-stats",
        "game_pk": game_pk,
        "home": _normalize_box_side(teams.get("home") or {}),
        "away": _normalize_box_side(teams.get("away") or {}),
        "copyright": data.get("copyright"),
    }


@_guard
def get_mlbstats_standings(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    season = _season_str(params.get("season"))

    data = _request("standings", {"leagueId": "103,104", "season": season})
    divisions = []
    for record in data.get("records", []):
        rows = []
        for tr in record.get("teamRecords", []):
            team = tr.get("team") or {}
            row = {
                "team_id": str(team.get("id", "")),
                "team_name": team.get("name"),
                "wins": tr.get("wins"),
                "losses": tr.get("losses"),
                "pct": tr.get("winningPercentage"),
                "games_back": tr.get("gamesBack"),
                "streak": (tr.get("streak") or {}).get("streakCode"),
                "run_differential": tr.get("runDifferential"),
                "division_rank": tr.get("divisionRank"),
                "wildcard_rank": tr.get("wildCardRank"),
            }
            rows.append(row)
        divisions.append(
            {
                "division_id": str((record.get("division") or {}).get("id", "")),
                "league_id": str((record.get("league") or {}).get("id", "")),
                "teams": rows,
            }
        )
    return {
        "provider": "mlb-stats",
        "season": season,
        "divisions": divisions,
        "count": sum(len(d["teams"]) for d in divisions),
        "copyright": data.get("copyright"),
    }


@_guard
def get_mlbstats_leaders(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    category = params.get("category")
    if not category:
        raise _MlbStatsError(
            "category is required — an MLB stat name in camelCase, e.g. homeRuns, "
            "battingAverage, earnedRunAverage, strikeouts, stolenBases, wins, saves."
        )
    season = _season_str(params.get("season"))
    group = params.get("stat_group")
    limit = params.get("limit") or 10

    query = {
        "leaderCategories": str(category),
        "season": season,
        "sportId": 1,
        "limit": int(limit),
    }
    if group is not None:
        query["statGroup"] = _lookup(_STAT_GROUPS, group, None, "stat_group")

    data = _request("stats/leaders", query)
    blocks = data.get("leagueLeaders", [])
    # One block arrives per stat group that carries this category — "homeRuns"
    # exists for hitting, catching, AND pitching (home runs *allowed*). Flattening
    # without labels would silently mix them, so every row names its group.
    leaders = []
    groups_seen = []
    for block in blocks:
        stat_group = block.get("statGroup")
        if stat_group not in groups_seen:
            groups_seen.append(stat_group)
        for entry in block.get("leaders", []):
            team = entry.get("team") or {}
            leaders.append(
                {
                    "rank": entry.get("rank"),
                    "player_id": str((entry.get("person") or {}).get("id", "")),
                    "player": (entry.get("person") or {}).get("fullName"),
                    "team": team.get("name"),
                    "value": entry.get("value"),
                    "stat_group": stat_group,
                }
            )
    if not leaders:
        raise _MlbStatsError(
            f"No leaders returned for category {category!r} in {season}. Categories "
            "are camelCase MLB stat names, e.g. homeRuns, battingAverage, "
            "earnedRunAverage, strikeouts, stolenBases, wins, saves."
        )
    result = {
        "provider": "mlb-stats",
        "category": category,
        "season": season,
        "leaders": leaders,
        "count": len(leaders),
        "copyright": data.get("copyright"),
    }
    if len(groups_seen) > 1:
        result["warnings"] = [
            f"category {category!r} exists in {len(groups_seen)} stat groups "
            f"({', '.join(str(g) for g in groups_seen)}); rows are labelled by "
            "stat_group — pass group=<name> for just one"
        ]
    return result
