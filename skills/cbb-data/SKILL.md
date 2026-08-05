---
name: cbb-data
description: |
  College Basketball (CBB) data via ESPN public endpoints — scores, standings, rosters, schedules, game summaries, play-by-play, win probability, rankings, futures, team/player stats, and news for NCAA Division I men's basketball. Zero config, no API keys.

  Use when: user asks about college basketball scores, March Madness, NCAA tournament, standings, rankings, team rosters, schedules, play-by-play, betting futures, team/player statistics, or CBB news.
  Don't use when: user asks about NBA/WNBA (use nba-data/wnba-data), college football (use cfb-data), or non-sports topics.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# College Basketball Data (CBB)

Before writing queries, consult `references/api-reference.md` for endpoints, conference IDs, team IDs, and data shapes.

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
sports-skills cbb get_scoreboard
sports-skills cbb get_rankings
sports-skills cbb get_standings --group=23
```

## CRITICAL: Before Any Query

CRITICAL: Before calling any data endpoint, verify:
- Season year is derived from the system prompt's `currentDate` — never hardcoded.
- For standings, the `group` parameter is set to the correct conference ID (see `references/api-reference.md`).
- If only a team name is provided, use `get_teams` to resolve the team ID.

## Choosing the Season

Derive the current year from the system prompt's date (e.g., `currentDate: 2026-02-28` → current year is 2026).

- **If the user specifies a season**, use it as-is.
- **If the user says "current", "this season", or doesn't specify**: The CBB season runs November–April. If the current month is November or December, use `season = current_year + 1`. If January–April, use `season = current_year`. If May–October (offseason), use `season = current_year` (most recently completed season).

## Important: College vs. Pro Differences

- **Standings are per-conference** — use the `group` parameter to filter
- **Rankings replace leaders** — college uses AP Top 25 and Coaches Poll
- **Ranked teams** have a `rank` field (null = unranked) on scoreboard competitors
- **360+ D1 teams** — many games per day during the season (50+ during conference play)
- **March Madness** — NCAA Tournament runs in March/April with 68 teams

## Commands

| Command | Description |
|---|---|
| `get_scoreboard` | Live/recent college basketball scores |
| `get_standings` | Standings by conference (use `group` parameter) |
| `get_teams` | All 360+ D1 men's basketball teams |
| `get_team_roster` | Full roster for a team |
| `get_team_schedule` | Schedule for a specific team |
| `get_game_summary` | Detailed box score and player stats |
| `get_rankings` | AP Top 25 and Coaches Poll rankings |
| `get_news` | College basketball news |
| `get_play_by_play` | Full play-by-play for a game |
| `get_win_probability` | Win probability chart data |
| `get_schedule` | Schedule for a date or season |
| `get_futures` | Futures/odds markets (National Championship, etc.) |
| `get_team_stats` | Team statistical profile |
| `get_player_stats` | Player statistical profile |
| `get_ncaa_scoreboard` | Official NCAA scoreboard — D1, D2, and D3 |
| `get_ncaa_schedule` | Which dates have games (official index) |
| `get_ncaa_game` | Official NCAA game information |
| `get_ncaa_boxscore` | Official NCAA box score |
| `get_ncaa_play_by_play` | Official play-by-play |
| `get_ncaa_bracket` | March Madness bracket with live scores |
| `get_ncaa_schools` | NCAA schools index (all divisions) |

See `references/api-reference.md` for full parameter lists and return shapes.

## Official NCAA Backend

The `get_ncaa_*` commands read the NCAA's own endpoints (data.ncaa.com +
sdataprod.ncaa.com) — coverage ESPN does not carry:

- **D2 and D3 scoreboards** via `division="d2"`/`"d3"` — ESPN's college
  coverage is D1-centric.
- **The official March Madness bracket** with live scores: `get_ncaa_bracket`.
- **Official game detail**: `get_ncaa_game`, `get_ncaa_boxscore`,
  `get_ncaa_play_by_play`.
- **The schools index** (~1,200 schools, all divisions): `get_ncaa_schools`.

NCAA game ids (from `get_ncaa_scoreboard`) and ESPN event ids share nothing —
join on game date plus team names. Game-detail and bracket commands ride NCAA's
GraphQL persisted queries, whose hashes rotate when ncaa.com redeploys; when
that happens those commands say so explicitly while the scoreboard/schedule
commands keep working.

## Examples

Example 1: Current rankings
User says: "What are the college basketball rankings?"
Actions:
1. Call `get_rankings()`
Result: AP Top 25 and Coaches Poll with rank, previous rank, record, and points

Example 2: Conference standings
User says: "Show me SEC basketball standings"
Actions:
1. Derive season year from `currentDate`
2. Call `get_standings(group=23, season=<derived_year>)` (group 23 = SEC)
Result: SEC standings with W-L records per team

Example 3: Today's scores
User says: "What are today's college basketball scores?"
Actions:
1. Call `get_scoreboard()`
Result: All live and recent CBB games with scores and ranked status

Example 4: Team roster
User says: "Show me Duke's roster"
Actions:
1. Call `get_team_roster(team_id="150")`
Result: Full Duke roster with name, position, jersey number

Example 5: March Madness futures
User says: "Who's favored to win March Madness?"
Actions:
1. Call `get_futures(limit=10)`
Result: Top National Championship contenders with odds values

Example 6: Team statistics
User says: "Show me Duke's team stats"
Actions:
1. Derive season year from `currentDate`
2. Call `get_team_stats(team_id="150", season_year=<derived_year>)`
Result: Duke's season stats by category with value, rank, and per-game averages

## Commands that DO NOT exist — never call these

- ~~`get_odds`~~ / ~~`get_betting_odds`~~ — not available. For prediction market odds, use the polymarket or kalshi skill.
- ~~`search_teams`~~ — does not exist. Use `get_teams` instead.
- ~~`get_box_score`~~ — does not exist. Use `get_game_summary` instead.
- ~~`get_player_ratings`~~ — does not exist. Use `get_player_stats` instead.
- ~~`get_ap_poll`~~ — does not exist. Use `get_rankings` instead.

If a command is not listed in the Commands table above, it does not exist.

## Error Handling

When a command fails, **do not surface raw errors to the user**. Instead:
1. If no events found, check if it's the off-season (CBB runs November–April)
2. If standings are empty without a group filter, try a specific conference
3. During March Madness, the scoreboard will have tournament games
4. Only report failure with a clean message after exhausting alternatives

## Troubleshooting

Error: `sports-skills` command not found
Cause: Package not installed
Solution: Run `pip install sports-skills`

Error: No games found on scoreboard
Cause: CBB is seasonal (November–April); off-season scoreboard will be empty
Solution: Use `get_rankings` or `get_news` year-round; check `get_schedule` for when the season resumes

Error: Too many games returned — hard to filter
Cause: During the season, 50+ games per day are scheduled
Solution: Use `--group` to filter by conference, or `--limit` to cap results

Error: Rankings empty
Cause: Rankings are published weekly during the season (November–March) only
Solution: Use `get_news` in the offseason; rankings resume in November
