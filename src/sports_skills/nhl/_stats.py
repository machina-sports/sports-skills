"""NHL API (api-web.nhle.com) connector — direct HTTP, stdlib only.

Covers the analytics layer ESPN's public endpoints do not provide: play-by-play
with on-ice shot coordinates, career and season-by-season player totals across
leagues, skater and goalie leaders, and schedules/standings reaching back to
the Original Six era. Same role the nflverse, NBA Stats, and MLB Stats
backends play for their sports.

This is the NHL's current API. The retired ``statsapi.web.nhl.com`` — which
most community documentation still describes — no longer resolves at all.
"""

from __future__ import annotations

import functools
import json
import logging
import re
import unicodedata
import urllib.parse
from datetime import datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import Any

from sports_skills._espn_base import (
    RateLimiter,
    _cache_get,
    _cache_set,
    _http_fetch,
)

logger = logging.getLogger("sports_skills.nhl._stats")

_API_BASE = "https://api-web.nhle.com/v1"
_SEARCH_BASE = "https://search.d3.nhle.com/api/v1"


def _default_user_agent() -> str:
    """An honest project User-Agent.

    api-web.nhle.com accepts nearly any client but rejects exactly the
    ``Python-urllib/*`` prefix — the third distinct edge policy in this package
    (ESPN's site.api *requires* that prefix; stats.nba.com wants a browser plus
    client hints). So this connector must not share the ESPN User-Agent, and
    since anything else passes, it identifies itself truthfully.
    """
    try:
        pkg_version = _pkg_version("sports-skills")
    except PackageNotFoundError:
        pkg_version = "dev"
    return f"sports-skills/{pkg_version} (+https://github.com/machina-sports/sports-skills)"


_NHL_HEADERS = {"User-Agent": _default_user_agent()}

_nhl_rate_limiter = RateLimiter(max_tokens=2, refill_rate=2.0)

_TIMEOUT = 15

# ESPN and the NHL disagree on five team abbreviations. Both spellings are
# accepted everywhere a team filter exists; rows carry both systems so results
# can be joined against the ESPN-backed functions in this module.
_ESPN_TO_NHL = {"LA": "LAK", "NJ": "NJD", "SJ": "SJS", "TB": "TBL", "UTAH": "UTA"}
_NHL_TO_ESPN = {v: k for k, v in _ESPN_TO_NHL.items()}

# NHL game-type codes used by the leaders and schedule endpoints.
_SEASON_TYPES = {"regular": 2, "playoffs": 3}

_SKATER_CATEGORIES = ("goals", "assists", "points", "plusMinus", "penaltyMins", "toi", "faceoffLeaders")
_GOALIE_CATEGORIES = ("wins", "shutouts", "savePctg", "goalsAgainstAverage")


class _NhlStatsError(Exception):
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
        except _NhlStatsError as exc:
            return {"error": True, "message": str(exc)}
        except Exception as exc:  # noqa: BLE001 — surface, never crash the agent
            logger.debug("nhl-stats call failed", exc_info=True)
            return {
                "error": True,
                "message": f"NHL Stats backend error ({type(exc).__name__}): {exc}",
            }

    return wrapper


def _request(url: str, ttl: int = 600) -> dict[str, Any] | list:
    """Fetch one NHL API URL. Rate-limited and cached."""
    cached = _cache_get(f"nhlstats:{url}")
    if cached is not None:
        return cached
    raw, err = _http_fetch(url, headers=_NHL_HEADERS, rate_limiter=_nhl_rate_limiter, timeout=_TIMEOUT)
    if err:
        raise _NhlStatsError(err.get("message", "request failed"))
    try:
        data = json.loads(raw.decode())
    except (json.JSONDecodeError, ValueError) as exc:
        raise _NhlStatsError("the NHL API returned invalid JSON") from exc
    _cache_set(f"nhlstats:{url}", data, ttl=ttl)
    return data


def _current_season_start_year() -> int:
    """The season identified by its starting year (Oct-June)."""
    now = datetime.now()
    return now.year if now.month >= 9 else now.year - 1


def _season_str(season: Any) -> str:
    """Coerce a season into the NHL's eight-digit form ("20242025").

    Accepts the starting year (2024 or "2024") or the eight-digit form.
    """
    if season is None:
        season = _current_season_start_year()
    text = str(season).strip()
    if re.fullmatch(r"\d{8}", text):
        start, end = int(text[:4]), int(text[4:])
        if end != start + 1:
            raise _NhlStatsError(
                f"Invalid season {season!r}: the two halves must be consecutive "
                "years (e.g. 20242025)."
            )
        return text
    if re.fullmatch(r"\d{4}", text):
        year = int(text)
        return f"{year}{year + 1}"
    raise _NhlStatsError(
        f"Invalid season {season!r}. Pass the starting year (e.g. 2024) or the "
        "NHL form (e.g. '20242025')."
    )


