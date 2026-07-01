---
name: polymarket
description: |
  Polymarket sports prediction markets — live odds, prices, order books, events, series, and market search. No auth required. Covers NFL, NBA, MLB, football (EPL, UCL, La Liga), tennis, cricket, MMA, esports. Supports moneyline, spreads, totals, and player props.

  Use when: user asks about sports betting odds, prediction markets, win probabilities, market sentiment, or "who is favored to win" questions.
  Don't use when: user asks about actual match results, scores, or statistics — use the sport-specific skill: football-data (soccer), nfl-data (NFL), nba-data (NBA), wnba-data (WNBA), nhl-data (NHL), mlb-data (MLB), tennis-data (tennis), golf-data (golf), cricket-data (cricket), cfb-data (college football), cbb-data (college basketball), or fastf1 (F1). Don't use for historical match data. Don't use for news — use sports-news instead. Don't confuse with Kalshi — Polymarket focuses on crypto-native prediction markets with deeper sports coverage; Kalshi is a US-regulated exchange with different market structure.
license: MIT
metadata:
  author: machina-sports
  version: "0.3.0"
---

# Polymarket — Sports Prediction Markets

Before writing queries, consult `references/api-reference.md` for sport codes, command parameters, and price format.

## Quick Start

Prefer the CLI — it avoids Python import path issues:
```bash
sports-skills polymarket search_markets --sport=nba --sports_market_types=moneyline
sports-skills polymarket get_todays_events --sport=epl
sports-skills polymarket search_markets --sport=epl --query="Leeds" --sports_market_types=moneyline
sports-skills polymarket get_sports_config
```

Python SDK (alternative):
```python
from sports_skills import polymarket

polymarket.search_markets(sport='nba', sports_market_types='moneyline')
polymarket.get_todays_events(sport='epl')
polymarket.search_markets(sport='epl', query='Leeds')
polymarket.get_sports_config()
```

## CRITICAL: Before Any Query

CRITICAL: Before calling any market endpoint, verify:
- The `sport` parameter is always passed to `search_markets` and `get_todays_events` for single-game markets.
- Prices are probabilities on a 0-1 scale (0.65 = 65%) — no conversion needed.
- For price/orderbook endpoints, use `token_id` (CLOB), not `market_id` (Gamma). Call `get_market_details` first to get `clobTokenIds`.

Without the `sport` parameter:
```
WRONG: search_markets(query="Leeds")           → 0 results
RIGHT: search_markets(sport='epl', query='Leeds') → returns all Leeds markets
```

## Prerequisites

**Core commands** (no dependencies, no API keys):
All read commands work out of the box.

**Trading commands** require `py-clob-client-v2`:
```bash
pip install sports-skills[polymarket]
```
Additionally requires a configured wallet:
```bash
export POLYMARKET_PRIVATE_KEY=0x...
# Only for proxy / email (Magic) wallets, where the signer differs from the
# funds holder. EOA wallets don't need it.
export POLYMARKET_FUNDER_ADDRESS=0x...
```

## Workflows

### Find Single-Game Markets for a Sport
1. `search_markets --sport=nba` (or epl, nfl, bun, etc.)
2. Each market includes outcomes with prices (price = probability).
3. For detailed prices, use `get_market_prices --token_id=<clob_token_id>`.

### Today's Events for a League
1. `get_todays_events --sport=epl` — returns events sorted by start date.
2. Each event includes nested markets (moneyline, spreads, totals, props).
3. Pick a market, get `clob_token_id` from outcomes, then `get_market_prices`.

### Live Odds Check
1. `search_markets --sport=nba --query="Lakers" --sports_market_types=moneyline`
2. `get_market_prices --token_id=<id>` for live CLOB prices.
3. Present probabilities.

### Price Trend Analysis
1. Find market via `search_markets --sport=nba`.
2. Get `clob_token_id` from the outcomes.
3. `get_price_history --token_id=<id> --interval=1w`
4. Present price movement.

## Commands

| Command | Description |
|---|---|
| `get_sports_config` | Available sport codes |
| `get_todays_events` | Today's events for a league |
| `search_markets` | Find markets by sport, keyword, and type |
| `get_sports_markets` | Browse all sports markets |
| `get_sports_events` | Browse sports events |
| `get_series` | List series (leagues) |
| `get_market_details` | Single market details |
| `get_event_details` | Single event details |
| `get_market_prices` | Current CLOB prices |
| `get_order_book` | Full order book |
| `get_price_history` | Historical prices |
| `get_last_trade_price` | Most recent trade |

See `references/api-reference.md` for full parameter lists and return shapes.

## Examples

Example 1: Tonight's NBA favorites
User says: "Who's favored in tonight's NBA games?"
Actions:
1. Call `search_markets(sport='nba', sports_market_types='moneyline')`
Result: Each matchup with implied win probabilities (price = probability)

Example 2: Team-specific odds
User says: "Show me Leeds vs Man City odds"
Actions:
1. Call `search_markets(sport='epl', query='Leeds', sports_market_types='moneyline')`
Result: Leeds moneyline market with outcome prices

Example 3: Today's EPL events
User says: "What EPL matches are on today?"
Actions:
1. Call `get_todays_events(sport='epl')`
Result: Today's EPL events with nested markets (moneyline, spreads, totals, props)

Example 4: League winner futures
User says: "Who will win the Premier League?"
Actions:
1. Call `search_markets(query='Premier League')` — returns futures
2. Sort results by Yes outcome price descending
Result: Top contenders ranked by win probability

Example 5: Bundesliga odds
User says: "Show me Bundesliga odds for Dortmund vs Bayern"
Actions:
1. Call `search_markets(sport='bun', query='Dortmund', sports_market_types='moneyline')`
Result: Dortmund/Bayern moneyline market with outcome prices

## Commands that DO NOT exist — never call these

- ~~`cli_search_markets`~~ — does not exist. Use `search_markets` instead.
- ~~`cli_sports_list`~~ — does not exist. Use `get_sports_config` instead.
- ~~`get_market_odds`~~ / ~~`get_odds`~~ / ~~`get_current_odds`~~ — prices ARE probabilities. Use `get_market_prices(token_id=...)`.
- ~~`get_implied_probability`~~ — the price IS the implied probability.
- ~~`get_markets`~~ — use `get_sports_markets` (browse) or `search_markets` (search).
- ~~`get_team_schedule`~~ — this is a football-data command, not polymarket.

If a command is not listed in `references/api-reference.md`, it does not exist.

## Troubleshooting

Error: `search_markets` returns 0 results
Cause: The `sport` parameter is missing — without it, search only checks high-volume markets and misses single-game events
Solution: Always pass `sport='<code>'` to `search_markets`. Check `references/api-reference.md` for valid sport codes

Error: `get_market_prices` fails or returns wrong data
Cause: `market_id` (Gamma) was used instead of `token_id` (CLOB)
Solution: Call `get_market_details(market_id=<id>)` first to get the CLOB `clobTokenIds`, then use those with `get_market_prices`

Error: Prices seem stale or unchanged
Cause: Low-liquidity market — may have wide spreads and infrequent trades
Solution: Check `get_last_trade_price(token_id=<id>)` for the most recent actual trade price

Error: Trading commands fail
Cause: `py-clob-client-v2` is not installed or wallet is not configured
Solution: Run `pip install sports-skills[polymarket]` and set `POLYMARKET_PRIVATE_KEY` environment variable
