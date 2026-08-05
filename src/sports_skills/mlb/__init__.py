"""MLB data — scores, standings, rosters, schedules, game summaries, and more.

Wraps ESPN public endpoints. No API keys required. Zero config.
"""

from __future__ import annotations

from sports_skills._response import wrap
from sports_skills.mlb._connector import (
    get_depth_chart as _get_depth_chart,
)
from sports_skills.mlb._connector import (
    get_game_summary as _get_game_summary,
)
from sports_skills.mlb._connector import (
    get_injuries as _get_injuries,
)
from sports_skills.mlb._connector import (
    get_leaders as _get_leaders,
)
from sports_skills.mlb._connector import (
    get_news as _get_news,
)
from sports_skills.mlb._connector import (
    get_play_by_play as _get_play_by_play,
)
from sports_skills.mlb._connector import (
    get_player_stats as _get_player_stats,
)
from sports_skills.mlb._connector import (
    get_schedule as _get_schedule,
)
from sports_skills.mlb._connector import (
    get_scoreboard as _get_scoreboard,
)
from sports_skills.mlb._connector import (
    get_standings as _get_standings,
)
from sports_skills.mlb._connector import (
    get_team_roster as _get_team_roster,
)
from sports_skills.mlb._connector import (
    get_team_schedule as _get_team_schedule,
)
from sports_skills.mlb._connector import (
    get_team_stats as _get_team_stats,
)
from sports_skills.mlb._connector import (
    get_teams as _get_teams,
)
from sports_skills.mlb._connector import (
    get_transactions as _get_transactions,
)
from sports_skills.mlb._connector import (
    get_win_probability as _get_win_probability,
)
from sports_skills.mlb._stats import (
    find_mlb_player as _find_mlb_player,
)
from sports_skills.mlb._stats import (
    get_mlbstats_boxscore as _get_mlbstats_boxscore,
)
from sports_skills.mlb._stats import (
    get_mlbstats_leaders as _get_mlbstats_leaders,
)
from sports_skills.mlb._stats import (
    get_mlbstats_play_by_play as _get_mlbstats_play_by_play,
)
from sports_skills.mlb._stats import (
    get_mlbstats_player_stats as _get_mlbstats_player_stats,
)
from sports_skills.mlb._stats import (
    get_mlbstats_schedule as _get_mlbstats_schedule,
)
from sports_skills.mlb._stats import (
    get_mlbstats_standings as _get_mlbstats_standings,
)


def _params(**kwargs):
    """Build params dict, filtering out None values."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def get_scoreboard(*, date: str | None = None) -> dict:
    """Get live/recent MLB scores.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.
    """
    return wrap(_get_scoreboard(_params(date=date)))


def get_standings(*, season: int | None = None) -> dict:
    """Get MLB standings by league and division.

    Args:
        season: Season year (e.g. 2025). Defaults to current.
    """
    return wrap(_get_standings(_params(season=season)))


def get_teams() -> dict:
    """Get all 30 MLB teams."""
    return wrap(_get_teams(_params()))


def get_team_roster(*, team_id: str) -> dict:
    """Get full roster for an MLB team.

    Args:
        team_id: ESPN team ID (e.g. "10" for New York Yankees).
    """
    return wrap(_get_team_roster(_params(team_id=team_id)))


def get_team_schedule(*, team_id: str, season: int | None = None) -> dict:
    """Get schedule for a specific MLB team.

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
    """Get MLB statistical leaders (batting avg, home runs, ERA, etc.).

    Args:
        season: Season year. Defaults to current.
    """
    return wrap(_get_leaders(_params(season=season)))


def get_news(*, team_id: str | None = None) -> dict:
    """Get MLB news articles.

    Args:
        team_id: Optional ESPN team ID to filter news by team.
    """
    return wrap(_get_news(_params(team_id=team_id)))


def get_schedule(*, date: str | None = None, season: int | None = None) -> dict:
    """Get MLB schedule.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today.
        season: Season year. Defaults to current.
    """
    return wrap(_get_schedule(_params(date=date, season=season)))


def get_play_by_play(*, event_id: str) -> dict:
    """Get play-by-play log for an MLB game.

    Args:
        event_id: ESPN event ID.
    """
    return wrap(_get_play_by_play(_params(event_id=event_id)))


def get_win_probability(*, event_id: str) -> dict:
    """Get win probability timeline for an MLB game.

    Args:
        event_id: ESPN event ID.
    """
    return wrap(_get_win_probability(_params(event_id=event_id)))


def get_injuries() -> dict:
    """Get current MLB injury report for all teams."""
    return wrap(_get_injuries(_params()))


def get_transactions(*, limit: int | None = None) -> dict:
    """Get recent MLB transactions (trades, signings, releases).

    Args:
        limit: Max number of transactions. Defaults to 50.
    """
    return wrap(_get_transactions(_params(limit=limit)))


