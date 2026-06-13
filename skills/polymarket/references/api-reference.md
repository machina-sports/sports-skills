# Polymarket — API Reference

## Core Commands (no dependencies needed)

| Command | Required | Optional | Description |
|---|---|---|---|
| `get_sports_config` | | | Available sport codes (nba, epl, nfl, bun, fl1, etc.) |
| `get_todays_events` | sport | limit | Today's events for a league — sorted by start date |
| `search_markets` | | query, sport, sports_market_types, tag_id, limit | Find markets by sport, keyword, and type |
| `get_sports_markets` | | limit, offset, sports_market_types, game_id, active, closed, order, ascending | Browse all sports markets |
| `get_sports_events` | | limit, offset, active, closed, order, ascending, series_id | Browse sports events |
| `get_series` | | limit, offset | List series (leagues) |
| `get_market_details` | | market_id, slug | Single market details |
| `get_event_details` | | event_id, slug | Single event details |
| `get_market_prices` | | token_id, token_ids | Current CLOB prices |
| `get_order_book` | token_id | | Full order book |
| `get_sports_market_types` | | | Valid market types |
| `get_price_history` | token_id | interval, fidelity | Historical prices |
| `get_last_trade_price` | token_id | | Most recent trade |

## Trading Commands (requires py-clob-client-v2 + wallet)

| Command | Required | Optional | Description |
|---|---|---|---|
| `configure` | | private_key, signature_type | Configure wallet |
| `create_order` | token_id, side, price, size | order_type | Place limit order |
| `market_order` | token_id, side, amount | | Place market order |
| `cancel_order` | order_id | | Cancel order |
| `cancel_all_orders` | | | Cancel all orders |
| `get_orders` | | market | Open orders |
| `get_user_trades` | | | Your trades |

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

See `references/api.md` and `references/commands.md` for extended documentation.
