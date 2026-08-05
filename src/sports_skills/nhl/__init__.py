"""NHL data — scores, standings, rosters, schedules, game summaries, and more.

Wraps ESPN public endpoints. No API keys required. Zero config.
"""

from __future__ import annotations

from sports_skills._response import wrap
from sports_skills.nhl._connector import (
    get_futures as _get_futures,
)
from sports_skills.nhl._connector import (
    get_game_summary as _get_game_summary,
)
from sports_skills.nhl._connector import (
    get_injuries as _get_injuries,
)
from sports_skills.nhl._connector import (
    get_leaders as _get_leaders,
)
from sports_skills.nhl._connector import (
    get_news as _get_news,
)
from sports_skills.nhl._connector import (
    get_play_by_play as _get_play_by_play,
)
from sports_skills.nhl._connector import (
    get_player_stats as _get_player_stats,
)
from sports_skills.nhl._connector import (
    get_schedule as _get_schedule,
)
from sports_skills.nhl._connector import (
    get_scoreboard as _get_scoreboard,
)
from sports_skills.nhl._connector import (
    get_standings as _get_standings,
)
from sports_skills.nhl._connector import (
    get_team_roster as _get_team_roster,
)
from sports_skills.nhl._connector import (
    get_team_schedule as _get_team_schedule,
)
from sports_skills.nhl._connector import (
    get_team_stats as _get_team_stats,
)
from sports_skills.nhl._connector import (
    get_teams as _get_teams,
)
from sports_skills.nhl._connector import (
    get_transactions as _get_transactions,
)
from sports_skills.nhl._stats import (
    find_nhl_player as _find_nhl_player,
)
from sports_skills.nhl._stats import (
    get_nhlstats_boxscore as _get_nhlstats_boxscore,
)
from sports_skills.nhl._stats import (
    get_nhlstats_leaders as _get_nhlstats_leaders,
)
from sports_skills.nhl._stats import (
    get_nhlstats_play_by_play as _get_nhlstats_play_by_play,
)
from sports_skills.nhl._stats import (
    get_nhlstats_player_stats as _get_nhlstats_player_stats,
)
from sports_skills.nhl._stats import (
    get_nhlstats_schedule as _get_nhlstats_schedule,
)
from sports_skills.nhl._stats import (
    get_nhlstats_standings as _get_nhlstats_standings,
)


def _params(**kwargs):
    """Build params dict, filtering out None values."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def get_scoreboard(*, date: str | None = None) -> dict:
    """Get live/recent NHL scores.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.
    """
    return wrap(_get_scoreboard(_params(date=date)))


def get_standings(*, season: int | None = None) -> dict:
    """Get NHL standings by conference and division.

    Args:
        season: Season year (e.g. 2025). Defaults to current.
    """
    return wrap(_get_standings(_params(season=season)))


def get_teams() -> dict:
    """Get all 32 NHL teams."""
    return wrap(_get_teams(_params()))


def get_team_roster(*, team_id: str) -> dict:
    """Get full roster for an NHL team.

    Args:
        team_id: ESPN team ID (e.g. "10" for Toronto Maple Leafs).
    """
    return wrap(_get_team_roster(_params(team_id=team_id)))


def get_team_schedule(*, team_id: str, season: int | None = None) -> dict:
    """Get schedule for a specific NHL team.

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
    """Get NHL statistical leaders (goals, assists, points, etc.).

    Args:
        season: Season year. Defaults to current.
    """
    return wrap(_get_leaders(_params(season=season)))


def get_news(*, team_id: str | None = None) -> dict:
    """Get NHL news articles.

    Args:
        team_id: Optional ESPN team ID to filter news by team.
    """
    return wrap(_get_news(_params(team_id=team_id)))


def get_schedule(*, date: str | None = None, season: int | None = None) -> dict:
    """Get NHL schedule.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.
        season: Season year. Defaults to current.
    """
    return wrap(_get_schedule(_params(date=date, season=season)))


def get_play_by_play(*, event_id: str) -> dict:
    """Get full play-by-play log for an NHL game.

    Args:
        event_id: ESPN event ID.
    """
    return wrap(_get_play_by_play(_params(event_id=event_id)))


def get_injuries() -> dict:
    """Get current NHL injury report for all teams."""
    return wrap(_get_injuries(_params()))


def get_transactions(*, limit: int | None = None) -> dict:
    """Get recent NHL transactions (trades, signings, releases).

    Args:
        limit: Max number of transactions. Defaults to 50.
    """
    return wrap(_get_transactions(_params(limit=limit)))


