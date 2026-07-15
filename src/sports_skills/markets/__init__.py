"""Markets orchestration — connects ESPN schedules with Kalshi & Polymarket.

Bridges live sports schedules with prediction markets for unified dashboards,
odds comparison, entity search, and bet evaluation. Reuses betting module for
odds conversion and arbitrage detection.

No extra dependencies — uses existing sport modules and prediction market modules.
"""

from __future__ import annotations

from sports_skills.markets._connector import (
    compare_odds as _compare_odds,
)
from sports_skills.markets._connector import (
    evaluate_market as _evaluate_market,
)
from sports_skills.markets._connector import (
    get_live_tick as _get_live_tick,
)
from sports_skills.markets._connector import (
    get_market_price as _get_market_price,
)
from sports_skills.markets._connector import (
    get_mock_tick as _get_mock_tick,
)
from sports_skills.markets._connector import (
    get_plays_near_timestamp as _get_plays_near_timestamp,
)
from sports_skills.markets._connector import (
    get_price_history as _get_price_history,
)
from sports_skills.markets._connector import (
    get_sport_markets as _get_sport_markets,
)
from sports_skills.markets._connector import (
    get_sport_schedule as _get_sport_schedule,
)
from sports_skills.markets._connector import (
    get_todays_markets as _get_todays_markets,
)
from sports_skills.markets._connector import (
    match_markets as _match_markets,
)
from sports_skills.markets._connector import (
    normalize_price as _normalize_price,
)
from sports_skills.markets._connector import (
    search_entity as _search_entity,
)


