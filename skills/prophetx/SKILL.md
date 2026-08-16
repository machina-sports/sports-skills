---
name: prophetx
description: |
  ProphetX betting exchange — public tournaments, events, markets, and exchange odds. No API key, read-only. Covers soccer, tennis, basketball, baseball (MLB), NFL, NHL. IMPORTANT: odds are per-market optional — they appear only when a public order book exists (check `selections_available`); empty/suspended books return market structure and matched stake only. Full guaranteed odds coverage requires the authenticated ProphetX Affiliate API (separate Machina connector).

  Use when: user asks what markets/lines ProphetX offers for a game, ProphetX exchange odds and order-book prices (when exposed), event/tournament discovery, market structure (spreads, totals, alt lines, player props), or matched-stake activity.
  Don't use when: user needs guaranteed odds on every market or in-play liquidity — that requires the authenticated Affiliate connector (Machina platform). For prediction-market prices use polymarket or kalshi. For scores/stats use the sport-specific skill (nfl-data, mlb-data, football-data, ...). For news use sports-news.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# ProphetX — Public Exchange Markets (read-only)

Before writing queries, consult `references/api-reference.md` for sport codes and command parameters.

**Read this first — what this skill can and cannot return:**
- ✅ Tournaments (leagues), events (with home/away, schedule, status), market catalog (moneyline/spread/total, alt lines, player props on v2), matched stake (`total_stake`), primary-line flag (`favourite`).
- ✅ Exchange odds (American) with derived implied probability — but ONLY on markets where a public order book is exposed. Check `selections_available` per market; availability varies (pre-game core markets usually have books; in-play and low-activity markets often come back `[null, null]`).
- ❌ Guaranteed odds on every market, or full order-book depth/liquidity. When `selections_available` is `False`, only structure and matched stake exist — never invent odds. Complete odds coverage lives behind the authenticated ProphetX Affiliate API, a separate credentialed Machina connector — never wire tokens into this skill.

## Quick Start

Prefer the CLI — it avoids Python import path issues:
```bash
sports-skills prophetx get_sports_config
sports-skills prophetx search_markets --sport=nfl --query="Eagles"
sports-skills prophetx get_todays_events --sport=mlb
sports-skills prophetx get_tournaments --sport=soccer
sports-skills prophetx get_markets --event_id=19742 --api_version=v2
```

Python SDK (alternative):
```python
from sports_skills import prophetx

prophetx.get_sports_config()
prophetx.search_markets(sport="nfl", query="Eagles")
prophetx.get_todays_events(sport="mlb")
prophetx.get_events(109)                      # tournament_id
prophetx.get_markets(19742, api_version="v2") # event_id
prophetx.get_market(19742, 219)               # market id or "19742:219"
```

## CRITICAL: Before Any Query

- Market `id` is the market-TYPE id (219 = Moneyline on ANY event) — the stable per-event key is `market_key` (`"<event_id>:<market_id>"`).
- `api_version="v2"` adds category, subType, alt lines (`market_lines`) and player props; default v1 is the lean catalog. v2 automatically falls back to v1 on failure.
- Check `selections_available` before reading odds fields — odds exist only where a public order book does; never present `total_stake` (matched volume) as odds or liquidity.
- Sport codes: `soccer`, `tennis`, `basketball`, `baseball`, `ice-hockey`, `american-football` + aliases (`nfl`, `nba`, `mlb`, `nhl`, `epl`, `mls`, `worldcup`, ...).

## Workflows

### Market discovery for a game
1. `search_markets --sport=nfl --query="Eagles"` — soonest matching events with their markets.
2. Present market names/types/lines; quote odds only from markets with `selections_available: true`, and say explicitly when a market's public book is empty.

### Today's slate
1. `get_todays_events --sport=mlb` — today's events (UTC) with home/away and schedule.
2. Follow with `get_markets --event_id=<id> --api_version=v2` for the full catalog (player props, alt lines).

### Explore the exchange
1. `get_sports_config` — sports and live tournaments.
2. `get_tournaments --sport=soccer` → `get_events --tournament_id=<id>`.

## Important Notes

- **Read-only by design**: no login, no cookies, no browser automation, only GETs; conservative throttling + caching + retries with backoff; fails closed on 403/WAF and on schema drift.
- Event `status` values observed: `not_started`, `live`.
- `_raw` preserves the full provider payload on every normalized record.
- Unified cross-venue discovery: `sports-skills markets search_entity --query="Yankees"` includes a `prophetx` section (top-of-book odds per outcome when a public book exists; events without any exposed book are flagged with a `note`).
