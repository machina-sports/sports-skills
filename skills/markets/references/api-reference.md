# Markets Orchestration — API Reference

## Commands

| Command | Required | Optional | Description |
|---|---|---|---|
| `get_todays_markets` | | sport, date | Fetch ESPN schedule → search supported Kalshi, Polymarket, ProphetX, Novig and Gemini listings → unified dashboard |
| `search_entity` | query | sport | Search Kalshi, Polymarket, ProphetX, Novig and Gemini for a team/player/event name; each venue retains its supported sport coverage |
| `compare_odds` | sport, event_id | | ESPN odds + prediction market prices → normalized side-by-side reference quotes (listed, not ranked) |
| `get_sport_markets` | sport | status, limit | Sport-filtered market listing on both platforms (uses sport code, not text query) |
| `get_sport_schedule` | | sport, date | Unified ESPN schedule across one or all sports |
| `normalize_price` | price, source | | Convert any source format to common {implied_prob, american, decimal} |
| `evaluate_market` | sport, event_id | token_id, kalshi_ticker, outcome, fee_per_contract | ESPN odds + executable ask → devig → fee-aware edge → Kelly |
| `match_markets` | sport | date | Pair the same game across Kalshi and Polymarket (date + team-code join, fuzzy title fallback) |
| `get_market_price` | venue, ticker (kalshi) or token_id (polymarket) | at_time | Live or point-in-time price — both sides as 0-1 probabilities, one shape for both venues |
| `get_price_history` | venue, ticker (kalshi) or token_id (polymarket) | interval, start_time, end_time | {timestamp, price} series (0-1 yes probability) at 1m/1h/1d resolution |
| `get_live_tick` | sport, event_id | | Live market tick for an in-progress game — Kalshi home price + ESPN frame |
| `get_mock_tick` | mock_file_path | interval_seconds | Deterministic timeline slice from a static mock game file |
| `get_plays_near_timestamp` | sport, timestamp | game_id, window_seconds, mock_file_path | Plays in the window [timestamp - window_seconds, timestamp] |
| `resolve_game_market` | sport, event_id | status | Resolve one ESPN game to its Kalshi game-winner market (home side) |

### `get_todays_markets` notes

- Each game is searched the way the venues title it, not by ESPN display name: Kalshi by the sport's `{series}GAME` ticker (team codes + date), the other venues by mascot (`"Heat 76ers"`). A game ESPN named no teams for keeps the display-name search.
- `kalshi_markets` holds the game's winner event when its ticker proves the matchup and the date. When the series has no event for the game — markets not open yet, a sport with no mapped series — the text search's results are kept instead, and those are not ticker-proven.
- Teams that meet on consecutive days are told apart by the day the game is played: a 01:00 UTC start belongs to the previous US venue day, which is the day Kalshi dates its ticker by. `compare_odds` prices one game and abstains on that ambiguity instead; the dashboard lists what it found.

### `evaluate_market` notes

- Prices the side named by `outcome` (0 = home, default; 1 = away) at the **ask** from the venue's order book, plus `fee_per_contract`. A bid, a last trade or a midpoint is a reference price, not what a purchase costs.
- `fee_per_contract` is dollars per $1 contract. Without it the ask is still reported, but `evaluation` is `null` — the net edge and Kelly are refused rather than computed as if trading were free. Pass `0` to assert a zero-fee venue.
- The market must be provably this game's full-game winner market: series/slug family, both teams, the right date, and the right side. A wrong-team ticker, a first-half or spread market, a repeat matchup on another date, or a `token_id` naming the other side is refused — never swapped for a different bet.
- Fails closed on a missing ask or zero depth.
- `market_prob` is the effective executable cost (ask + fee) the evaluation used. `sources` reports per-venue outcomes (`ok` / `empty` / `error` / `unmatched`).

### `compare_odds` notes

- `sources` gives a per-source outcome (`ok` / `empty` / `error` / `unmatched`) and `completeness` lists which sources actually priced this game's sides. A provider that errored is distinguishable from one with genuinely no markets. When nothing is usable the call fails instead of returning an empty success.
- `side_prices.home` / `side_prices.away` list every admitted reference quote with its provenance. They are not ranked: `lowest_reference` and `arbitrage_check` are always `null`.
- `ranking_status` is `insufficient_evidence` when quotes exist, or `no_quotes` when none were admitted. `ranking_reason` explains it: current feeds do not prove that the venues settle this game identically, that their prices mean the same thing, or that they were observed at the same moment. Coverage (`sources`, `completeness`) does not imply ranking eligibility.

### Gemini coverage per command

| Command | Gemini |
|---|---|
| `search_entity` | Searched with no `sport` or `nba`, `wnba`, `nfl`, `cfb`, `mlb`, `nhl`, `epl`, `laliga`, `mls`, `ligamx`, `ufc`, `f1`, `golf`; results under `gemini` (grouped by game event, child markets included, soccer three-way outcomes kept as home/away/tie with no fabricated prices) |
| `get_todays_markets` | `gemini_markets` per game for `nba`, `wnba`, `nfl`, `cfb`, `mlb`, `nhl`; other scoreboard sports skip Gemini |
| `compare_odds` | `nba` only; other sports leave Gemini out of `sources`. See admission rules below |
| `normalize_price` | `source="gemini"`: 0-1 probability; values outside [0, 1] or NaN are an error |
| `evaluate_market`, `match_markets`, `get_sport_markets`, `get_market_price`, `get_price_history`, `compare_market_url` | Not supported |

`compare_odds` admits a Gemini market only when it is the single active `moneyline`/`contest`/`full_contest` event of the same league, its `startTime` equals ESPN's start instant, and it has exactly two active, open, non-combo contracts whose sides agree with ESPN's teams and whose buy-YES prices are both in (0, 1). The quote is that buy-YES price from a cached public snapshot (`execution_guaranteed: false`). Everything else (spreads, totals, props, periods, combos, three-way markets, closed/settled contracts, missing/malformed prices, another start, duplicate candidates) is refused with a reason in `sources.gemini.detail`. A failed search is `error`; partial scans are reported in `sources.gemini.warnings`.

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
| Gemini | Probability (0-1) | `0.51` | 51% implied probability (rejected outside [0, 1]) |

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
