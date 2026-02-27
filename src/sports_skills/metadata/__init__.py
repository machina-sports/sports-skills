"""Metadata — team logos, player photos, stadium info via TheSportsDB.

Wraps the TheSportsDB free API (key=3). No API key required. Zero config.

## Coverage

**Teams (logos, banners, stadium info):**
- Soccer: 100+ leagues worldwide (Premier League, La Liga, Bundesliga, Serie A, MLS, etc.)
- NFL (American Football)
- NBA (Basketball) — use full team names (e.g., "Los Angeles Lakers" not "Lakers")
- MLB (Baseball)
- NHL (Ice Hockey)
- F1 (Motorsport)
- Cricket (IPL, international)

**Players (photos, bios):**
- All team sports above
- Tennis (ATP/WTA players)
- Golf (PGA/LPGA players)

**Not covered:** MMA/UFC, Rugby, Esports, Boxing

## Usage

    from sports_skills.metadata import get_team_logo, search_teams

    # Get Arsenal's logo
    logo = get_team_logo(team_name="Arsenal")

    # Search for teams
    teams = search_teams(query="Manchester")

    # Get player photo
    photo = get_player_photo(player_name="Messi")
"""

from __future__ import annotations

from sports_skills._response import wrap
from sports_skills.metadata._connector import (
    get_player_photo as _get_player_photo,
    get_team_info as _get_team_info,
    get_team_logo as _get_team_logo,
    search_players as _search_players,
    search_teams as _search_teams,
)


def _params(**kwargs):
    """Build params dict, filtering out None values."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def get_team_logo(*, team_name: str, sport: str = "Soccer") -> dict:
    """Get team logo URL by team name.

    Args:
        team_name: Name of the team (e.g. "Arsenal", "Los Angeles Lakers").
                   For NBA teams, use full name (not abbreviations).
        sport: Sport to filter by (default: "Soccer").
               Options: Soccer, Basketball, American Football, Baseball, Ice Hockey, Motorsport, Cricket.
    """
    return wrap(_get_team_logo(_params(team_name=team_name, sport=sport)))


def get_team_info(*, team_name: str) -> dict:
    """Get full team info including stadium, description, social links.

    Args:
        team_name: Name of the team to look up.
    """
    return wrap(_get_team_info(_params(team_name=team_name)))


def get_player_photo(*, player_name: str) -> dict:
    """Get player photo URL by player name.

    Args:
        player_name: Name of the player (e.g. "Messi", "LeBron James", "Tiger Woods").
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
