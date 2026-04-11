---
name: nfl-data
description: |
  NFL data via ESPN public endpoints plus an nflverse backend for schedules, weekly rosters, play-by-play, and normalized player/team stat tables. Zero config, no API keys.

  Use when: user asks about NFL scores, standings, team rosters, schedules, game stats, box scores, play-by-play, injuries, transactions, betting futures, depth charts, team/player statistics, or NFL news.
  Don't use when: user asks about football/soccer (use football-data), college football (use cfb-data), or other sports.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# NFL Data

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

For nflverse-backed commands (`get_nflverse_*`), install the NFL extra:
```bash
pip install sports-skills[nfl]
```
This installs `nfl-data-py` (or use `nflreadpy` if preferred). Parquet support (`pyarrow`) is also needed for most nflverse data beyond schedules.

## Quick Start

Prefer the CLI — it avoids Python import path issues:
```bash
sports-skills nfl get_scoreboard
sports-skills nfl get_standings --season=2025
sports-skills nfl get_teams
```

Python SDK (alternative):
```python
from sports_skills import nfl

scores = nfl.get_scoreboard({})
standings = nfl.get_standings({"params": {"season": "2025"}})
```

## CRITICAL: Before Any Query

CRITICAL: Before calling any data endpoint, verify:
- Season year is derived from the system prompt's `currentDate` — never hardcoded.
- If only a team name is provided, call `get_teams` to resolve the team ID before using team-specific commands.

## Choosing the Season

Derive the current year from the system prompt's date (e.g., `currentDate: 2026-02-16` → current year is 2026).

- **If the user specifies a season**, use it as-is.
- **If the user says "current", "this season", or doesn't specify**: The NFL season runs September–February. If the current month is March–August, use `season = current_year` (upcoming season). If September–February, the active season started in the previous calendar year if you're in Jan/Feb, otherwise current year.

## Commands

| Command | Description |
|---|---|
| `get_scoreboard` | Live/recent NFL scores |
| `get_standings` | Standings by conference and division |
| `get_teams` | All 32 NFL teams |
| `get_team_roster` | Full roster for a team |
| `get_team_schedule` | Schedule for a specific team |
| `get_game_summary` | Detailed box score and scoring plays |
| `get_leaders` | NFL statistical leaders |
| `get_news` | NFL news articles |
| `get_play_by_play` | Full play-by-play for a game |
| `get_win_probability` | Win probability chart data |
| `get_schedule` | Season schedule by week |
| `get_injuries` | Injury reports across all teams |
| `get_transactions` | Recent transactions |
| `get_futures` | Futures/odds markets |
| `get_depth_chart` | Depth chart for a team |
| `get_team_stats` | Team statistical profile |
| `get_player_stats` | Player statistical profile |
| `get_nflverse_schedule` | nflverse-backed schedules/results table |
| `get_nflverse_weekly_rosters` | nflverse-backed weekly rosters |
| `get_nflverse_player_stats` | nflverse-backed normalized player stat rows |
| `get_nflverse_team_stats` | nflverse-backed normalized team stat rows |
| `get_nflverse_play_by_play` | nflverse-backed play-by-play rows |

See `references/api-reference.md` for full parameter lists and return shapes.

## Examples

Example 1: Today's scores
User says: "What are today's NFL scores?"
Actions:
1. Call `get_scoreboard()`
Result: All live and recent NFL games with scores and status

Example 2: Conference standings
User says: "Show me the AFC standings"
Actions:
1. Derive season year from `currentDate`
2. Call `get_standings(season=<derived_year>)`
3. Filter results for AFC conference
Result: AFC standings table with W-L-T, PCT, PF, PA per team

Example 3: Team roster
User says: "Who's on the Chiefs roster?"
Actions:
1. Call `get_team_roster(team_id="12")`
Result: Full Chiefs roster with name, position, jersey number, height, weight

Example 4: Super Bowl box score
User says: "How did the Super Bowl go?"
Actions:
1. Call `get_schedule(week=23)` to find the Super Bowl event_id
2. Call `get_game_summary(event_id=<id>)` for full box score
Result: Complete box score with passing/rushing/receiving stats and scoring plays

Example 5: Injury report
User says: "Who's injured on the Chiefs?"
Actions:
1. Call `get_injuries()`
2. Filter results for Kansas City Chiefs (team_id=12)
Result: Chiefs injury list with player name, position, status, and injury type

Example 6: Player statistics
User says: "Show me Patrick Mahomes' stats this season"
Actions:
1. Derive season year from `currentDate`
2. Call `get_player_stats(player_id="3139477", season_year=<derived_year>)`
Result: Season stats by category with value, rank, and per-game averages

Example 7: nflverse weekly rosters
User says: "Give me the Week 1 Chiefs roster from the data table backend"
Actions:
1. Derive season year from `currentDate`
2. Call `get_nflverse_weekly_rosters(season=<derived_year>, week=1, team="KC")`
Result: Weekly roster rows normalized for team, player, position, jersey, and status

Example 8: nflverse play-by-play
User says: "Pull Bills Week 3 play-by-play"
Actions:
1. Derive season year from `currentDate`
2. Call `get_nflverse_play_by_play(season=<derived_year>, week=3, team="BUF")`
Result: Play rows with game_id, down/distance, description, EPA, WP/WPA, and score state

## Commands that DO NOT exist — never call these

- ~~`get_odds`~~ / ~~`get_betting_odds`~~ — not available. For prediction market odds, use the polymarket or kalshi skill.
- ~~`search_teams`~~ — does not exist. Use `get_teams` instead.
- ~~`get_box_score`~~ — does not exist. Use `get_game_summary` instead.
- ~~`get_player_ratings`~~ — does not exist. Use `get_player_stats` instead.

If a command is not listed in the Commands table above, it does not exist.

## Error Handling

When a command fails, **do not surface raw errors to the user**. Instead:
1. Catch silently and try alternatives
2. If team name given instead of ID, use `get_teams` to find the ID first
3. Only report failure with a clean message after exhausting alternatives

## Troubleshooting

Error: `sports-skills` command not found
Cause: Package not installed
Solution: Run `pip install sports-skills`. If not on PyPI, install from GitHub: `pip install git+https://github.com/machina-sports/sports-skills.git`

Error: nflverse backend unavailable
Cause: Optional NFL backend extra not installed
Solution: Install `sports-skills[nfl]` so the nflverse provider (`nflreadpy` or compatibility fallback) is available

Error: Team not found by ID
Cause: Wrong or outdated ESPN team ID used
Solution: Call `get_teams` to get the current list of all 32 NFL teams with their IDs

Error: No data returned for a future game
Cause: ESPN only returns data for completed or in-progress games
Solution: Use `get_schedule` to see upcoming game details; `get_scoreboard` only covers active/recent games

Error: Postseason week number returns no results
Cause: Postseason uses unified week numbers (19-23) that differ from regular season
Solution: Use week 19 for Wild Card, 20 for Divisional, 21 for Conference Championship, 23 for Super Bowl
