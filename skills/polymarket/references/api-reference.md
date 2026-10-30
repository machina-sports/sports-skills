# Polymarket — API Reference (Read-Only)

## Core Commands (no dependencies needed)

| Command | Required | Optional | Description |
|---|---|---|---|
| `get_sports_config` | | | Available sport codes (nba, epl, nfl, bun, etc.) |
| `get_todays_events` | sport | limit, offset, date, timezone, sports_market_types, compact | One league's games kicking off on `date` (default today) in `timezone` (default UTC), from ONE volume-sorted page — see coverage fields below |
| `search_markets` | | query, sport, sports_market_types, tag_id, limit | Find markets by sport, keyword, and type |
| `get_sports_markets` | | limit, offset, sports_market_types, game_id, active, closed, order, ascending | Browse all sports markets |
| `get_sports_events` | | limit, offset, active, closed, order, ascending, series_id, sport | Browse sports events; `sport` resolves to the league series (unknown codes error), no date filter |
| `get_series` | | limit, offset | List series (leagues) |
| `get_market_details` | | market_id, slug | Single market details |
| `get_event_details` | | event_id, slug | Single event details |
| `get_market_prices` | | token_id, token_ids | Current CLOB prices |
| `get_order_book` | token_id | | Full order book |
| `get_sports_market_types` | | | Valid market types |
| `get_price_history` | token_id | interval, fidelity | Historical prices |
| `get_last_trade_price` | token_id | | Most recent trade |
| `get_esports_events` | | query, limit, closed | Esports prediction markets (implied probabilities via outcome prices) |

### `get_todays_events` coverage

- Kickoff is the event `startTime` (else the nested markets' `gameStartTime` when they all agree), exposed as `game_start_time`. The listing `start_date`, `end_date` and a bare `eventDate` are never used as the game time.
- Events with no usable kickoff are listed in `unknown_start`, not guessed onto a date.
- `scanned` is the rows read from the one provider page; when the page was full, `truncated` is true and `next_offset` is the offset for the next call. No hidden paging.
- `complete` is true only for a short first page with every kickoff and required market state known. `unknown_market_state` lists market IDs with missing or non-boolean active/closed/order-acceptance/order-book flags or event IDs whose markets were not supplied. An empty `events` list with `complete: false` is NOT proof that no games exist.
- Markets the provider marks closed, inactive or not accepting orders are dropped. `accepting_orders` / `enable_order_book` are the provider's booleans, or `null` when not reported — `null` is unknown, not tradable.
- `sports_market_types` keeps one exact type (e.g. `moneyline`). `compact=true` returns identity, kickoff, status, order flags, outcomes and token IDs without descriptions.
- Outcome `price` values are Gamma indicative prices, not executable quotes. Use `get_order_book` / `get_market_prices` (CLOB) for actual bid/ask.
- A malformed provider response or API error returns `status: false`, never an empty success.

Financial execution commands are intentionally omitted from this read-only reference. If a user explicitly asks to place/cancel orders, load the separate `polymarket-trading` skill and require explicit confirmation.

## Sport Codes (Common)

| Code | League | Code | League |
|---|---|---|---|
| `nba` | NBA | `epl` | English Premier League |
| `nfl` | NFL | `bun` | Bundesliga |
| `nhl` | NHL | `lal` | La Liga |
| `mlb` | MLB | `fl1` | Ligue 1 |
| `wnba` | WNBA | `sea` | Serie A |
| `cfb` | College Football | `ucl` | Champions League |
| `cbb` | College Basketball | `uel` | Europa League |
| `atp` | ATP Tennis | `mls` | MLS |
| `wta` | WTA Tennis | `fifwc` | FIFA World Cup 2026 |

Run `get_sports_config()` for the full list of 120+ sport codes.

## Price Format

Prices on Polymarket are probabilities on a 0-1 scale:
- Price of `0.65` = 65% implied probability
- No conversion needed
- `token_id` (CLOB) is required for price/orderbook endpoints — use `get_market_details` to get `clobTokenIds` from a `market_id`

See `references/api.md` and `references/commands.md` for extended read-only documentation.
