"""Polymarket sports prediction markets — prices, order books, events, and series.

Uses Gamma API (public, no auth) and CLOB API (public reads) via stdlib only.
Trading operations use the ``py_clob_client`` Python SDK (no CLI binary needed).
"""

from __future__ import annotations

from sports_skills.polymarket._cli import (
    cancel_all_orders as _cli_cancel_all_orders,
)
from sports_skills.polymarket._cli import (
    cancel_order as _cli_cancel_order,
)
from sports_skills.polymarket._cli import (
    configure as configure,
)
from sports_skills.polymarket._cli import (
    create_order as _cli_create_order,
)
from sports_skills.polymarket._cli import (
    get_orders as _cli_get_orders,
)
from sports_skills.polymarket._cli import (
    get_user_trades as _cli_get_user_trades,
)
from sports_skills.polymarket._cli import (
    is_cli_available as is_cli_available,
)
from sports_skills.polymarket._cli import (
    market_order as _cli_market_order,
)
from sports_skills.polymarket._connector import (
    get_esports_events as _get_esports_events,
)
from sports_skills.polymarket._connector import (
    get_event_details as _get_event_details,
)
from sports_skills.polymarket._connector import (
    get_last_trade_price as _get_last_trade_price,
)
from sports_skills.polymarket._connector import (
    get_market_details as _get_market_details,
)
from sports_skills.polymarket._connector import (
    get_market_prices as _get_market_prices,
)
from sports_skills.polymarket._connector import (
    get_order_book as _get_order_book,
)
from sports_skills.polymarket._connector import (
    get_price_history as _get_price_history,
)
from sports_skills.polymarket._connector import (
    get_series as _get_series,
)
from sports_skills.polymarket._connector import (
    get_sports_config as _get_sports_config,
)
from sports_skills.polymarket._connector import (
    get_sports_events as _get_sports_events,
)
from sports_skills.polymarket._connector import (
    get_sports_market_types as _get_sports_market_types,
)
from sports_skills.polymarket._connector import (
    get_sports_markets as _get_sports_markets,
)
from sports_skills.polymarket._connector import (
    get_todays_events as _get_todays_events,
)
from sports_skills.polymarket._connector import (
    search_markets as _search_markets,
)


