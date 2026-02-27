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


def get_team_stats(
    *, team_id: str, season_year: int | None = None, season_type: int | None = None
) -> dict:
    """Get NBA team season statistics.

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
    """Get NBA player season statistics.

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


def get_live_playbyplay(*, game_id: str) -> dict:
    """Get real-time NBA play-by-play. Primary: cdn.nba.com, Fallback: ESPN.

    Uses NBA CDN for fastest live updates. Automatically falls back to
    ESPN play-by-play if CDN is unavailable.

    Args:
        game_id: NBA game ID (e.g. "0022400001"). For ESPN fallback,
                 this is converted to event_id format.
    """
    try:
        result = _get_live_playbyplay(_params(game_id=game_id))
        if result and result.get("actions"):
            return wrap(result)
    except Exception:
        pass
    # Fallback to ESPN
    return get_play_by_play(event_id=game_id)
