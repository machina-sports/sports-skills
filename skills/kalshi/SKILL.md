---
name: kalshi
description: |
  Kalshi prediction markets — events, series, markets, trades, and candlestick data. Public API, no auth required for reads. US-regulated exchange (CFTC). Covers football (EPL, UCL, La Liga), basketball, baseball, tennis, NFL, hockey event contracts.

  Use when: user asks about Kalshi-specific markets, event contracts, CFTC-regulated prediction markets, or candlestick/OHLC price history on sports outcomes.
  Don't use when: user asks about actual match results, scores, or statistics — use the sport-specific skill: football-data (soccer), nfl-data (NFL), nba-data (NBA), wnba-data (WNBA), nhl-data (NHL), mlb-data (MLB), tennis-data (tennis), golf-data (golf), cricket-data (cricket), cfb-data (college football), cbb-data (college basketball), or fastf1 (F1). Don't use for general "who will win" questions unless Kalshi is specifically mentioned — try polymarket first (broader sports coverage). Don't use for news — use sports-news instead.
license: MIT
metadata:
  author: machina-sports
  version: "0.2.0"
---

# Kalshi — Prediction Markets

Before writing queries, consult `references/api-reference.md` for sport codes, series tickers, and command parameters.

## Quick Start

Prefer the CLI — it avoids Python import path issues:
```bash
sports-skills kalshi search_markets --sport=nba
sports-skills kalshi get_todays_events --sport=nba
sports-skills kalshi get_sports_config
sports-skills kalshi get_markets --series_ticker=KXNBA --status=open
```

Python SDK (alternative):
```python
from sports_skills import kalshi

kalshi.search_markets(sport='nba')
kalshi.search_markets(sport='nba', query='Lakers')
kalshi.get_todays_events(sport='nba')
kalshi.get_sports_config()
kalshi.get_markets(series_ticker="KXNBA", status="open")
```

## CRITICAL: Before Any Query

CRITICAL: Before calling any market endpoint, verify:
- The `sport` parameter is always passed to `search_markets` and `get_todays_events` for single-game markets.
- Prices are on a 0-100 integer scale (20 = 20% implied probability) — do not treat as American odds.
- `status="open"` is used when querying markets to exclude settled/closed markets.

Without the `sport` parameter:
```
WRONG: search_markets(query="Leeds")           → 0 results
RIGHT: search_markets(sport='epl', query='Leeds') → returns all Leeds markets
```

## Important Notes

- **On Kalshi, "Football" = NFL.** For football/soccer (EPL, La Liga, etc.), use sport codes: `epl`, `ucl`, `laliga`, `bundesliga`, `seriea`, `ligue1`, `mls`, `worldcup`.
- **Prices are probabilities.** A `last_price` of 20 means 20% implied probability. Scale is 0-100 (not 0-1 like Polymarket).
- **Always use `status="open"`** when querying markets, otherwise results include settled/closed markets.
- **Shared interface with Polymarket:** `search_markets(sport=...)`, `get_todays_events(sport=...)`, and `get_sports_config()` work the same way on both platforms.

## Workflows

### Sport Market Search (Recommended)
1. `search_markets --sport=nba` — finds all open NBA markets.
2. Optionally add `--query="Lakers"` to filter by keyword.
3. Results include yes_bid, no_bid, volume for each market.

### Today's Events
1. `get_todays_events --sport=nba` — open events with nested markets.
2. Present events with prices (price = implied probability, 0-100 scale).

### Futures Market Check
1. `get_markets --series_ticker=<ticker> --status=open`
2. Sort by `last_price` descending.
3. Present top contenders with probability and volume.

### Market Price History
1. Get market ticker from `search_markets --sport=nba`.
2. `get_market_candlesticks --series_ticker=<s> --ticker=<t> --start_ts=<start> --end_ts=<end> --period_interval=60`
3. Present OHLC with volume.

## Commands

See `references/api-reference.md` for the full command list with parameters.

| Command | Description |
|---|---|
| `get_sports_config` | Available sport codes and series tickers |
| `get_todays_events` | Today's events for a sport with nested markets |
| `search_markets` | Find markets by sport and/or keyword |
| `get_esports_odds` | Esports markets (cs2/lol/dota2): prices in cents (0-100) plus `implied_probability` (0-1) and `decimal_odds` |
| `get_markets` | Market listing (raw API) |
| `get_event` | Event details |
| `get_market` | Market details |
| `get_trades` | Recent trades |
| `get_market_candlesticks` | OHLC price history |

## Examples

Example 1: NBA market search
User says: "What NBA markets are on Kalshi?"
Actions:
1. Call `search_markets(sport='nba')`
Result: All open NBA markets with yes/no prices and volume

Example 2: EPL game markets
User says: "Show me Leeds vs Man City odds on Kalshi"
Actions:
1. Call `search_markets(sport='epl', query='Leeds')`
Result: Leeds EPL markets across all EPL series with prices and volume

Example 3: Today's EPL events
User says: "What EPL games are available on Kalshi?"
Actions:
1. Call `get_todays_events(sport='epl')`
Result: Today's EPL events with nested markets

Example 4: Champions League futures
User says: "Who will win the Champions League?"
Actions:
1. Call `search_markets(sport='ucl')` or `get_markets(series_ticker="KXUCL", status="open")`
2. Sort by `last_price` descending (price = implied probability)
Result: Top UCL contenders with `yes_sub_title`, `last_price` (%), and volume

Example 5: Market price history
User says: "Show me the price history for this NBA game"
Actions:
1. Get market ticker from `search_markets(sport='nba')`
2. Call `get_market_candlesticks(series_ticker="KXNBA", ticker="...", start_ts=..., end_ts=..., period_interval=60)`
Result: OHLC price data with volume

## Commands that DO NOT exist — never call these

- ~~`get_odds`~~ — does not exist. Use `search_markets` or `get_markets` to find market prices.
- ~~`get_team_schedule`~~ — does not exist. Kalshi has markets, not schedules. Use the sport-specific skill for schedules.
- ~~`get_scores`~~ / ~~`get_results`~~ — does not exist. Kalshi is a prediction market. Use the sport-specific skill.

If a command is not listed in `references/api-reference.md`, it does not exist.

## Troubleshooting

Error: `search_markets` returns 0 results
Cause: The `sport` parameter is missing — without it, search only returns high-volume futures and misses single-game markets
Solution: Always pass `sport='<code>'` to `search_markets`. Check `references/api-reference.md` for valid sport codes

Error: Markets returned include settled/expired contracts
Cause: `status` parameter is not set
Solution: Always pass `status="open"` to filter to open markets only

Error: Series ticker returns no results
Cause: The series ticker may be incorrect or have no open markets
Solution: Call `get_series_list()` to discover available tickers, or check `references/series-tickers.md`

Error: Football/soccer markets not found when searching "Football"
Cause: On Kalshi, "Football" refers to NFL — soccer uses league-specific codes
Solution: Use `sport='epl'`, `sport='ucl'`, `sport='laliga'`, etc. for soccer leagues