def _req(**kwargs):
    """Build request_data dict from kwargs."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


# ============================================================
# Connector Commands (Gamma/CLOB API — no auth needed)
# ============================================================


def get_sports_markets(
    *,
    limit: int = 50,
    offset: int = 0,
    sports_market_types: str | None = None,
    game_id: str | None = None,
    active: bool = True,
    closed: bool = False,
    order: str = "volume",
    ascending: bool = False,
) -> dict:
    """Get active sports prediction markets with optional filtering."""
    return _get_sports_markets(
        _req(
            limit=limit,
            offset=offset,
            sports_market_types=sports_market_types,
            game_id=game_id,
            active=active,
            closed=closed,
            order=order,
            ascending=ascending,
        )
    )


def get_sports_events(
    *,
    limit: int = 50,
    offset: int = 0,
    active: bool = True,
    closed: bool = False,
    order: str = "volume",
    ascending: bool = False,
    series_id: str | None = None,
) -> dict:
    """Get sports events (each event groups related markets)."""
    return _get_sports_events(
        _req(
            limit=limit,
            offset=offset,
            active=active,
            closed=closed,
            order=order,
            ascending=ascending,
            series_id=series_id,
        )
    )


def get_series(*, limit: int = 100, offset: int = 0) -> dict:
    """Get all series (leagues, recurring event groups)."""
    return _get_series(_req(limit=limit, offset=offset))


def get_market_details(
    *, market_id: str | None = None, slug: str | None = None
) -> dict:
    """Get detailed information for a specific market."""
    return _get_market_details(_req(market_id=market_id, slug=slug))


def get_event_details(*, event_id: str | None = None, slug: str | None = None) -> dict:
    """Get detailed information for a specific event (includes nested markets)."""
    return _get_event_details(_req(event_id=event_id, slug=slug))


def get_market_prices(
    *, token_id: str | None = None, token_ids: list[str] | None = None
) -> dict:
    """Get current prices for one or more markets from the CLOB API."""
    return _get_market_prices(_req(token_id=token_id, token_ids=token_ids))


def get_order_book(*, token_id: str) -> dict:
    """Get the full order book for a market."""
    return _get_order_book(_req(token_id=token_id))


def get_sports_market_types() -> dict:
    """Get all valid sports market types (moneyline, spreads, totals, props, etc.)."""
    return _get_sports_market_types(_req())


def get_sports_config() -> dict:
    """Get available sports and their series IDs for filtering.

    Returns sport codes you can use with search_markets(sport=...) and
    get_todays_events(sport=...). Examples: 'nba', 'epl', 'nfl', 'nhl',
    'mlb', 'bun', 'fl1', 'ucl', 'mls', 'atp', 'wta'.
    """
    return _get_sports_config(_req())


def get_todays_events(*, sport: str, limit: int = 30) -> dict:
    """Get today's events (single-game markets) for a specific sport.

    Args:
        sport: Sport code — e.g. 'nba', 'epl', 'nfl', 'nhl', 'mlb',
            'bun', 'fl1', 'ucl', 'mls', 'atp', 'wta', 'lal'.
        limit: Max events (default: 30, max: 100).
    """
    return _get_todays_events(_req(sport=sport, limit=limit))


def search_markets(
    *,
    query: str | None = None,
    sport: str | None = None,
    sports_market_types: str | None = None,
    tag_id: int | None = None,
    limit: int = 20,
) -> dict:
    """Find sports markets by keyword, sport, or market type.

    Args:
        query: Keyword to match (e.g. 'Lakers', 'Leeds', 'Bayern').
        sport: Sport code to filter by league (e.g. 'nba', 'epl', 'nfl').
            Use get_sports_config() to see all available codes.
        sports_market_types: Filter by type ('moneyline', 'spreads', 'totals').
        tag_id: Tag ID (default: 1 = Sports).
        limit: Max results (default: 20, max: 100).
    """
    return _search_markets(
        _req(
            query=query,
            sport=sport,
            sports_market_types=sports_market_types,
            tag_id=tag_id,
            limit=limit,
        )
    )


def get_price_history(
    *, token_id: str, interval: str = "max", fidelity: int = 120
) -> dict:
    """Get historical price data for a market over time."""
    return _get_price_history(
        _req(token_id=token_id, interval=interval, fidelity=fidelity)
    )


def get_last_trade_price(*, token_id: str) -> dict:
    """Get the most recent trade price for a market."""
    return _get_last_trade_price(_req(token_id=token_id))


def get_esports_events(
    *, query: str | None = None, limit: int = 30, closed: bool = False
) -> dict:
    """Esports prediction markets on Polymarket (CS2, LoL, Dota2, Valorant). Implied probabilities via outcome prices."""
    return _get_esports_events(_req(query=query, limit=limit, closed=closed))


# ============================================================
# Trading Commands (requires py_clob_client + wallet)
# ============================================================


def create_order(
    *,
    token_id: str,
    side: str,
    price: str,
    size: str,
    order_type: str = "GTC",
) -> dict:
    """Place a limit order. Auth required: set POLYMARKET_PRIVATE_KEY=0x... in .env or call configure(private_key=...) first.

    Args:
        token_id: Market token ID.
        side: Order side — "buy" or "sell".
        price: Limit price (0.01–0.99).
        size: Number of shares.
        order_type: Order type — "GTC" (default), "FOK", or "GTD".
    """
    return _cli_create_order(
        token_id=token_id, side=side, price=price, size=size, order_type=order_type
    )


def market_order(*, token_id: str, side: str, amount: str) -> dict:
    """Place a market order. Auth required: set POLYMARKET_PRIVATE_KEY=0x... in .env or call configure(private_key=...) first.

    Args:
        token_id: Market token ID.
        side: Order side — "buy" or "sell".
        amount: USDC amount to spend.
    """
    return _cli_market_order(token_id=token_id, side=side, amount=amount)


def cancel_order(*, order_id: str) -> dict:
    """Cancel a specific order. Auth required: set POLYMARKET_PRIVATE_KEY=0x... in .env or call configure(private_key=...) first."""
    return _cli_cancel_order(order_id=order_id)


def cancel_all_orders() -> dict:
    """Cancel all open orders. Auth required: set POLYMARKET_PRIVATE_KEY=0x... in .env or call configure(private_key=...) first."""
    return _cli_cancel_all_orders()


def get_orders(*, market: str | None = None) -> dict:
    """View open orders. Auth required: set POLYMARKET_PRIVATE_KEY=0x... in .env or call configure(private_key=...) first."""
    return _cli_get_orders(market=market)


def get_user_trades() -> dict:
    """View your recent trades. Auth required: set POLYMARKET_PRIVATE_KEY=0x... in .env or call configure(private_key=...) first."""
    return _cli_get_user_trades()
