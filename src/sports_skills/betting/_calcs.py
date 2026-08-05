"""Betting analysis — odds conversion, de-vigging, edge detection, Kelly criterion.

Pure-computation module (no network calls). Uses stdlib only.
Works with odds from any source: ESPN (American), Polymarket (decimal prob),
Kalshi (integer prob), or raw decimal odds.

Functions:
1. convert_odds     — convert between American, decimal, and probability formats
2. devig            — strip vig/juice from sportsbook odds to get fair probabilities
3. find_edge        — compare fair probability to market price, compute edge + EV
4. kelly_criterion  — optimal bet sizing from two probabilities (no user estimation)
5. evaluate_bet     — all-in-one: book odds + market price → full risk profile
6. find_arbitrage   — detect guaranteed-profit opportunities across sources
7. parlay_analysis  — multi-leg parlay EV and Kelly analysis
8. line_movement    — quantify open→close line shifts
"""

from __future__ import annotations

# ============================================================
# Response Helpers
# ============================================================


def _success(data, message=""):
    return {"status": True, "data": data, "message": message}


def _error(message, data=None):
    return {"status": False, "data": data, "message": message}


# ============================================================
# Internal: American odds ↔ implied probability
# ============================================================


_MIN_AMERICAN = 100


def _invalid_american(*values: float) -> str | None:
    """Return an error message if any value is not a valid American price.

    The American scale runs from +100 (even money) upward for underdogs and from
    -100 downward for favorites; nothing lies between. The conversion formula
    degrades silently inside that band and even inverts the sign convention —
    -50 comes out as a 33% chance when negative odds must mean a favorite — so a
    value there is rejected rather than answered with a confident number. Decimal
    odds passed as American land here too, which is the common way to hit it.
    """
    bad = [v for v in values if -_MIN_AMERICAN < v < _MIN_AMERICAN]
    if not bad:
        return None
    shown = ", ".join(f"{v:g}" for v in bad)
    return (
        f"Invalid American odds: {shown}. American prices must be <= -100 or >= +100 "
        "(nothing lies between). If these are decimal odds or probabilities, pass "
        "them with from_format='decimal' or from_format='probability'."
    )


def _american_to_prob(odds: float) -> float:
    """Convert American odds to implied probability (0-1).

    Callers must validate with :func:`_invalid_american` first; this assumes a
    price already on the scale.
    """
    if odds < 0:
        return -odds / (-odds + 100)
    elif odds > 0:
        return 100 / (odds + 100)
    else:
        # Unreachable for validated input; even money rather than a ZeroDivision.
        return 0.5


def _prob_to_american(prob: float) -> float:
    """Convert implied probability (0-1) to American odds."""
    if prob <= 0 or prob >= 1:
        return 0.0
    if prob >= 0.5:
        return -(prob / (1 - prob)) * 100
    else:
        return ((1 - prob) / prob) * 100


def _decimal_to_prob(odds: float) -> float:
    """Convert decimal odds (e.g. 2.5) to implied probability."""
    if odds <= 0:
        return 0.0
    return 1.0 / odds


def _prob_to_decimal(prob: float) -> float:
    """Convert implied probability to decimal odds."""
    if prob <= 0:
        return 0.0
    return 1.0 / prob


# ============================================================
# 1. Convert Odds
# ============================================================


def convert_odds(request_data: dict) -> dict:
    """Convert odds between American, decimal, and probability formats.

    Params:
        odds (float): The odds value to convert.
        from_format (str): Source format — "american", "decimal", or "probability".
    """
    params = request_data.get("params", {})
    try:
        odds = float(params.get("odds", 0))
    except (TypeError, ValueError) as e:
        return _error(f"Invalid odds value: {e}")

    from_format = str(params.get("from_format", "american")).lower()

    if from_format == "american":
        bad = _invalid_american(odds)
        if bad:
            return _error(bad)
        prob = _american_to_prob(odds)
        decimal_odds = _prob_to_decimal(prob)
        american = odds
    elif from_format == "decimal":
        if odds <= 1.0:
            return _error("Decimal odds must be greater than 1.0")
        prob = _decimal_to_prob(odds)
        american = _prob_to_american(prob)
        decimal_odds = odds
    elif from_format == "probability":
        if not 0 < odds < 1:
            return _error("Probability must be between 0 and 1 (exclusive)")
        prob = odds
        american = _prob_to_american(prob)
        decimal_odds = _prob_to_decimal(prob)
    else:
        return _error(
            f"Unknown format '{from_format}'. Use 'american', 'decimal', or 'probability'"
        )

    return _success(
        {
            "implied_probability": round(prob, 6),
            "american": round(american, 1),
            "decimal": round(decimal_odds, 4),
            "from_format": from_format,
            "input_odds": odds,
        },
        f"Implied probability: {prob:.1%}",
    )


