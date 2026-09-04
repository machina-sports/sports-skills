---
name: football-data
description: |
  Football (soccer) data across the world's major leagues — standings, schedules, match stats, xG, transfers, player profiles, head-to-head history, team strength (Elo), and match forecasts. Zero config, no API keys. Covers Premier League, La Liga, Bundesliga, Serie A, Ligue 1, MLS, Champions League, World Cup, Championship, Eredivisie, Primeira Liga, Serie A Brazil, Russian Premier League, Scottish/Belgian/Turkish top flights, European Championship, and more (call get_competitions for the live list).

  Use when: user asks about football/soccer standings, fixtures, match stats, xG, lineups, player values, transfers, injury news, league tables, daily fixtures, player profiles, head-to-head records, team strength/Elo ratings, or match odds/forecasts.
  Don't use when: user asks about American football/NFL (use nfl-data), college football (use cfb-data), NBA (use nba-data), WNBA (use wnba-data), college basketball (use cbb-data), NHL (use nhl-data), MLB (use mlb-data), tennis (use tennis-data), golf (use golf-data), cricket (use cricket-data), Formula 1 (use fastf1), or betting odds (use polymarket or kalshi). Don't use for live/real-time scores — data updates post-match. Don't use get_season_leaders or get_missing_players for non-Premier League leagues (they return empty). Don't use get_event_xg for leagues outside the top 5 (EPL, La Liga, Bundesliga, Serie A, Ligue 1).
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# Football Data

Before writing queries, consult `references/api-reference.md` for endpoints, ID conventions, and data shapes.

## Setup

Before first use, check if the CLI is available:
```bash
which sports-skills || pip install sports-skills
```
If `pip install` fails (package not found or Python version error), install from GitHub:
```bash
pip install git+https://github.com/machina-sports/sports-skills.git
```
The package requires Python 3.10+. If your default Python is older, use a specific version:
```bash
python3 --version  # check version
# If < 3.10, try: python3.12 -m pip install sports-skills
# On macOS with Homebrew: /opt/homebrew/bin/python3.12 -m pip install sports-skills
```
No API keys required.

## Quick Start

Prefer the CLI — it avoids Python import path issues:
```bash
sports-skills football get_daily_schedule
sports-skills football get_season_standings --season_id=premier-league-2025
```

Python SDK (alternative):
```python
from sports_skills import football

standings = football.get_season_standings(season_id="premier-league-2025")
schedule = football.get_daily_schedule()
```

## CRITICAL: Before Any Query

CRITICAL: Before calling any data endpoint, verify:
- Season ID is derived from `get_current_season(competition_id="...")` — never hardcoded.
- Team ID is resolved via `search_team(query="...")` and passed as the numeric `team_id`. For `get_head_to_head`, `get_team_strength`, and `get_match_forecast`, always pass IDs — ambiguous names (e.g. two "Paris" clubs) can resolve to the wrong team.
- The endpoint actually covers the league in question — see the **Coverage & Source Map** below. Coverage is uneven across sources; an uncovered call returns an empty payload with a `message`, not data.
- `get_event_xg` and `get_event_players_statistics` (with xG) are only called for top-5 leagues (EPL, La Liga, Bundesliga, Serie A, Ligue 1).
- `get_season_leaders` and `get_missing_players` are only called for Premier League seasons (season_id must start with `premier-league-`).

## Choosing the Season

Derive the current year from the system prompt's date (e.g., `currentDate: 2026-02-16` → current year is 2026).

- **If the user specifies a season**, use it as-is.
- **If the user says "current", "latest", or doesn't specify**: Call `get_current_season(competition_id="...")` to get the active season_id. Do NOT guess or hardcode the year.
- **Season format**: Always `{league-slug}-{year}` (e.g., `"premier-league-2025"` for the 2025-26 season). The year is the start year of the season, not the end year.
- **MLS exception**: MLS runs spring-fall within a single calendar year. Use `get_current_season(competition_id="mls")`.

## Coverage & Source Map

