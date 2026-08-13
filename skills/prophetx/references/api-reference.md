# ProphetX — API Reference

## Sport-Aware Commands

| Command | Required | Optional | Description |
|---|---|---|---|
| `get_sports_config` | | | Sport codes, aliases, and live tournaments |
| `get_todays_events` | | sport, limit | Today's events (UTC) across tournaments |
| `search_markets` | | sport, query, status, limit, api_version | Markets of the soonest matching events (bounded fan-out) |

## Raw API Commands

| Command | Required | Optional | Description |
|---|---|---|---|
| `get_tournaments` | | limit, sport, next | Tournaments (leagues/competitions) |
| `get_events` | tournament_id | limit, status | Events of a tournament |
| `get_markets` | event_id | api_version, market_type | Market catalog of an event (v2 falls back to v1) |
| `get_market` | event_id, market_id | api_version | One market, filtered from the event payload (no per-market upstream endpoint) |

## Sport codes

Canonical: `soccer`, `tennis`, `basketball`, `baseball`, `ice-hockey`, `american-football`.
Aliases: `nfl`, `cfb` → american-football; `nba`, `wnba`, `cbb` → basketball; `mlb` → baseball; `nhl`, `hockey` → ice-hockey; `epl`, `ucl`, `laliga`, `bundesliga`, `seriea`, `ligue1`, `mls`, `worldcup` → soccer; `atp`, `wta` → tennis.

## Normalized fields

- Event: `id`, `name`, `tournament_id`, `tournament`, `scheduled` (ISO-8601 UTC), `status` (`not_started`, `live`), `home`, `away`, `competitors[]` (`seq` 0 = home), `venue`, `source_url`, `retrieved_at`, `_raw`.
- Market: `id` (market-TYPE id), `market_key` (`"<event_id>:<id>"` — the per-event key), `event_id`, `name`, `type` (`moneyline`/`spread`/`total`/`sup_moneyline`), `subtype` (v2), `category` (v2), `status`, `total_stake` (matched volume — NOT liquidity), `outcomes[]`, `market_lines[]` (v2 alt lines; `favourite: true` marks the primary line), `selections_available` (currently always `False` on the public surface), `api_version`, `source_url`, `retrieved_at`, `_raw`.
- Outcome: `id`, `name`, `competitor_id`, `line`, `display_line`, `line_id`; `odds_american` + `implied_probability` appear ONLY if the upstream ever populates odds.

## No odds on this surface

`selections` is `[null, null]` on every observed market (including live games). Do not present `total_stake` as odds/liquidity. Odds require the authenticated ProphetX Affiliate API (Machina connector track).