# ============================================================
# 2. De-vig
# ============================================================


def devig(request_data: dict) -> dict:
    """Remove vig/juice from sportsbook odds to get fair probabilities.

    Uses the multiplicative (proportional) method:
    fair_prob[i] = raw_prob[i] / sum(raw_probs)

    Params:
        odds (str): Comma-separated odds for all outcomes
                     (e.g. "-150,+130" for a 2-way, or "-110,-110" for spread/total).
        format (str): Odds format — "american" (default), "decimal", or "probability".
    """
    params = request_data.get("params", {})
    raw = params.get("odds", "")
    if not raw:
        return _error("odds is required (comma-separated, e.g. '-150,+130')")

    try:
        if isinstance(raw, str):
            odds_list = [float(o.strip()) for o in raw.split(",")]
        elif isinstance(raw, list):
            odds_list = [float(o) for o in raw]
        else:
            return _error("odds must be a comma-separated string or list")
    except (TypeError, ValueError) as e:
        return _error(f"Invalid odds format: {e}")

    if len(odds_list) < 2:
        return _error("Need at least 2 outcome odds to de-vig")

    fmt = str(params.get("format", "american")).lower()

    # Convert all to implied probabilities
    if fmt == "american":
        bad = _invalid_american(*odds_list)
        if bad:
            return _error(bad)
        raw_probs = [_american_to_prob(o) for o in odds_list]
    elif fmt == "decimal":
        raw_probs = [_decimal_to_prob(o) for o in odds_list]
    elif fmt == "probability":
        raw_probs = list(odds_list)
    else:
        return _error(
            f"Unknown format '{fmt}'. Use 'american', 'decimal', or 'probability'"
        )

    if any(p <= 0 for p in raw_probs):
        return _error("All implied probabilities must be positive")

    overround = sum(raw_probs)
    fair_probs = [p / overround for p in raw_probs]
    vig_pct = (overround - 1.0) * 100

    outcomes = []
    for i, (odds_val, raw_p, fair_p) in enumerate(
        zip(odds_list, raw_probs, fair_probs)
    ):
        outcomes.append(
            {
                "outcome": i,
                "input_odds": odds_val,
                "implied_prob": round(raw_p, 6),
                "fair_prob": round(fair_p, 6),
                "fair_american": round(_prob_to_american(fair_p), 1),
            }
        )

    return _success(
        {
            "outcomes": outcomes,
            "overround": round(overround, 6),
            "vig_pct": round(vig_pct, 2),
            "format": fmt,
        },
        f"Vig: {vig_pct:.2f}% | Fair probs: {', '.join(f'{p:.1%}' for p in fair_probs)}",
    )


# ============================================================
# 3. Find Edge
# ============================================================


def find_edge(request_data: dict) -> dict:
    """Compare fair probability to market price — compute edge, EV, and Kelly.

    The agent provides both values from data it already has:
    - fair_prob: from de-vigged sportsbook odds (ESPN/DraftKings)
    - market_prob: from a prediction market (Polymarket, Kalshi)

    Params:
        fair_prob (float): True/fair probability of the outcome (0-1).
        market_prob (float): Market price / implied probability to bet at (0-1).
    """
    params = request_data.get("params", {})
    try:
        fair_prob = float(params.get("fair_prob", 0))
        market_prob = float(params.get("market_prob", 0))
    except (TypeError, ValueError) as e:
        return _error(f"Invalid parameters: {e}")

    if not 0 < fair_prob < 1:
        return _error("fair_prob must be between 0 and 1 (exclusive)")
    if not 0 < market_prob < 1:
        return _error("market_prob must be between 0 and 1 (exclusive)")

    edge = fair_prob - market_prob
    ev_per_dollar = fair_prob / market_prob - 1.0  # ROI per $1 bet
    kelly = (fair_prob - market_prob) / (1.0 - market_prob) if market_prob < 1 else 0.0

    if edge > 0:
        recommendation = "bet"
        rating = "positive edge"
    elif edge == 0:
        recommendation = "no bet"
        rating = "no edge"
    else:
        recommendation = "no bet"
        rating = "negative edge"

    return _success(
        {
            "edge": round(edge, 6),
            "edge_pct": f"{edge * 100:.2f}%",
            "ev_per_dollar": round(ev_per_dollar, 6),
            "kelly_fraction": round(kelly, 6),
            "fair_prob": fair_prob,
            "market_prob": market_prob,
            "recommendation": recommendation,
        },
        f"Edge: {edge * 100:.2f}% ({rating}) | EV: {ev_per_dollar * 100:.2f}% | Kelly: {kelly:.4f}",
    )


