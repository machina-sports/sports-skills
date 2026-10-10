---
name: markets
description: |
  Markets orchestration — connects ESPN live schedules with Kalshi and Polymarket prediction markets. Unified dashboards, odds comparison, entity search, and bet evaluation across platforms.

  Use when: user wants to see prediction market odds alongside ESPN game schedules, compare odds across platforms, search for a team/player on Kalshi or Polymarket, check for arbitrage between ESPN odds and prediction markets, or evaluate a specific game's market value.
  Don't use when: user wants raw prediction market data without ESPN context — use polymarket or kalshi directly. For pure odds math (conversion, de-vigging, Kelly) — use betting. For live scores without market data — use the sport-specific skill.
license: MIT
metadata:
  author: machina-sports
  version: "0.3.0"
---

# Markets Orchestration

Bridges ESPN live schedules (NBA, NFL, MLB, NHL, WNBA, CFB, CBB) with Kalshi and Polymarket prediction markets. Before writing queries, consult `references/api-reference.md` for supported sport codes, command parameters, and price normalization formats.

## Quick Start

```bash
sports-skills markets get_todays_markets --sport=nba
sports-skills markets search_entity --query="Lakers" --sport=nba
sports-skills markets compare_odds --sport=nba --event_id=401234567
sports-skills markets compare_market_url --url=https://polymarket.com/event/nfl-sf-sea-2026-10-11
sports-skills markets get_sport_markets --sport=nfl
sports-skills markets get_sport_schedule --sport=nba
sports-skills markets normalize_price --price=0.65 --source=polymarket
sports-skills markets evaluate_market --sport=nba --event_id=401234567 --fee_per_contract=<verified fee>
sports-skills markets match_markets --sport=mlb --date=2026-06-06
sports-skills markets get_market_price --venue=kalshi --ticker=KXMENWORLDCUP-26-FR
sports-skills markets get_price_history --venue=kalshi --ticker=KXMENWORLDCUP-26-FR --interval=1d
```

Python SDK:
```python
from sports_skills import markets

markets.get_todays_markets(sport="nba")
markets.search_entity(query="Lakers", sport="nba")
markets.compare_odds(sport="nba", event_id="401234567")
markets.compare_market_url(url="https://kalshi.com/markets/kxnflgame/sf-vs-sea/kxnflgame-26oct11sfsea")
markets.get_sport_markets(sport="nfl")
markets.get_sport_schedule(sport="nba", date="2025-02-26")
markets.normalize_price(price=0.65, source="polymarket")
markets.evaluate_market(sport="nba", event_id="401234567", fee_per_contract=fee)  # fee: verified (user-stated or documented venue fee)
markets.match_markets(sport="mlb", date="2026-06-06")
markets.get_market_price(venue="kalshi", ticker="KXMENWORLDCUP-26-FR", at_time="2026-05-01T12:00:00+00:00")
markets.get_price_history(venue="polymarket", token_id="<token_id>", interval="1h")
```

## CRITICAL: Before Any Query

CRITICAL: Before calling any orchestration command, verify:
- A `sport` code is provided for sport-aware commands (`get_todays_markets`, `compare_odds`, `get_sport_markets`, `evaluate_market`).
- Price sources are identified correctly before normalization: `espn` = American odds, `polymarket` = 0-1 probability, `kalshi` = 0-100 integer.

## Important Notes

- **Sport context is passed through.** `--sport=nba` maps automatically to the correct Polymarket sport code and Kalshi series ticker.
- **Venues differ by command.** `get_todays_markets`, `search_entity` and `compare_odds` search Kalshi, Polymarket, ProphetX and Novig. `get_sport_markets`, `match_markets` and `evaluate_market` use Kalshi and Polymarket only.
- **Sport-aware search.** Polymarket uses `sport` → series_id; Kalshi searches every series mapped for the sport (game winners, spreads, totals, futures).
- **Prices are normalized.** Everything is converted to implied probability for comparison.
- **Discovery is not verification.** Raw market lists (`*_markets`, `get_sport_markets`, `search_entity`) are search hits, not verified equivalents of a given game's contract. Only `compare_odds` `side_prices` (and `evaluate_market`) are identity-checked.

## Workflows

### Today's NBA Dashboard