This skill stitches several free sources together. **Coverage is not uniform** — each endpoint works only where its underlying source has data. Check this before promising an answer; when an endpoint isn't covered, it returns an empty payload with an explanatory `message` (never an error) — read that message and fall back.

| Endpoint(s) | Source | Coverage |
|---|---|---|
| standings, schedules, teams, event summary/lineups/stats/timeline | ESPN | **All leagues** (broadest — the backbone) |
| `get_event_xg`, `get_event_players_statistics` (xG fields) | Understat | **Top 5 only** (EPL, La Liga, Bundesliga, Serie A, Ligue 1). *Not RFPL — Understat dropped it.* |
| `get_season_leaders`, `get_missing_players` | FPL | **Premier League only** |
| `get_player_profile`, `get_season_transfers` (market value) | Transfermarkt | Any player with a `tm_player_id` |
| `get_head_to_head` | football-data.co.uk | **11 European domestic leagues** (EPL, Championship, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie, Primeira Liga, Scottish, Belgian, Turkish). Same-division meetings only. |
| `get_team_strength` | ClubElo, falling back to local Elo | **European clubs** (incl. Russia). Falls back to ratings computed from football-data.co.uk when ClubElo is down. |
| `get_match_forecast` | ClubElo | **European clubs** (incl. Russia). No fallback — needs ClubElo's fixture feed. |

Rule of thumb: **ESPN answers "what happened" everywhere; the enrichment sources ( Understat/FPL/ClubElo/football-data.co.uk ) add depth only in their coverage zone.** ESPN is always the fixture/score authority — never let an enrichment source override an ESPN score.