# ============================================================
# 4. Kelly Criterion
# ============================================================


def kelly_criterion(request_data: dict) -> dict:
    """Compute the Kelly fraction from fair probability and market probability.

    f* = (fair_prob - market_prob) / (1 - market_prob)

    Equivalent to the classical f* = (p*b - q) / b where:
      p = fair_prob, b = (1/market_prob) - 1

    Params:
        fair_prob (float): True/fair probability of winning (0-1).
        market_prob (float): Market price you'd buy at (0-1).
    """
    params = request_data.get("params", {})
    try:
        fair_prob = float(params.get("fair_prob", 0))
        market_prob = float(params.get("market_prob", 0))
    except (TypeError, ValueError) as e:
        return _error(f"Invalid parameters: {e}")

    if not 0 < fair_prob < 1:
        return _error("fair_prob must be between 0 and 1 (exclusive)")
    if not 0 < market_prob < 1:
        return _error("market_prob must be between 0 and 1 (exclusive)")

    edge = fair_prob - market_prob
    f_star = edge / (1.0 - market_prob)
    b = (1.0 / market_prob) - 1.0  # net odds equivalent
    ev_per_dollar = fair_prob / market_prob - 1.0

    return _success(
        {
            "kelly_fraction": round(f_star, 6),
            "edge": round(edge, 6),
            "ev_per_dollar": round(ev_per_dollar, 6),
            "fair_prob": fair_prob,
            "market_prob": market_prob,
            "net_odds": round(b, 4),
            "recommendation": "bet" if f_star > 0 else "no bet",
        },
        f"Kelly fraction: {f_star:.4f} ({'positive edge' if f_star > 0 else 'negative edge'})",
    )


# ============================================================
# 5. Evaluate Bet (all-in-one)
# ============================================================


def evaluate_bet(request_data: dict) -> dict:
    """Full bet evaluation: convert book odds → de-vig → edge → Kelly.

    Takes sportsbook odds and a prediction market price, computes everything
    without requiring the user to estimate probabilities.

    Params:
        book_odds (str): Comma-separated sportsbook odds for all outcomes
                         (e.g. "-150,+130" for a 2-way market).
        market_prob (float): Prediction market price for the outcome you're
                             evaluating (0-1). This is the first outcome in book_odds.
        book_format (str): Format of book_odds — "american" (default), "decimal",
                           or "probability".
        outcome (int): Which outcome to evaluate (0-indexed, default: 0 = first).
    """
    params = request_data.get("params", {})

    # Step 1: De-vig the book odds
    book_odds = params.get("book_odds", "")
    if not book_odds:
        return _error("book_odds is required (e.g. '-150,+130')")

    book_format = str(params.get("book_format", "american")).lower()
    devig_result = devig({"params": {"odds": book_odds, "format": book_format}})
    if not devig_result["status"]:
        return devig_result

    # Step 2: Get fair probability for the target outcome
    outcome_idx = int(params.get("outcome", 0))
    outcomes = devig_result["data"]["outcomes"]
    if outcome_idx < 0 or outcome_idx >= len(outcomes):
        return _error(
            f"outcome index {outcome_idx} out of range (0-{len(outcomes) - 1})"
        )
    fair_prob = outcomes[outcome_idx]["fair_prob"]

    # Step 3: Get market probability
    try:
        market_prob = float(params.get("market_prob", 0))
    except (TypeError, ValueError) as e:
        return _error(f"Invalid market_prob: {e}")

    if not 0 < market_prob < 1:
        return _error("market_prob must be between 0 and 1 (exclusive)")

    # Step 4: Edge + Kelly
    edge_result = find_edge(
        {"params": {"fair_prob": fair_prob, "market_prob": market_prob}}
    )
    if not edge_result["status"]:
        return edge_result

    # Build response
    edge = edge_result["data"]["edge"]
    kelly = edge_result["data"]["kelly_fraction"]
    ev = edge_result["data"]["ev_per_dollar"]

    data = {
        "devig": devig_result["data"],
        "edge": edge_result["data"],
        "recommendation": "bet" if kelly > 0 else "no bet",
        "summary": (
            f"Fair: {fair_prob:.1%} | Market: {market_prob:.1%} | "
            f"Edge: {edge * 100:.2f}% | Kelly: {kelly:.4f} | EV: {ev * 100:.2f}%"
        ),
    }

    return _success(data, data["summary"])


