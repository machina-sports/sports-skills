"""WNBA data — scores, standings, rosters, schedules, game summaries, and more.

Wraps ESPN public endpoints. No API keys required. Zero config.
"""

from __future__ import annotations

from sports_skills._response import wrap
from sports_skills.wnba._connector import (
    get_futures as _get_futures,
)
from sports_skills.wnba._connector import (
    get_game_summary as _get_game_summary,
)
from sports_skills.wnba._connector import (
    get_injuries as _get_injuries,
)
from sports_skills.wnba._connector import (
    get_leaders as _get_leaders,
)
from sports_skills.wnba._connector import (
    get_news as _get_news,
)
from sports_skills.wnba._connector import (
    get_play_by_play as _get_play_by_play,
)
from sports_skills.wnba._connector import (
    get_player_stats as _get_player_stats,
)
from sports_skills.wnba._connector import (
    get_schedule as _get_schedule,
)
from sports_skills.wnba._connector import (
    get_scoreboard as _get_scoreboard,
)
from sports_skills.wnba._connector import (
    get_standings as _get_standings,
)
from sports_skills.wnba._connector import (
    get_team_roster as _get_team_roster,
)
from sports_skills.wnba._connector import (
    get_team_schedule as _get_team_schedule,
)
from sports_skills.wnba._connector import (
    get_team_stats as _get_team_stats,
)
from sports_skills.wnba._connector import (
    get_teams as _get_teams,
)
from sports_skills.wnba._connector import (
    get_transactions as _get_transactions,
)
from sports_skills.wnba._connector import (
    get_win_probability as _get_win_probability,
)


def _params(**kwargs):
    """Build params dict, filtering out None values."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def get_scoreboard(*, date: str | None = None) -> dict:
    """Get live/recent WNBA scores.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.
    """
    return wrap(_get_scoreboard(_params(date=date)))


def get_standings(*, season: int | None = None) -> dict:
    """Get WNBA standings by conference.

    Args:
        season: Season year (e.g. 2025). Defaults to current.
    """
    return wrap(_get_standings(_params(season=season)))


def get_teams() -> dict:
    """Get all WNBA teams."""
    return wrap(_get_teams(_params()))


def get_team_roster(*, team_id: str) -> dict:
    """Get full roster for a WNBA team.

    Args:
        team_id: ESPN team ID (e.g. "14" for Las Vegas Aces).
    """
    return wrap(_get_team_roster(_params(team_id=team_id)))


def get_team_schedule(*, team_id: str, season: int | None = None, season_type: str | None = None) -> dict:
    """Get schedule for a specific WNBA team.

    Args:
        team_id: ESPN team ID.
        season: Season year. Defaults to current.
        season_type: "regular", "postseason" (alias "playoffs"), "preseason", or "all"
            (regular + postseason). Omitted, ESPN's default (every game, each row's
            ``season_type`` says which) is returned.
    """
    return wrap(_get_team_schedule(_params(team_id=team_id, season=season, season_type=season_type)))


def get_game_summary(*, event_id: str) -> dict:
    """Get detailed game summary with box score and scoring plays.

    Args:
        event_id: ESPN event ID.
    """
    return wrap(_get_game_summary(_params(event_id=event_id)))


def get_leaders(*, season: int | None = None) -> dict:
    """Get WNBA statistical leaders (points, rebounds, assists, etc.).

    Args:
        season: Season year. Defaults to current.
    """
    return wrap(_get_leaders(_params(season=season)))


def get_news(*, team_id: str | None = None) -> dict:
    """Get WNBA news articles.

    Args:
        team_id: Optional ESPN team ID to filter news by team.
    """
    return wrap(_get_news(_params(team_id=team_id)))


def get_schedule(*, date: str | None = None, season: int | None = None) -> dict:
    """Get WNBA schedule.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.
        season: Season year. Defaults to current.
    """
    return wrap(_get_schedule(_params(date=date, season=season)))


def get_play_by_play(*, event_id: str) -> dict:
    """Get full play-by-play log for a WNBA game.

    Args:
        event_id: ESPN event ID.
    """
    return wrap(_get_play_by_play(_params(event_id=event_id)))


def get_win_probability(*, event_id: str) -> dict:
    """Get win probability timeline for a WNBA game.

    Args:
        event_id: ESPN event ID.
    """
    return wrap(_get_win_probability(_params(event_id=event_id)))


def get_injuries() -> dict:
    """Get current WNBA injury report for all teams."""
    return wrap(_get_injuries(_params()))


def get_transactions(*, limit: int | None = None) -> dict:
    """Get recent WNBA transactions (trades, signings, releases).

    Args:
        limit: Max number of transactions. Defaults to 50.
    """
    return wrap(_get_transactions(_params(limit=limit)))


def get_futures(*, limit: int | None = None, season_year: int | None = None) -> dict:
    """Get WNBA futures odds (championship winner, MVP, etc.).

    Args:
        limit: Max entries per futures market. Defaults to 10.
        season_year: Season year. Defaults to current.
    """
    return wrap(_get_futures(_params(limit=limit, season_year=season_year)))


def get_team_stats(
    *, team_id: str, season_year: int | None = None, season_type: int | None = None
) -> dict:
    """Get WNBA team season statistics.

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
    """Get WNBA player season statistics.

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
