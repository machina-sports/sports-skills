"""College Football (CFB) data — scores, standings, rosters, schedules, rankings, and more.

Wraps ESPN public endpoints. No API keys required. Zero config.
"""

from __future__ import annotations

from sports_skills._ncaa import (
    fetch_boxscore as _fetch_ncaa_boxscore,
)
from sports_skills._ncaa import (
    fetch_game_info as _fetch_ncaa_game_info,
)
from sports_skills._ncaa import (
    fetch_play_by_play as _fetch_ncaa_play_by_play,
)
from sports_skills._ncaa import (
    fetch_schedule as _fetch_ncaa_schedule,
)
from sports_skills._ncaa import (
    fetch_schools as _fetch_ncaa_schools,
)
from sports_skills._ncaa import (
    fetch_scoreboard as _fetch_ncaa_scoreboard,
)
from sports_skills._ncaa import (
    fetch_scoring_summary as _fetch_ncaa_scoring_summary,
)
from sports_skills._ncaa import (
    guard as _ncaa_guard,
)
from sports_skills._response import wrap
from sports_skills.cfb._connector import (
    get_futures as _get_futures,
)
from sports_skills.cfb._connector import (
    get_game_summary as _get_game_summary,
)
from sports_skills.cfb._connector import (
    get_injuries as _get_injuries,
)
from sports_skills.cfb._connector import (
    get_news as _get_news,
)
from sports_skills.cfb._connector import (
    get_play_by_play as _get_play_by_play,
)
from sports_skills.cfb._connector import (
    get_player_stats as _get_player_stats,
)
from sports_skills.cfb._connector import (
    get_rankings as _get_rankings,
)
from sports_skills.cfb._connector import (
    get_schedule as _get_schedule,
)
from sports_skills.cfb._connector import (
    get_scoreboard as _get_scoreboard,
)
from sports_skills.cfb._connector import (
    get_standings as _get_standings,
)
from sports_skills.cfb._connector import (
    get_team_roster as _get_team_roster,
)
from sports_skills.cfb._connector import (
    get_team_schedule as _get_team_schedule,
)
from sports_skills.cfb._connector import (
    get_team_stats as _get_team_stats,
)
from sports_skills.cfb._connector import (
    get_teams as _get_teams,
)


def _params(**kwargs):
    """Build params dict, filtering out None values."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def get_scoreboard(*, date: str | None = None, week: int | None = None, group: int | None = None, limit: int | None = None) -> dict:
    """Get live/recent college football scores.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.
        week: CFB week number.
        group: Conference group ID to filter by.
        limit: Max number of events to return.
    """
    return wrap(_get_scoreboard(_params(date=date, week=week, group=group, limit=limit)))


def get_standings(*, season: int | None = None, group: int | None = None) -> dict:
    """Get college football standings by conference.

    Args:
        season: Season year (e.g. 2025). Defaults to current.
        group: Conference ID to filter (e.g. 1=ACC, 4=Big 12, 8=SEC, 9=Big Ten, 15=Pac-12).
    """
    return wrap(_get_standings(_params(season=season, group=group)))


def get_teams() -> dict:
    """Get all FBS college football teams."""
    return wrap(_get_teams(_params()))


def get_team_roster(*, team_id: str) -> dict:
    """Get full roster for a college football team.

    Args:
        team_id: ESPN team ID (e.g. "333" for Alabama).
    """
    return wrap(_get_team_roster(_params(team_id=team_id)))


def get_team_schedule(*, team_id: str, season: int | None = None) -> dict:
    """Get schedule for a specific college football team.

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


def get_rankings(*, season: int | None = None, week: int | None = None) -> dict:
    """Get college football rankings (AP Top 25, Coaches Poll, CFP).

    Args:
        season: Season year. Defaults to current.
        week: Week number for historical rankings.
    """
    return wrap(_get_rankings(_params(season=season, week=week)))


def get_news(*, team_id: str | None = None) -> dict:
    """Get college football news articles.

    Args:
        team_id: Optional ESPN team ID to filter news by team.
    """
    return wrap(_get_news(_params(team_id=team_id)))


def get_schedule(*, season: int | None = None, week: int | None = None, group: int | None = None) -> dict:
    """Get college football schedule.

    Args:
        season: Season year. Defaults to current.
        week: CFB week number.
        group: Conference group ID to filter by.
    """
    return wrap(_get_schedule(_params(season=season, week=week, group=group)))


def get_play_by_play(*, event_id: str) -> dict:
    """Get drive-by-drive play-by-play data for a college football game.

    Args:
        event_id: ESPN event ID.
    """
    return wrap(_get_play_by_play(_params(event_id=event_id)))


