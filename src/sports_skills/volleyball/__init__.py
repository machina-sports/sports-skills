"""Volleyball data — standings, schedules, results, clubs, and tournaments.

Wraps the Nevobo (Dutch Volleyball Federation) open API.
No API keys required. Zero config.
"""

from __future__ import annotations

import re

from sports_skills import _replay
from sports_skills._response import error, wrap
from sports_skills.volleyball import _nevobo

# ---------------------------------------------------------------------------
# League configuration — maps competition_id to Nevobo poule paths
# ---------------------------------------------------------------------------

LEAGUES = {
    "nevobo-eredivisie-heren": {
        "source": "nevobo",
        "poule_path": "nationale-competitie/competitie-eredivisie-1/nationale-competitie-eh-11",
        "competition_family": "competitie-eredivisie",
        "poule_code": "eh",
        "name": "Eredivisie Heren",
        "country": "Netherlands",
        "gender": "men",
    },
    "nevobo-eredivisie-dames": {
        "source": "nevobo",
        "poule_path": "nationale-competitie/competitie-eredivisie-1/nationale-competitie-ed-11",
        "competition_family": "competitie-eredivisie",
        "poule_code": "ed",
        "name": "Eredivisie Dames",
        "country": "Netherlands",
        "gender": "women",
    },
    "nevobo-topdivisie-heren-a": {
        "source": "nevobo",
        "poule_path": "nationale-competitie/competitie-seniorencompetitie-5/nationale-competitie-tah-1",
        "competition_family": "competitie-seniorencompetitie",
        "poule_code": "tah",
        "name": "Topdivisie Heren A",
        "country": "Netherlands",
        "gender": "men",
    },
    "nevobo-topdivisie-heren-b": {
        "source": "nevobo",
        "poule_path": "nationale-competitie/competitie-seniorencompetitie-5/nationale-competitie-tbh-1",
        "competition_family": "competitie-seniorencompetitie",
        "poule_code": "tbh",
        "name": "Topdivisie Heren B",
        "country": "Netherlands",
        "gender": "men",
    },
    "nevobo-topdivisie-dames-a": {
        "source": "nevobo",
        "poule_path": "nationale-competitie/competitie-seniorencompetitie-5/nationale-competitie-tad-1",
        "competition_family": "competitie-seniorencompetitie",
        "poule_code": "tad",
        "name": "Topdivisie Dames A",
        "country": "Netherlands",
        "gender": "women",
    },
    "nevobo-topdivisie-dames-b": {
        "source": "nevobo",
        "poule_path": "nationale-competitie/competitie-seniorencompetitie-5/nationale-competitie-tbd-1",
        "competition_family": "competitie-seniorencompetitie",
        "poule_code": "tbd",
        "name": "Topdivisie Dames B",
        "country": "Netherlands",
        "gender": "women",
    },
    "nevobo-superdivisie-heren": {
        "source": "nevobo",
        "poule_path": "nationale-competitie/competitie-seniorencompetitie-5/nationale-competitie-sh-1",
        "competition_family": "competitie-seniorencompetitie",
        "poule_code": "sh",
        "name": "Superdivisie Heren",
        "country": "Netherlands",
        "gender": "men",
    },
    "nevobo-superdivisie-dames": {
        "source": "nevobo",
        "poule_path": "nationale-competitie/competitie-seniorencompetitie-5/nationale-competitie-sd-1",
        "competition_family": "competitie-seniorencompetitie",
        "poule_code": "sd",
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


def _poule_path(league):
    """Resolve a league's current Nevobo poule path.

    Nevobo bumps a season counter inside these paths, so the configured value is
    only a fallback — the live path is looked up by the parts that do not change.
    """
    return _nevobo.resolve_poule_path(
        league.get("competition_family"),
        league.get("poule_code"),
        fallback=league.get("poule_path"),
    )


def _season_error(season):
    """Return an error if `season` is not the one Nevobo serves, else None.

    Nevobo lists earlier seasons' competitions, but their poules can no longer be
    queried (HTTP 400) and their RSS exports return 404, so only the current
    season's standings, schedule and results exist upstream.
    """
    if season is None or season == "":
        return None
    wanted = str(season).strip()
    if re.fullmatch(r"\d{4}", wanted):
        wanted = f"{wanted}-{int(wanted) + 1}"
    if not re.fullmatch(r"\d{4}-\d{4}", wanted):
        return error(f"Invalid season '{season}'. Use a start year (2026) or a range (2026-2027).")
    current = _nevobo.current_season()
    if current is None:
        return error("Could not determine Nevobo's current season; try again without 'season'.")
    if wanted != current:
        return error(
            f"Season {wanted} is not available: Nevobo only serves the current season "
            f"({current}). Past-season poules and RSS exports are removed upstream."
        )
    return None


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
    if isinstance(api_comps, dict) and (api_comps.get("replay_miss") or api_comps.get("replay_error")):
        return wrap(api_comps)
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


def get_standings(*, competition_id: str, season: str | int | None = None) -> dict:
    """Get standings for a volleyball competition.

    Args:
        competition_id: League identifier (e.g. "nevobo-eredivisie-heren").
        season: Optional season ("2026-2027" or start year 2026). Nevobo only
            serves the current season; any other value returns an error.
    """
    league, err = _get_league(competition_id)
    if err:
        return err
    try:
        err = _season_error(season)
        if err:
            return err
        poule_path = _poule_path(league)
    except _replay.ReplayFailure as exc:
        return wrap(exc.error)
    result = _nevobo.get_poule_standings(poule_path)
    if isinstance(result, dict) and result.get("error"):
        return wrap(result)
    result["competition_id"] = competition_id
    result["competition_name"] = league["name"]
    return wrap(result)


def get_schedule(*, competition_id: str, season: str | int | None = None) -> dict:
    """Get upcoming match schedule for a volleyball competition.

    Args:
        competition_id: League identifier (e.g. "nevobo-eredivisie-dames").
        season: Optional season ("2026-2027" or start year 2026). Nevobo only
            serves the current season; any other value returns an error.
    """
    league, err = _get_league(competition_id)
    if err:
        return err
    try:
        err = _season_error(season)
        if err:
            return err
        poule_path = _poule_path(league)
    except _replay.ReplayFailure as exc:
        return wrap(exc.error)
    result = _nevobo.get_poule_schedule(poule_path)
    if isinstance(result, dict) and result.get("error"):
        return wrap(result)
    result["competition_id"] = competition_id
    result["competition_name"] = league["name"]
    return wrap(result)


def get_results(*, competition_id: str, season: str | int | None = None) -> dict:
    """Get match results for a volleyball competition.

    Args:
        competition_id: League identifier (e.g. "nevobo-eredivisie-heren").
        season: Optional season ("2026-2027" or start year 2026). Nevobo only
            serves the current season; any other value returns an error.
    """
    league, err = _get_league(competition_id)
    if err:
        return err
    try:
        err = _season_error(season)
        if err:
            return err
        poule_path = _poule_path(league)
    except _replay.ReplayFailure as exc:
        return wrap(exc.error)
    result = _nevobo.get_poule_results(poule_path)
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
