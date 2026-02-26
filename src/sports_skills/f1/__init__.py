"""Formula 1 data — race schedules, results, lap data, driver/team info.

Install with: pip install sports-skills
"""

from __future__ import annotations

from sports_skills.f1._connector import (
    get_championship_standings as _get_championship_standings,
)
from sports_skills.f1._connector import (
    get_driver_comparison as _get_driver_comparison,
)
from sports_skills.f1._connector import (
    get_driver_info as _get_driver_info,
)
from sports_skills.f1._connector import (
    get_lap_data as _get_lap_data,
)
from sports_skills.f1._connector import (
    get_pit_stops as _get_pit_stops,
)
from sports_skills.f1._connector import (
    get_race_results as _get_race_results,
)
from sports_skills.f1._connector import (
    get_race_schedule as _get_race_schedule,
)
from sports_skills.f1._connector import (
    get_season_stats as _get_season_stats,
)
from sports_skills.f1._connector import (
    get_session_data as _get_session_data,
)
from sports_skills.f1._connector import (
    get_speed_data as _get_speed_data,
)
from sports_skills.f1._connector import (
    get_team_comparison as _get_team_comparison,
)
from sports_skills.f1._connector import (
    get_team_info as _get_team_info,
)
from sports_skills.f1._connector import (
    get_tire_analysis as _get_tire_analysis,
)


def _req(**kwargs):
    """Build request_data dict from kwargs."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def get_session_data(
    *, session_year: int, session_name: str, session_type: str = "Q"
) -> dict:
    """Get detailed session data (qualifying, race, practice).

    Args:
        session_year: Year of the session.
        session_name: Event name (e.g., "Monza").
        session_type: Session type — "Q" (qualifying), "R" (race), "FP1", etc.
    """
    return _get_session_data(
        _req(
            session_year=session_year,
            session_name=session_name,
            session_type=session_type,
        )
    )


def get_driver_info(*, year: int, driver: str | None = None) -> dict:
    """Get driver information for a season.

    Args:
        year: Season year.
        driver: Driver code or name (optional — omit for all drivers).
    """
    return _get_driver_info(_req(year=year, driver=driver))


def get_team_info(*, year: int, team: str | None = None) -> dict:
    """Get team information for a season.

    Args:
        year: Season year.
        team: Team name (optional — omit for all teams).
    """
    return _get_team_info(_req(year=year, team=team))


def get_race_schedule(*, year: int) -> dict:
    """Get race schedule for a season."""
    return _get_race_schedule(_req(year=year))


def get_lap_data(
    *, year: int, event: str, session_type: str = "R", driver: str | None = None
) -> dict:
    """Get lap-by-lap timing data.

    Args:
        year: Season year.
        event: Event name (e.g., "Monza").
        session_type: Session type — "R" (race), "Q", "FP1", etc.
        driver: Driver code (optional — omit for all drivers).
    """
    return _get_lap_data(
        _req(year=year, event=event, session_type=session_type, driver=driver)
    )


def get_race_results(*, year: int, event: str) -> dict:
    """Get race results (positions, times, points).

    Args:
        year: Season year.
        event: Event name (e.g., "Monza").
    """
    return _get_race_results(_req(year=year, event=event))


def get_pit_stops(
    *, year: int, event: str | None = None, driver: str | None = None
) -> dict:
    """Get pit stop durations (PitIn → PitOut) for a race or full season.

    Args:
        year: Season year.
        event: Event name (optional — omit for full season).
        driver: Driver code (optional — omit for all drivers).
    """
    return _get_pit_stops(_req(year=year, event=event, driver=driver))


def get_speed_data(
    *, year: int, event: str | None = None, driver: str | None = None
) -> dict:
    """Get speed trap and intermediate speed data for a race or full season.

    Args:
        year: Season year.
        event: Event name (optional — omit for full season).
        driver: Driver code (optional — omit for all drivers).
    """
    return _get_speed_data(_req(year=year, event=event, driver=driver))


def get_championship_standings(*, year: int) -> dict:
    """Get driver and constructor championship standings aggregated from all race results.

    Args:
        year: Season year.
    """
    return _get_championship_standings(_req(year=year))


def get_season_stats(*, year: int) -> dict:
    """Get aggregated season stats: fastest laps, top speeds, points, wins, podiums per driver/team.

    Args:
        year: Season year.
    """
    return _get_season_stats(_req(year=year))


def get_team_comparison(
    *, year: int, team1: str, team2: str, event: str | None = None
) -> dict:
    """Compare two teams head-to-head: qualifying, race pace, sectors, points.

    Args:
        year: Season year.
        team1: First team name (e.g., "Red Bull").
        team2: Second team name (e.g., "McLaren").
        event: Event name (optional — omit for full season).
    """
    return _get_team_comparison(_req(year=year, team1=team1, team2=team2, event=event))


def get_driver_comparison(
    *, year: int, driver1: str, driver2: str, event: str | None = None
) -> dict:
    """Compare any two drivers head-to-head: qualifying H2H, race H2H, pace delta.

    Works for teammates (e.g., Norris vs Piastri) and cross-team matchups
    (e.g., Norris vs Verstappen).

    Args:
        year: Season year.
        driver1: Driver code or name (e.g., "NOR" or "Norris").
        driver2: Driver code or name (e.g., "PIA" or "Piastri").
        event: Event name (optional — omit for full season). Supports "last" for most recent race.
    """
    return _get_driver_comparison(
        _req(year=year, driver1=driver1, driver2=driver2, event=event)
    )


def get_tire_analysis(
    *, year: int, event: str | None = None, driver: str | None = None
) -> dict:
    """Tire strategy and degradation analysis: compound usage, stint lengths, deg rates.

    Args:
        year: Season year.
        event: Event name (optional — omit for full season).
        driver: Driver code (optional — omit for all drivers).
    """
    return _get_tire_analysis(_req(year=year, event=event, driver=driver))