def _req(**kwargs):
    """Build request_data dict from kwargs."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def get_todays_markets(*, sport: str | None = None, date: str | None = None) -> dict:
    """Fetch ESPN schedule, search both exchanges, return unified dashboard.

    Args:
        sport: Sport key (nba, nfl, mlb, nhl, wnba, cfb, cbb). Omit for all sports.
        date: Date in YYYY-MM-DD format. Defaults to today.
    """
    return _get_todays_markets(_req(sport=sport, date=date))


def search_entity(*, query: str, sport: str | None = None) -> dict:
    """Search Kalshi + Polymarket for a team, player, or event name.

    Args:
        query: Search query (e.g. "Lakers", "Patrick Mahomes", "Super Bowl").
        sport: Optional sport key to scope Kalshi search.
    """
    return _search_entity(_req(query=query, sport=sport))


def compare_odds(*, sport: str, event_id: str) -> dict:
    """ESPN odds + prediction market prices, normalized side-by-side + arb check.

    Args:
        sport: Sport key (nba, nfl, etc.).
        event_id: ESPN event ID (from get_scoreboard or get_sport_schedule).
    """
    return _compare_odds(_req(sport=sport, event_id=event_id))


def get_sport_markets(*, sport: str, status: str | None = None, limit: int | None = None) -> dict:
    """Sports-filtered market listing on both Kalshi and Polymarket.

    Args:
        sport: Sport key (nba, nfl, etc.).
        status: Market status filter (default: "open").
        limit: Max results per platform (default: 20).
    """
    return _get_sport_markets(_req(sport=sport, status=status, limit=limit))


def get_sport_schedule(*, sport: str | None = None, date: str | None = None) -> dict:
    """Unified ESPN schedule across one or all sports.

    Args:
        sport: Sport key. Omit for all sports.
        date: Date in YYYY-MM-DD format. Defaults to today.
    """
    return _get_sport_schedule(_req(sport=sport, date=date))


def match_markets(*, sport: str, date: str | None = None) -> dict:
    """Pair the same game across Kalshi and Polymarket.

    Single-game markets encode {date, away, home} deterministically in
    Kalshi event tickers and Polymarket slugs; games are joined on
    date + team codes, with fuzzy title matching as a fallback. Each
    match carries the Kalshi market tickers and the Polymarket token IDs
    so prices can be compared directly.

    Args:
        sport: League code available on both venues (mlb, nfl, nba, nhl,
            epl, worldcup, ...).
        date: Optional YYYY-MM-DD filter. Omit for all upcoming games.
    """
    return _match_markets(_req(sport=sport, date=date))


def get_market_price(
    *,
    venue: str,
    ticker: str | None = None,
    token_id: str | None = None,
    at_time: int | str | None = None,
) -> dict:
    """Current or point-in-time price for a market on either venue.

    Returns both sides as 0-1 probabilities in one shape regardless
    of venue.

    Args:
        venue: 'kalshi' or 'polymarket'.
        ticker: Kalshi market ticker (required for kalshi).
        token_id: Polymarket CLOB token ID (required for polymarket).
        at_time: Unix timestamp or ISO 8601 datetime for a historical
            price. Omit for the live price.
    """
    return _get_market_price(
        _req(venue=venue, ticker=ticker, token_id=token_id, at_time=at_time)
    )


def get_price_history(
    *,
    venue: str,
    ticker: str | None = None,
    token_id: str | None = None,
    interval: str | None = None,
    start_time: int | str | None = None,
    end_time: int | str | None = None,
) -> dict:
    """Price history for a market on either venue, in one shape.

    Points are {timestamp, price} with price as the 0-1 yes probability.

    Args:
        venue: 'kalshi' or 'polymarket'.
        ticker: Kalshi market ticker (required for kalshi).
        token_id: Polymarket CLOB token ID (required for polymarket).
        interval: '1m', '1h', or '1d' (default: '1d').
        start_time: Unix timestamp or ISO 8601 (defaults by interval).
        end_time: Unix timestamp or ISO 8601 (default: now).
    """
    return _get_price_history(
        _req(
            venue=venue,
            ticker=ticker,
            token_id=token_id,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
        )
    )


def get_mock_tick(*, mock_file_path: str, interval_seconds: int = 5) -> dict:
    """Deterministic timeline slice from a static mock game file.

    Returns the current tick chosen by system clock —
    ``(epoch // interval_seconds) % total_ticks`` — so a poller advances
    through the timeline as real time passes, with no state files. The
    returned ``data`` carries game_id, teams, timestamp, game_clock,
    play_by_play, and polymarket_home_price_cents for the current tick.

    Args:
        mock_file_path: Path to the mock game JSON (with a ``timeline`` array).
        interval_seconds: Seconds each tick is held (default: 5).
    """
    return _get_mock_tick(_req(mock_file_path=mock_file_path, interval_seconds=interval_seconds))


def get_plays_near_timestamp(
    *,
    sport: str,
    game_id: str,
    timestamp: str,
    window_seconds: int = 120,
) -> dict:
    """Plays in the window ``[timestamp - window_seconds, timestamp]``.

    Fetches raw ESPN play-by-play, parses each play's UTC ``wallclock``, and
    returns those landing in the window ending at ``timestamp`` — used to find
    the play(s) behind a market move detected at ``timestamp``.

    Args:
        sport: Sport key (nfl, nba, mlb, nhl, wnba, cfb, cbb).
        game_id: ESPN event ID.
        timestamp: ISO 8601 UTC instant, e.g. '2026-06-30T18:07:00Z'.
        window_seconds: Look-back window before timestamp (default: 120).
    """
    return _get_plays_near_timestamp(
        _req(
            sport=sport,
            game_id=game_id,
            timestamp=timestamp,
            window_seconds=window_seconds,
        )
    )


def get_live_tick(*, sport: str, event_id: str) -> dict:
    """Live market tick for an in-progress game — Kalshi home price + ESPN frame.

    Returns the same top-level shape as ``get_mock_tick`` (game_id, teams,
    timestamp, game_clock, plus the price) sourced from real data: teams and
    game clock from the ESPN summary, and the home win-probability from Kalshi.
    The price is under the source-neutral key ``home_price_cents`` (with
    ``price_source`` and ``kalshi_ticker``); ``game_id`` is the ESPN event id.

    Args:
        sport: Sport key (nfl, nba, mlb, nhl, wnba, cfb, cbb).
        event_id: ESPN event ID.
    """
    return _get_live_tick(_req(sport=sport, event_id=event_id))


def normalize_price(*, price: float, source: str) -> dict:
    """Convert any source format to common {implied_prob, american, decimal}.

    Args:
        price: The price/odds value to normalize.
        source: Source platform — "polymarket", "kalshi", or "espn".
    """
    return _normalize_price(_req(price=price, source=source))


def evaluate_market(
    *,
    sport: str,
    event_id: str,
    token_id: str | None = None,
    kalshi_ticker: str | None = None,
    outcome: int | None = None,
) -> dict:
    """All-in-one: ESPN odds + market price, devig, edge, Kelly.

    Args:
        sport: Sport key (nba, nfl, etc.).
        event_id: ESPN event ID.
        token_id: Polymarket token ID (optional, for direct price lookup).
        kalshi_ticker: Kalshi market ticker (optional, for direct price lookup).
        outcome: Which outcome to evaluate (0=home, 1=away, default: 0).
    """
    return _evaluate_market(
        _req(
            sport=sport,
            event_id=event_id,
            token_id=token_id,
            kalshi_ticker=kalshi_ticker,
            outcome=outcome,
        )
    )