# ============================================================
# 6. Arbitrage Detection
# ============================================================


def find_arbitrage(request_data: dict) -> dict:
    """Detect arbitrage opportunities across outcomes.

    If the sum of market probabilities for all outcomes is less than 1.0,
    there is a guaranteed-profit arbitrage opportunity. When no arbitrage
    exists, reports the overround (vig embedded in the prices).

    Params:
        market_probs (str): Comma-separated market probabilities for ALL outcomes
                            (0-1 each), e.g. "0.48,0.49" for 2-way or "0.40,0.25,0.30"
                            for 3-way.
        labels (str): Optional comma-separated outcome labels, e.g. "home,away".
    """
    params = request_data.get("params", {})
    raw = params.get("market_probs", "")
    if not raw:
        return _error("market_probs is required (comma-separated, e.g. '0.48,0.49')")

    try:
        if isinstance(raw, str):
            probs = [float(p.strip()) for p in raw.split(",")]
        elif isinstance(raw, list):
            probs = [float(p) for p in raw]
        else:
            return _error("market_probs must be a comma-separated string or list")
    except (TypeError, ValueError) as e:
        return _error(f"Invalid market_probs format: {e}")

    if len(probs) < 2:
        return _error("Need at least 2 outcome probabilities")
    if any(p <= 0 or p >= 1 for p in probs):
        return _error("All probabilities must be between 0 and 1 (exclusive)")

    # Parse labels
    raw_labels = params.get("labels", "")
    if raw_labels:
        if isinstance(raw_labels, str):
            labels = [l.strip() for l in raw_labels.split(",")]
        elif isinstance(raw_labels, list):
            labels = [str(l) for l in raw_labels]
        else:
            labels = None
        if labels and len(labels) != len(probs):
            return _error(
                f"labels count ({len(labels)}) must match market_probs count ({len(probs)})"
            )
    else:
        labels = None

    total_implied = sum(probs)
    arb_found = total_implied < 1.0

    if arb_found:
        arb_pct = (1.0 / total_implied - 1.0) * 100
    else:
        arb_pct = 0.0

    overround_pct = (total_implied - 1.0) * 100

    allocations = []
    for i, prob in enumerate(probs):
        alloc_pct = (prob / total_implied) * 100
        entry = {
            "outcome": i,
            "market_prob": prob,
            "allocation_pct": round(alloc_pct, 2),
        }
        if labels:
            entry["label"] = labels[i]
        allocations.append(entry)

    data = {
        "arbitrage_found": arb_found,
        "total_implied": round(total_implied, 6),
        "arbitrage_pct": round(arb_pct, 2),
        "overround_pct": round(overround_pct, 2),
        "allocations": allocations,
    }

    if arb_found:
        msg = f"Arbitrage found: {arb_pct:.2f}% guaranteed ROI"
    else:
        msg = f"No arbitrage (overround: {overround_pct:.2f}%)"

    return _success(data, msg)


# ============================================================
# 7. Parlay Analysis
# ============================================================


