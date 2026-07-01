---
name: esports
description: |
  Esports data — Dota 2 (OpenDota) and League of Legends esports (Leaguepedia).
  Pro matches, tournaments, teams, and structured LoL competitive data.
  Use when: user asks about Dota 2 pro matches/teams/leagues, or LoL esports
  tournaments/rosters/results.
  For esports betting/odds: use the `kalshi` (get_esports_odds) or `polymarket`
  (get_esports_events) skills — there is no keyless bookmaker-odds source.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# Esports Data

Keyless, public sources. **No API key, no signup.**

- **Dota 2** → OpenDota (`api.opendota.com`). Real JSON. Free tier ~60 req/min.
- **League of Legends esports** → Leaguepedia Cargo (`lol.fandom.com`). Structured
  rows. **CC-BY-SA — attribute Leaguepedia when you reuse the data.**

## CRITICAL

- **Dota 2 only** for match/team/league data (OpenDota). LoL uses Leaguepedia Cargo.
- **Leaguepedia is aggressively rate-limited.** The throttle comes back as an
  *in-body* error (`Leaguepedia API error: ...`) on an HTTP 200 — not a 4xx.
  Results are cached ~30 min; don't hammer it.
- **No odds here.** Bookmaker odds for esports are not available keyless. For
  implied-probability signals, use `kalshi get_esports_odds --game=cs2` or
  `polymarket get_esports_events`.
- **Personal use.** Third-party ToS apply (OpenDota MIT; Leaguepedia CC-BY-SA).

## Quick Start

CLI:
```bash
sports-skills esports get_pro_matches --limit=10
sports-skills esports get_pro_teams --limit=10
sports-skills esports get_leagues --tier=premium
sports-skills esports get_lol_tournaments --region=Korea --limit=5
sports-skills esports lol_cargo_query --tables=Teams --fields=Name,Region --limit=5
```

Python:
```python
from sports_skills import esports

esports.get_pro_matches(limit=10)
esports.get_lol_tournaments(region="Brazil")
```

## Commands

| Command | Description |
|---|---|
| `get_pro_matches` | Recent Dota 2 professional matches (OpenDota) |
| `get_leagues` | Dota 2 leagues/tournaments, filter by tier (OpenDota) |
| `get_pro_teams` | Top Dota 2 teams by rating (OpenDota) |
| `get_match` | Detailed Dota 2 match by id (OpenDota) |
| `get_lol_tournaments` | Recent LoL esports tournaments (Leaguepedia) |
| `lol_cargo_query` | Raw Leaguepedia Cargo query (any table/fields) |

## Leaguepedia Cargo reference

`lol_cargo_query` needs `tables` + `fields`. Common tables (fields vary — verify
with a small query first): `Tournaments` (Name, DateStart, DateEnd, League,
Region, Prizepool), `MatchSchedule` (Team1, Team2, Winner, DateTime_UTC, BestOf),
`ScoreboardGames`, `Players`, `Teams`. Full schema:
<https://lol.fandom.com/wiki/Special:CargoTables>.

## Troubleshooting

- `Leaguepedia API error: You've exceeded your rate limit` → you're being
  throttled. Wait and retry; the connector caches for ~30 min to help.
- Empty `matches`/`teams` from OpenDota → transient; OpenDota is volunteer-run
  best-effort infra with no SLA. Retry.