```bash
sports-skills markets get_todays_markets --sport=nba
```
Returns each game with ESPN info, DraftKings odds, and matching Kalshi, Polymarket, ProphetX and Novig markets.

### Find Arb on a Specific Game

1. Get the ESPN event ID: `get_sport_schedule --sport=nba`
2. Compare odds: `compare_odds --sport=nba --event_id=<id>`
3. If arbitrage detected, response includes allocation percentages and ROI — computed from **reference** prices (`price_basis: "reference"`), so confirm both legs on each venue's order book before trading it.
4. `sources` and `completeness` say which venues actually priced this game; a provider error is reported as `error`, not as "no markets".
5. For a direct price comparison read `side_prices.home` / `side_prices.away`: each lists `quotes` (`venue`, `implied_probability`, `price_basis: "reference"`, `execution_guaranteed: false`) admitted as this game's full-game moneyline, plus `lowest_reference` (`null` when a side has no quote; ties keep the first-listed venue). The lowest reference is not an executable quote, not fee-adjusted, and not a bet recommendation. Check `warnings` and `completeness.complete` before calling a comparison complete.
6. Venues searched: Kalshi, Polymarket, ProphetX and Novig. Novig counts only when the event date matches and a full-game `MONEY` market has a two-way order book. Its price is the derived ask (1 − best opposite bid), a cached snapshot. Catalog-only markets, spreads and period markets show up in `novig_markets` but never price a side. `search_entity` and `get_todays_markets` also include a `novig` section with the same results.

### Compare a Pasted Market Link

#### compare_market_url

1. `compare_market_url --url=<link>`. Supported links: `https://polymarket.com/event/<event-slug>[/<market-slug>]` and `https://kalshi.com/markets/<series>/<slug>/<event-ticker>` (`www.` allowed), for single games of nfl, nba, mlb, nhl, wnba, cfb, cbb.
2. The link is never fetched. The host must match exactly. Credentials, ports, fragments, encoded or odd path segments, and unknown query keys are refused before any call (only `utm_*` and other click-tracking keys are ignored).
3. The venue API resolves exactly one **open** full-game two-way moneyline (Polymarket) or the two open game-winner contracts (Kalshi). Closed, non-moneyline, three-way or ambiguous sources are refused, and so is a provider answer that names another slug/ticker.
4. ESPN scoreboards for the source date ±1 day must yield exactly one game whose teams and date validate. Doubleheaders and multiple matches are refused, and a scoreboard failure is reported as a failure, not as "no game".
5. Returns the `compare_odds` payload unchanged (`side_prices`, `sources`, `warnings`, …) plus `source_market` (venue, canonical `url`, event/market ids, `espn_event_id`, `in_downstream_search`). When the source contract is missing from the comparison's venue search, a warning says so and no price is invented.
6. This matches the same game's moneyline only. It does not mean the venues settle identically, and it guarantees no execution. Novig and ProphetX links are not accepted yet, though both venues still appear in the comparison.

### Full Bet Evaluation

1. `evaluate_market --sport=nba --event_id=<id> --outcome=0 --fee_per_contract=<dollars per $1 contract>`
2. Verifies the market is this game's full-game winner market for the chosen side, then reads the **ask** off the order book
3. Pipes ask + fee through `betting.evaluate_bet`: devig → edge → Kelly
4. Returns fair probability, edge, EV, Kelly fraction, and recommendation

Without `fee_per_contract` the ask is reported but `evaluation` is `null` — the net numbers are refused rather than assumed free. A ticker or `token_id` that names another team, another date, or a derivative (first-half, spread) market is refused, not substituted. Pass the fee via the CLI (`--fee_per_contract=<dollars>`) or the Python wrapper. The fee must be an explicit, verified assumption: one the user stated, or the venue's officially documented fee schedule (say which). Never silently assume `0`. If no fee can be verified, `evaluation` stays `null`.

### Same Game on Both Venues

1. `match_markets --sport=mlb --date=2026-06-06`
2. Each match pairs the Kalshi event (with market tickers) and the Polymarket event (with moneyline token IDs) for the same game — joined deterministically on date + team codes, fuzzy title match as fallback.
3. Feed `kalshi.market_tickers[i]` and `polymarket.markets[i].token_ids[j]` straight into `get_market_price` to compare prices.