def get_injuries() -> dict:
    """Get current college football injury report for all teams."""
    return wrap(_get_injuries(_params()))


def get_futures(*, limit: int | None = None, season_year: int | None = None) -> dict:
    """Get college football futures odds (national championship, Heisman, etc.).

    Args:
        limit: Max entries per futures market. Defaults to 10.
        season_year: Season year. Defaults to current.
    """
    return wrap(_get_futures(_params(limit=limit, season_year=season_year)))


def get_team_stats(
    *, team_id: str, season_year: int | None = None, season_type: int | None = None
) -> dict:
    """Get college football team season statistics.

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
    """Get college football player season statistics.

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
# Official NCAA backend (data.ncaa.com + sdataprod.ncaa.com)
# ============================================================

def _ncaa_call(fetch, *args, **kwargs):
    """Run one shared-NCAA fetcher through the agent-safe error guard."""
    return _ncaa_guard(lambda _rd: fetch(*args, **kwargs))({})


def _ncaa_scoreboard(sport, division, **kw):
    return _ncaa_call(_fetch_ncaa_scoreboard, sport, division, **kw)


def _ncaa_schedule(sport, division, **kw):
    return _ncaa_call(_fetch_ncaa_schedule, sport, division, **kw)


def _ncaa_game_info(game_id):
    return _ncaa_call(_fetch_ncaa_game_info, game_id)


def _ncaa_boxscore(sport, game_id):
    return _ncaa_call(_fetch_ncaa_boxscore, sport, game_id)


def _ncaa_play_by_play(sport, game_id, limit):
    return _ncaa_call(_fetch_ncaa_play_by_play, sport, game_id, limit)


def _ncaa_scoring_summary(game_id):
    return _ncaa_call(_fetch_ncaa_scoring_summary, game_id)


def _ncaa_schools(query):
    return _ncaa_call(_fetch_ncaa_schools, query)



def get_ncaa_scoreboard(*, week: int, division: str | None = None, season: int | None = None) -> dict:
    """Get the official NCAA scoreboard — including FCS, which ESPN barely covers.

    Rows carry NCAA game ids, which the other get_ncaa_* functions take. NCAA
    ids and ESPN event ids share nothing; join on game date plus team names.

    Args:
        week: Week number (1-20; 16+ are the playoff).
        division: "fbs" (default) or "fcs".
        season: Season starting year (e.g. 2024). Defaults to the current season.
    """
    return wrap(_ncaa_scoreboard("football", division, year=season, week=week))


def get_ncaa_schedule(*, division: str | None = None, season: int | None = None) -> dict:
    """Get which weeks have games, from the official NCAA schedule index.

    Args:
        division: "fbs" (default) or "fcs".
        season: Season starting year (e.g. 2024). Defaults to the current season.
    """
    return wrap(_ncaa_schedule("football", division, year=season))


def get_ncaa_game(*, game_id: str) -> dict:
    """Get official NCAA game information for one game.

    Args:
        game_id: NCAA game id from get_ncaa_scoreboard (e.g. "6306261").
            Not an ESPN event id.
    """
    return wrap(_ncaa_game_info(game_id))


def get_ncaa_boxscore(*, game_id: str) -> dict:
    """Get the official NCAA box score for one game.

    Args:
        game_id: NCAA game id from get_ncaa_scoreboard (e.g. "6306261").
            Not an ESPN event id.
    """
    return wrap(_ncaa_boxscore("football", game_id))


def get_ncaa_play_by_play(*, game_id: str, limit: int | None = None) -> dict:
    """Get official NCAA play-by-play with drive context for one game.

    Args:
        game_id: NCAA game id from get_ncaa_scoreboard (e.g. "6306261").
            Not an ESPN event id.
        limit: Maximum plays to return; truncation is flagged in the response.
    """
    return wrap(_ncaa_play_by_play("football", game_id, limit))


def get_ncaa_scoring_summary(*, game_id: str) -> dict:
    """Get the official NCAA scoring summary for one game.

    Args:
        game_id: NCAA game id from get_ncaa_scoreboard (e.g. "6306261").
            Not an ESPN event id.
    """
    return wrap(_ncaa_scoring_summary(game_id))


def get_ncaa_schools(*, query: str | None = None) -> dict:
    """Search the NCAA schools index (~1,200 schools, all divisions).

    Args:
        query: Optional name or slug filter (e.g. "michigan").
    """
    return wrap(_ncaa_schools(query))
