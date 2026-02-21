---
name: tennis-data
description: |
  ATP and WTA tennis data via ESPN public endpoints — tournament scores, season calendars, player rankings, player profiles, and news. Zero config, no API keys.

  Use when: user asks about tennis scores, match results, tournament draws, ATP/WTA rankings, tennis player info, or tennis news.
  Don't use when: user asks about other sports. Don't use for live point-by-point data — scores update after each set/match.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# Tennis Data (ATP + WTA)

## Quick Start

Prefer the CLI — it avoids Python import path issues:
```bash
sports-skills tennis get_scoreboard --tour=atp
sports-skills tennis get_rankings --tour=wta
sports-skills tennis get_calendar --tour=atp --year=2026
```

## Important: Tennis is Not a Team Sport

Tennis data is fundamentally different from team sports (NFL, NBA, etc.):
- **Tournaments, not games**: Events are multi-day tournaments containing many matches.
- **Individual athletes**: Competitors are individual players (singles) or pairs (doubles), not teams.
- **Set-based scoring**: Scores are per-set game counts (e.g., 6-4, 7-5), not quarters.
- **Rankings, not standings**: Players have ATP/WTA ranking points, not team records.
- **No rosters or team schedules**: Tennis has no team-level commands.

## The `tour` Parameter

Most commands require `--tour=atp` or `--tour=wta`:
- **ATP**: Men's professional tennis tour
- **WTA**: Women's professional tennis tour

If the user doesn't specify, default to `atp` for men's tennis or `wta` for women's tennis. If the user just says "tennis" without specifying, ask which tour or show both by calling the command twice.

Before complex fetches, run the parameter validator: `bash scripts/validate_params.sh [args]`

*For detailed reference data, see the files in the `references/` directory.*

## Workflows

### Workflow: Live Tournament Check
1. `get_scoreboard --tour=<atp|wta>`
2. Present current matches by round.
3. For player info, use `get_player_info --player_id=<id>`.

### Workflow: Rankings Lookup
1. `get_rankings --tour=<atp|wta> --limit=20`
2. Present rankings with points and trend.

### Workflow: Season Calendar
1. `get_calendar --tour=<atp|wta> --year=<year>`
2. Filter for specific tournament.
3. `get_news --tour=<tour>` for latest coverage.

## Examples

User: "What ATP matches are happening right now?"
1. Call `get_scoreboard(tour="atp")`
2. Present current tournaments and matches by round

User: "Show me the WTA rankings"
1. Call `get_rankings(tour="wta", limit=20)`
2. Present rankings with rank, name, points, and trend

User: "When is the French Open this year?"
1. Call `get_calendar(tour="atp", year=2026)`
2. Search results for "Roland Garros" (the French Open's official name)

## Error Handling & Fallbacks

- If `get_scoreboard` returns no matches, tournaments run specific weeks. Use `get_calendar` to find when events are scheduled.
- If rankings are empty, rankings update weekly on Mondays. The command auto-retries previous weeks.
- If player profile fails, use `get_rankings` to verify the player_id.
- **Never fabricate match scores or rankings.** If data is unavailable, state so.
