"""NBA G League data — scores, standings, rosters, schedules, game summaries, play-by-play, and news.

Wraps ESPN public endpoints (``basketball/nba-development``). G League team
ids are separate from NBA ids; nothing here uses NBA endpoints, the NBA live
CDN, or stats.nba.com. No API keys required. Zero config.
"""

from __future__ import annotations

from sports_skills._response import wrap
from sports_skills.gleague._connector import (
    get_game_summary as _get_game_summary,
)
from sports_skills.gleague._connector import (
    get_news as _get_news,
)
from sports_skills.gleague._connector import (
    get_play_by_play as _get_play_by_play,
)
from sports_skills.gleague._connector import (
    get_schedule as _get_schedule,
)
from sports_skills.gleague._connector import (
    get_scoreboard as _get_scoreboard,
)
from sports_skills.gleague._connector import (
    get_standings as _get_standings,
)
from sports_skills.gleague._connector import (
    get_team_roster as _get_team_roster,
)
from sports_skills.gleague._connector import (
    get_team_schedule as _get_team_schedule,
)
from sports_skills.gleague._connector import (
    get_teams as _get_teams,
)


def _params(**kwargs):
    """Build params dict, filtering out None values."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def get_scoreboard(*, date: str | None = None) -> dict:
    """Get G League scores for a date.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to ESPN's current game day.
    """
    return wrap(_get_scoreboard(_params(date=date)))


def get_schedule(*, date: str | None = None, season: int | None = None) -> dict:
    """Get G League games on a date.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to ESPN's current game day.
        season: Not a filter (ESPN's scoreboard has none); without a date it returns an error.
            Use get_team_schedule(team_id, season) for a season.
    """
    return wrap(_get_schedule(_params(date=date, season=season)))


def get_standings(*, season: int | None = None) -> dict:
    """Get G League standings by conference.

    Args:
        season: Season ending year (2025-26 is 2026). Defaults to the latest season with games.
    """
    return wrap(_get_standings(_params(season=season)))


def get_teams() -> dict:
    """Get all G League teams (ESPN G League ids, not NBA ids)."""
    return wrap(_get_teams(_params()))


def get_team_roster(*, team_id: str) -> dict:
    """Get a G League team's roster as ESPN currently returns it (no historical rosters here).

    Args:
        team_id: ESPN G League team ID (e.g. "2" for Austin Spurs).
    """
    return wrap(_get_team_roster(_params(team_id=team_id)))


def get_team_schedule(*, team_id: str, season: int | None = None, season_type: str | None = None) -> dict:
    """Get schedule for a specific G League team.

    Args:
        team_id: ESPN G League team ID.
        season: Season ending year (2025-26 is 2026). Defaults to the season ESPN selects.
        season_type: "regular", "postseason" (alias "playoffs"), "tournament" (alias "showcase";
            the Tip-Off Tournament, ESPN type 5), or "all" (tournament + regular + postseason).
            ESPN codes 2, 3, 5 also work. Omitted, ESPN's default rows are returned.
    """
    return wrap(_get_team_schedule(_params(team_id=team_id, season=season, season_type=season_type)))


def get_game_summary(*, event_id: str) -> dict:
    """Get detailed G League game summary with box score and scoring plays.

    Args:
        event_id: ESPN event ID.
    """
    return wrap(_get_game_summary(_params(event_id=event_id)))


def get_play_by_play(*, event_id: str) -> dict:
    """Get full play-by-play log for a G League game.

    Args:
        event_id: ESPN event ID.
    """
    return wrap(_get_play_by_play(_params(event_id=event_id)))


def get_news(*, limit: int | None = None) -> dict:
    """Get G League news articles (ESPN's feed also carries other leagues' stories).

    Args:
        limit: Max number of articles. Defaults to all ESPN returns.
    """
    return wrap(_get_news(_params(limit=limit)))
