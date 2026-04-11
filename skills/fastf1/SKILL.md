---
name: fastf1
description: |
  Formula 1 data — race schedules, results, lap timing, driver and team info. Powered by the FastF1 library. Covers F1 sessions, qualifying, practice, race results, sector times, tire strategy.

  Use when: user asks about F1 race results, qualifying, lap times, driver stats, team info, the F1 calendar, or Formula 1 data.
  Don't use when: user asks about other motorsports (MotoGP, NASCAR, IndyCar, WEC, Formula E). Don't use for F1 betting odds or predictions — use kalshi or polymarket instead. Don't use for F1 news articles — use sports-news instead.
license: MIT
compatibility: "Requires Python 3.10+ (install with: pip install sports-skills)"
metadata:
  author: machina-sports
  version: "0.1.0"
---

# FastF1 — Formula 1 Data

Before writing queries, consult `references/api-reference.md` for endpoints, ID conventions, and data shapes.

## Quick Start

Prefer the CLI — it avoids Python import path issues:
```bash
sports-skills f1 get_race_schedule --year=2025
sports-skills f1 get_race_results --year=2025 --event=Monza
```

Python SDK (alternative):
```python
from sports_skills import f1

schedule = f1.get_race_schedule(year=2025)
results = f1.get_race_results(year=2025, event="Monza")
```

## CRITICAL: Before Any Query

CRITICAL: Before calling any data endpoint, verify:
- Year is derived from the system prompt's `currentDate` — never hardcoded.
- In January or February, use `year = current_year - 1` (pre-season; the new F1 season has not started yet).

## Choosing the Year

Derive the current year from the system prompt's date (e.g., `currentDate: 2026-02-16` → current year is 2026).

- **If the user specifies a year**, use it as-is.
- **If the user says "latest", "recent", "last season", or doesn't specify**: The F1 season runs roughly March–December. If the current month is January or February, use `year = current_year - 1`. From March onward, use the current year.

## Workflows

### Race Weekend Analysis
1. `get_race_schedule --year=<year>` — find the event name and date
2. `get_race_results --year=<year> --event=<name>` — final classification (positions, times, points)
3. `get_lap_data --year=<year> --event=<name> --session_type=R` — lap-by-lap pace analysis
4. `get_tire_analysis --year=<year> --event=<name>` — strategy breakdown (compounds, stint lengths, degradation)

### Driver/Team Comparison
1. `get_championship_standings --year=<year>` — championship context (points, wins, podiums)
2. `get_team_comparison --year=<year> --team1=<t1> --team2=<t2>` OR `get_driver_comparison --year=<year> --driver1=<d1> --driver2=<d2>`
3. `get_season_stats --year=<year>` — aggregate performance (fastest laps, top speeds)

### Season Overview
1. `get_race_schedule --year=<year>` — full calendar with dates and circuits
2. `get_championship_standings --year=<year>` — driver and constructor standings
3. `get_season_stats --year=<year>` — season-wide fastest laps, top speeds, points leaders
4. `get_driver_info --year=<year>` — current grid (driver numbers, teams, nationalities)

## Commands

| Command | Description |
|---|---|
| `get_race_schedule` | Full season calendar with dates and circuits |
| `get_race_results` | Final race classification (positions, times, points) |
| `get_session_data` | Raw session info (Q, FP1, FP2, FP3, R) |
| `get_driver_info` | Driver details from the grid |
| `get_team_info` | Team info with driver lineup |
| `get_lap_data` | Lap-by-lap timing with sectors and tire data |
| `get_pit_stops` | Pit stop durations and team averages |
| `get_speed_data` | Speed trap and intermediate speed data |
| `get_championship_standings` | Driver and constructor championship standings |
| `get_season_stats` | Aggregate season performance |
| `get_team_comparison` | Team head-to-head: qualifying, race pace, sectors |
| `get_driver_comparison` | Driver head-to-head: qualifying H2H, race H2H, pace delta |
| `get_tire_analysis` | Tire strategy, stint lengths, degradation rates |

See `references/api-reference.md` for full parameter lists and return shapes.

## Examples

Example 1: F1 calendar
User says: "Show me the F1 calendar"
Actions:
1. Derive year from `currentDate`
2. Call `get_race_schedule(year=<derived_year>)`
Result: Full calendar with event names, dates, and circuits

Example 2: Driver race performance
User says: "How did Verstappen do at Monza?"
Actions:
1. Derive year from `currentDate` (or from context)
2. Call `get_race_results(year=<year>, event="Monza")` for final classification
3. Call `get_lap_data(year=<year>, event="Monza", session_type="R", driver="VER")` for lap times
Result: Finishing position, gap to leader, fastest lap, and tire strategy

Example 3: Latest results queried in pre-season
User says: "What were the latest F1 results?" (asked in February 2026)
Actions:
1. Current month is February → season not yet started → use `year = 2025`
2. Call `get_race_schedule(year=2025)` to find the last event of that season
3. Call `get_race_results(year=2025, event=<last_event>)` for the final race results
Result: Results of the final 2025 race

## Commands that DO NOT exist — never call these

- ~~`get_qualifying`~~ / ~~`get_practice`~~ — does not exist. Use `get_session_data` with `session_type="Q"` for qualifying or `session_type="FP1"`/`"FP2"`/`"FP3"` for practice.
- ~~`get_standings`~~ — does not exist. Use `get_championship_standings` instead.
- ~~`get_results`~~ — does not exist. Use `get_race_results` instead.
- ~~`get_calendar`~~ — does not exist. Use `get_race_schedule` instead.

If a command is not listed in the Commands table above, it does not exist.

## Troubleshooting

Error: Event name not found
Cause: Event name spelling does not match FastF1's internal naming
Solution: Call `get_race_schedule(year=<year>)` first to get the exact event names, then retry with the correct name

Error: Session data is empty
Cause: The session has not happened yet
Solution: FastF1 only returns data for completed sessions. Check `get_race_schedule` for when the session is scheduled

Error: `get_race_results` returns no `fastest_lap_time`
Cause: Some races do not include fastest lap data in the results endpoint
Solution: Use `get_lap_data(session_type="R")` and find the minimum `lap_time` across all drivers

Error: Querying the current year in January or February returns no data
Cause: The new F1 season has not started yet
Solution: Use `year = current_year - 1` for any pre-March query; do not query the current year before March
