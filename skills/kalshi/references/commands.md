# Valid Commands & Common Mistakes

**These are the ONLY valid commands.** Do not invent or guess command names:
- `get_exchange_status`
- `get_exchange_schedule`
- `get_series_list`
- `get_series`
- `get_events`
- `get_event`
- `get_markets`
- `get_market`
- `get_trades`
- `get_market_candlesticks`
- `get_sports_filters`

## Commands that DO NOT exist (commonly hallucinated)

- ~~`get_odds`~~ / ~~`get_probability`~~ -- market prices ARE the implied probability. Use `get_market(ticker="...")` and read the `last_price` field (e.g., 20 = 20% implied probability).
- ~~`get_market_odds`~~ -- use `get_market` or `get_markets` and interpret `last_price` as probability.
- ~~`search_markets`~~ -- Kalshi has no search endpoint. Use `get_events(series_ticker="...")` or `get_markets(series_ticker="...")` to filter by sport.
- ~~`get_series_by_sport`~~ -- use `get_series_list()` and filter, or check the series tickers table.

## Other common mistakes

- Confusing "Football" (NFL) with "Soccer" on Kalshi -- see the series tickers table.
- Guessing series or event tickers instead of discovering them via `get_series_list()` or `get_events()`.
- Forgetting `status="open"` when querying markets -- without it, results include settled/closed markets mixed with active ones.

If you're unsure whether a command exists, check this list. Do not try commands that aren't listed above.
