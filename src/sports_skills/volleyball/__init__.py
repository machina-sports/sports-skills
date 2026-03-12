"""Volleyball data — standings, schedules, results, clubs, and tournaments.

Wraps the Nevobo (Dutch Volleyball Federation) open API.
No API keys required. Zero config.
"""

from __future__ import annotations

from sports_skills._response import error, wrap
from sports_skills.volleyball import _nevobo

# ---------------------------------------------------------------------------
# League configuration — maps competition_id to Nevobo poule paths
# ---------------------------------------------------------------------------

LEAGUES = {
    "nevobo-eredivisie-heren": {
        "source": "nevobo",
        "poule_path": "nationale-competitie/competitie-eredivisie-1/nationale-competitie-eh-11",
        "name": "Eredivisie Heren",
        "country": "Netherlands",
        "gender": "men",
    },
    "nevobo-eredivisie-dames": {
        "source": "nevobo",
        "poule_path": "nationale-competitie/competitie-eredivisie-1/nationale-competitie-ed-11",
        "name": "Eredivisie Dames",
        "country": "Netherlands",
        "gender": "women",
    },
    "nevobo-topdivisie-heren-a": {
        "source": "nevobo",
        "poule_path": "nationale-competitie/competitie-seniorencompetitie-5/nationale-competitie-tah-1",
        "name": "Topdivisie Heren A",
        "country": "Netherlands",
        "gender": "men",
    },
    "nevobo-topdivisie-heren-b": {
        "source": "nevobo",
        "poule_path": "nationale-competitie/competitie-seniorencompetitie-5/nationale-competitie-tbh-1",
        "name": "Topdivisie Heren B",
        "country": "Netherlands",
        "gender": "men",
    },
    "nevobo-topdivisie-dames-a": {
        "source": "nevobo",
        "poule_path": "nationale-competitie/competitie-seniorencompetitie-5/nationale-competitie-tad-1",
        "name": "Topdivisie Dames A",
        "country": "Netherlands",
        "gender": "women",
    },
    "nevobo-topdivisie-dames-b": {
        "source": "nevobo",
        "poule_path": "nationale-competitie/competitie-seniorencompetitie-5/nationale-competitie-tbd-1",
        "name": "Topdivisie Dames B",
        "country": "Netherlands",
        "gender": "women",
    },
    "nevobo-superdivisie-heren": {
        "source": "nevobo",
        "poule_path": "nationale-competitie/competitie-seniorencompetitie-5/nationale-competitie-sh-1",
        "name": "Superdivisie Heren",
        "country": "Netherlands",
        "gender": "men",
    },
    "nevobo-superdivisie-dames": {
        "source": "nevobo",
        "poule_path": "nationale-competitie/competitie-seniorencompetitie-5/nationale-competitie-sd-1",
        "name": "Superdivisie Dames",
        "country": "Netherlands",
        "gender": "women",
    },
}


def _get_league(competition_id):
    """Look up a league config by competition_id."""
    league = LEAGUES.get(competition_id)
    if not league:
        available = ", ".join(sorted(LEAGUES.keys()))
        return None, error(
            f"Unknown competition_id '{competition_id}'. Available: {available}"
        )
    return league, None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_competitions() -> dict:
    """List all available volleyball competitions and leagues.

    Returns configured league IDs and Nevobo competitions from the API.
    """
    configured = [
        {"competition_id": cid, **{k: v for k, v in cfg.items() if k != "poule_path"}}
        for cid, cfg in LEAGUES.items()
    ]

    api_comps = _nevobo.get_competitions()
    if isinstance(api_comps, dict) and api_comps.get("error"):
        return wrap({
            "configured_leagues": configured,
            "api_competitions": None,
            "message": "Could not fetch API competitions; showing configured leagues only.",
        })

    return wrap({
        "configured_leagues": configured,
        "api_competitions": api_comps,
    })


def get_standings(*, competition_id: str) -> dict:
    """Get standings for a volleyball competition.

    Args:
        competition_id: League identifier (e.g. "nevobo-eredivisie-heren").
    """
    league, err = _get_league(competition_id)
    if err:
        return err
    result = _nevobo.get_poule_standings(league["poule_path"])
    if isinstance(result, dict) and result.get("error"):
        return wrap(result)
    result["competition_id"] = competition_id
    result["competition_name"] = league["name"]
    return wrap(result)


def get_schedule(*, competition_id: str) -> dict:
    """Get upcoming match schedule for a volleyball competition.

    Args:
        competition_id: League identifier (e.g. "nevobo-eredivisie-dames").
    """
    league, err = _get_league(competition_id)
    if err:
        return err
    result = _nevobo.get_poule_schedule(league["poule_path"])
    if isinstance(result, dict) and result.get("error"):
        return wrap(result)
    result["competition_id"] = competition_id
    result["competition_name"] = league["name"]
    return wrap(result)


def get_results(*, competition_id: str) -> dict:
    """Get match results for a volleyball competition.

    Args:
        competition_id: League identifier (e.g. "nevobo-eredivisie-heren").
    """
    league, err = _get_league(competition_id)
    if err:
        return err
    result = _nevobo.get_poule_results(league["poule_path"])
    if isinstance(result, dict) and result.get("error"):
        return wrap(result)
    result["competition_id"] = competition_id
    result["competition_name"] = league["name"]
    return wrap(result)


def get_clubs(*, competition_id: str | None = None, limit: int | None = None) -> dict:
    """List volleyball clubs.

    Args:
        competition_id: Optional competition_id to filter context (informational only).
        limit: Max number of clubs to return.
    """
    result = _nevobo.get_clubs()
    if isinstance(result, dict) and result.get("error"):
        return wrap(result)
    if limit and "items" in result:
        result["items"] = result["items"][:int(limit)]
    return wrap(result)


def get_club_schedule(*, club_id: str) -> dict:
    """Get upcoming matches for a club across all its teams.

    Args:
        club_id: Nevobo club identifier (e.g. "CKL5C67").
    """
    result = _nevobo.get_club_schedule(club_id)
    return wrap(result)


def get_club_results(*, club_id: str) -> dict:
    """Get match results for a club across all its teams.

    Args:
        club_id: Nevobo club identifier (e.g. "CKL5C67").
    """
    result = _nevobo.get_club_results(club_id)
    return wrap(result)


def get_poules(
    *, competition_id: str | None = None, regio: str | None = None, limit: int | None = None
) -> dict:
    """Browse Nevobo poules for advanced discovery.

    Args:
        competition_id: Filter by competition (uses regio path prefix).
        regio: Filter by region slug (e.g. "nationale-competitie", "regio-noord",
            "regio-west", "regio-oost", "regio-zuid", "kampioenschappen").
        limit: Max number of poules to return.
    """
    params = {}
    if regio:
        # The API expects the full IRI path for regio filtering
        if not regio.startswith("/regios/"):
            regio = f"/regios/{regio}"
        params["regio"] = regio
    result = _nevobo.get_poules(params if params else None)
    if isinstance(result, dict) and result.get("error"):
        return wrap(result)
    if limit and "items" in result:
        result["items"] = result["items"][:int(limit)]
    return wrap(result)


def get_tournaments(*, limit: int | None = None) -> dict:
    """Get volleyball tournament calendar.

    Args:
        limit: Max number of tournaments to return.
    """
    result = _nevobo.get_tournaments(limit=limit)
    return wrap(result)


def get_news(*, limit: int | None = None) -> dict:
    """Get volleyball federation news.

    Args:
        limit: Max number of news items to return.
    """
    result = _nevobo.get_news(limit=limit)
    return wrap(result)
