---
name: mlb-data
description: |
  MLB data via ESPN public endpoints — scores, standings, rosters, schedules, game summaries, play-by-play, win probability, injuries, transactions, depth charts, team/player stats, leaders, and news. Zero config, no API keys.

  Use when: user asks about MLB scores, standings, team rosters, schedules, game stats, box scores, play-by-play, injuries, transactions, depth charts, team/player statistics, or MLB news.
  Don't use when: user asks about minor league baseball, college baseball, or international baseball. For other sports use: nfl-data (NFL), nba-data (NBA), wnba-data (WNBA), nhl-data (NHL), football-data (soccer), tennis-data (tennis), golf-data (golf), cricket-data (cricket), cfb-data (college football), cbb-data (college basketball), fastf1 (F1). For betting odds use polymarket or kalshi. For news use sports-news.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# MLB Data

Before writing queries, consult `references/api-reference.md` for endpoints, ID conventions, and data shapes.

## Setup

Before first use, check if the CLI is available:
```bash
which sports-skills || pip install sports-skills
```
If `pip install` fails with a Python version error, the package requires Python 3.10+. Find a compatible Python:
```bash
python3 --version  # check version
# If < 3.10, try: python3.12 -m pip install sports-skills
# On macOS with Homebrew: /opt/homebrew/bin/python3.12 -m pip install sports-skills
```
No API keys required.

## Quick Start

Prefer the CLI — it avoids Python import path issues:
```bash
sports-skills mlb get_scoreboard
sports-skills mlb get_standings --season=2025
sports-skills mlb get_teams
```

## CRITICAL: Before Any Query

CRITICAL: Before calling any data endpoint, verify:
- Season year is derived from the system prompt's `currentDate` — never hardcoded.
- If only a team name is provided, call `get_teams` to resolve the team ID before using team-specific commands.

## Choosing the Season

Derive the active season from the system prompt's date — not just the calendar year.

- **If the user specifies a season**, use it as-is.
- **If the user says "current", "this season", or doesn't specify**: The MLB season runs late March/April through October. If the current month is January–March, the last completed season was the prior calendar year. From April onward, use the current calendar year.

## Commands

| Command | Description |
|---|---|
| `get_scoreboard` | Live/recent MLB scores |
| `get_standings` | Standings by league and division |
| `get_teams` | All 30 MLB teams |
| `get_team_roster` | Full roster for a team |
| `get_team_schedule` | Schedule for a specific team |
| `get_game_summary` | Detailed box score and scoring plays |
| `get_leaders` | MLB statistical leaders |
| `get_news` | MLB news articles |
| `get_play_by_play` | Full play-by-play for a game |
| `get_win_probability` | Win probability chart data |
| `get_schedule` | Schedule for a specific date or season |
| `get_injuries` | Injury reports across all teams |
| `get_transactions` | Recent transactions |
| `get_depth_chart` | Depth chart for a team |
| `get_team_stats` | Team statistical profile |
| `get_player_stats` | Player statistical profile |

See `references/api-reference.md` for full parameter lists and return shapes.

## Examples

Example 1: Today's scores
User says: "What are today's MLB scores?"
Actions:
1. Call `get_scoreboard()`
Result: All live and recent MLB games with scores by inning and status

Example 2: Division standings
User says: "Show me the AL East standings"
Actions:
1. Derive season year from `currentDate`
2. Call `get_standings(season=<derived_year>)`
3. Filter results for American League East
Result: AL East standings with W-L, PCT, GB, run differential

Example 3: Team roster
User says: "Who's on the Yankees roster?"
Actions:
1. Call `get_team_roster(team_id="10")`
Result: Full Yankees roster with name, position, bats/throws, height, weight

Example 4: Game box score
User says: "Show me the full box score for last night's Dodgers game"
Actions:
1. Call `get_scoreboard(date="<yesterday>")` to find the event_id
2. Call `get_game_summary(event_id=<id>)` for full box score
Result: Complete box score with batting/pitching stats per player

Example 5: Injury report
User says: "Who's on the IL for the Yankees?"
Actions:
1. Call `get_injuries()`
2. Filter results for New York Yankees (team_id=10)
Result: Yankees IL list with player name, position, IL type, and injury detail

Example 6: Player statistics
User says: "Show me Shohei Ohtani's stats"
Actions:
1. Derive season year from `currentDate`
2. Call `get_player_stats(player_id="39832", season_year=<derived_year>)`
Result: Season stats by category (batting, pitching) with value, rank, and per-game averages

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
Solution: Run `pip install sports-skills`

Error: Team not found by ID
Cause: Wrong or outdated ESPN team ID used
Solution: Call `get_teams` to get the current list of all 30 MLB teams with their IDs

Error: No data returned for a future game
Cause: ESPN only returns data for completed or in-progress games
Solution: Use `get_schedule` to see upcoming game details; `get_scoreboard` only covers active/recent games

Error: Offseason — scoreboard returns 0 events
Cause: No games scheduled during the offseason (November–March)
Solution: Use `get_standings` or `get_news` instead; MLB offseason transactions are available via `get_transactions`
