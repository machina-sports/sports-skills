"""Kalshi prediction markets — events, series, markets, trades, and candlesticks.

Public read-only endpoints. No authentication required. Uses stdlib only.
"""

from __future__ import annotations

from sports_skills.kalshi._connector import (
    get_event as _get_event,
)
from sports_skills.kalshi._connector import (
    get_events as _get_events,
)
from sports_skills.kalshi._connector import (
    get_exchange_schedule as _get_exchange_schedule,
)
from sports_skills.kalshi._connector import (
    get_exchange_status as _get_exchange_status,
)
from sports_skills.kalshi._connector import (
    get_market as _get_market,
)
from sports_skills.kalshi._connector import (
    get_market_candlesticks as _get_market_candlesticks,
)
from sports_skills.kalshi._connector import (
    get_markets as _get_markets,
)
from sports_skills.kalshi._connector import (
    get_series as _get_series,
)
from sports_skills.kalshi._connector import (
    get_series_list as _get_series_list,
)
from sports_skills.kalshi._connector import (
    get_sports_config as _get_sports_config,
)
from sports_skills.kalshi._connector import (
    get_sports_filters as _get_sports_filters,
)
from sports_skills.kalshi._connector import (
    get_todays_events as _get_todays_events,
)
from sports_skills.kalshi._connector import (
    get_trades as _get_trades,
)
from sports_skills.kalshi._connector import (
    search_markets as _search_markets,
)


def _req(**kwargs):
    """Build request_data dict from kwargs."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def get_exchange_status() -> dict:
    """Get exchange status (trading active, maintenance windows)."""
    return _get_exchange_status(_req())


def get_exchange_schedule() -> dict:
    """Get exchange operating schedule."""
    return _get_exchange_schedule(_req())


def get_series_list(*, category: str | None = None, tags: str | None = None) -> dict:
    """Low-level series listing. For sport-specific markets, prefer get_todays_events(sport=...) or search_markets(sport=...) instead."""
    return _get_series_list(_req(category=category, tags=tags))


def get_series(*, series_ticker: str) -> dict:
    """Get details for a specific series."""
    return _get_series(_req(series_ticker=series_ticker))


def get_events(
    *,
    limit: int = 100,
    cursor: str | None = None,
    status: str | None = None,
    series_ticker: str | None = None,
    with_nested_markets: bool = False,
) -> dict:
    """Low-level event listing. For sport-specific game markets, prefer get_todays_events(sport=...) which auto-filters by series ticker and includes nested markets."""
    return _get_events(
        _req(
            limit=limit,
            cursor=cursor,
            status=status,
            series_ticker=series_ticker,
            with_nested_markets=with_nested_markets,
        )
    )


def get_event(*, event_ticker: str, with_nested_markets: bool = False) -> dict:
    """Get details for a specific event."""
    return _get_event(
        _req(event_ticker=event_ticker, with_nested_markets=with_nested_markets)
    )


def get_markets(
    *,
    limit: int = 100,
    cursor: str | None = None,
    event_ticker: str | None = None,
    series_ticker: str | None = None,
    status: str | None = None,
    tickers: str | None = None,
) -> dict:
    """Low-level market listing. For sport-specific market search, prefer search_markets(sport=..., query=...) which auto-resolves series tickers and finds game-level markets."""
    return _get_markets(
        _req(
            limit=limit,
            cursor=cursor,
            event_ticker=event_ticker,
            series_ticker=series_ticker,
            status=status,
            tickers=tickers,
        )
    )


def get_market(*, ticker: str) -> dict:
    """Get details for a specific market."""
    return _get_market(_req(ticker=ticker))


def get_trades(
    *,
    limit: int = 100,
    cursor: str | None = None,
    ticker: str | None = None,
    min_ts: int | None = None,
    max_ts: int | None = None,
) -> dict:
    """Get recent trades with optional filtering."""
    return _get_trades(
        _req(limit=limit, cursor=cursor, ticker=ticker, min_ts=min_ts, max_ts=max_ts)
    )


def get_market_candlesticks(
    *,
    series_ticker: str,
    ticker: str,
    start_ts: int,
    end_ts: int,
    period_interval: int,
) -> dict:
    """Get candlestick (OHLC) data for a market.

    Args:
        period_interval: Candlestick interval in minutes (1, 60, or 1440).
    """
    return _get_market_candlesticks(
        _req(
            series_ticker=series_ticker,
            ticker=ticker,
            start_ts=start_ts,
            end_ts=end_ts,
            period_interval=period_interval,
        )
    )


def get_sports_filters() -> dict:
    """Get available sports filter categories (leagues, teams, etc.)."""
    return _get_sports_filters(_req())


def get_sports_config() -> dict:
    """Get available sport codes and their Kalshi series tickers.

    Returns sport codes you can use with search_markets(sport=...) and
    get_todays_events(sport=...).

    US sports: 'nba', 'nfl', 'nhl', 'mlb', 'wnba', 'cfb', 'cbb'.
    Football: 'epl', 'ucl', 'laliga', 'bundesliga', 'seriea', 'ligue1', 'mls', 'worldcup'.
    """
    return _get_sports_config(_req())


def get_todays_events(*, sport: str, limit: int = 50) -> dict:
    """Primary tool for finding game-day prediction markets for a sport. Use this instead of get_events when a sport context is available.

    Returns today's open events filtered by series ticker, with nested markets
    included. Covers spread, moneyline, totals, and player-prop markets.

    Args:
        sport: Sport code — US sports: 'nba', 'nfl', 'nhl', 'mlb', 'wnba',
            'cfb', 'cbb'. Football: 'epl', 'ucl', 'laliga', 'bundesliga',
            'seriea', 'ligue1', 'mls', 'worldcup'.
        limit: Max events (default: 50, max: 200).
    """
    return _get_todays_events(_req(sport=sport, limit=limit))


def search_markets(
    *,
    sport: str | None = None,
    query: str | None = None,
    status: str = "open",
    limit: int = 50,
) -> dict:
    """Primary tool for finding Kalshi markets by sport and keyword. Use this instead of get_markets when a sport context is available. Supports team mascots (e.g. Lakers).

    Auto-resolves sport codes to the correct series tickers so you get
    game-level markets (spread, totals, player props) — not just futures.

    Args:
        sport: Sport code — US sports: 'nba', 'nfl', 'nhl', 'mlb', 'wnba',
            'cfb', 'cbb'. Football: 'epl', 'ucl', 'laliga', 'bundesliga',
            'seriea', 'ligue1', 'mls', 'worldcup'. Resolves to series_ticker(s).
        query: Keyword to match in event/market titles.
        status: Market status filter (default: 'open').
        limit: Max results (default: 50, max: 200).
    """
    return _search_markets(_req(sport=sport, query=query, status=status, limit=limit))
