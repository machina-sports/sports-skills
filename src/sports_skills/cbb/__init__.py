"""College Basketball (CBB) data — scores, standings, rosters, schedules, rankings, and more.

Wraps ESPN public endpoints for NCAA Division I men's basketball. No API keys required. Zero config.
"""

from __future__ import annotations

from sports_skills._ncaa import (
    fetch_boxscore as _fetch_ncaa_boxscore,
)
from sports_skills._ncaa import (
    fetch_bracket as _fetch_ncaa_bracket,
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
    guard as _ncaa_guard,
)
from sports_skills._response import wrap
from sports_skills.cbb._connector import (
    compare_teams as _compare_teams,
)
from sports_skills.cbb._connector import (
    find_upset_candidates as _find_upset_candidates,
)
from sports_skills.cbb._connector import (
    get_futures as _get_futures,
)
from sports_skills.cbb._connector import (
    get_game_summary as _get_game_summary,
)
from sports_skills.cbb._connector import (
    get_news as _get_news,
)
from sports_skills.cbb._connector import (
    get_play_by_play as _get_play_by_play,
)
from sports_skills.cbb._connector import (
    get_player_stats as _get_player_stats,
)
from sports_skills.cbb._connector import (
    get_power_index as _get_power_index,
)
from sports_skills.cbb._connector import (
    get_rankings as _get_rankings,
)
from sports_skills.cbb._connector import (
    get_schedule as _get_schedule,
)
from sports_skills.cbb._connector import (
    get_scoreboard as _get_scoreboard,
)
from sports_skills.cbb._connector import (
    get_standings as _get_standings,
)
from sports_skills.cbb._connector import (
    get_team_roster as _get_team_roster,
)
from sports_skills.cbb._connector import (
    get_team_schedule as _get_team_schedule,
)
from sports_skills.cbb._connector import (
    get_team_stats as _get_team_stats,
)
from sports_skills.cbb._connector import (
    get_teams as _get_teams,
)
from sports_skills.cbb._connector import (
    get_tournament_projections as _get_tournament_projections,
)
from sports_skills.cbb._connector import (
    get_win_probability as _get_win_probability,
)


def _params(**kwargs):
    """Build params dict, filtering out None values."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def get_scoreboard(*, date: str | None = None, group: int | None = None, limit: int | None = None) -> dict:
    """Get live/recent college basketball scores.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.
        group: Conference group ID to filter by.
        limit: Max number of events to return.
    """
    return wrap(_get_scoreboard(_params(date=date, group=group, limit=limit)))


def get_standings(*, season: int | None = None, group: int | None = None) -> dict:
    """Get college basketball standings by conference.

    Args:
        season: Season year (e.g. 2025). Defaults to current.
        group: Conference ID to filter (e.g. 2=ACC, 7=Big 12, 8=Big East, 23=SEC).
    """
    return wrap(_get_standings(_params(season=season, group=group)))


def get_teams() -> dict:
    """Get all D1 men's college basketball teams."""
    return wrap(_get_teams(_params()))


def get_team_roster(*, team_id: str) -> dict:
    """Get full roster for a college basketball team.

    Args:
        team_id: ESPN team ID (e.g. "2250" for Duke).
    """
    return wrap(_get_team_roster(_params(team_id=team_id)))


def get_team_schedule(*, team_id: str, season: int | None = None) -> dict:
    """Get schedule for a specific college basketball team.

    Args:
        team_id: ESPN team ID.
        season: Season year. Defaults to current.
    """
    return wrap(_get_team_schedule(_params(team_id=team_id, season=season)))


def get_game_summary(*, event_id: str) -> dict:
    """Get detailed game summary with box score.

    Args:
        event_id: ESPN event ID.
    """
    return wrap(_get_game_summary(_params(event_id=event_id)))


def get_rankings(*, season: int | None = None, week: int | None = None) -> dict:
    """Get college basketball rankings (AP Top 25, Coaches Poll).

    Args:
        season: Season year. Defaults to current.
        week: Week number for historical rankings.
    """
    return wrap(_get_rankings(_params(season=season, week=week)))


def get_news(*, team_id: str | None = None) -> dict:
    """Get college basketball news articles.

    Args:
        team_id: Optional ESPN team ID to filter news by team.
    """
    return wrap(_get_news(_params(team_id=team_id)))


def get_schedule(*, date: str | None = None, season: int | None = None, group: int | None = None) -> dict:
    """Get college basketball schedule.

    Args:
        date: Date in YYYY-MM-DD format.
        season: Season year. Defaults to current.
        group: Conference group ID to filter by.
    """
    return wrap(_get_schedule(_params(date=date, season=season, group=group)))


def get_play_by_play(*, event_id: str) -> dict:
    """Get full play-by-play log for a college basketball game.

    Args:
        event_id: ESPN event ID.
    """
    return wrap(_get_play_by_play(_params(event_id=event_id)))


def get_win_probability(*, event_id: str) -> dict:
    """Get win probability timeline for a college basketball game.

    Args:
        event_id: ESPN event ID.
    """
    return wrap(_get_win_probability(_params(event_id=event_id)))


