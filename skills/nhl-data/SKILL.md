---
name: nhl-data
description: |
  NHL data via ESPN public endpoints — scores, standings, rosters, schedules, game summaries, play-by-play, injuries, transactions, futures, team/player stats, leaders, and news. Zero config, no API keys.

  Use when: user asks about NHL scores, standings, team rosters, schedules, game stats, box scores, play-by-play, injuries, transactions, betting futures, team/player statistics, or NHL news.
  Don't use when: user asks about other hockey leagues (AHL, KHL, college hockey). For other sports use: nfl-data (NFL), nba-data (NBA), wnba-data (WNBA), mlb-data (MLB), football-data (soccer), tennis-data (tennis), golf-data (golf), cricket-data (cricket), cfb-data (college football), cbb-data (college basketball), fastf1 (F1). For betting odds use polymarket or kalshi. For news use sports-news.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# NHL Data

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
sports-skills nhl get_scoreboard
sports-skills nhl get_standings --season=2025
sports-skills nhl get_teams
```

## CRITICAL: Before Any Query

CRITICAL: Before calling any data endpoint, verify:
- Season year is derived from the system prompt's `currentDate` — never hardcoded.
- If only a team name is provided, call `get_teams` to resolve the team ID before using team-specific commands.

## Choosing the Season

Derive the current year from the system prompt's date (e.g., `currentDate: 2026-02-18` → current year is 2026).

- **If the user specifies a season**, use it as-is.
- **If the user says "current", "this season", or doesn't specify**: The NHL season runs October–June. If the current month is October–December, the active season year matches the current year. If January–June, the active season started the previous calendar year (use that year as the season).
- **Example:** Current date is February 2026 → active season started October 2025 → use season `2025`.

## Commands

| Command | Description |
|---|---|
| `get_scoreboard` | Live/recent NHL scores |
| `get_standings` | Standings by conference and division |
| `get_teams` | All NHL teams |
| `get_team_roster` | Full roster for a team |
| `get_team_schedule` | Schedule for a specific team |
| `get_game_summary` | Detailed box score and scoring plays |
| `get_leaders` | NHL statistical leaders |
| `get_news` | NHL news articles |
| `get_play_by_play` | Full play-by-play for a game |
| `get_schedule` | Schedule for a specific date or season |
| `get_injuries` | Injury reports across all teams |
| `get_transactions` | Recent transactions |
| `get_futures` | Futures/odds markets |
| `get_team_stats` | Team statistical profile |
| `get_player_stats` | Player statistical profile |

See `references/api-reference.md` for full parameter lists and return shapes.

## Examples

Example 1: Today's scores
User says: "What are today's NHL scores?"
Actions:
1. Call `get_scoreboard()`
Result: All live and recent NHL games with scores and status

Example 2: Conference standings
User says: "Show me the Eastern Conference standings"
Actions:
1. Derive season year from `currentDate`
2. Call `get_standings(season=<derived_year>)`
3. Filter results for Eastern Conference
Result: Eastern Conference standings with W-L-OTL, points, regulation wins

Example 3: Team roster
User says: "Who's on the Maple Leafs roster?"
Actions:
1. Call `get_team_roster(team_id="21")`
Result: Full Maple Leafs roster with name, position, jersey number, shoots/catches

Example 4: Game box score
User says: "Show me the full box score for last night's Bruins game"
Actions:
1. Call `get_scoreboard(date="<yesterday>")` to find the event_id
2. Call `get_game_summary(event_id=<id>)` for full box score
Result: Complete box score with per-player stats and scoring plays

Example 5: Stanley Cup odds
User says: "What are the Stanley Cup odds?"
Actions:
1. Call `get_futures(limit=10)`
Result: Top Stanley Cup contenders with odds values

Example 6: Player statistics
User says: "Show me Connor McDavid's stats"
Actions:
1. Derive season year from `currentDate`
2. Call `get_player_stats(player_id="3895074", season_year=<derived_year>)`
Result: Season stats by category with value, rank, and per-game averages

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
Solution: Call `get_teams` to get the current list of all NHL teams with their IDs (expansion teams like the Seattle Kraken and Utah Mammoth have non-sequential IDs)

Error: No data returned for a future game
Cause: ESPN only returns data for completed or in-progress games
Solution: Use `get_schedule` to see upcoming game details; `get_scoreboard` only covers active/recent games

Error: Offseason — scoreboard returns 0 events
Cause: No games scheduled during the offseason (July–September)
Solution: Use `get_standings` or `get_news` instead; use `get_schedule` to find when the season resumes