def get_depth_chart(*, team_id: str) -> dict:
    """Get MLB depth chart for a team.

    Args:
        team_id: ESPN team ID.
    """
    return wrap(_get_depth_chart(_params(team_id=team_id)))


def get_team_stats(
    *, team_id: str, season_year: int | None = None, season_type: int | None = None
) -> dict:
    """Get MLB team season statistics.

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
    """Get MLB player season statistics.

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
# MLB Stats API backend (statsapi.mlb.com) — analytics layer
# ============================================================


def find_mlb_player(*, name: str) -> dict:
    """Search MLB's player registry by name.

    Returns MLB person ids, which the other get_mlbstats_* functions take as
    ``player_id``. These are MLB ids, unrelated to ESPN athlete ids. ASCII
    queries match accented names ("acuna" finds "Ronald Acuña Jr.").

    Args:
        name: Full or partial player name (e.g. "Ohtani", "Aaron Judge").
    """
    return wrap(_find_mlb_player(_params(name=name)))


def get_mlbstats_schedule(
    *,
    date: str | None = None,
    season: int | None = None,
    team: str | None = None,
    game_type: str | None = None,
) -> dict:
    """Get MLB games via the MLB Stats API, keyed by gamePk.

    The gamePk each row carries is what the other get_mlbstats_* functions
    take. History reaches back to 1901. Rows carry both MLB and ESPN team
    abbreviations; join to the ESPN functions on (game_date, teams) — the two
    id systems are unrelated.

    Args:
        date: A single day, YYYY-MM-DD.
        season: Season year for a team schedule (requires team).
        team: Team abbreviation. ESPN spellings ("ARI", "CHW") are translated
            to MLB's ("AZ", "CWS").
        game_type: "regular", "spring", "wildcard", "division", "lcs",
            "worldseries", or "allstar".
    """
    return wrap(
        _get_mlbstats_schedule(
            _params(date=date, season=season, team=team, game_type=game_type)
        )
    )


def get_mlbstats_player_stats(
    *,
    player_id: str | None = None,
    player: str | None = None,
    stat_type: str | None = None,
    stat_group: str | None = None,
    season: int | None = None,
) -> dict:
    """Get a player's stats via the MLB Stats API.

    Args:
        player_id: MLB person id (e.g. "660271"). Find it with find_mlb_player.
        player: Player name to resolve instead of player_id. Must match exactly
            one player; ambiguous names return the candidates.
        stat_type: "season" (default), "career", or "year_by_year".
        stat_group: "hitting" (default), "pitching", or "fielding".
        season: Season year when stat_type is "season". Defaults to the most
            recent season.
    """
    return wrap(
        _get_mlbstats_player_stats(
            _params(
                player_id=player_id,
                player=player,
                stat_type=stat_type,
                stat_group=stat_group,
                season=season,
            )
        )
    )


def get_mlbstats_play_by_play(*, game_pk: str, limit: int | None = None) -> dict:
    """Get pitch-level play-by-play via the MLB Stats API.

    Every pitch carries velocity, spin rate, and plate coordinates; balls in
    play add exit velocity, launch angle, and distance — data the ESPN-backed
    get_play_by_play does not carry.

    Args:
        game_pk: MLB game id from get_mlbstats_schedule (e.g. "775296").
            Not an ESPN event id.
        limit: Maximum plays to return; truncation is flagged in the response.
    """
    return wrap(_get_mlbstats_play_by_play(_params(game_pk=game_pk, limit=limit)))


def get_mlbstats_boxscore(*, game_pk: str) -> dict:
    """Get the full box score (team + per-player batting/pitching) via the MLB Stats API.

    Args:
        game_pk: MLB game id from get_mlbstats_schedule (e.g. "775296").
            Not an ESPN event id.
    """
    return wrap(_get_mlbstats_boxscore(_params(game_pk=game_pk)))


def get_mlbstats_standings(*, season: int | None = None) -> dict:
    """Get MLB standings by division via the MLB Stats API.

    Args:
        season: Season year. Defaults to the most recent season.
    """
    return wrap(_get_mlbstats_standings(_params(season=season)))


def get_mlbstats_leaders(
    *,
    category: str,
    season: int | None = None,
    stat_group: str | None = None,
    limit: int | None = None,
) -> dict:
    """Get league leaders for a stat category via the MLB Stats API.

    Args:
        category: MLB stat name in camelCase — e.g. "homeRuns",
            "battingAverage", "earnedRunAverage", "strikeouts", "stolenBases",
            "wins", "saves".
        season: Season year. Defaults to the most recent season.
        stat_group: Optional "hitting", "pitching", or "fielding" to
            disambiguate categories that exist in more than one group
            (e.g. strikeouts, homeRuns).
        limit: Max leaders to return (default 10).
    """
    return wrap(
        _get_mlbstats_leaders(
            _params(category=category, season=season, stat_group=stat_group, limit=limit)
        )
    )
