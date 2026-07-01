"""Esports data — Dota 2 (OpenDota) and LoL esports (Leaguepedia). Keyless, stdlib only.

For esports betting/probability signals use the `kalshi` (get_esports_odds) and
`polymarket` (get_esports_events) skills — no keyless bookmaker odds exist.
"""

from __future__ import annotations

from sports_skills.esports._connector import (
    get_leagues as _get_leagues,
)
from sports_skills.esports._connector import (
    get_lol_tournaments as _get_lol_tournaments,
)
from sports_skills.esports._connector import (
    get_match as _get_match,
)
from sports_skills.esports._connector import (
    get_pro_matches as _get_pro_matches,
)
from sports_skills.esports._connector import (
    get_pro_teams as _get_pro_teams,
)
from sports_skills.esports._connector import (
    lol_cargo_query as _lol_cargo_query,
)


def _req(**kwargs):
    """Build request_data dict from kwargs."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def get_pro_matches(*, limit: int = 20) -> dict:
    """Recent professional Dota 2 matches (OpenDota)."""
    return _get_pro_matches(_req(limit=limit))


def get_leagues(*, tier: str | None = None, limit: int = 50) -> dict:
    """Dota 2 leagues / tournaments (OpenDota). tier: 'premium' | 'professional' | 'excluded'."""
    return _get_leagues(_req(tier=tier, limit=limit))


def get_pro_teams(*, limit: int = 25) -> dict:
    """Top professional Dota 2 teams by rating (OpenDota)."""
    return _get_pro_teams(_req(limit=limit))


def get_match(*, match_id: str) -> dict:
    """Detailed Dota 2 match by id (OpenDota)."""
    return _get_match(_req(match_id=match_id))


def lol_cargo_query(
    *,
    tables: str,
    fields: str,
    where: str | None = None,
    order_by: str | None = None,
    group_by: str | None = None,
    limit: int = 20,
) -> dict:
    """Raw Leaguepedia Cargo query for LoL esports data. See SKILL.md for tables/fields."""
    return _lol_cargo_query(
        _req(
            tables=tables,
            fields=fields,
            where=where,
            order_by=order_by,
            group_by=group_by,
            limit=limit,
        )
    )


def get_lol_tournaments(*, region: str | None = None, limit: int = 20) -> dict:
    """Recent LoL esports tournaments (Leaguepedia Tournaments table)."""
    return _get_lol_tournaments(_req(region=region, limit=limit))
