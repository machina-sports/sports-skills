---
name: tennis-data
description: |
  ATP and WTA tennis data via ESPN public endpoints — tournament scores, season calendars, player rankings, player profiles, and news. Zero config, no API keys.

  Use when: user asks about tennis scores, match results, tournament draws, ATP/WTA rankings, tennis player info, or tennis news.
  Don't use when: user asks about other sports — use football-data (soccer), nfl-data (NFL), nba-data (NBA), wnba-data (WNBA), nhl-data (NHL), mlb-data (MLB), golf-data (golf), cricket-data (cricket), cfb-data (college football), cbb-data (college basketball), or fastf1 (F1). For betting odds use polymarket or kalshi. For news use sports-news. Don't use for live point-by-point data — scores update after each set/match.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# Tennis Data (ATP + WTA)

Before writing queries, consult `references/api-reference.md` for endpoints, ID conventions, and data shapes.

## Quick Start

Prefer the CLI — it avoids Python import path issues:
```bash
sports-skills tennis get_scoreboard --tour=atp
sports-skills tennis get_rankings --tour=wta
sports-skills tennis get_calendar --tour=atp --year=2026
```

## CRITICAL: Before Any Query

CRITICAL: Before calling any data endpoint, verify:
- The `tour` parameter is specified (`atp` or `wta`) — there is no default.
- Year is derived from the system prompt's `currentDate` — never hardcoded.

## The `tour` Parameter

Most commands require `--tour=atp` or `--tour=wta`:
- **ATP**: Men's professional tennis tour
- **WTA**: Women's professional tennis tour

If the user doesn't specify, ask which tour or show both by calling the command twice.

## Commands

| Command | Description |
|---|---|
| `get_scoreboard` | Live/recent tournament scores for a tour |
| `get_rankings` | ATP or WTA player rankings |
| `get_calendar` | Full season tournament calendar |
| `get_player_info` | Individual tennis player profile |

See `references/api-reference.md` for full parameter lists and return shapes.

## Workflows

### Live Tournament Check
1. `get_scoreboard --tour=<atp|wta>`
2. Present current matches by round.
3. For player info, use `get_player_info --player_id=<id>`.

### Rankings Lookup
1. `get_rankings --tour=<atp|wta> --limit=20`
2. Present rankings with points and trend.

### Season Calendar
1. `get_calendar --tour=<atp|wta> --year=<year>`
2. Filter for specific tournament.

## Examples

Example 1: Live matches
User says: "What ATP matches are happening right now?"
Actions:
1. Call `get_scoreboard(tour="atp")`
Result: Current tournament matches organized by round with scores and status

Example 2: Women's rankings
User says: "Show me the WTA rankings"
Actions:
1. Call `get_rankings(tour="wta", limit=20)`
Result: Top 20 WTA players with rank, name, points, and trend

Example 3: Upcoming Grand Slam date
User says: "When is the French Open this year?"
Actions:
1. Derive year from `currentDate`
2. Call `get_calendar(tour="atp", year=<derived_year>)`
3. Search results for "Roland Garros" (the French Open's official name)
Result: French Open dates, location (Paris), and surface (clay)

## Commands that DO NOT exist — never call these

- ~~`get_matches`~~ — does not exist. Use `get_scoreboard` for current match scores.
- ~~`get_draw`~~ — does not exist. Tournament draw data is not available via this API.
- ~~`get_head_to_head`~~ — does not exist. Head-to-head records are not available via this API.
- ~~`get_standings`~~ — does not exist. Tennis uses `get_rankings`, not standings.

If a command is not listed in the Commands table above, it does not exist.

## Troubleshooting

Error: `get_scoreboard` returns no matches
Cause: Tennis tournaments run specific weeks; no tournament may be scheduled this week
Solution: Call `get_calendar(tour=...)` to find when the next event is scheduled

Error: Rankings are empty
Cause: Rankings update weekly on Mondays; there may be a brief update window
Solution: The command auto-retries previous weeks. If still empty, retry in a few minutes

Error: Player profile fails
Cause: Player ID is incorrect
Solution: Use `get_rankings` to find player IDs from the current rankings list, or verify via ESPN tennis URLs

Error: Scores seem delayed or don't update live
Cause: Scores update after each set/match is completed, not point-by-point
Solution: This is expected behavior. Refresh `get_scoreboard` periodically for updated set scores
