# Betting Analysis — API Reference

## Odds Formats

| Format | Example | Description |
|---|---|---|
| American | `-150`, `+130` | US sportsbook standard. Negative = favorite, positive = underdog |
| Decimal | `1.67`, `2.30` | European standard. Payout per $1 (includes stake) |
| Probability | `0.60`, `0.43` | Direct implied probability (0-1). Polymarket uses this format |

**Conversion rules:**
- American negative: prob = -odds / (-odds + 100). Example: -150 → 150/250 = 0.600
- American positive: prob = 100 / (odds + 100). Example: +130 → 100/230 = 0.435
- Decimal: prob = 1 / odds. Example: 1.67 → 0.599
- Kalshi prices (0-100 integer): divide by 100 to get probability format

## Commands

| Command | Required | Optional | Description |
|---|---|---|---|
| `convert_odds` | odds, from_format | | Convert between American, decimal, probability |
| `devig` | odds | format | Remove vig from sportsbook odds → fair probabilities |
| `find_edge` | fair_prob, market_prob | | Compute edge, EV, and Kelly from two probabilities |
| `kelly_criterion` | fair_prob, market_prob | | Kelly fraction for optimal bet sizing |
| `evaluate_bet` | book_odds, market_prob | book_format, outcome | Full pipeline: devig → edge → Kelly |
| `find_arbitrage` | market_probs | labels | Detect arbitrage across outcomes from multiple sources |
| `parlay_analysis` | legs, parlay_odds | odds_format, correlation | Multi-leg parlay EV and Kelly analysis |
| `line_movement` | | open_odds, close_odds, open_line, close_line, market_type | Analyze open-to-close line movement |
| `matchup_probability` | bpi_a, bpi_b | | Win probability from two BPI ratings using a logistic model |

## Key Concepts

- **Vig/Juice**: The sportsbook's margin. A -110/-110 line implies 52.4% + 52.4% = 104.8% total (4.8% overround). De-vigging removes this to get fair probabilities.
- **Edge**: The difference between your estimated true probability and the market price. Positive edge = profitable in expectation.
- **Kelly Criterion**: Optimal bet sizing. f* = (fair_prob - market_prob) / (1 - market_prob). For conservative sizing, use half-Kelly (×0.5) or quarter-Kelly (×0.25).
- **Expected Value (EV)**: Average return per dollar bet. EV = fair_prob / market_prob - 1.
- **Arbitrage**: When prices across sources don't sum to 100%, you can bet all outcomes and guarantee profit regardless of the result.
- **Parlay**: Multi-leg bet where all legs must win. Combined probability = product of individual leg probabilities. Higher risk, higher reward.
- **Line Movement**: How odds change between open and close. Large moves toward one side suggest sharp/professional money. Reverse line movement (ML and spread moving opposite directions) suggests a public vs sharp split.
