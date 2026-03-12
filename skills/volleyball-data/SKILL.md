---
name: volleyball-data
description: |
  Dutch volleyball data (Eredivisie, Topdivisie, Superdivisie, and the full Dutch pyramid) via the Nevobo API. Standings, schedules, results, clubs, tournaments, and news. Zero config, no API keys.

  Use when: user asks about Dutch volleyball, Eredivisie volleyball, Nevobo, volleyball standings, volleyball match results, volleyball schedules, or Dutch volleyball clubs.
  Don't use when: user asks about other sports — use football-data (soccer), nfl-data (NFL), nba-data (NBA), wnba-data (WNBA), nhl-data (NHL), mlb-data (MLB), golf-data (golf), cfb-data (college football), cbb-data (college basketball), tennis-data (tennis), or fastf1 (F1). For betting odds use polymarket or kalshi. For general news use sports-news.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# Volleyball Data (Nevobo — Dutch Volleyball)

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
No API keys required. All data comes from the Nevobo (Nederlandse Volleybalbond) open API.

## Quick Start

Prefer the CLI — it avoids Python import path issues:
```bash
sports-skills volleyball get_competitions
sports-skills volleyball get_standings --competition_id=nevobo-eredivisie-heren
sports-skills volleyball get_results --competition_id=nevobo-eredivisie-dames
sports-skills volleyball get_schedule --competition_id=nevobo-topdivisie-heren-a
```

Python SDK (alternative):
```python
from sports_skills import volleyball

standings = volleyball.get_standings(competition_id="nevobo-eredivisie-heren")
results = volleyball.get_results(competition_id="nevobo-eredivisie-dames")
```

## CRITICAL: Before Any Query

CRITICAL: Before calling any data endpoint, verify:
- The `competition_id` uses a valid value from `references/competition-ids.md` — never guess.
- For club-specific commands, you have a valid Nevobo `club_id` (use `get_clubs` to find one — the `organisatiecode` field).
- Do NOT guess club IDs or competition IDs. Use `get_competitions` or `get_clubs` to discover them.

## The `competition_id` Parameter

8 leagues across the top 3 tiers of Dutch volleyball are pre-configured. The `competition_id` follows the pattern `nevobo-<league>-<gender>[-<pool>]`:

- **Eredivisie** (Tier 1, 8 teams): `nevobo-eredivisie-heren`, `nevobo-eredivisie-dames`
- **Topdivisie** (Tier 2, 10 teams/pool): `nevobo-topdivisie-heren-a`, `nevobo-topdivisie-heren-b`, `nevobo-topdivisie-dames-a`, `nevobo-topdivisie-dames-b`
- **Superdivisie** (Tier 3, 10 teams): `nevobo-superdivisie-heren`, `nevobo-superdivisie-dames`

For lower divisions (1e/2e/3e Divisie, regional, youth, beach — 6,400+ poules), use `get_poules` to discover them.

See `references/competition-ids.md` for the full reference with team counts and the Dutch volleyball pyramid.

## Commands

| Command | Description |
|---|---|
| `get_competitions` | List all available competitions and leagues |
| `get_standings` | League table (rank, team, matches, points) |
| `get_schedule` | Upcoming matches (teams, venue, date) |
| `get_results` | Match results (score, set-by-set scores) |
| `get_clubs` | List volleyball clubs (name, city, province) |
| `get_club_schedule` | Club's upcoming matches across all teams |
| `get_club_results` | Club's results across all teams |
| `get_poules` | Browse Nevobo poules (for lower divisions discovery) |
| `get_tournaments` | Tournament calendar |
| `get_news` | Federation news |

See `references/api-reference.md` for full parameter lists and return shapes.

## Examples

Example 1: Eredivisie standings
User says: "What are the current Dutch volleyball standings?"
Actions:
1. Call `get_standings(competition_id="nevobo-eredivisie-heren")` for men
2. Call `get_standings(competition_id="nevobo-eredivisie-dames")` for women
Result: League tables with rank, team name, matches played, and points

Example 2: Recent match results
User says: "Show me recent Eredivisie volleyball results"
Actions:
1. Call `get_results(competition_id="nevobo-eredivisie-heren")`
Result: Match results with home/away teams, match score (e.g. "3-1"), and set scores (e.g. ["25-21", "25-18", "21-25", "25-20"])

Example 3: Club schedule
User says: "What matches does LSV have coming up?"
Actions:
1. Call `get_clubs(limit=10)` and find LSV's organisatiecode (CKL5C67)
2. Call `get_club_schedule(club_id="CKL5C67")`
Result: Upcoming matches for all of LSV's teams with venues and dates

Example 4: Second tier standings
User says: "Show me the Topdivisie standings"
Actions:
1. Call `get_standings(competition_id="nevobo-topdivisie-heren-a")` for men pool A
2. Call `get_standings(competition_id="nevobo-topdivisie-heren-b")` for men pool B
Result: Two pool tables with 10 teams each

Example 5: Discover lower divisions
User says: "What divisions are available in Dutch volleyball?"
Actions:
1. Call `get_poules(regio="nationale-competitie", limit=20)`
Result: List of national-level poules including 1e/2e/3e Divisie with their abbreviations and descriptions

## Commands that DO NOT exist — never call these

- ~~`get_scoreboard`~~ — does not exist. Use `get_results` for recent match results.
- ~~`get_rankings`~~ — does not exist. Volleyball uses `get_standings` for league tables.
- ~~`get_team_roster`~~ — does not exist. Use `get_clubs` for club information.
- ~~`get_player_info`~~ — does not exist. Player-level data is not available via this API.

If a command is not listed in the Commands table above, it does not exist.

## Error Handling

When a command fails, **do not surface raw errors to the user**. Instead:
1. Catch silently and try alternatives
2. If a club name is given instead of ID, use `get_clubs` to find the `organisatiecode` first
3. If a competition_id returns no data, use `get_competitions` to verify available leagues
4. Only report failure with a clean message after exhausting alternatives

## Troubleshooting

Error: `sports-skills` command not found
Cause: Package not installed
Solution: Run `pip install sports-skills`. If not on PyPI, install from GitHub: `pip install git+https://github.com/machina-sports/sports-skills.git`

Error: Standings returns empty list
Cause: The competition's regular season phase may have ended, or the season hasn't started yet
Solution: Use `get_results` to check recent results, or `get_poules` to discover current active poule paths

Error: Schedule returns 0 matches
Cause: The competition phase has completed and no more matches are scheduled for that poule
Solution: This is expected between season phases. Check other leagues (Topdivisie/Superdivisie may still be active)

Error: Club schedule/results returns error
Cause: The club_id may be incorrect
Solution: Use `get_clubs` to find valid club IDs (the `organisatiecode` field, e.g. "CKL5C67")

Error: Connection errors or timeouts
Cause: The Nevobo API may be temporarily unavailable
Solution: Wait a moment and retry. The API is public and unauthenticated but may have brief outages
