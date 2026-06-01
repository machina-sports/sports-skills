---
name: cfb-data
description: |
  College Football (CFB) data via ESPN public endpoints — scores, standings, rosters, schedules, game summaries, play-by-play, rankings, injuries, futures, team/player stats, and news for NCAA Division I FBS. Zero config, no API keys.

  Use when: user asks about college football scores, standings, rankings, team rosters, schedules, game results, play-by-play, injuries, betting futures, team/player statistics, or CFB news.
  Don't use when: user asks about NFL (use nfl-data), college basketball (use cbb-data), or non-sports topics.
license: MIT
# `metadata` is the only free-form field the VS Code agent-skills
# schema accepts; we nest the Machina manifest under `metadata.machina`
# so the picker (Machina Factory `/c`) and Truth Point can read it
# without breaking any other consumer of this SKILL.md. All
# `metadata.machina.*` fields are optional — older skills without
# them still parse and just render fewer chips in the picker.
metadata:
  author: machina-sports
  version: "0.1.0"
  machina:
    categories: [sports-data, college-football]
    pricing_tier: free
    # Connector slugs this skill needs at runtime. Empty = uses only
    # public/free APIs (ESPN here).
    integrations: []
    # Credential vault keys the customer must have set before invoking.
    # Empty = no auth required.
    vault_keys: []
    # Surface area for the picker + the agent's pre-flight. Keep
    # summaries under ~80 chars so the picker's expand panel stays
    # compact.
    commands:
      - name: get_scoreboard
        summary: Live or recent CFB scores. Filter by date, week, conference, or limit.
        returns: events[]
      - name: get_standings
        summary: Standings by conference. Use the `group` param for SEC, ACC, etc.
        returns: conferences[]
      - name: get_teams
        summary: All 750+ FBS teams with id, name, abbreviation, logo, location.
        returns: teams[]
      - name: get_team_roster
        summary: Full roster for a team — players, positions, jerseys, height/weight.
        returns: athletes[]
      - name: get_team_schedule
        summary: Season schedule for one team — opponent, date, score (if played), venue.
        returns: events[]
      - name: get_game_summary
        summary: Detailed box score, scoring plays, and leaders for a single game.
        returns: "{ game_info, competitors, boxscore, scoring_plays, leaders }"
      - name: get_rankings
        summary: AP Top 25, Coaches Poll, and CFP rankings — rank, previous, record, votes.
        returns: polls[]
      - name: get_news
        summary: CFB news articles, optionally filtered by team.
        returns: articles[]
      - name: get_play_by_play
        summary: Full drive + play-by-play breakdown for a game.
        returns: drives[]
      - name: get_schedule
        summary: Season schedule by week — filter by conference group.
        returns: events[]
      - name: get_injuries
        summary: Injury reports across every team.
        returns: teams[]
      - name: get_futures
        summary: Futures markets (National Championship, Heisman, etc.).
        returns: futures[]
      - name: get_team_stats
        summary: Team statistical profile by category — value, rank, per-game.
        returns: stats[]
      - name: get_player_stats
        summary: Player statistical profile.
        returns: stats[]
    # The agent in the customer build sandbox can call `machina sports
    # cfb <command> --json` directly to capture a live sample output —
    # we don't ship static fixtures here so the public repo stays
    # data-free. List the runtime invocation pattern explicitly so
    # tooling / pre-flight knows how to fetch a real shape on demand.
    runtime:
      cli: "machina sports cfb"
      sample_command: "machina sports cfb get_scoreboard"
    references:
      api: references/api-reference.md
      conferences: references/conference-ids.md
      teams: references/team-ids.md
---