def get_futures(*, limit: int | None = None, season_year: int | None = None) -> dict:
    """Get college basketball futures odds (national championship, etc.).

    Args:
        limit: Max entries per futures market. Defaults to 10.
        season_year: Season year. Defaults to current.
    """
    return wrap(_get_futures(_params(limit=limit, season_year=season_year)))


def get_team_stats(
    *, team_id: str, season_year: int | None = None, season_type: int | None = None
) -> dict:
    """Get college basketball team season statistics.

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
    """Get college basketball player season statistics.

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


def get_power_index(
    *, team_id: str | None = None, limit: int | None = None, page: int | None = None
) -> dict:
    """Get BPI (Basketball Power Index) ratings for college basketball teams.

    Args:
        team_id: Optional ESPN team ID to filter to one team.
        limit: Max teams to return. Defaults to 25.
        page: Page number for pagination. Defaults to 1.
    """
    return wrap(_get_power_index(_params(team_id=team_id, limit=limit, page=page)))


def get_tournament_projections(*, limit: int | None = None) -> dict:
    """Get NCAA tournament projections with seeds, regions, and advancement probabilities.

    Args:
        limit: Max teams to return. Defaults to 68 for full tournament field.
    """
    return wrap(_get_tournament_projections(_params(limit=limit)))


def compare_teams(*, team_a_id: str, team_b_id: str) -> dict:
    """Compare two college basketball teams using BPI ratings and season stats.

    Args:
        team_a_id: ESPN team ID for team A.
        team_b_id: ESPN team ID for team B.
    """
    return wrap(_compare_teams(_params(team_a_id=team_a_id, team_b_id=team_b_id)))


def find_upset_candidates(
    *, min_seed: int | None = None, max_seed: int | None = None
) -> dict:
    """Find potential upset candidates based on BPI vs seed differential.

    Args:
        min_seed: Minimum seed to consider. Defaults to 10.
        max_seed: Maximum seed to consider. Defaults to 16.
    """
    return wrap(_find_upset_candidates(_params(min_seed=min_seed, max_seed=max_seed)))


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


def _ncaa_bracket(sport, division, year):
    return _ncaa_call(_fetch_ncaa_bracket, sport, division, year)


def _ncaa_schools(query):
    return _ncaa_call(_fetch_ncaa_schools, query)



def get_ncaa_scoreboard(*, date: str, division: str | None = None) -> dict:
    """Get the official NCAA scoreboard — including D2 and D3, which ESPN barely covers.

    Rows carry NCAA game ids, which the other get_ncaa_* functions take. NCAA
    ids and ESPN event ids share nothing; join on game date plus team names.

    Args:
        date: A single day, YYYY-MM-DD.
        division: "d1" (default), "d2", or "d3".
    """
    return wrap(_ncaa_scoreboard("basketball-men", division, date=date))


def get_ncaa_schedule(*, month: int, division: str | None = None, season: int | None = None) -> dict:
    """Get which dates have games, from the official NCAA schedule index.

    Args:
        month: Month number (1-12).
        division: "d1" (default), "d2", or "d3".
        season: Season starting year (e.g. 2024). Defaults to the current season.
    """
    return wrap(_ncaa_schedule("basketball-men", division, year=season, month=month))


def get_ncaa_game(*, game_id: str) -> dict:
    """Get official NCAA game information for one game.

    Args:
        game_id: NCAA game id from get_ncaa_scoreboard (e.g. "6398604").
            Not an ESPN event id.
    """
    return wrap(_ncaa_game_info(game_id))


def get_ncaa_boxscore(*, game_id: str) -> dict:
    """Get the official NCAA box score for one game.

    Args:
        game_id: NCAA game id from get_ncaa_scoreboard (e.g. "6398604").
            Not an ESPN event id.
    """
    return wrap(_ncaa_boxscore("basketball-men", game_id))


def get_ncaa_play_by_play(*, game_id: str, limit: int | None = None) -> dict:
    """Get official NCAA play-by-play for one game.

    Args:
        game_id: NCAA game id from get_ncaa_scoreboard (e.g. "6398604").
            Not an ESPN event id.
        limit: Maximum plays to return; truncation is flagged in the response.
    """
    return wrap(_ncaa_play_by_play("basketball-men", game_id, limit))


def get_ncaa_bracket(*, year: int | None = None, division: str | None = None) -> dict:
    """Get the NCAA tournament bracket (March Madness), with live scores in season.

    Args:
        year: Tournament year (e.g. 2025 for the 2024-25 bracket). Defaults to
            the current season's tournament.
        division: "d1" (default), "d2", or "d3".
    """
    return wrap(_ncaa_bracket("basketball-men", division, year))


def get_ncaa_schools(*, query: str | None = None) -> dict:
    """Search the NCAA schools index (~1,200 schools, all divisions).

    Args:
        query: Optional name or slug filter (e.g. "gonzaga").
    """
    return wrap(_ncaa_schools(query))
