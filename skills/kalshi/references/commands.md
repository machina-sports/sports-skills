# Valid Commands & Common Mistakes

## CRITICAL: Always use the `sport` parameter

For single-game markets, ALWAYS pass `sport='<code>'` to `search_markets` and `get_todays_events`.

```
WRONG: search_markets(query="Leeds")           → 0 results
RIGHT: search_markets(sport='epl', query='Leeds') → returns all Leeds markets
```

## Sport-Aware Commands (recommended)

These use sport codes (`nba`, `nfl`, `mlb`, `epl`, `ucl`, etc.) — same interface as Polymarket:
- `get_sports_config` — **list all available sport codes** and series tickers
- `get_todays_events` — **today's events for a sport** (requires `sport` param)
- `search_markets` — **find markets by sport and keyword** (use `sport` param for single-game markets)

## Raw API Commands

These query the Kalshi API directly using series/event/market tickers:
- `get_exchange_status`
- `get_exchange_schedule`
- `get_series_list`
- `get_series`
- `get_events`
- `get_event`
- `get_markets`
- `get_market`
- `get_market_orderbook`
- `get_trades`
- `get_market_candlesticks`
- `get_sports_filters`

## Key Usage Patterns

### Finding sport markets (MOST COMMON)
```bash
# Use the sport parameter — maps to the right series ticker(s) automatically
sports-skills kalshi search_markets --sport=nba
sports-skills kalshi search_markets --sport=nba --query="Lakers"
sports-skills kalshi search_markets --sport=epl --query="Leeds"
sports-skills kalshi get_todays_events --sport=nba
sports-skills kalshi get_todays_events --sport=epl
```

### Discovering sport codes
```bash
sports-skills kalshi get_sports_config
# Returns: nba, nfl, mlb, nhl, wnba, cfb, cbb, epl, ucl, laliga, bundesliga, seriea, ligue1, mls, worldcup
```

## Commands that DO NOT exist (commonly hallucinated)

- ~~`get_odds`~~ / ~~`get_probability`~~ — market prices ARE the implied probability. Use `search_markets` or `get_todays_events`, which return `last_price` in cents (e.g., 20 = 20% implied probability).
- ~~`get_market_odds`~~ — use `search_markets`/`get_todays_events` and interpret `last_price` as probability. Note: raw `get_market`/`get_markets` payloads carry dollar-string fields instead (`last_price_dollars: "0.2000"`), not integer cents.
- ~~`get_series_by_sport`~~ — use `get_sports_config()` to see sport codes and series tickers.

## Other common mistakes

- **Not using the `sport` parameter** — without it, you need to know series tickers. `search_markets(sport='nba')` automatically resolves to `KXNBA`. `search_markets(sport='epl')` resolves to all EPL series.
- **Searching by team name without `sport`** — `search_markets(query="Leeds")` returns 0 results. Always include `sport='epl'`.
- Confusing NFL with football on Kalshi — Kalshi's "Football" category = NFL. For football (EPL, UCL, etc.), use `epl`, `ucl`, `laliga`, etc.
- Guessing series or event tickers instead of using `get_sports_config()` or `get_series_list()`.
- Forgetting `status="open"` when querying raw markets — without it, results include settled/closed markets.

If you're unsure whether a command exists, check this list. Do not try commands that aren't listed above.
