# Valid Commands & Common Mistakes

**These are the ONLY valid commands.** Do not invent or guess command names:
- `get_sports_markets`
- `get_sports_events`
- `get_series`
- `get_market_details`
- `get_event_details`
- `get_market_prices`
- `get_order_book`
- `get_sports_market_types`
- `search_markets`
- `get_price_history`
- `get_last_trade_price`

## Commands that DO NOT exist (commonly hallucinated)

- ~~`get_market_odds`~~ / ~~`get_odds`~~ -- market prices ARE the implied probability. Use `get_market_prices(token_id="...")` where price = probability.
- ~~`get_implied_probability`~~ -- the price IS the implied probability. No conversion needed.
- ~~`get_current_odds`~~ -- use `get_last_trade_price(token_id="...")` for the most recent price.
- ~~`get_markets`~~ -- the correct command is `get_sports_markets` (for browsing) or `search_markets` (for searching by keyword).

## Other common mistakes

- Using `market_id` where `token_id` is needed -- price and orderbook endpoints require the CLOB `token_id`, not the Gamma `market_id`. Always call `get_market_details` first to get `clobTokenIds`.
- Searching generic terms like "soccer" or "football" -- `search_markets` matches event titles. Use specific league names: "Premier League", "Champions League", "La Liga", etc.
- Forgetting to get the `token_id` before calling price/orderbook endpoints -- always fetch market details first.

If you're unsure whether a command exists, check this list. Do not try commands that aren't listed above.