### Price Movement Over Time

1. `get_market_price --venue=kalshi --ticker=<ticker> --at_time=2026-05-01` for a single point-in-time price (both `yes`/`no` sides, 0-1).
2. `get_price_history --venue=kalshi --ticker=<ticker> --interval=1d` for the full series — same `{timestamp, price}` shape on either venue.

## Examples

Example 1: Today's games with prediction market odds
User says: "What NBA games are on today and what are the prediction market odds?"
Actions:
1. Call `get_todays_markets(sport="nba")`
Result: Unified dashboard with each game's ESPN info and Kalshi/Polymarket/ProphetX/Novig markets

Example 2: Cross-platform team search
User says: "Find me Lakers markets on Kalshi and Polymarket"
Actions:
1. Call `search_entity(query="Lakers", sport="nba")`
Result: Lakers search hits from Kalshi, Polymarket, ProphetX and Novig (discovery only — not verified as the same contract)

Example 3: Odds comparison for a specific game
User says: "Compare the odds for this Celtics game across ESPN and Polymarket"
Actions:
1. Get event_id from `get_sport_schedule(sport="nba")`
2. Call `compare_odds(sport="nba", event_id="<id>")`
Result: `side_prices` per side (admitted reference quotes + `lowest_reference`) and an arbitrage check on reference prices

Example 4: Full market evaluation
User says: "Is there edge on the Chiefs game?"
Actions:
1. Get event_id from `get_sport_schedule(sport="nfl")`
2. Establish a verified fee (user-stated or the venue's documented fee), then call `evaluate_market(sport="nfl", event_id="<id>", fee_per_contract=<verified fee>)`
Result: Fair probability, edge percentage, EV, Kelly fraction, and bet recommendation. Without a verified fee, the executable ask is reported and `evaluation` is `null`.

Example 5: Browse all markets for a sport
User says: "Show me all NFL prediction markets"
Actions:
1. Call `get_sport_markets(sport="nfl")`
Result: All open NFL markets across Kalshi and Polymarket

Example 6: Price conversion
User says: "Convert a Polymarket price of 65 cents to American odds"
Actions:
1. Call `normalize_price(price=0.65, source="polymarket")`
Result: Common structure with implied probability (0.65), American odds (-185.7), and decimal (1.54)

Example 7: Pair a game across venues
User says: "Find the Mets game on both Kalshi and Polymarket"
Actions:
1. Call `match_markets(sport="mlb", date="<game date>")`
Result: The game paired across venues — Kalshi market tickers and Polymarket moneyline token IDs side by side

Example 8: Historical price
User says: "What was France's World Cup price a month ago?"
Actions:
1. Call `get_market_price(venue="kalshi", ticker="KXMENWORLDCUP-26-FR", at_time="2026-05-03T12:00:00+00:00")`
Result: Yes/no prices (0-1) as of that moment; use `get_price_history` for the full curve

## Commands that DO NOT exist — never call these

- ~~`get_odds`~~ — does not exist. Use `compare_odds` to see odds across sources.
- ~~`search_markets`~~ — does not exist on the markets module. Use `search_entity` instead.
- ~~`get_schedule`~~ — does not exist. Use `get_sport_schedule` instead.

If a command is not listed in `references/api-reference.md` or in this file's workflows (e.g. `compare_market_url`), it does not exist.

## Troubleshooting

Error: No markets returned for a sport
Cause: Sport code may be missing or incorrect
Solution: Check `references/api-reference.md` for valid sport codes. Use the exact code (e.g., `nba`, `epl`, `laliga`)

Error: `compare_odds` returns no data for an event
Cause: The event_id is incorrect or the game has not been indexed yet
Solution: Call `get_sport_schedule(sport=...)` to retrieve the correct event_id first

Error: One source shows warnings in the response
Cause: Kalshi or Polymarket is temporarily unavailable
Solution: The module returns partial results — use what is available. Retry the unavailable source separately using the kalshi or polymarket skill directly

Error: `normalize_price` returns unexpected American odds value
Cause: Wrong `source` parameter — Kalshi uses 0-100 integers, Polymarket uses 0-1 decimals
Solution: Verify the source. Kalshi price of 65 requires `source="kalshi"`, Polymarket price of 0.65 requires `source="polymarket"`
