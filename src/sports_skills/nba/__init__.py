"""NBA data — scores, standings, rosters, schedules, game summaries, and more.

## Data Sources (Priority Order)

**Live game data** uses NBA CDN (cdn.nba.com) as primary source with ESPN fallback:
- ``get_live_scoreboard()`` — Real-time scores, game clock, leaders
- ``get_live_boxscore(game_id)`` — Real-time box scores, player stats
- ``get_live_playbyplay(game_id)`` — Real-time play-by-play

If NBA CDN is unavailable, these automatically fall back to ESPN.

**Static data** uses ESPN directly:
- Standings, rosters, schedules, team stats, news, etc.

No API keys required. Zero config.
"""

from __future__ import annotations

from sports_skills._response import wrap
from sports_skills.nba._cdn import (
    get_live_boxscore as _get_live_boxscore,
)
from sports_skills.nba._cdn import (
    get_live_playbyplay as _get_live_playbyplay,
)
from sports_skills.nba._cdn import (
    get_live_scoreboard as _get_live_scoreboard,
)
from sports_skills.nba._cdn import (
    get_player_live_stats as _get_player_live_stats,
)
from sports_skills.nba._connector import (
    get_depth_chart as _get_depth_chart,
)
from sports_skills.nba._connector import (
    get_futures as _get_futures,
)
from sports_skills.nba._connector import (
    get_game_summary as _get_game_summary,
)
from sports_skills.nba._connector import (
    get_injuries as _get_injuries,
)
from sports_skills.nba._connector import (
    get_leaders as _get_leaders,
)
from sports_skills.nba._connector import (
    get_news as _get_news,
)
from sports_skills.nba._connector import (
    get_play_by_play as _get_play_by_play,
)
from sports_skills.nba._connector import (
    get_player_stats as _get_player_stats,
)
from sports_skills.nba._connector import (
    get_schedule as _get_schedule,
)
from sports_skills.nba._connector import (
    get_scoreboard as _get_scoreboard,
)
from sports_skills.nba._connector import (
    get_standings as _get_standings,
)
from sports_skills.nba._connector import (
    get_team_roster as _get_team_roster,
)
from sports_skills.nba._connector import (
    get_team_schedule as _get_team_schedule,
)
from sports_skills.nba._connector import (
    get_team_stats as _get_team_stats,
)
from sports_skills.nba._connector import (
    get_teams as _get_teams,
)
from sports_skills.nba._connector import (
    get_transactions as _get_transactions,
)
from sports_skills.nba._connector import (
    get_win_probability as _get_win_probability,
)
from sports_skills.nba._stats import (
    find_nba_player as _find_nba_player,
)
from sports_skills.nba._stats import (
    get_nbastats_advanced_boxscore as _get_nbastats_advanced_boxscore,
)
from sports_skills.nba._stats import (
    get_nbastats_game_log as _get_nbastats_game_log,
)
from sports_skills.nba._stats import (
    get_nbastats_play_by_play as _get_nbastats_play_by_play,
)
from sports_skills.nba._stats import (
    get_nbastats_player_career as _get_nbastats_player_career,
)
from sports_skills.nba._stats import (
    get_nbastats_shot_chart as _get_nbastats_shot_chart,
)
from sports_skills.nba._stats import (
    get_nbastats_team_stats as _get_nbastats_team_stats,
)


