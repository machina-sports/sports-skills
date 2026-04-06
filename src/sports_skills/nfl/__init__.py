"""NFL data — scores, standings, rosters, schedules, game summaries, and more.

Wraps ESPN public endpoints. No API keys required. Zero config.
"""

from __future__ import annotations

from sports_skills._response import wrap
from sports_skills.nfl._connector import (
    get_depth_chart as _get_depth_chart,
)
from sports_skills.nfl._connector import (
    get_futures as _get_futures,
)
from sports_skills.nfl._connector import (
    get_game_summary as _get_game_summary,
)
from sports_skills.nfl._connector import (
    get_injuries as _get_injuries,
)
from sports_skills.nfl._connector import (
    get_leaders as _get_leaders,
)
from sports_skills.nfl._connector import (
    get_news as _get_news,
)
from sports_skills.nfl._connector import (
    get_play_by_play as _get_play_by_play,
)
from sports_skills.nfl._connector import (
    get_player_stats as _get_player_stats,
)
from sports_skills.nfl._connector import (
    get_schedule as _get_schedule,
)
from sports_skills.nfl._connector import (
    get_scoreboard as _get_scoreboard,
)
from sports_skills.nfl._connector import (
    get_standings as _get_standings,
)
from sports_skills.nfl._connector import (
    get_team_roster as _get_team_roster,
)
from sports_skills.nfl._connector import (
    get_team_schedule as _get_team_schedule,
)
from sports_skills.nfl._connector import (
    get_team_stats as _get_team_stats,
)
from sports_skills.nfl._connector import (
    get_teams as _get_teams,
)
from sports_skills.nfl._connector import (
    get_transactions as _get_transactions,
)
from sports_skills.nfl._connector import (
    get_win_probability as _get_win_probability,
)
from sports_skills.nfl._nflverse import (
    get_nflverse_play_by_play as _get_nflverse_play_by_play,
)
from sports_skills.nfl._nflverse import (
    get_nflverse_player_stats as _get_nflverse_player_stats,
)
from sports_skills.nfl._nflverse import (
    get_nflverse_schedule as _get_nflverse_schedule,
)
from sports_skills.nfl._nflverse import (
    get_nflverse_team_stats as _get_nflverse_team_stats,
)
from sports_skills.nfl._nflverse import (
    get_nflverse_weekly_rosters as _get_nflverse_weekly_rosters,
)


def _params(**kwargs):
    """Build params dict, filtering out None values."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def get_scoreboard(*, date: str | None = None, week: int | None = None) -> dict:
    """Get live/recent NFL scores.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.
        week: NFL week number (1-18 regular season, 19+ postseason).
    """
    return wrap(_get_scoreboard(_params(date=date, week=week)))


def get_standings(*, season: int | None = None) -> dict:
    """Get NFL standings by conference and division.

    Args:
        season: Season year (e.g. 2025). Defaults to current.
    """
    return wrap(_get_standings(_params(season=season)))


def get_teams() -> dict:
    """Get all 32 NFL teams."""
    return wrap(_get_teams(_params()))


def get_team_roster(*, team_id: str) -> dict:
    """Get full roster for an NFL team.

    Args:
        team_id: ESPN team ID (e.g. "12" for Kansas City Chiefs).
    """
    return wrap(_get_team_roster(_params(team_id=team_id)))


def get_team_schedule(*, team_id: str, season: int | None = None) -> dict:
    """Get schedule for a specific NFL team.

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
    """Get NFL statistical leaders (passing, rushing, receiving, etc.).

    Args:
        season: Season year. Defaults to current.
    """
    return wrap(_get_leaders(_params(season=season)))


def get_news(*, team_id: str | None = None) -> dict:
    """Get NFL news articles.

    Args:
        team_id: Optional ESPN team ID to filter news by team.
    """
    return wrap(_get_news(_params(team_id=team_id)))


def get_schedule(*, season: int | None = None, week: int | None = None) -> dict:
    """Get NFL season schedule.

    Args:
        season: Season year. Defaults to current.
        week: NFL week number. Defaults to current week.
    """
    return wrap(_get_schedule(_params(season=season, week=week)))


def get_play_by_play(*, event_id: str) -> dict:
    """Get drive-by-drive play-by-play data for an NFL game.

    Args:
        event_id: ESPN event ID.
    """
    return wrap(_get_play_by_play(_params(event_id=event_id)))


