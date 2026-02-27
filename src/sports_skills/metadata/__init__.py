"""Metadata — team logos, player photos, and search via TheSportsDB.

Wraps the TheSportsDB free API (key=3). No API key purchase required. Zero config.
"""

from __future__ import annotations

from sports_skills._response import wrap
from sports_skills.metadata._connector import (
    get_player_photo as _get_player_photo,
)
from sports_skills.metadata._connector import (
    get_team_info as _get_team_info,
)
from sports_skills.metadata._connector import (
    get_team_logo as _get_team_logo,
)
from sports_skills.metadata._connector import (
    search_players as _search_players,
)
from sports_skills.metadata._connector import (
    search_teams as _search_teams,
)


def _params(**kwargs):
    """Build params dict, filtering out None values."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def get_team_logo(*, team_name: str, sport: str = "Soccer") -> dict:
    """Get team logo URL by team name.

    Args:
        team_name: Name of the team (e.g. "Arsenal", "LA Lakers").
        sport: Sport to filter by (default: "Soccer"). Examples: Soccer, Basketball, Ice Hockey.
    """
    return wrap(_get_team_logo(_params(team_name=team_name, sport=sport)))


def get_team_info(*, team_name: str) -> dict:
    """Get detailed team information including stadium, capacity, and description.

    Args:
        team_name: Name of the team (e.g. "Arsenal", "LA Lakers").
    """
    return wrap(_get_team_info(_params(team_name=team_name)))


def get_player_photo(*, player_name: str) -> dict:
    """Get player photo URL by player name.

    Args:
        player_name: Name of the player (e.g. "Lionel Messi", "LeBron James").
    """
    return wrap(_get_player_photo(_params(player_name=player_name)))


def search_teams(*, query: str) -> dict:
    """Search for teams by name.

    Args:
        query: Team name or partial name to search for.
    """
    return wrap(_search_teams(_params(query=query)))


def search_players(*, query: str) -> dict:
    """Search for players by name.

    Args:
        query: Player name or partial name to search for.
    """
    return wrap(_search_players(_params(query=query)))
