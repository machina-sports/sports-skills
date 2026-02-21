---
name: kalshi
description: |
  Kalshi prediction markets — events, series, markets, trades, and candlestick data. Public API, no auth required for reads. US-regulated exchange (CFTC). Covers soccer, basketball, baseball, tennis, NFL, hockey event contracts.

  Use when: user asks about Kalshi-specific markets, event contracts, CFTC-regulated prediction markets, or candlestick/OHLC price history on sports outcomes.
  Don't use when: user asks about actual match results, scores, or statistics — use football-data or fastf1 instead. Don't use for general "who will win" questions unless Kalshi is specifically mentioned — try polymarket first (broader sports coverage). Don't use for news — use sports-news instead.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# Kalshi — Prediction Markets

## Quick Start

Prefer the CLI — it avoids Python import path issues:
```bash
sports-skills kalshi get_markets --series_ticker=KXNBA
sports-skills kalshi get_events --series_ticker=KXNBA --status=open
```

Python SDK (alternative):
```python
from sports_skills import kalshi

markets = kalshi.get_markets(series_ticker="KXNBA")
event = kalshi.get_event(event_ticker="KXNBA-26FEB14")
```

## Important Notes

- **"Football" = NFL on Kalshi.** Soccer is under "Soccer". Use `KXUCL`, `KXLALIGA`, etc. for soccer leagues.
- **Prices are probabilities.** A `last_price` of 20 means 20% implied probability. No conversion needed.
- **Always use `status="open"`** when querying markets, otherwise results include settled/closed markets.
- Before complex fetches, run the parameter validator: `bash scripts/validate_params.sh <command> [args]`

*For detailed reference data, see the files in the `references/` directory.*

## Workflows

### Workflow: Sport Odds Discovery
1. `get_events --series_ticker=<ticker> --status=open --with_nested_markets=True`
2. Present events with prices (price = implied probability).
3. For price history, use `get_market_candlesticks`.

### Workflow: Futures Market Check
1. `get_markets --series_ticker=<ticker> --status=open`
2. Sort by `last_price` descending.
3. Present top contenders with probability and volume.

### Workflow: Market Price History
1. Get market ticker from `get_markets`.
2. `get_market_candlesticks --series_ticker=<s> --ticker=<t> --start_ts=<start> --end_ts=<end> --period_interval=60`
3. Present OHLC with volume.

## Examples

User: "What NBA markets are on Kalshi?"
1. Call `get_events(series_ticker="KXNBA", status="open", with_nested_markets=True)`
2. Present events with their nested markets, yes/no prices, and volume

User: "Who will win the Champions League?"
1. Call `get_markets(series_ticker="KXUCL", status="open")`
2. Sort by `last_price` descending -- price = implied probability (e.g., 20 = 20%)
3. Present top teams with `yes_sub_title`, `last_price`, and `volume`

User: "Show me the price history for this NBA game"
1. Get the market ticker from `get_markets(series_ticker="KXNBA")`
2. Call `get_market_candlesticks(series_ticker="KXNBA", ticker="...", start_ts=..., end_ts=..., period_interval=60)`
3. Present OHLC data with volume

## Error Handling & Fallbacks

- If series ticker returns no results, call `get_series_list()` to discover available tickers. See `references/series-tickers.md`.
- If markets are empty, use `status="open"` to filter. Default includes settled/closed markets.
- If "Football" returns NFL instead of soccer, Kalshi uses "Football" for NFL, "Soccer" for soccer. Use KXUCL, KXLALIGA, etc. for soccer.
- **Never fabricate market prices or probabilities.** If no market exists, state so.