### Gotchas (from live testing)
- **Pass IDs, not ambiguous names.** For H2H/strength/forecast, resolve teams with `search_team` first and pass the numeric `team_id`. Names like "Paris Saint-Germain" can collapse onto the wrong club (Paris FC) during name resolution.
- **ClubElo off-season gaps**: current-date `get_team_strength` can miss clubs in the summer break (a club's weekly Elo period may not span today). If a well-known club returns unresolved, pass an in-season `date` (e.g. `date="2026-03-01"`).
- **ClubElo outages**: `get_team_strength` falls back to locally computed Elo and sets `source: "local-elo"`. Check that field before comparing numbers across calls — the local scale is division-local, so a rating means nothing outside its own division and cross-division comparisons are refused. `get_match_forecast` has no fallback and stays empty.
- **`get_match_forecast` is short-horizon**: ClubElo only forecasts ~a week ahead — empty between matchdays / off-season. That's expected, not a failure.
- **H2H is same-division only**: two clubs that met in a cup or across tiers won't show; it counts league meetings in the resolved division.
- **H2H tells "unresolved" apart from "never met"**: football-data.co.uk uses short exonyms/abbreviations ("FC Koln", "M'gladbach", "Sp Lisbon"). Each club in `teams[]` reports `resolved` + `matched_as`; if a club is `resolved: false`, zero meetings means the lookup failed, not that the clubs never played.

## Combining Endpoints (mix-and-match)

Compose sources for richer answers. Run independent calls in parallel.

- **Match preview** (`X vs Y`): `search_team` ×2 → `get_head_to_head` (recent record) + `get_team_strength(team_id, team_id_2)` (Elo gap / favorite) + `get_match_forecast` (if within ~a week: W/D/L + scoreline). For a top-5 fixture add historical `get_event_xg` context from recent meetings.
- **Match report** (post-game): `get_event_summary` + `get_event_statistics` + `get_event_timeline`, and for top-5 leagues `get_event_xg` + `get_event_players_statistics`.
- **Team form + context**: `get_team_schedule` (recent results) + `get_team_strength` (current Elo & rank) + `get_missing_players` (PL only) + per-match `get_event_xg` (top-5).
- **Rivalry / derby deep dive**: `get_head_to_head` (all-time-ish record + goals) + `get_team_strength` comparison for the current power balance.
- **Odds sanity-check**: `get_match_forecast` gives a free model baseline (W/D/L) to compare against the `kalshi` / `polymarket` betting skills.

When a piece of the composition isn't covered (e.g. xG outside the top 5, H2H for MLS), skip it silently and deliver the parts that are covered — don't block the whole answer on one missing source.

## Commands

| Command | Description |
|---|---|
| `get_current_season` | Detect current season for a competition |
| `get_competitions` | List available competitions with current season info |
| `get_competition_seasons` | Available seasons for a competition |
| `get_season_schedule` | Full season match schedule |
| `get_season_standings` | League table for a season |
| `get_season_leaders` | Top scorers/leaders (Premier League only) |
| `get_season_teams` | Teams in a season |
| `search_team` | Search for a team by name |
| `search_player` | Search for a player by name |
| `get_team_profile` | Basic team info (no squad/roster) |
| `get_daily_schedule` | All matches for a date across all leagues |
| `get_event_summary` | Match summary with scores |
| `get_event_lineups` | Match lineups |
| `get_event_statistics` | Match team statistics |
| `get_event_timeline` | Match timeline (goals, cards, subs) |
| `get_team_schedule` | Schedule for a specific team |
| `get_head_to_head` | Historical H2H results + stats (European domestic leagues) |
| `get_team_strength` | Elo rating / two-team comparison (European clubs); local-Elo fallback if ClubElo is down |
| `get_match_forecast` | ClubElo win/draw/loss + scoreline forecast (~week ahead) |
| `get_event_xg` | xG data (top 5 leagues only) |
| `get_event_players_statistics` | Player-level match stats with optional xG |
| `get_missing_players` | Injured/doubtful players (Premier League only) |
| `get_season_transfers` | Transfer history via Transfermarkt |
| `get_player_season_stats` | Player season stats via ESPN |
| `get_player_profile` | Player profile (FPL and/or Transfermarkt) |

See `references/api-reference.md` for full parameter lists, return shapes, and data coverage table.

## Examples

Example 1: Premier League table
User says: "Show me the Premier League table"
Actions:
1. Call `get_current_season(competition_id="premier-league")` to get the current season_id
2. Call `get_season_standings(season_id=<season_id from step 1>)`
Result: Standings table with position, team, played, won, drawn, lost, GD, points

Example 2: Match report
User says: "How did Arsenal vs Liverpool go?"
Actions:
1. Call `get_daily_schedule()` or `get_team_schedule(team_id="359")` to find the event_id
2. Call `get_event_summary(event_id="...")` for the score
3. Call `get_event_statistics(event_id="...")` for possession, shots, etc.
4. Call `get_event_xg(event_id="...")` for xG comparison (EPL — top 5 only)
Result: Match report with scores, key stats, and xG

Example 3: Team deep dive
User says: "Deep dive on Chelsea's recent form"
Actions:
1. Call `search_team(query="Chelsea")` → team_id=363, competition=premier-league
2. Call `get_team_schedule(team_id="363", competition_id="premier-league")` → find recent closed events
3. For each recent match, call in parallel: `get_event_xg`, `get_event_statistics`, `get_event_players_statistics`
4. Call `get_missing_players(season_id=<season_id>)` → filter Chelsea's injured/doubtful players
Result: xG trend across matches, key player stats, and injury report

Example 4: Player market value
User says: "What's Saka's market value?"
Actions:
1. Call `get_player_profile(tm_player_id="433177")` for Transfermarkt data
2. Optionally add `fpl_id` for FPL stats
Result: Market value, value history, and transfer history

Example 5: Non-PL club
User says: "Tell me about Corinthians"
Actions:
1. Call `search_team(query="Corinthians")` → team_id=874, competition=serie-a-brazil
2. Call `get_team_schedule(team_id="874", competition_id="serie-a-brazil")` for fixtures
3. Pick a recent match and call `get_event_timeline(event_id="...")` for goals, cards, subs
Result: Fixtures, timeline events (note: xG, FPL stats, and season leaders NOT available for Brazilian Serie A)

Example 6: Match preview (mix-and-match)
User says: "Preview Arsenal vs Man City this weekend"
Actions:
1. Call `search_team(query="Arsenal")` and `search_team(query="Manchester City")` → team_ids 359, 382
2. In parallel: `get_head_to_head(team_id="359", team_id_2="382")` (recent record + goals),
   `get_team_strength(team_id="359", team_id_2="382")` (Elo gap + favorite),
   `get_match_forecast(team_id="359", team_id_2="382")` (W/D/L + likely scoreline, if within ~a week)
3. Synthesize: form/record + power balance + model odds. Skip any piece that returns empty (e.g. forecast if the match is >1 week out).
Result: A preview blending head-to-head history, current strength, and a free model forecast

## Commands that DO NOT exist — never call these

- ~~`get_standings`~~ — the correct command is `get_season_standings` (requires `season_id`).
- ~~`get_live_scores`~~ — not available. Use `get_daily_schedule()` for today's matches.
- ~~`get_team_squad`~~ / ~~`get_team_roster`~~ — `get_team_profile` does NOT return players. Use `get_season_leaders` for PL player IDs, then `get_player_profile`.
- ~~`get_transfers`~~ — the correct command is `get_season_transfers` (requires `season_id` + `tm_player_ids`).
- ~~`get_match_results`~~ / ~~`get_match`~~ — use `get_event_summary` with an `event_id`.
- ~~`get_player_stats`~~ — use `get_event_players_statistics` for match-level stats, or `get_player_profile` for career data.
- ~~`get_scores`~~ / ~~`get_results`~~ — use `get_event_summary` with an `event_id`.
- ~~`get_fixtures`~~ — use `get_daily_schedule` for today's matches or `get_season_schedule` for a full season.
- ~~`get_league_table`~~ — use `get_season_standings` with a `season_id`.

If a command is not in the Commands table above, it does not exist. Do not try commands not listed.

## Error Handling

When a command fails (wrong event_id, missing data, network error, etc.), **do not surface the raw error to the user**. Instead:
1. Catch it silently — treat the failure as an exploratory miss.
2. Try alternatives — if an event_id returns no data, call `get_daily_schedule()` or `get_team_schedule()` to discover the correct ID.
3. Only report failure after exhausting alternatives — use a clean message (e.g., "I couldn't find that match — can you confirm the teams or date?").

## Troubleshooting

Error: `sports-skills` command not found
Cause: Package not installed
Solution: Run `pip install sports-skills`. If not on PyPI, install from GitHub: `pip install git+https://github.com/machina-sports/sports-skills.git`

Error: `ModuleNotFoundError: No module named 'sports_skills'`
Cause: Package not installed or path issue
Solution: Install the package. Prefer the CLI over Python imports to avoid path issues

Error: `get_season_leaders` or `get_missing_players` returns empty for a non-PL league
Cause: These commands only work for Premier League; they silently return empty for other leagues
Solution: Check the Data Coverage table in `references/api-reference.md`. For other leagues, use `get_event_players_statistics` for player data

Error: `get_team_profile` returns no players
Cause: This command does not return squad rosters — this is expected behavior
Solution: For PL teams, use `get_season_leaders` to find player FPL IDs, then `get_player_profile(fpl_id="...")`

Error: Wrong season_id format
Cause: Season ID must follow the `{league-slug}-{year}` format
Solution: Use `get_current_season(competition_id="...")` to discover the correct format. Example: `"premier-league-2025"`, not `"2025-2026"` or `"EPL-2025"`

Error: No xG data for a recent match
Cause: Understat data may lag 24-48 hours after a match ends
Solution: If `get_event_xg` returns empty for a recent top-5 match, retry later. Only available for EPL, La Liga, Bundesliga, Serie A, Ligue 1

Error: Team or event ID unknown
Cause: ID was guessed instead of looked up
Solution: Use `search_team(query="team name")` to find team IDs, or `get_daily_schedule` / `get_season_schedule` to find event IDs. Never guess IDs.
