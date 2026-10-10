"""Novig exchange — public events, market catalog, and order books.

Public read-only endpoints (https://api.novig.com/v3/public). No API key,
GET only, stdlib only. Never places, modifies, or cancels orders.

Prices exist only on order books: bids per outcome, as probabilities, for
contracts that pay $0.01 each. Catalog markets never carry prices.
"""

from __future__ import annotations

from sports_skills.novig._connector import get_event as _get_event
from sports_skills.novig._connector import get_events as _get_events
from sports_skills.novig._connector import get_market as _get_market
from sports_skills.novig._connector import get_markets as _get_markets
from sports_skills.novig._connector import get_order_book as _get_order_book
from sports_skills.novig._connector import get_sports_config as _get_sports_config
from sports_skills.novig._connector import get_todays_events as _get_todays_events
from sports_skills.novig._connector import search_markets as _search_markets


def _req(**kwargs):
    """Build request_data dict from kwargs."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def get_sports_config() -> dict:
    """Get Novig sports, leagues, and accepted league aliases (e.g. 'cfb' -> 'NCAAF')."""
    return _get_sports_config(_req())


def get_events(*, league: str | None = None, limit: int = 50, after: str | None = None) -> dict:
    """Get Novig events (one upstream page).

    Args:
        league: League name or alias — 'NFL', 'NBA', 'MLB', 'NHL', 'NCAAF' ('cfb'), 'EPL', 'ATP', ...
        limit: Max events (default: 50, max: 100).
        after: Pagination cursor — the `next` value from a previous response.
    """
    return _get_events(_req(league=league, limit=limit, after=after))


def get_event(*, event_id: str) -> dict:
    """Get one Novig event.

    Args:
        event_id: Novig event id from get_events().
    """
    return _get_event(_req(event_id=event_id))


def get_markets(
    *,
    event_id: str | None = None,
    league: str | None = None,
    market_type: str | None = None,
    limit: int = 50,
    after: str | None = None,
) -> dict:
    """Get Novig catalog markets (outcomes, fee, void rules — no prices).

    Args:
        event_id: Restrict to one Novig event id.
        league: League name or alias ('NFL', 'cfb', 'EPL', ...).
        market_type: Upstream market type — 'MONEY', 'SPREAD', 'TOTAL', 'MONEY_1H', ...
        limit: Max markets (default: 50, max: 100).
        after: Pagination cursor — the `next` value from a previous response.
    """
    return _get_markets(_req(event_id=event_id, league=league, market_type=market_type, limit=limit, after=after))


def get_market(*, market_id: str) -> dict:
    """Get one Novig catalog market (no prices; use get_order_book).

    Args:
        market_id: Novig market id from get_markets().
    """
    return _get_market(_req(market_id=market_id))


def get_order_book(*, market_id: str, depth: int | None = None) -> dict:
    """Get a Novig market's order book: best bid per outcome and, for two-way markets, the derived ask.

    Args:
        market_id: Novig market id from get_markets().
        depth: Price levels per outcome to request upstream (1-20).
    """
    return _get_order_book(_req(market_id=market_id, depth=depth))


def search_markets(
    *,
    query: str | None = None,
    league: str | None = None,
    market_type: str | None = None,
    limit: int = 50,
) -> dict:
    """Primary tool for finding Novig markets by keyword and league (bounded scan, reports `truncated`).

    Args:
        query: Keywords; every token must appear in the event description (e.g. 'Commanders 49ers').
        league: League name or alias ('NFL', 'nba', 'cfb', 'EPL', ...).
        market_type: Upstream market type filter, e.g. 'MONEY'.
        limit: Max markets (default: 50, max: 100).
    """
    return _search_markets(_req(query=query, league=league, market_type=market_type, limit=limit))


def get_todays_events(*, league: str | None = None, limit: int = 50) -> dict:
    """Get Novig events starting today (UTC), optionally by league.

    Args:
        league: League name or alias ('NFL', 'mlb', 'cfb', ...).
        limit: Max events (default: 50, max: 100).
    """
    return _get_todays_events(_req(league=league, limit=limit))