def parlay_analysis(request_data: dict) -> dict:
    """Analyze a multi-leg parlay: combined probability, EV, and Kelly.

    Computes the combined fair probability from independent legs, compares
    to the offered parlay odds, and determines if the parlay is +EV.

    Params:
        legs (str): Comma-separated fair probabilities per leg (0-1 each),
                     e.g. "0.58,0.62,0.55".
        parlay_odds (float): Offered parlay payout (American by default, e.g. 600
                              for +600, or decimal like 7.0).
        odds_format (str): Format of parlay_odds — "american" (default) or "decimal".
        correlation (float): Correlation adjustment (0.0 = independent, max 0.5). Positive
                              values increase combined probability since correlated legs
                              are more likely to co-occur (e.g. same-game parlays).
    """
    params = request_data.get("params", {})

    # Parse legs
    raw = params.get("legs", "")
    if not raw:
        return _error("legs is required (comma-separated fair probs, e.g. '0.58,0.62,0.55')")
    try:
        if isinstance(raw, str):
            leg_probs = [float(l.strip()) for l in raw.split(",")]
        elif isinstance(raw, list):
            leg_probs = [float(l) for l in raw]
        else:
            return _error("legs must be a comma-separated string or list")
    except (TypeError, ValueError) as e:
        return _error(f"Invalid legs format: {e}")

    if any(p <= 0 or p >= 1 for p in leg_probs):
        return _error("All leg probabilities must be between 0 and 1 (exclusive)")

    # Parse parlay odds
    try:
        parlay_odds = float(params.get("parlay_odds", 0))
    except (TypeError, ValueError) as e:
        return _error(f"Invalid parlay_odds: {e}")

    odds_format = str(params.get("odds_format", "american")).lower()
    if odds_format == "american":
        bad = _invalid_american(parlay_odds)
        if bad:
            return _error(bad)
        implied_prob = _american_to_prob(parlay_odds)
        offered_american = parlay_odds
        offered_decimal = _prob_to_decimal(implied_prob)
    elif odds_format == "decimal":
        if parlay_odds <= 1.0:
            return _error("Decimal parlay_odds must be greater than 1.0")
        implied_prob = _decimal_to_prob(parlay_odds)
        offered_decimal = parlay_odds
        offered_american = _prob_to_american(implied_prob)
    else:
        return _error(f"Unknown odds_format '{odds_format}'. Use 'american' or 'decimal'")

    # Correlation
    try:
        correlation = float(params.get("correlation", 0.0))
    except (TypeError, ValueError):
        correlation = 0.0
    if correlation < 0 or correlation > 0.5:
        return _error("correlation must be between 0 and 0.5")

    # Combined fair probability
    # For independent legs: product of probs.
    # Correlation adjustment: blend between independent (product) and
    # "perfectly correlated" (min leg prob).  This gives a reasonable
    # approximation for same-game parlays without requiring a full
    # copula model.
    independent_prob = 1.0
    for p in leg_probs:
        independent_prob *= p
    if correlation > 0 and len(leg_probs) >= 2:
        min_leg = min(leg_probs)
        combined_adjusted = independent_prob + correlation * (min_leg - independent_prob)
    else:
        combined_adjusted = independent_prob

    fair_american = _prob_to_american(combined_adjusted)
    fair_decimal = _prob_to_decimal(combined_adjusted)

    # Edge and EV
    edge = combined_adjusted - implied_prob
    ev_per_dollar = combined_adjusted / implied_prob - 1.0 if implied_prob > 0 else 0.0
    is_plus_ev = edge > 0

    # Kelly on the parlay
    kelly = (combined_adjusted - implied_prob) / (1.0 - implied_prob) if implied_prob < 1 else 0.0

    # Build legs detail
    legs_detail = []
    for i, p in enumerate(leg_probs):
        legs_detail.append({
            "leg": i,
            "fair_prob": p,
            "fair_american": round(_prob_to_american(p), 1),
        })

    data = {
        "num_legs": len(leg_probs),
        "legs": legs_detail,
        "combined_fair_prob": round(combined_adjusted, 6),
        "fair_parlay_american": round(fair_american, 1),
        "fair_parlay_decimal": round(fair_decimal, 4),
        "offered_parlay_american": round(offered_american, 1),
        "offered_parlay_decimal": round(offered_decimal, 4),
        "implied_parlay_prob": round(implied_prob, 6),
        "edge": round(edge, 6),
        "edge_pct": f"{edge * 100:.2f}%",
        "ev_per_dollar": round(ev_per_dollar, 6),
        "is_plus_ev": is_plus_ev,
        "kelly_fraction": round(kelly, 6),
        "correlation_applied": correlation,
    }

    if is_plus_ev:
        recommendation = f"+EV parlay (edge: {edge * 100:.2f}%)"
    else:
        recommendation = f"-EV parlay (edge: {edge * 100:.2f}%). No bet."

    data["recommendation"] = recommendation

    msg = (
        f"{len(leg_probs)}-leg parlay | "
        f"Fair: {combined_adjusted:.1%} | "
        f"Offered: {'+' if offered_american > 0 else ''}{offered_american:.0f} ({implied_prob:.1%}) | "
        f"Edge: {edge * 100:.2f}% | "
        f"{'+ EV' if is_plus_ev else '- EV'}"
    )

    return _success(data, msg)


