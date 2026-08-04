"""Prospect index (MPI) — a continuous score for players who don't have a market price yet.

Every player opens at a base of 7,500 and moves by two published components:
FACT (what he already did: goals, weighted by a public rule) and PROJECTION
(the calibrated probability of reaching a professional-value threshold,
converted to points: p × 2,000).

v0 ships one retrospective cohort — the FIFA U-17 World Cup 2015 — where the
11-year outcome window is already known, so the calibration is verifiable:
the segment probabilities ARE the rates measured in the backtest
(machina-market-radar, 2026-08-03), not fitted parameters.

No third-party market values are redistributed: outcomes appear only as the
derived boolean `outcome_reached_eur5m_peak`.
"""

from __future__ import annotations

import unicodedata

from sports_skills._response import error, success
from sports_skills.prospects._cohort_2015 import COHORT_ID, PLAYERS

_BASE = 7500
_MAX_PROJECTION_POINTS = 2000

# ponytail: single embedded cohort; a registry earns its keys when cohort #2 lands
_COHORTS = {
    COHORT_ID: {
        "cohort_id": COHORT_ID,
        "name": "FIFA U-17 World Cup 2015",
        "kind": "retrospective_backtest",
        "players": PLAYERS,
        "outcome_window_years": 11,
        "notes": (
            "Demo cohort with known outcomes. Segment probabilities are the "
            "measured backtest rates, not fitted parameters."
        ),
    }
}

# measured in the 2026-08-03 backtest over 250 players with a valid series
_SEGMENT_CALIBRATION = {
    "scored_and_market_aware": {"p_reach": 0.50, "measured": "3/6", "note": "tiny n"},
    "scored_not_market_aware": {"p_reach": 0.25, "measured": "9/36"},
    "market_aware_only": {"p_reach": 0.22, "measured": "12/54"},
    "baseline": {"p_reach": 0.11, "measured": "17/154"},
}


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def list_cohorts():
    """List the cohorts the index covers."""
    data = [
        {k: v for k, v in c.items() if k != "players"} | {"player_count": len(c["players"])} for c in _COHORTS.values()
    ]
    return success({"cohorts": data}, f"{len(data)} cohort(s) available")


def get_methodology():
    """The MPI formula, component weights, and the measured calibration behind it."""
    return success(
        {
            "formula": "MPI = 7500 + FACT + PROJECTION",
            "base": _BASE,
            "fact_component": {
                "v0_rule": "min(goals_in_tracked_tournament, 5) * 40 points",
                "planned": [
                    "minutes weighted by competition level",
                    "goals/assists normalized by position",
                    "national-team call-ups",
                    "club-level progression",
                ],
            },
            "projection_component": {
                "rule": f"p_reach * {_MAX_PROJECTION_POINTS} points",
                "p_reach_source": "measured backtest rate per segment (see calibration)",
                "calibration": _SEGMENT_CALIBRATION,
                "threshold": "peak market value >= EUR 5M within the outcome window",
            },
            "migration_rule": (
                "as a player accumulates verified senior minutes the projection "
                "weight decays toward zero; at the resolved threshold he exits "
                "the index universe"
            ),
            "tradable_unit": "basket (cohort / draft class), never an individual player",
            "reference": "https://github.com/RodrigoAlbe/machina-market-radar",
        },
        "MPI methodology v0",
    )


def get_cohort_index(cohort_id=COHORT_ID, position=None, country=None, limit=50):
    """Ranked MPI scores for a cohort, with optional position/country filters."""
    cohort = _COHORTS.get(str(cohort_id))
    if not cohort:
        return error(
            f"Unknown cohort_id '{cohort_id}'. Use list_cohorts to discover valid ids.",
            data={"valid": sorted(_COHORTS)},
        )
    players = cohort["players"]
    if position:
        players = [p for p in players if p["position"].lower() == str(position).lower()]
    if country:
        players = [p for p in players if p["country"].lower() == str(country).lower()]
    try:
        limit = max(1, min(int(limit), len(PLAYERS) or 1))
    except (TypeError, ValueError):
        limit = 50
    basket = sum(p["mpi"] for p in players) / len(players) if players else None
    return success(
        {
            "cohort_id": cohort["cohort_id"],
            "cohort_name": cohort["name"],
            "kind": cohort["kind"],
            "basket_mpi": round(basket, 1) if basket else None,
            "player_count": len(players),
            "players": players[:limit],
        },
        f"{len(players)} players (showing {min(limit, len(players))})",
    )


def get_player_index(query, cohort_id=COHORT_ID):
    """One player's MPI with the full fact/projection decomposition."""
    cohort = _COHORTS.get(str(cohort_id))
    if not cohort:
        return error(
            f"Unknown cohort_id '{cohort_id}'. Use list_cohorts to discover valid ids.",
            data={"valid": sorted(_COHORTS)},
        )
    q = _norm(query)
    if not q:
        return error("Empty query. Pass a player name, e.g. query='Christian Pulisic'.")
    exact = [p for p in cohort["players"] if _norm(p["name"]) == q]
    partial = [p for p in cohort["players"] if q in _norm(p["name"])]
    hits = exact or partial
    if not hits:
        return error(
            f"No player matching '{query}' in cohort '{cohort_id}'. Names are the 2015 squad-list spellings.",
        )
    player = dict(hits[0])
    player["decomposition"] = {
        "base": _BASE,
        "fact_points": player["fact_points"],
        "projection_points": player["projection_points"],
        "projection_share": round(
            player["projection_points"] / max(player["mpi"] - _BASE, 1),
            2,
        ),
        "reading": (
            "high projection_share = expectation-driven (fragile); high fact share = production-driven (solid)"
        ),
    }
    return success(
        {"player": player, "also_matched": [p["name"] for p in hits[1:6]]},
        f"MPI {player['mpi']} for {player['name']}",
    )
