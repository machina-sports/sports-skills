# Kalshi — API Reference

## Sport-Aware Commands

| Command | Required | Optional | Description |
|---|---|---|---|
| `get_sports_config` | | | Available sport codes and series tickers |
| `get_todays_events` | sport | limit | Today's events for a sport with nested markets |
| `search_markets` | | sport, query, status, limit | Find markets by sport and/or keyword |

## Raw API Commands

| Command | Required | Optional | Description |
|---|---|---|---|
| `get_exchange_status` | | | Exchange trading status |
| `get_exchange_schedule` | | | Operating hours |
| `get_series_list` | | category, tags | All series (leagues) |
| `get_series` | series_ticker | | Series details |
| `get_events` | | limit, cursor, status, series_ticker, with_nested_markets | Event listing |
| `get_event` | event_ticker | with_nested_markets | Event details |
| `get_markets` | | limit, cursor, event_ticker, series_ticker, status, tickers | Market listing |
| `get_market` | ticker | | Market details |
| `get_market_orderbook` | ticker | depth | Order book — yes/no bid depth (dollar-string levels) |
| `get_trades` | | limit, cursor, ticker, min_ts, max_ts | Recent trades |
| `get_market_candlesticks` | series_ticker, ticker, start_ts, end_ts, period_interval | | OHLC data |
| `get_sports_filters` | | | Filter categories |

## Sport Codes

### US Sports

| Sport | Code | Series Ticker |
|---|---|---|
| NBA | `nba` | KXNBA |
| NFL | `nfl` | KXNFL |
| MLB | `mlb` | KXMLB |
| NHL | `nhl` | KXNHL |
| WNBA | `wnba` | KXWNBA |
| College Football | `cfb` | KXCFB |
| College Basketball | `cbb` | KXCBB |

### Football (Soccer)

| League | Code | Series Tickers |
|---|---|---|
| English Premier League | `epl` | KXEPLGAME, KXEPLTOTAL, KXEPLBTTS, KXEPLSPREAD, KXEPLGOAL |
| Champions League | `ucl` | KXUCL, KXUEFAGAME |
| La Liga | `laliga` | KXLALIGA |
| Bundesliga | `bundesliga` | KXBUNDESLIGA |
| Serie A | `seriea` | KXSERIEA |
| Ligue 1 | `ligue1` | KXLIGUE1 |
| MLS | `mls` | KXMLSGAME |
| FIFA World Cup 2026 | `worldcup` | KXMENWORLDCUP, KXWCGAME, KXWCGROUPQUAL, KXWCGROUPORDER, KXWCSTAGE, KXWCHOSTSTAGE, KXWCBESTHOST, KXWCNOEURSA, KXWCREGIONKO, KXWCEVERYTEAMGOAL |

See `references/series-tickers.md` for the full series ticker list and `references/api.md` for raw API documentation.

## Price Scale

Kalshi prices are on a 0-100 integer scale:
- `last_price` of `20` = 20% implied probability
- `yes_bid` / `no_bid` = current bid prices for Yes and No sides
- Always use `status="open"` to exclude settled/closed markets