def _params(**kwargs):
    """Build params dict, filtering out None values."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def get_scoreboard(*, date: str | None = None) -> dict:
    """Get live/recent NBA scores.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.
    """
    return wrap(_get_scoreboard(_params(date=date)))


def get_standings(*, season: int | None = None) -> dict:
    """Get NBA standings by conference.

    Args:
        season: Season year (e.g. 2025). Defaults to current.
    """
    return wrap(_get_standings(_params(season=season)))


def get_teams() -> dict:
    """Get all 30 NBA teams."""
    return wrap(_get_teams(_params()))


def get_team_roster(*, team_id: str) -> dict:
    """Get full roster for an NBA team.

    Args:
        team_id: ESPN team ID (e.g. "13" for Los Angeles Lakers).
    """
    return wrap(_get_team_roster(_params(team_id=team_id)))


def get_team_schedule(*, team_id: str, season: int | None = None) -> dict:
    """Get schedule for a specific NBA team.

    Args:
        team_id: ESPN team ID.
        season: Season year. Defaults to current.
    """
    return wrap(_get_team_schedule(_params(team_id=team_id, season=season)))


def get_game_summary(*, event_id: str) -> dict:
    """Get detailed game summary with box score and scoring plays.

    Args:
        event_id: ESPN event ID.
    """
    return wrap(_get_game_summary(_params(event_id=event_id)))


def get_leaders(*, season: int | None = None) -> dict:
    """Get NBA statistical leaders (points, rebounds, assists, etc.).

    Args:
        season: Season year. Defaults to current.
    """
    return wrap(_get_leaders(_params(season=season)))


def get_news(*, team_id: str | None = None) -> dict:
    """Get NBA news articles.

    Args:
        team_id: Optional ESPN team ID to filter news by team.
    """
    return wrap(_get_news(_params(team_id=team_id)))


def get_schedule(*, date: str | None = None, season: int | None = None) -> dict:
    """Get NBA schedule.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.
        season: Season year. Defaults to current.
    """
    return wrap(_get_schedule(_params(date=date, season=season)))


def get_play_by_play(*, event_id: str) -> dict:
    """Get full play-by-play log for an NBA game.

    Args:
        event_id: ESPN event ID.
    """
    return wrap(_get_play_by_play(_params(event_id=event_id)))


def get_win_probability(*, event_id: str) -> dict:
    """Get win probability timeline for an NBA game.

    Args:
        event_id: ESPN event ID.
    """
    return wrap(_get_win_probability(_params(event_id=event_id)))


def get_injuries() -> dict:
    """Get current NBA injury report for all teams."""
    return wrap(_get_injuries(_params()))


def get_transactions(*, limit: int | None = None) -> dict:
    """Get recent NBA transactions (trades, signings, releases).

    Args:
        limit: Max number of transactions. Defaults to 50.
    """
    return wrap(_get_transactions(_params(limit=limit)))


def get_futures(*, limit: int | None = None, season_year: int | None = None) -> dict:
    """Get NBA futures odds (championship winner, MVP, etc.).

    Args:
        limit: Max entries per futures market. Defaults to 10.
        season_year: Season year. Defaults to current.
    """
    return wrap(_get_futures(_params(limit=limit, season_year=season_year)))


def get_depth_chart(*, team_id: str) -> dict:
    """Get NBA depth chart for a team.

    Args:
        team_id: ESPN team ID.
    """
    return wrap(_get_depth_chart(_params(team_id=team_id)))


def get_team_stats(*, team_id: str, season_year: int | None = None, season_type: int | None = None) -> dict:
    """Get NBA team season statistics.

    Args:
        team_id: ESPN team ID.
        season_year: Season year. Defaults to current.
        season_type: 2 = regular season (default), 3 = postseason.
    """
    return wrap(_get_team_stats(_params(team_id=team_id, season_year=season_year, season_type=season_type)))


def get_player_stats(*, player_id: str, season_year: int | None = None, season_type: int | None = None) -> dict:
    """Get NBA player season statistics.

    Args:
        player_id: ESPN athlete ID.
        season_year: Season year. Defaults to current.
        season_type: 2 = regular season (default), 3 = postseason.
    """
    return wrap(_get_player_stats(_params(player_id=player_id, season_year=season_year, season_type=season_type)))


# ============================================================
# NBA CDN — Real-Time Live Data
# ============================================================


def get_live_scoreboard() -> dict:
    """Get real-time NBA scores. Primary: cdn.nba.com, Fallback: ESPN.

    Uses NBA CDN for fastest live updates. Automatically falls back to
    ESPN if CDN is unavailable or returns empty data.
    """
    try:
        result = _get_live_scoreboard()
        if result and result.get("games"):
            return wrap(result)
    except Exception:
        pass
    # Fallback to ESPN
    return get_scoreboard()


def get_live_boxscore(*, game_id: str) -> dict:
    """Get real-time NBA box score. Primary: cdn.nba.com, Fallback: ESPN.

    Uses NBA CDN for fastest live updates. Automatically falls back to
    ESPN game summary if CDN is unavailable.

    Args:
        game_id: NBA game ID (e.g. "0022400001"). For ESPN fallback,
                 this is converted to event_id format.
    """
    try:
        result = _get_live_boxscore(_params(game_id=game_id))
        if result and result.get("game_info"):
            return wrap(result)
    except Exception:
        pass
    # Fallback to ESPN - game_id format differs, try direct
    return get_game_summary(event_id=game_id)


def get_live_playbyplay(*, game_id: str, limit: int = 25, scoring_only: bool = False) -> dict:
    """Get real-time NBA play-by-play (most recent plays first).

    Uses NBA CDN for fastest live updates. Returns plays in reverse
    chronological order so you see what just happened.

    Args:
        game_id: NBA game ID (e.g. "0022400001").
        limit: Maximum plays to return (default 25).
        scoring_only: Only return scoring plays (default False).
    """
    try:
        result = _get_live_playbyplay(_params(game_id=game_id, limit=limit, scoring_only=scoring_only))
        if result and result.get("actions"):
            return wrap(result)
    except Exception:
        pass
    # Fallback to ESPN
    return get_play_by_play(event_id=game_id)


def get_player_live_stats(*, player_name: str) -> dict:
    """Get real-time stats for a specific NBA player in today's games.

    Searches all live/completed games to find the player and returns
    their full box score line including shooting splits, minutes,
    steals, blocks, and plus/minus.

    Args:
        player_name: Player name to search for (e.g. "Luka", "LeBron James").
                     Partial matches supported.
    """
    return wrap(_get_player_live_stats(_params(player_name=player_name)))


# ============================================================
# NBA Stats backend (stats.nba.com) — analytics layer
# ============================================================


def find_nba_player(*, name: str) -> dict:
    """Search the NBA Stats player registry (all eras) by name.

    Returns NBA person ids, which the other get_nbastats_* functions take as
    ``player_id``. These are NBA.com ids, unrelated to ESPN athlete ids.

    Args:
        name: Full or partial player name (e.g. "Jokic", "LeBron James").
    """
    return wrap(_find_nba_player(_params(name=name)))


def get_nbastats_game_log(
    *,
    season: int | str | None = None,
    team: str | None = None,
    season_type: str | None = None,
) -> dict:
    """Get the league-wide game log via the NBA Stats backend.

    One row per team per game, with the 10-digit NBA game ids the other
    get_nbastats_* functions take. History reaches back to the 1946-47 season.
    Rows carry both NBA.com and ESPN team abbreviations; join to the ESPN
    functions on (game_date, team abbreviations) — the two id systems are
    unrelated.

    Args:
        season: Season starting year (e.g. 2024) or NBA form ("2024-25").
            Defaults to the current season.
        team: Optional team abbreviation filter. ESPN spellings ("GS", "NY",
            "NO", "SA", "UTAH", "WSH") are translated to NBA.com's.
        season_type: "regular" (default), "playoffs", "preseason", or "playin".
    """
    return wrap(
        _get_nbastats_game_log(_params(season=season, team=team, season_type=season_type))
    )


def get_nbastats_player_career(
    *,
    player_id: str | None = None,
    player: str | None = None,
    per_mode: str | None = None,
) -> dict:
    """Get a player's career, season by season, via the NBA Stats backend.

    Args:
        player_id: NBA person id (e.g. "2544"). Find it with find_nba_player.
        player: Player name to resolve instead of player_id. Must match exactly
            one player; ambiguous names return the candidates.
        per_mode: "totals" (default), "per_game", or "per_36".
    """
    return wrap(
        _get_nbastats_player_career(
            _params(player_id=player_id, player=player, per_mode=per_mode)
        )
    )


def get_nbastats_team_stats(
    *,
    season: int | str | None = None,
    team: str | None = None,
    measure: str | None = None,
    per_mode: str | None = None,
    season_type: str | None = None,
) -> dict:
    """Get league-wide team stats via the NBA Stats backend.

    The "advanced" measure adds ratings, pace, and true-shooting — data the
    ESPN-backed get_team_stats does not provide.

    Args:
        season: Season starting year (e.g. 2024) or NBA form ("2024-25").
            Defaults to the current season.
        team: Optional team abbreviation filter. ESPN spellings are translated.
        measure: "base" (default), "advanced", "four_factors", "misc",
            "scoring", "opponent", or "defense".
        per_mode: "totals" (default), "per_game", or "per_36".
        season_type: "regular" (default), "playoffs", "preseason", or "playin".
    """
    return wrap(
        _get_nbastats_team_stats(
            _params(
                season=season,
                team=team,
                measure=measure,
                per_mode=per_mode,
                season_type=season_type,
            )
        )
    )


def get_nbastats_shot_chart(
    *,
    player_id: str | None = None,
    player: str | None = None,
    season: int | str | None = None,
    season_type: str | None = None,
    limit: int | None = None,
) -> dict:
    """Get a player's shot chart (court x/y per attempt) via the NBA Stats backend.

    Coordinates are in tenths of feet from the basket (loc_x lateral,
    loc_y toward half court).

    Args:
        player_id: NBA person id. Find it with find_nba_player.
        player: Player name to resolve instead of player_id.
        season: Season starting year (e.g. 2024) or NBA form ("2024-25").
            Defaults to the current season.
        season_type: "regular" (default), "playoffs", "preseason", or "playin".
        limit: Maximum shots to return; truncation is flagged in the response.
    """
    return wrap(
        _get_nbastats_shot_chart(
            _params(
                player_id=player_id,
                player=player,
                season=season,
                season_type=season_type,
                limit=limit,
            )
        )
    )


def get_nbastats_play_by_play(*, game_id: str, limit: int | None = None) -> dict:
    """Get play-by-play with court coordinates via the NBA Stats backend.

    Unlike the live CDN feed, this covers completed games from past seasons.

    Args:
        game_id: 10-digit NBA game id from get_nbastats_game_log
            (e.g. "0022400061"). Not an ESPN event id.
        limit: Maximum actions to return; truncation is flagged in the response.
    """
    return wrap(_get_nbastats_play_by_play(_params(game_id=game_id, limit=limit)))


def get_nbastats_advanced_boxscore(*, game_id: str) -> dict:
    """Get the advanced box score (ratings, pace, usage) via the NBA Stats backend.

    Args:
        game_id: 10-digit NBA game id from get_nbastats_game_log
            (e.g. "0022400061"). Not an ESPN event id.
    """
    return wrap(_get_nbastats_advanced_boxscore(_params(game_id=game_id)))
