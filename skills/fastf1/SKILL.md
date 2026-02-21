---
name: fastf1
description: |
  Formula 1 data — race schedules, results, lap timing, driver and team info. Powered by the FastF1 library. Covers F1 sessions, qualifying, practice, race results, sector times, tire strategy.

  Use when: user asks about F1 race results, qualifying, lap times, driver stats, team info, the F1 calendar, or Formula 1 data.
  Don't use when: user asks about other motorsports (MotoGP, NASCAR, IndyCar, WEC, Formula E). Don't use for F1 betting odds or predictions — use kalshi or polymarket instead. Don't use for F1 news articles — use sports-news instead.
license: MIT
compatibility: Requires Python 3.10+ with fastf1 and pandas (pip install sports-skills[f1])
metadata:
  author: machina-sports
  version: "0.1.0"
---

# FastF1 — Formula 1 Data

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

## Choosing the Year

Derive the current year from the system prompt's date (e.g., `currentDate: 2026-02-16` → current year is 2026).

- **If the user specifies a year**, use it as-is.
- **If the user says "latest", "recent", "last season", or doesn't specify a year**: The F1 season runs roughly March-December. If the current month is January or February (i.e., before the new season starts), use `year = current_year - 1` since that's the most recent completed season. From March onward, use the current year — races will have started or be imminent.
- **Never hardcode a year.** Always derive it from the system date.

## Workflows

### Workflow: Race Weekend Analysis

1. `get_race_schedule --year=<year>` — find the event name and date
2. `get_race_results --year=<year> --event=<name>` — final classification (positions, times, points)
3. `get_lap_data --year=<year> --event=<name> --session_type=R` — lap-by-lap pace analysis
4. `get_tire_analysis --year=<year> --event=<name>` — strategy breakdown (compounds, stint lengths, degradation)

### Workflow: Driver/Team Comparison

1. `get_championship_standings --year=<year>` — championship context (points, wins, podiums)
2. `get_team_comparison --year=<year> --team1=<t1> --team2=<t2>` OR `get_teammate_comparison --year=<year> --team=<team>` — head-to-head qualifying and race pace
3. `get_season_stats --year=<year>` — aggregate performance (fastest laps, top speeds)

### Workflow: Season Overview

1. `get_race_schedule --year=<year>` — full calendar with dates and circuits
2. `get_championship_standings --year=<year>` — driver and constructor standings
3. `get_season_stats --year=<year>` — season-wide fastest laps, top speeds, points leaders
4. `get_driver_info --year=<year>` — current grid (driver numbers, teams, nationalities)

### Available Commands

`get_race_schedule`, `get_race_results`, `get_session_data`, `get_driver_info`, `get_team_info`, `get_lap_data`, `get_pit_stops`, `get_speed_data`, `get_championship_standings`, `get_season_stats`, `get_team_comparison`, `get_teammate_comparison`, `get_tire_analysis`.

For return schemas, parameter details, and valid command lists, read the files in the `references/` directory.

## Examples

User: "Show me the F1 calendar"
1. Call `get_race_schedule(year={year})`
2. Present schedule with event names, dates, and circuits

User: "How did Verstappen do at Monza?"
1. Derive the year (if unspecified, use the latest completed season per the rules above)
2. Call `get_race_results(year={year}, event="Monza")` for final classification
3. Call `get_lap_data(year={year}, event="Monza", session_type="R", driver="VER")` for lap times
4. Present finishing position, gap to leader, fastest lap, and tire strategy

User: "What were the latest F1 results?" (asked in February 2026)
1. Current month is February → season hasn't started → use `year = 2025`
2. Call `get_race_schedule(year=2025)` to find the last event of that season
3. Call `get_race_results(year=2025, event=<last_event>)` for the final race results
4. Present the results

## Error Handling & Fallbacks

- If event name not found → call `get_race_schedule` first to find the exact event name. Retry with the correct name.
- If session data is empty → the session hasn't happened yet. FastF1 only returns data for completed sessions.
- If a command returns an error → check the valid commands list in `references/commands.md`. Do NOT invent command names.
- If `get_race_results` returns no `fastest_lap_time` → use `get_lap_data` and find the minimum `lap_time` across all drivers instead.
- In Jan/Feb, use `year = current_year - 1` for the most recent completed season. Do NOT query the current year before March.
- **Never fabricate lap times, race results, or championship points.** If data is unavailable, state so clearly.
