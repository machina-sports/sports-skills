---
name: polymarket
description: |
  Polymarket sports prediction markets — live odds, prices, order books, events, series, and market search. No auth required. Covers NFL, NBA, MLB, soccer, tennis, cricket, MMA, esports. Supports moneyline, spreads, totals, and player props.

  Use when: user asks about sports betting odds, prediction markets, win probabilities, market sentiment, or "who is favored to win" questions.
  Don't use when: user asks about actual match results, scores, or statistics — use football-data or fastf1 instead. Don't use for historical match data. Don't use for news — use sports-news instead. Don't confuse with Kalshi — Polymarket focuses on crypto-native prediction markets with deeper sports coverage; Kalshi is a US-regulated exchange with different market structure.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# Polymarket — Sports Prediction Markets

## Quick Start

Prefer the CLI — it avoids Python import path issues:
```bash
sports-skills polymarket get_sports_markets --limit=20
sports-skills polymarket search_markets --query="NBA Finals"
```

Python SDK (alternative):
```python
from sports_skills import polymarket

markets = polymarket.get_sports_markets(limit=20)
prices = polymarket.get_market_prices(token_id="abc123")
```

## Important Notes

- **Prices are probabilities.** A price of 0.65 means 65% implied probability. No conversion needed.
- **`token_id` vs `market_id`:** Price and orderbook endpoints require the CLOB `token_id`, not the Gamma `market_id`. Always call `get_market_details` first to get `clobTokenIds`.
- **`search_markets` matches event titles**, not sport categories. Use specific league names ("Premier League", "Champions League"), not generic terms ("soccer", "football").
- Before complex fetches, run the parameter validator: `bash scripts/validate_params.sh <command> [args]`

*For detailed reference data, see the files in the `references/` directory.*

## Workflows

### Workflow: Live Odds Check
1. `search_markets --query="<league/event name>"`
2. `get_market_details --market_id=<id>` to get CLOB token IDs.
3. `get_market_prices --token_id=<id>`
4. Present probabilities.

### Workflow: Event Overview
1. `get_sports_events --active=true`
2. Pick event, then `get_event_details --event_id=<id>`.
3. For each market, get prices.

### Workflow: Price Trend Analysis
1. Find market via `search_markets`.
2. `get_market_details` for token_id.
3. `get_price_history --token_id=<id> --interval=1w`
4. Present price movement.

## Examples

User: "Who's favored to win the NBA Finals?"
1. Call `search_markets(query="NBA Finals", sports_market_types="moneyline")`
2. Get `token_id` from the market details
3. Call `get_market_prices(token_id="...")` for current odds
4. Present teams with implied probabilities (price = probability)

User: "Who will win the Premier League?"
1. Call `search_markets(query="English Premier League")` -- use full league name
2. Sort results by Yes outcome price descending
3. Present teams with implied probabilities (price = probability)

User: "Show me Champions League odds"
1. Call `search_markets(query="Champions League")`
2. Present top contenders with prices, volume, and liquidity

## Error Handling & Fallbacks

- If search returns 0 results, try full league names ("English Premier League" not "EPL", "Champions League" not "CL"). search_markets matches event titles.
- If `get_market_prices` fails, you likely used `market_id` instead of `token_id`. Always call `get_market_details` first to get CLOB `token_id`.
- If prices seem stale, check `get_last_trade_price` for the most recent trade. Low-liquidity markets may have wide spreads.
- **Never fabricate odds or probabilities.** If no market exists, state so.