def _require_game_id(game_id: Any) -> str:
    """Validate the NHL's ten-digit game id, catching ESPN event ids early.

    NHL ids encode season, game type, and game number (e.g. ``2023030417`` is
    the 2023-24 playoffs, series game 417). ESPN event ids are nine digits
    starting with 4 — the natural mix-up given both id systems live here.
    """
    if not game_id:
        raise _NhlStatsError(
            "game_id is required — the 10-digit NHL game id from "
            "get_nhlstats_schedule (e.g. '2023030417'), not an ESPN event id."
        )
    text = str(game_id).strip()
    if re.fullmatch(r"4\d{8}", text):
        raise _NhlStatsError(
            f"{game_id!r} looks like an ESPN event id. Pass the NHL game id from "
            "get_nhlstats_schedule instead — join via game date plus team "
            "abbreviations; the two id systems share nothing."
        )
    if not re.fullmatch(r"\d{10}", text):
        raise _NhlStatsError(
            f"Invalid NHL game id {game_id!r}. Expected the 10-digit id from "
            "get_nhlstats_schedule (e.g. '2023030417')."
        )
    return text


def _normalize_team(team: Any) -> str | None:
    """Translate a team abbreviation to the NHL's spelling (accepts ESPN's)."""
    if team is None:
        return None
    value = str(team).strip().upper()
    return _ESPN_TO_NHL.get(value, value)


def _annotate_abbrs(row: dict[str, Any], abbr: Any) -> None:
    if abbr:
        text = str(abbr)
        row["team_abbreviation"] = text
        row["team_abbreviation_espn"] = _NHL_TO_ESPN.get(text, text)


def _fold(text: Any) -> str:
    """Lowercase and strip diacritics for name matching."""
    normalized = unicodedata.normalize("NFKD", str(text))
    return normalized.encode("ascii", "ignore").decode().lower()


def _default(value: Any) -> Any:
    """Unwrap the NHL API's ``{"default": ...}`` localized-string wrapper."""
    if isinstance(value, dict):
        return value.get("default")
    return value


# ============================================================
# Public connector functions
# ============================================================


@_guard
def find_nhl_player(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    name = params.get("name")
    if not name:
        raise _NhlStatsError("name is required")
    query = urllib.parse.urlencode({"culture": "en-us", "limit": 20, "q": str(name)})
    data = _request(f"{_SEARCH_BASE}/search/player?{query}")
    players = []
    for p in data if isinstance(data, list) else []:
        row = {
            "player_id": str(p.get("playerId", "")),
            "name": p.get("name"),
            "is_active": bool(p.get("active")),
            "position": p.get("positionCode"),
            "sweater": p.get("sweaterNumber"),
        }
        _annotate_abbrs(row, p.get("teamAbbrev"))
        players.append(row)
    return {
        "provider": "nhl-stats",
        "query": name,
        "players": players,
        "count": len(players),
    }


def _resolve_player(player_id: Any, player: Any) -> str:
    """Return a person id from an id or a name query."""
    if player_id is not None:
        return str(player_id)
    if not player:
        raise _NhlStatsError("Pass player_id or player (a name to search for).")
    result = find_nhl_player({"params": {"name": player}})
    if result.get("error"):
        raise _NhlStatsError(str(result.get("message")))
    needle = _fold(str(player).strip())
    matches = [p for p in result.get("players", []) if needle in _fold(p.get("name", ""))]
    if not matches:
        raise _NhlStatsError(
            f"No NHL player matched {player!r}. Try find_nhl_player to search the registry."
        )
    if len(matches) > 1:
        names = ", ".join(str(m.get("name")) for m in matches[:6])
        raise _NhlStatsError(
            f"{player!r} matched {len(matches)} players ({names}"
            + (", …" if len(matches) > 6 else "")
            + "). Pass player_id, or a more specific name."
        )
    return str(matches[0]["player_id"])


def _normalize_score_game(game: dict[str, Any]) -> dict[str, Any]:
    away, home = game.get("awayTeam") or {}, game.get("homeTeam") or {}
    row = {
        "game_id": str(game.get("id", "")),
        "game_date": game.get("gameDate"),
        "season": str(game.get("season", "")),
        "game_type": game.get("gameType"),
        "status": game.get("gameState"),
        "away_team": _default(away.get("name")) or away.get("abbrev"),
        "home_team": _default(home.get("name")) or home.get("abbrev"),
        "away_abbreviation": away.get("abbrev"),
        "home_abbreviation": home.get("abbrev"),
        "away_score": away.get("score"),
        "home_score": home.get("score"),
        "venue": _default(game.get("venue")),
    }
    return row


@_guard
def get_nhlstats_schedule(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    date = params.get("date")
    raw_team = params.get("team")
    team = _normalize_team(raw_team)

    if team is not None:
        season = _season_str(params.get("season"))
        data = _request(f"{_API_BASE}/club-schedule-season/{team}/{season}")
        games = [_normalize_score_game(g) for g in data.get("games", [])]
        for row in games:
            _annotate_abbrs(row, team)
        result = {
            "provider": "nhl-stats",
            "season": season,
            "team": team,
            "games": games,
            "count": len(games),
        }
        if not games:
            result["warnings"] = [
                f"no games for {team!r} in {season} — the franchise may not have "
                "existed under this abbreviation that season"
            ]
        return result

    if date is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)):
        raise _NhlStatsError(f"Invalid date {date!r}. Use YYYY-MM-DD.")
    data = _request(f"{_API_BASE}/score/{date}" if date else f"{_API_BASE}/score/now")
    games = [_normalize_score_game(g) for g in data.get("games", [])]
    return {
        "provider": "nhl-stats",
        "date": date or data.get("currentDate"),
        "games": games,
        "count": len(games),
    }


