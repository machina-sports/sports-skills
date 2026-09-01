---
name: nba-data
description: |
  NBA data via ESPN public endpoints, the NBA live CDN, and NBA Stats (stats.nba.com) — scores, standings, rosters, schedules, game summaries, play-by-play, injuries, futures, depth charts, leaders, and news, plus an analytics backend: advanced ratings, per-shot court coordinates, career splits, and history to 1946. Zero config, no API keys.

  Use when: user asks about NBA scores, standings, team rosters, schedules, game stats, box scores, play-by-play, injuries, transactions, betting futures, depth charts, team/player statistics, NBA news, shot charts, advanced ratings/pace, career stats, or historical NBA seasons.
  Don't use when: user asks about WNBA (use wnba-data), college basketball (use cbb-data), or other sports.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# NBA Data

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
sports-skills nba get_scoreboard
sports-skills nba get_standings --season=2025
sports-skills nba get_teams
```

## CRITICAL: Before Any Query

CRITICAL: Before calling any data endpoint, verify:
- Season year is derived from the system prompt's `currentDate` — never hardcoded.
- If only a team name is provided, call `get_teams` to resolve the team ID before using team-specific commands.

## Choosing the Season

Derive the current year from the system prompt's date (e.g., `currentDate: 2026-02-18` → current year is 2026).

- **If the user specifies a season**, use it as-is.
- **If the user says "current", "this season", or doesn't specify**: The NBA season runs October–June. If the current month is October–December, the active season year matches the current year. If January–June, the active season started the previous calendar year (use that year as the season).

## Commands

| Command | Description |
|---|---|
| `get_scoreboard` | Live/recent NBA scores |
| `get_standings` | Standings by conference |
| `get_teams` | All 30 NBA teams |
| `get_team_roster` | Full roster for a team |
| `get_team_schedule` | Schedule for a specific team |
| `get_game_summary` | Detailed box score and scoring plays |
| `get_leaders` | NBA statistical leaders |
| `get_news` | NBA news articles |
| `get_play_by_play` | Full play-by-play for a game |
| `get_win_probability` | Win probability chart data |
| `get_schedule` | Schedule for a specific date or season |
| `get_injuries` | Injury reports across all teams |
| `get_transactions` | Recent transactions |
| `get_futures` | Futures/odds markets |
| `get_depth_chart` | Depth chart for a team |
| `get_team_stats` | Team statistical profile |
| `get_player_stats` | Player statistical profile |
| `find_nba_player` | Search the NBA Stats player registry (all eras) |
| `get_nbastats_game_log` | League game log via NBA Stats — history to 1946, carries NBA game ids |
| `get_nbastats_player_career` | Career stats season by season via NBA Stats |
| `get_nbastats_team_stats` | League team stats via NBA Stats — advanced ratings, pace, four factors |
| `get_nbastats_shot_chart` | Per-shot court coordinates via NBA Stats |
| `get_nbastats_play_by_play` | Play-by-play with coordinates for past seasons via NBA Stats |
| `get_nbastats_advanced_boxscore` | Advanced box score (ratings, usage) via NBA Stats |
| `get_live_scoreboard` | Real-time scores. Primary cdn.nba.com, fallback ESPN |
| `get_live_boxscore` | Real-time box score. Primary cdn.nba.com, fallback ESPN |
| `get_live_playbyplay` | Real-time play-by-play, most recent plays first |
| `get_player_live_stats` | Real-time stats for one player in today's games |

See `references/api-reference.md` for full parameter lists and return shapes.

## Using ESPN and NBA Stats Together

The `get_nbastats_*` commands read stats.nba.com — the analytics layer (advanced
ratings, shot coordinates, deep history) that ESPN's endpoints do not carry. The
two sources use unrelated id systems:

- **Game ids.** NBA Stats uses 10-digit ids (`"0022400061"`); ESPN uses event ids
  (`"401704627"`). There is no shared column — join on the game date plus the two
  team abbreviations.
- **Team abbreviations.** Six teams are spelled differently: ESPN `GS`/`NO`/`NY`/
  `SA`/`UTAH`/`WSH` vs NBA `GSW`/`NOP`/`NYK`/`SAS`/`UTA`/`WAS`. Every
  `get_nbastats_*` team filter accepts either spelling, and result rows carry both
  (`team_abbreviation` and `team_abbreviation_espn`).
- **Player ids.** NBA person ids (`"203999"`) and ESPN athlete ids are unrelated.
  Resolve names with `find_nba_player`; ASCII spellings match accented names
  ("jokic" finds "Nikola Jokić").
- **Seasons.** Pass the starting year (`season=2024` means 2024-25). The NBA form
  (`"2024-25"`) is also accepted.

stats.nba.com throttles by client and volume: heavy bursts (and many
datacenter/cloud IPs) get silently tarpitted rather than refused. The commands
fail fast with an explanatory error when that happens — wait before retrying;
do not hammer. Responses are cached, and the ESPN-backed and `get_live_*`
commands are unaffected.

## Examples

Example 1: Today's scores
User says: "What are today's NBA scores?"
Actions:
1. Call `get_scoreboard()`
Result: All live and recent NBA games with scores and status

Example 2: Conference standings
User says: "Show me the Western Conference standings"
Actions:
1. Derive season year from `currentDate`
2. Call `get_standings(season=<derived_year>)`
3. Filter results for Western Conference
Result: Western Conference standings table with W-L, PCT, GB per team

Example 3: Team roster
User says: "Who's on the Lakers roster?"
Actions:
1. Call `get_team_roster(team_id="13")`
Result: Full Lakers roster with name, position, jersey number, height, weight

Example 4: Game box score
User says: "Show me the full box score for last night's Celtics game"
Actions:
1. Call `get_scoreboard(date="<yesterday>")` to find the event_id
2. Call `get_game_summary(event_id=<id>)` for full box score
Result: Complete box score with per-player stats and scoring plays

Example 5: Injury report
User says: "Who's injured on the Lakers?"
Actions:
1. Call `get_injuries()`
2. Filter results for Los Angeles Lakers (team_id=13)
Result: Lakers injury list with player name, position, status, and injury type

Example 6: Player statistics
User says: "Show me LeBron's stats this season"
Actions:
1. Derive season year from `currentDate`
2. Call `get_player_stats(player_id="1966", season_year=<derived_year>)`
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
Solution: Call `get_teams` to get the current list of all 30 NBA teams with their IDs

Error: No data returned for a future game
Cause: ESPN only returns data for completed or in-progress games
Solution: Use `get_schedule` to see upcoming game details; `get_scoreboard` only covers active/recent games

Error: Offseason — scoreboard returns 0 events
Cause: No games scheduled during the offseason (July–September)
Solution: Use `get_standings` or `get_news` instead; use `get_schedule` to find when the season resumes