def get_futures(*, limit: int | None = None, season_year: int | None = None) -> dict:
    """Get NHL futures odds (Stanley Cup winner, Hart Trophy, etc.).

    Args:
        limit: Max entries per futures market. Defaults to 10.
        season_year: Season year. Defaults to current.
    """
    return wrap(_get_futures(_params(limit=limit, season_year=season_year)))


def get_team_stats(
    *, team_id: str, season_year: int | None = None, season_type: int | None = None
) -> dict:
    """Get NHL team season statistics.

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
    """Get NHL player season statistics.

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
# NHL API backend (api-web.nhle.com) — analytics layer
# ============================================================


def find_nhl_player(*, name: str) -> dict:
    """Search the NHL's player registry by name.

    Returns NHL player ids, which the other get_nhlstats_* functions take as
    ``player_id``. These are NHL ids, unrelated to ESPN athlete ids. ASCII
    queries match accented names ("stutzle" finds "Tim Stützle").

    Args:
        name: Full or partial player name (e.g. "McDavid", "Auston Matthews").
    """
    return wrap(_find_nhl_player(_params(name=name)))


def get_nhlstats_schedule(
    *,
    date: str | None = None,
    season: int | str | None = None,
    team: str | None = None,
) -> dict:
    """Get NHL games via the NHL API, keyed by NHL game ids.

    The 10-digit game id each row carries is what the other get_nhlstats_*
    functions take. Team season schedules reach back to the Original Six era.
    Rows carry both NHL and ESPN team abbreviations; join to the ESPN functions
    on (game_date, teams) — the two id systems are unrelated.

    Args:
        date: A single day, YYYY-MM-DD. Defaults to today when no team is given.
        season: Season starting year (e.g. 2024) or NHL form ("20242025").
            Used with team.
        team: Team abbreviation for a full season schedule. ESPN spellings
            ("LA", "NJ", "SJ", "TB", "UTAH") are translated to the NHL's.
    """
    return wrap(_get_nhlstats_schedule(_params(date=date, season=season, team=team)))


def get_nhlstats_player_stats(
    *, player_id: str | None = None, player: str | None = None
) -> dict:
    """Get a player's career, season by season, via the NHL API.

    Rows cover every league the player appeared in (each labelled with
    ``league``), plus NHL career regular-season totals.

    Args:
        player_id: NHL player id (e.g. "8478402"). Find it with find_nhl_player.
        player: Player name to resolve instead of player_id. Must match exactly
            one player; ambiguous names return the candidates.
    """
    return wrap(_get_nhlstats_player_stats(_params(player_id=player_id, player=player)))


def get_nhlstats_play_by_play(*, game_id: str, limit: int | None = None) -> dict:
    """Get play-by-play with on-ice coordinates via the NHL API.

    Every event carries x/y rink coordinates, zone, and shot type — data the
    ESPN-backed get_play_by_play does not carry. Covers completed games from
    past seasons.

    Args:
        game_id: 10-digit NHL game id from get_nhlstats_schedule
            (e.g. "2023030417"). Not an ESPN event id.
        limit: Maximum plays to return; truncation is flagged in the response.
    """
    return wrap(_get_nhlstats_play_by_play(_params(game_id=game_id, limit=limit)))


def get_nhlstats_boxscore(*, game_id: str) -> dict:
    """Get the full box score (skaters + goalies per team) via the NHL API.

    Args:
        game_id: 10-digit NHL game id from get_nhlstats_schedule
            (e.g. "2023030417"). Not an ESPN event id.
    """
    return wrap(_get_nhlstats_boxscore(_params(game_id=game_id)))


def get_nhlstats_standings(*, date: str | None = None) -> dict:
    """Get NHL standings via the NHL API, current or for any historical date.

    Args:
        date: Standings as of this day, YYYY-MM-DD (reaches back to 1917).
            Defaults to now.
    """
    return wrap(_get_nhlstats_standings(_params(date=date)))


def get_nhlstats_leaders(
    *,
    category: str | None = None,
    position: str | None = None,
    season: int | str | None = None,
    season_type: str | None = None,
    limit: int | None = None,
) -> dict:
    """Get skater or goalie leaders via the NHL API.

    Args:
        category: Skater: "goals", "assists", "points" (default), "plusMinus",
            "penaltyMins", "toi", "faceoffLeaders". Goalie: "wins" (default),
            "shutouts", "savePctg", "goalsAgainstAverage".
        position: "skater" (default) or "goalie".
        season: Season starting year (e.g. 2024) or NHL form ("20242025").
            Defaults to the current leaders.
        season_type: "regular" (default) or "playoffs". Used with season.
        limit: Max leaders to return (default 10).
    """
    return wrap(
        _get_nhlstats_leaders(
            _params(
                category=category,
                position=position,
                season=season,
                season_type=season_type,
                limit=limit,
            )
        )
    )
