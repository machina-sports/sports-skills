"""Tennis data — ATP and WTA tournament scores, calendars, rankings, players, and news.

Wraps ESPN public endpoints, plus the public WTA API for WTA entry lists and
player match results (keyed by native WTA ids). No API keys required. Zero config.
"""

from __future__ import annotations

from sports_skills._response import wrap
from sports_skills.tennis._connector import (
    get_calendar as _get_calendar,
)
from sports_skills.tennis._connector import (
    get_news as _get_news,
)
from sports_skills.tennis._connector import (
    get_player_info as _get_player_info,
)
from sports_skills.tennis._connector import (
    get_rankings as _get_rankings,
)
from sports_skills.tennis._connector import (
    get_scoreboard as _get_scoreboard,
)
from sports_skills.tennis._wta import (
    get_wta_entry_list as _get_wta_entry_list,
)
from sports_skills.tennis._wta import (
    get_wta_player_results as _get_wta_player_results,
)


def _params(**kwargs):
    """Build params dict, filtering out None values."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def get_scoreboard(*, tour: str | None = None, date: str | None = None) -> dict:
    """Get active tournaments with matches for a tour.

    Args:
        tour: Tour name — "atp" or "wta". Omit to fetch both tours.
        date: Date in YYYY-MM-DD format. Defaults to today.
    """
    return wrap(_get_scoreboard(_params(tour=tour, date=date)))


def get_calendar(*, tour: str, year: int | None = None) -> dict:
    """Get full season tournament calendar.

    Args:
        tour: Tour name — "atp" or "wta".
        year: Season year. Defaults to current.
    """
    return wrap(_get_calendar(_params(tour=tour, year=year)))


def get_rankings(*, tour: str, limit: int | None = None) -> dict:
    """Get current ATP or WTA rankings. Returns athlete IDs alongside names.

    Args:
        tour: Tour name — "atp" or "wta".
        limit: Max number of ranked players to return. Defaults to 50.
    """
    return wrap(_get_rankings(_params(tour=tour, limit=limit)))


def get_player_info(*, player_id: str) -> dict:
    """Get individual player profile. Use the id field from get_rankings results to look up a player.

    Args:
        player_id: ESPN athlete ID (e.g. "3782" for Carlos Alcaraz).
    """
    return wrap(_get_player_info(_params(player_id=player_id)))


def get_news(*, tour: str) -> dict:
    """Get tennis news articles.

    Args:
        tour: Tour name — "atp" or "wta".
    """
    return wrap(_get_news(_params(tour=tour)))


def get_wta_entry_list(*, tournament_id: str, year: int) -> dict:
    """Get the WTA entry list (singles players and doubles teams) for one tournament edition.

    Args:
        tournament_id: Native WTA tournament id, digits only, no leading zeros (e.g. "901"). Not an ESPN event id.
        year: Tournament year (e.g. 2025).
    """
    return wrap(_get_wta_entry_list(_params(tournament_id=tournament_id, year=year)))


def get_wta_player_results(*, player_id: str, year: int | None = None, limit: int = 20) -> dict:
    """Get a WTA player's most recent match results (a bounded window, not full history), newest first.

    Args:
        player_id: Native WTA player id, digits only, no leading zeros (e.g. "320760"). Not an ESPN athlete id.
        year: Only matches from this tournament year, filtered by the WTA API. Omit for the latest matches.
        limit: Max matches to return, 1-200. Defaults to 20.
    """
    return wrap(_get_wta_player_results(_params(player_id=player_id, year=year, limit=limit)))