# ============================================================
# 8. Line Movement Analysis
# ============================================================


def line_movement(request_data: dict) -> dict:
    """Analyze line movement between open and close.

    Quantifies how a line has moved and classifies the movement. Works with
    moneyline odds, spread lines, or both. ESPN provides open and close data
    in its odds structure.

    Params:
        open_odds (float): Opening American odds (e.g. -140).
        close_odds (float): Closing American odds (e.g. -160).
        open_line (float): Opening spread/total line (e.g. -6.5).
        close_line (float): Closing spread/total line (e.g. -7.5).
        market_type (str): "moneyline", "spread", or "total" (default: "moneyline").
    """
    params = request_data.get("params", {})

    has_ml = params.get("open_odds") is not None and params.get("close_odds") is not None
    has_spread = params.get("open_line") is not None and params.get("close_line") is not None

    if not has_ml and not has_spread:
        return _error(
            "Need at least one pair: open_odds + close_odds, or open_line + close_line"
        )

    market_type = str(params.get("market_type", "moneyline")).lower()
    data = {"market_type": market_type}

    prob_shift = 0.0
    ml_direction = None
    spread_direction = None

    # Moneyline analysis
    if has_ml:
        try:
            open_odds = float(params["open_odds"])
            close_odds = float(params["close_odds"])
        except (TypeError, ValueError) as e:
            return _error(f"Invalid odds values: {e}")

        bad = _invalid_american(open_odds, close_odds)
        if bad:
            return _error(bad)
        open_prob = _american_to_prob(open_odds)
        close_prob = _american_to_prob(close_odds)
        prob_shift = close_prob - open_prob

        if prob_shift > 0:
            direction = "shortened"
            moved_toward = "favorite"
        elif prob_shift < 0:
            direction = "lengthened"
            moved_toward = "underdog"
        else:
            direction = "no movement"
            moved_toward = "none"

        ml_direction = direction

        data["moneyline"] = {
            "open_odds": open_odds,
            "close_odds": close_odds,
            "open_implied_prob": round(open_prob, 6),
            "close_implied_prob": round(close_prob, 6),
            "prob_shift": round(prob_shift, 6),
            "prob_shift_pct": f"{prob_shift * 100:.2f}%",
            "direction": direction,
            "moved_toward": moved_toward,
        }

    # Spread/total analysis
    if has_spread:
        try:
            open_line = float(params["open_line"])
            close_line = float(params["close_line"])
        except (TypeError, ValueError) as e:
            return _error(f"Invalid line values: {e}")

        line_change = close_line - open_line

        if market_type == "total":
            if line_change > 0:
                direction = "total moved up"
            elif line_change < 0:
                direction = "total moved down"
            else:
                direction = "no movement"
        else:
            # Spread: more negative = favorite giving more points
            if line_change < 0:
                direction = "moved toward favorite"
            elif line_change > 0:
                direction = "moved toward underdog"
            else:
                direction = "no movement"

        spread_direction = direction

        data["spread"] = {
            "open_line": open_line,
            "close_line": close_line,
            "line_change": round(line_change, 2),
            "direction": direction,
        }

    # Magnitude classification (based on moneyline prob shift if available)
    abs_shift = abs(prob_shift)
    if has_ml:
        if abs_shift < 0.02:
            magnitude = "small"
        elif abs_shift < 0.05:
            magnitude = "moderate"
        else:
            magnitude = "large"
    elif has_spread:
        abs_line = abs(close_line - open_line)
        if market_type == "total":
            # Totals move in larger increments (e.g., 220 → 223)
            if abs_line <= 1.0:
                magnitude = "small"
            elif abs_line <= 3.0:
                magnitude = "moderate"
            else:
                magnitude = "large"
        else:
            # Spread: 0.5 = half-point move (minor), 1-2 = moderate, 3+ = large
            if abs_line <= 0.5:
                magnitude = "small"
            elif abs_line <= 2.0:
                magnitude = "moderate"
            else:
                magnitude = "large"
    else:
        magnitude = "unknown"

    data["magnitude"] = magnitude

    # Classification
    if has_ml and has_spread:
        # Check for reverse line movement (ML and spread move opposite ways)
        ml_fav = ml_direction == "shortened"
        spread_fav = spread_direction == "moved toward favorite"
        if ml_fav != spread_fav and ml_direction != "no movement" and spread_direction != "no movement":
            classification = "reverse_line_movement"
        elif magnitude == "large":
            classification = "steam_move"
        elif magnitude == "moderate":
            classification = "sharp_action"
        else:
            classification = "minor_adjustment"
    elif magnitude == "large":
        classification = "steam_move"
    elif magnitude == "moderate":
        classification = "sharp_action"
    else:
        classification = "minor_adjustment"

    data["classification"] = classification

    # Build interpretation
    parts = []
    if has_ml:
        sign = "+" if close_odds > 0 else ""
        parts.append(
            f"Moneyline moved from {'+' if open_odds > 0 else ''}{open_odds:.0f} "
            f"to {sign}{close_odds:.0f} ({prob_shift * 100:+.2f}% probability shift)"
        )
    if has_spread:
        parts.append(
            f"{'Total' if market_type == 'total' else 'Spread'} moved from "
            f"{open_line} to {close_line} ({line_change:+.1f})"
        )

    classification_labels = {
        "steam_move": "Large, one-directional move suggesting coordinated sharp money.",
        "sharp_action": "Moderate move suggesting professional action.",
        "minor_adjustment": "Small adjustment, normal market balancing.",
        "reverse_line_movement": "Moneyline and spread moving in opposite directions — possible sharp vs public split.",
    }
    parts.append(classification_labels.get(classification, ""))

    data["interpretation"] = " ".join(parts)

    # Message
    if has_ml:
        msg = (
            f"Line movement: {'+' if open_odds > 0 else ''}{open_odds:.0f} → "
            f"{'+' if close_odds > 0 else ''}{close_odds:.0f} | "
            f"Shift: {prob_shift * 100:+.2f}% | "
            f"{magnitude.title()} ({classification.replace('_', ' ')})"
        )
    else:
        msg = (
            f"Line movement: {open_line} → {close_line} | "
            f"{magnitude.title()} ({classification.replace('_', ' ')})"
        )

    return _success(data, msg)


