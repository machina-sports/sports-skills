# Markets Orchestration — API Reference

## Commands

| Command | Required | Optional | Description |
|---|---|---|---|
| `get_todays_markets` | | sport, date | Fetch ESPN schedule → search both exchanges with sport context → unified dashboard |
| `search_entity` | query | sport | Search Kalshi + Polymarket for a team/player/event name (passes sport to both platforms) |
| `compare_odds` | sport, event_id | | ESPN odds + prediction market prices → normalized side-by-side + arb check |
| `get_sport_markets` | sport | status, limit | Sport-filtered market listing on both platforms (uses sport code, not text query) |
| `get_sport_schedule` | | sport, date | Unified ESPN schedule across one or all sports |
| `normalize_price` | price, source | | Convert any source format to common {implied_prob, american, decimal} |
| `evaluate_market` | sport, event_id | token_id, kalshi_ticker, outcome | ESPN odds + market price → devig → edge → Kelly |
| `match_markets` | sport | date | Pair the same game across Kalshi and Polymarket (date + team-code join, fuzzy title fallback) |
| `get_market_price` | venue, ticker (kalshi) or token_id (polymarket) | at_time | Live or point-in-time price — both sides as 0-1 probabilities, one shape for both venues |
| `get_price_history` | venue, ticker (kalshi) or token_id (polymarket) | interval, start_time, end_time | {timestamp, price} series (0-1 yes probability) at 1m/1h/1d resolution |

### `match_markets` notes

- `sport` must exist on both venues: mlb, nfl, nba, nhl, wnba, cfb, cbb, epl, ucl, laliga, bundesliga, seriea, ligue1, mls, worldcup.
- Each match returns `kalshi.market_tickers` and `polymarket.markets[]` (moneyline markets with `token_ids` and `outcomes`). US-league games have one moneyline market with team-named outcomes; soccer games have several binary ones (home/away/draw).
- `match_method` is `code` (deterministic identifier join) or `title` (fuzzy fallback — used when the venues' team codes differ, e.g. World Cup ISO vs FIFA country codes).
- `unmatched` lists games seen on only one venue (listing windows differ).

### `get_market_price` / `get_price_history` notes

- `at_time`, `start_time`, `end_time` accept Unix timestamps or ISO 8601 datetimes.
- Historical Kalshi prices come from candlesticks (hourly within 7 days of `at_time`, daily within 31); Polymarket from CLOB price history.
- All prices are 0-1 probabilities for the YES side regardless of venue — no unit conversion needed downstream.

## Supported Sports

### US Sports (with ESPN schedules)

| Sport | Key | Kalshi Series | Polymarket Code |
|---|---|---|---|
| NFL | `nfl` | KXNFL | `nfl` |
| NBA | `nba` | KXNBA | `nba` |
| MLB | `mlb` | KXMLB | `mlb` |
| NHL | `nhl` | KXNHL | `nhl` |
| WNBA | `wnba` | KXWNBA | `wnba` |
| College Football | `cfb` | KXCFB | `cfb` |
| College Basketball | `cbb` | KXCBB | `cbb` |

### Football (prediction markets only — no ESPN schedule)

| League | Key | Kalshi Series | Polymarket Code |
|---|---|---|---|
| English Premier League | `epl` | KXEPLGAME | `epl` |
| Champions League | `ucl` | KXUCL | `ucl` |
| La Liga | `laliga` | KXLALIGA | `lal` |
| Bundesliga | `bundesliga` | KXBUNDESLIGA | `bun` |
| Serie A | `seriea` | KXSERIEA | `sea` |
| Ligue 1 | `ligue1` | KXLIGUE1 | `fl1` |
| MLS | `mls` | KXMLSGAME | `mls` |
| FIFA World Cup 2026 | `worldcup` | KXWCGAME | `fifwc` |

## Price Normalization

Different sources use different formats. `normalize_price` converts any format to a common structure.

| Source | Format | Example | Meaning |
|---|---|---|---|
| ESPN | American odds | `-150` | Favorite, implied 60% |
| Polymarket | Probability (0-1) | `0.65` | 65% implied probability |
| Kalshi | Integer (0-100) | `65` | 65% implied probability |

**Normalized output shape:**
```json
{
  "implied_probability": 0.65,
  "american": -185.7,
  "decimal": 1.5385,
  "source": "polymarket"
}
```

## Partial Results Behavior

If one source is unavailable, the module returns what it has with warnings:
```json
{
  "status": true,
  "data": {
    "games": [],
    "warnings": ["Kalshi search failed: connection timeout"]
  }
}
```