def get_win_probability(*, event_id: str) -> dict:
    """Get win probability timeline for an NFL game.

    Args:
        event_id: ESPN event ID.
    """
    return wrap(_get_win_probability(_params(event_id=event_id)))


def get_injuries() -> dict:
    """Get current NFL injury report for all teams."""
    return wrap(_get_injuries(_params()))


def get_transactions(*, limit: int | None = None) -> dict:
    """Get recent NFL transactions (trades, signings, releases).

    Args:
        limit: Max number of transactions. Defaults to 50.
    """
    return wrap(_get_transactions(_params(limit=limit)))


def get_futures(*, limit: int | None = None, season_year: int | None = None) -> dict:
    """Get NFL futures odds (Super Bowl winner, MVP, etc.).

    Args:
        limit: Max entries per futures market. Defaults to 10.
        season_year: Season year. Defaults to current.
    """
    return wrap(_get_futures(_params(limit=limit, season_year=season_year)))


def get_depth_chart(*, team_id: str) -> dict:
    """Get NFL depth chart for a team.

    Args:
        team_id: ESPN team ID.
    """
    return wrap(_get_depth_chart(_params(team_id=team_id)))


def get_team_stats(
    *, team_id: str, season_year: int | None = None, season_type: int | None = None
) -> dict:
    """Get NFL team season statistics.

    Args:
        team_id: ESPN team ID.
        season_year: Season year. Defaults to current.
        season_type: 2 = regular season (default), 3 = postseason.
    """
    return wrap(
        _get_team_stats(
            _params(team_id=team_id, season_year=season_year, season_type=season_type)
        )
    )


def get_player_stats(
    *, player_id: str, season_year: int | None = None, season_type: int | None = None
) -> dict:
    """Get NFL player season statistics.

    Args:
        player_id: ESPN athlete ID.
        season_year: Season year. Defaults to current.
        season_type: 2 = regular season (default), 3 = postseason.
    """
    return wrap(
        _get_player_stats(
            _params(
                player_id=player_id, season_year=season_year, season_type=season_type
            )
        )
    )


def get_nflverse_schedule(*, season: int | None = None, week: int | None = None) -> dict:
    """Get NFL schedule via nflverse backend.

    Args:
        season: Season year. Defaults to current NFL season.
        week: Optional NFL week number.
    """
    return wrap(_get_nflverse_schedule(_params(season=season, week=week)))


def get_nflverse_weekly_rosters(
    *, season: int | None = None, week: int | None = None, team: str | None = None
) -> dict:
    """Get weekly NFL rosters via nflverse backend.

    Args:
        season: Season year. Defaults to current NFL season.
        week: Optional NFL week number.
        team: Optional team abbreviation filter (e.g. "KC").
    """
    return wrap(
        _get_nflverse_weekly_rosters(_params(season=season, week=week, team=team))
    )


def get_nflverse_player_stats(
    *,
    season: int | None = None,
    player_id: str | None = None,
    team: str | None = None,
    position: str | None = None,
) -> dict:
    """Get NFL player stats via nflverse backend.

    Args:
        season: Season year. Defaults to current NFL season.
        player_id: Optional nflverse/GSIS player identifier.
        team: Optional team abbreviation filter.
        position: Optional position filter.
    """
    return wrap(
        _get_nflverse_player_stats(
            _params(season=season, player_id=player_id, team=team, position=position)
        )
    )


def get_nflverse_team_stats(
    *, season: int | None = None, team: str | None = None, week: int | None = None
) -> dict:
    """Get NFL team stats via nflverse backend.

    Args:
        season: Season year. Defaults to current NFL season.
        team: Optional team abbreviation filter.
        week: Optional week filter when the backend exposes weekly rows.
    """
    return wrap(_get_nflverse_team_stats(_params(season=season, team=team, week=week)))


def get_nflverse_play_by_play(
    *,
    season: int | None = None,
    week: int | None = None,
    team: str | None = None,
    game_id: str | None = None,
    limit: int | None = None,
) -> dict:
    """Get NFL play-by-play via nflverse backend.

    Args:
        season: Season year. Defaults to current NFL season.
        week: Optional NFL week number.
        team: Optional team abbreviation filter.
        game_id: Optional nflverse game identifier.
        limit: Optional max number of plays to return.
    """
    return wrap(
        _get_nflverse_play_by_play(
            _params(season=season, week=week, team=team, game_id=game_id, limit=limit)
        )
    )