# College Football Data (CFB)

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
sports-skills cfb get_scoreboard
sports-skills cfb get_rankings
sports-skills cfb get_standings --group=8
```

## CRITICAL: Before Any Query

CRITICAL: Before calling any data endpoint, verify:
- Season year is derived from the system prompt's `currentDate` — never hardcoded.
- For standings, the `group` parameter is set to the correct conference ID (see `references/api-reference.md`).
- If only a team name is provided, use `get_teams` to resolve the team ID.

## Choosing the Season

Derive the current year from the system prompt's date (e.g., `currentDate: 2026-02-28` → current year is 2026).

- **If the user specifies a season**, use it as-is.
- **If the user says "current", "this season", or doesn't specify**: The CFB season runs August–January. If the current month is February–July (offseason), use `season = current_year - 1`. From August onward, use the current year.

## Important: College vs. Pro Differences

- **Standings are per-conference** — use the `group` parameter to filter
- **Rankings replace leaders** — college uses AP Top 25, Coaches Poll, and CFP rankings
- **Ranked teams** have a `rank` field (null = unranked) on scoreboard competitors
- **Week-based schedule** — like NFL, college football uses week numbers

## Commands

| Command | Description |
|---|---|
| `get_scoreboard` | Live/recent college football scores |
| `get_standings` | Standings by conference (use `group` parameter) |
| `get_teams` | All 750+ FBS college football teams |
| `get_team_roster` | Full roster for a team |
| `get_team_schedule` | Schedule for a specific team |
| `get_game_summary` | Detailed box score and scoring plays |
| `get_rankings` | AP Top 25, Coaches Poll, CFP rankings |
| `get_news` | College football news |
| `get_play_by_play` | Full play-by-play for a game |
| `get_schedule` | Season schedule by week |
| `get_injuries` | Injury reports across all teams |
| `get_futures` | Futures/odds markets (National Championship, Heisman, etc.) |
| `get_team_stats` | Team statistical profile |
| `get_player_stats` | Player statistical profile |

See `references/api-reference.md` for full parameter lists and return shapes.

## Examples

Example 1: Current rankings
User says: "What are the college football rankings?"
Actions:
1. Call `get_rankings()`
Result: AP Top 25, Coaches Poll, and CFP rankings with rank, previous rank, record

Example 2: Conference standings
User says: "Show me SEC football standings"
Actions:
1. Derive season year from `currentDate`
2. Call `get_standings(group=8, season=<derived_year>)` (group 8 = SEC)
Result: SEC standings with W-L records per team

Example 3: Team schedule
User says: "What's Alabama's schedule this season?"
Actions:
1. Derive season year from `currentDate`
2. Call `get_team_schedule(team_id="333", season=<derived_year>)`
Result: Alabama's full season schedule with opponent, date, score (if played)

Example 4: Weekly scores
User says: "Show me this week's college football scores"
Actions:
1. Call `get_scoreboard()`
Result: All live and recent CFB games with scores and ranked status

Example 5: Heisman favorites
User says: "Who's the Heisman favorite?"
Actions:
1. Call `get_futures(limit=10)`
Result: Top Heisman Trophy candidates with odds values

Example 6: Team statistics
User says: "Show me Alabama's team stats"
Actions:
1. Derive season year from `currentDate`
2. Call `get_team_stats(team_id="333", season_year=<derived_year>)`
Result: Alabama's season stats by category with value, rank, and per-game averages

## Commands that DO NOT exist — never call these

- ~~`get_odds`~~ / ~~`get_betting_odds`~~ — not available. For prediction market odds, use the polymarket or kalshi skill.
- ~~`search_teams`~~ — does not exist. Use `get_teams` instead.
- ~~`get_box_score`~~ — does not exist. Use `get_game_summary` instead.
- ~~`get_player_ratings`~~ — does not exist. Use `get_player_stats` instead.
- ~~`get_bcs_rankings`~~ / ~~`get_playoff_rankings`~~ — does not exist. Use `get_rankings` instead.

If a command is not listed in the Commands table above, it does not exist.

## Error Handling

When a command fails, **do not surface raw errors to the user**. Instead:
1. If no events found for a date, check if it's in the off-season (CFB runs August–January)
2. If standings are empty without a group filter, try with a specific conference group
3. Only report failure with a clean message after exhausting alternatives

## Troubleshooting

Error: `sports-skills` command not found
Cause: Package not installed
Solution: Run `pip install sports-skills`

Error: No games found
Cause: CFB is seasonal (August–January); off-season scoreboard will be empty
Solution: Use `get_rankings` or `get_news` year-round; use `get_schedule` to find when the season starts

Error: Too many teams returned
Cause: `get_teams` returns 750+ FBS teams
Solution: Help users narrow down by suggesting specific team IDs from `references/api-reference.md`, or use ESPN URLs to look up IDs

Error: Rankings empty in off-season
Cause: Rankings are only published during the season and early off-season
Solution: Use `get_news` in the offseason; rankings resume in August