@_guard
def get_nhlstats_player_stats(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    person_id = _resolve_player(params.get("player_id"), params.get("player"))

    data = _request(f"{_API_BASE}/player/{person_id}/landing")
    seasons = []
    for row in data.get("seasonTotals", []):
        seasons.append(
            {
                "season": str(row.get("season", "")),
                "league": row.get("leagueAbbrev"),
                "team": _default(row.get("teamName")),
                "game_type": row.get("gameTypeId"),
                "stats": {
                    k: v
                    for k, v in row.items()
                    if k not in ("season", "leagueAbbrev", "teamName", "gameTypeId", "teamCommonName", "teamPlaceNameWithPreposition")
                },
            }
        )
    career = (data.get("careerTotals") or {}).get("regularSeason") or {}
    row = {
        "provider": "nhl-stats",
        "player_id": str(data.get("playerId", person_id)),
        "player": f"{_default(data.get('firstName')) or ''} {_default(data.get('lastName')) or ''}".strip(),
        "position": data.get("position"),
        "is_active": bool(data.get("isActive")),
        "seasons": seasons,
        "career_totals": career or None,
        "count": len(seasons),
    }
    _annotate_abbrs(row, data.get("currentTeamAbbrev"))
    return row


@_guard
def get_nhlstats_play_by_play(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    game_id = _require_game_id(params.get("game_id"))
    limit = params.get("limit")

    data = _request(f"{_API_BASE}/gamecenter/{game_id}/play-by-play")
    names = {}
    for spot in data.get("rosterSpots", []):
        pid = spot.get("playerId")
        if pid is not None:
            names[pid] = f"{_default(spot.get('firstName')) or ''} {_default(spot.get('lastName')) or ''}".strip()

    all_plays = data.get("plays", [])
    total = len(all_plays)
    if limit is not None:
        all_plays = all_plays[: int(limit)]

    plays = []
    for p in all_plays:
        det = p.get("details") or {}
        row = {
            "period": (p.get("periodDescriptor") or {}).get("number"),
            "time_in_period": p.get("timeInPeriod"),
            "event": p.get("typeDescKey"),
            "team_id": det.get("eventOwnerTeamId"),
            "x": det.get("xCoord"),
            "y": det.get("yCoord"),
            "zone": det.get("zoneCode"),
            "shot_type": det.get("shotType"),
            "player": names.get(
                det.get("scoringPlayerId")
                or det.get("shootingPlayerId")
                or det.get("hittingPlayerId")
                or det.get("playerId")
                or det.get("committedByPlayerId")
            ),
            "away_score": det.get("awayScore"),
            "home_score": det.get("homeScore"),
        }
        plays.append(row)

    result = {
        "provider": "nhl-stats",
        "game_id": game_id,
        "plays": plays,
        "count": len(plays),
    }
    if limit is not None and total > len(plays):
        result["truncated"] = True
        result["warnings"] = [f"results truncated to limit={int(limit)} of {total} plays"]
    return result


def _normalize_box_side(side: dict[str, Any], stats: dict[str, Any]) -> dict[str, Any]:
    abbr = side.get("abbrev") or ""
    skaters = []
    for key in ("forwards", "defense"):
        for p in stats.get(key) or []:
            skaters.append(
                {
                    "player_id": str(p.get("playerId", "")),
                    "name": _default(p.get("name")),
                    "position": p.get("position"),
                    "stats": {k: v for k, v in p.items() if k not in ("playerId", "name", "position")},
                }
            )
    goalies = [
        {
            "player_id": str(p.get("playerId", "")),
            "name": _default(p.get("name")),
            "stats": {k: v for k, v in p.items() if k not in ("playerId", "name", "position")},
        }
        for p in stats.get("goalies") or []
    ]
    out = {
        "team_id": str(side.get("id", "")),
        "team_name": _default(side.get("commonName")) or _default(side.get("name")),
        "score": side.get("score"),
        "shots": side.get("sog"),
        "skaters": skaters,
        "goalies": goalies,
    }
    _annotate_abbrs(out, abbr)
    return out


@_guard
def get_nhlstats_boxscore(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    game_id = _require_game_id(params.get("game_id"))

    data = _request(f"{_API_BASE}/gamecenter/{game_id}/boxscore")
    player_stats = data.get("playerByGameStats") or {}
    if not player_stats:
        raise _NhlStatsError(f"No box score for game_id {game_id!r}")

    return {
        "provider": "nhl-stats",
        "game_id": game_id,
        "game_date": data.get("gameDate"),
        "home": _normalize_box_side(data.get("homeTeam") or {}, player_stats.get("homeTeam") or {}),
        "away": _normalize_box_side(data.get("awayTeam") or {}, player_stats.get("awayTeam") or {}),
    }


@_guard
def get_nhlstats_standings(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    date = params.get("date")
    if date is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(date)):
        raise _NhlStatsError(f"Invalid date {date!r}. Use YYYY-MM-DD.")

    data = _request(f"{_API_BASE}/standings/{date}" if date else f"{_API_BASE}/standings/now")
    rows = []
    for tr in data.get("standings", []):
        row = {
            "team_name": _default(tr.get("teamName")),
            "conference": tr.get("conferenceName"),
            "division": tr.get("divisionName"),
            "games_played": tr.get("gamesPlayed"),
            "wins": tr.get("wins"),
            "losses": tr.get("losses"),
            "ot_losses": tr.get("otLosses"),
            "points": tr.get("points"),
            "point_pct": tr.get("pointPctg"),
            "goal_differential": tr.get("goalDifferential"),
            "streak": f"{tr.get('streakCode', '')}{tr.get('streakCount', '')}" or None,
            "division_rank": tr.get("divisionSequence"),
            "wildcard_rank": tr.get("wildcardSequence"),
        }
        _annotate_abbrs(row, _default(tr.get("teamAbbrev")))
        rows.append(row)
    return {
        "provider": "nhl-stats",
        "date": date or data.get("standingsDateTimeUtc", "")[:10] or None,
        "teams": rows,
        "count": len(rows),
    }


@_guard
def get_nhlstats_leaders(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    position = str(params.get("position") or "skater").strip().lower()
    if position not in ("skater", "goalie"):
        raise _NhlStatsError(f"Invalid position {params.get('position')!r}. Valid values: skater, goalie")
    valid = _SKATER_CATEGORIES if position == "skater" else _GOALIE_CATEGORIES
    category = params.get("category") or ("points" if position == "skater" else "wins")
    if category not in valid:
        raise _NhlStatsError(
            f"Invalid category {category!r} for {position}. Valid values: {', '.join(valid)}"
        )
    limit = int(params.get("limit") or 10)

    season = params.get("season")
    season_type = params.get("season_type")
    if season is not None or season_type is not None:
        season = _season_str(season)
        type_key = str(season_type or "regular").strip().lower()
        if type_key not in _SEASON_TYPES:
            raise _NhlStatsError(
                f"Invalid season_type {season_type!r}. Valid values: regular, playoffs"
            )
        path = f"{position}-stats-leaders/{season}/{_SEASON_TYPES[type_key]}"
    else:
        path = f"{position}-stats-leaders/current"

    query = urllib.parse.urlencode({"categories": category, "limit": limit})
    data = _request(f"{_API_BASE}/{path}?{query}")
    leaders = []
    for entry in data.get(category, []):
        row = {
            "rank": len(leaders) + 1,
            "player_id": str(entry.get("id", "")),
            "player": f"{_default(entry.get('firstName')) or ''} {_default(entry.get('lastName')) or ''}".strip(),
            "position": entry.get("position"),
            "value": entry.get("value"),
        }
        _annotate_abbrs(row, entry.get("teamAbbrev"))
        leaders.append(row)
    return {
        "provider": "nhl-stats",
        "position": position,
        "category": category,
        "season": season,
        "leaders": leaders,
        "count": len(leaders),
    }