# ============================================================
# 9. Matchup Probability (BPI-based)
# ============================================================


def matchup_probability(request_data: dict) -> dict:
    """Compute win probability from BPI ratings using a logistic model.

    Pure computation, no network calls. Input two BPI ratings and get the
    head-to-head win probability.

    Formula: P(A wins) = 1 / (1 + 10^(-(bpi_a - bpi_b) / scale))
    where scale = 10 is calibrated to BPI's typical range.

    Params:
        bpi_a (float): BPI rating for team A.
        bpi_b (float): BPI rating for team B.
    """
    params = request_data.get("params", {})
    try:
        bpi_a = float(params.get("bpi_a", 0))
        bpi_b = float(params.get("bpi_b", 0))
    except (TypeError, ValueError) as e:
        return _error(f"Invalid parameters: {e}")

    bpi_diff = bpi_a - bpi_b
    win_prob_a = 1.0 / (1.0 + 10 ** (-bpi_diff / 10.0))
    win_prob_b = 1.0 - win_prob_a

    return _success(
        {
            "win_prob_a": round(win_prob_a, 6),
            "win_prob_b": round(win_prob_b, 6),
            "bpi_a": bpi_a,
            "bpi_b": bpi_b,
            "bpi_diff": round(bpi_diff, 2),
        },
        f"Team A: {win_prob_a:.1%} | Team B: {win_prob_b:.1%} (BPI diff: {bpi_diff:+.1f})",
    )
