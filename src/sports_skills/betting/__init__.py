"""Betting analysis — odds conversion, de-vigging, edge detection, Kelly criterion.

Source-agnostic: works with odds from ESPN, Polymarket, Kalshi, or any sportsbook.
Pure computation — no network calls, no auth required.
"""

from __future__ import annotations

from sports_skills.betting._calcs import convert_odds as _convert_odds
from sports_skills.betting._calcs import devig as _devig
from sports_skills.betting._calcs import evaluate_bet as _evaluate_bet
from sports_skills.betting._calcs import find_arbitrage as _find_arbitrage
from sports_skills.betting._calcs import find_edge as _find_edge
from sports_skills.betting._calcs import kelly_criterion as _kelly_criterion
from sports_skills.betting._calcs import line_movement as _line_movement
from sports_skills.betting._calcs import matchup_probability as _matchup_probability
from sports_skills.betting._calcs import parlay_analysis as _parlay_analysis


def _req(**kwargs):
    """Build request_data dict from kwargs."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def convert_odds(*, odds: float, from_format: str = "american") -> dict:
    """Convert odds between American, decimal, and probability formats.

    Args:
        odds: The odds value to convert (e.g. -150, 2.5, or 0.6).
        from_format: Source format — "american" (default), "decimal", or "probability".
    """
    return _convert_odds(_req(odds=odds, from_format=from_format))


def devig(*, odds: str, format: str = "american") -> dict:
    """Remove vig/juice from sportsbook odds to get fair probabilities.

    Args:
        odds: Comma-separated odds for ALL outcomes (e.g. "-150,+130" for a
            2-way market, "-110,-110" for spread/total).
        format: Odds format — "american" (default), "decimal", or "probability".
    """
    return _devig(_req(odds=odds, format=format))


def find_edge(*, fair_prob: float, market_prob: float) -> dict:
    """Compare fair probability to market price — compute edge, EV, and Kelly.

    Args:
        fair_prob: True/fair probability of the outcome, 0-1 (e.g. 0.58).
        market_prob: Market price / implied probability to bet at, 0-1 (e.g. 0.52).
    """
    return _find_edge(_req(fair_prob=fair_prob, market_prob=market_prob))


def kelly_criterion(*, fair_prob: float, market_prob: float) -> dict:
    """Compute the Kelly fraction from fair and market probabilities.

    Args:
        fair_prob: True/fair probability of winning, 0-1 (e.g. 0.58).
        market_prob: Market price you would buy at, 0-1 (e.g. 0.52).
    """
    return _kelly_criterion(_req(fair_prob=fair_prob, market_prob=market_prob))


def evaluate_bet(
    *,
    book_odds: str,
    market_prob: float,
    book_format: str = "american",
    outcome: int = 0,
) -> dict:
    """Full bet evaluation: book odds + market price → devig → edge → Kelly.

    Args:
        book_odds: Comma-separated sportsbook odds for ALL outcomes
            (e.g. "-150,+130" for a 2-way market).
        market_prob: Prediction market price (0-1) for the outcome being
            evaluated.
        book_format: Format of book_odds — "american" (default), "decimal",
            or "probability".
        outcome: Which outcome to evaluate, 0-indexed into book_odds
            (default: 0 = first outcome).
    """
    return _evaluate_bet(
        _req(
            book_odds=book_odds,
            market_prob=market_prob,
            book_format=book_format,
            outcome=outcome,
        )
    )


def find_arbitrage(
    *, market_probs: str, labels: str | None = None
) -> dict:
    """Detect arbitrage opportunities across outcomes.

    Args:
        market_probs: Comma-separated market probabilities for ALL outcomes,
            0-1 each (e.g. "0.48,0.49" for 2-way, "0.40,0.25,0.30" for 3-way).
        labels: Optional comma-separated outcome labels (e.g. "home,away").
    """
    return _find_arbitrage(_req(market_probs=market_probs, labels=labels))


def parlay_analysis(
    *,
    legs: str,
    parlay_odds: float,
    odds_format: str = "american",
    correlation: float = 0.0,
) -> dict:
    """Analyze a multi-leg parlay: combined probability, EV, and Kelly.

    Args:
        legs: Comma-separated fair probabilities per leg, 0-1 each
            (e.g. "0.58,0.62,0.55").
        parlay_odds: Offered parlay payout (e.g. 600 for +600 American,
            or 7.0 decimal).
        odds_format: Format of parlay_odds — "american" (default) or "decimal".
        correlation: Correlation adjustment, 0.0-0.5 (0.0 = independent legs;
            positive for correlated legs like same-game parlays).
    """
    return _parlay_analysis(
        _req(
            legs=legs,
            parlay_odds=parlay_odds,
            odds_format=odds_format,
            correlation=correlation,
        )
    )


def matchup_probability(*, bpi_a: float, bpi_b: float) -> dict:
    """Compute win probability from BPI ratings using a logistic model.

    Args:
        bpi_a: BPI rating for team A.
        bpi_b: BPI rating for team B.
    """
    return _matchup_probability(_req(bpi_a=bpi_a, bpi_b=bpi_b))


def line_movement(
    *,
    open_odds: float | None = None,
    close_odds: float | None = None,
    open_line: float | None = None,
    close_line: float | None = None,
    market_type: str = "moneyline",
) -> dict:
    """Analyze line movement between open and close.

    Args:
        open_odds: Opening American odds (e.g. -140). For moneyline markets.
        close_odds: Closing American odds (e.g. -160). For moneyline markets.
        open_line: Opening spread/total line (e.g. -6.5). For spread/total markets.
        close_line: Closing spread/total line (e.g. -7.5). For spread/total markets.
        market_type: "moneyline" (default), "spread", or "total".
    """
    return _line_movement(
        _req(
            open_odds=open_odds,
            close_odds=close_odds,
            open_line=open_line,
            close_line=close_line,
            market_type=market_type,
        )
    )
