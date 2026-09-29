# FastF1 — API Reference

## Commands

| Command | Required | Optional | Description |
|---|---|---|---|
| `get_race_schedule` | | year | Full season calendar with dates and circuits |
| `get_race_results` | year, event | | Final race classification (positions, times, points) |
| `get_session_data` | | session_year, session_name, session_type | Raw session info (Q, FP1, FP2, FP3, R) |
| `get_driver_info` | | year, driver | Driver details from the grid |
| `get_team_info` | | year, team | Team info with driver lineup |
| `get_lap_data` | | year, event, session_type, driver | Lap-by-lap timing with sectors and tire data |
| `get_pit_stops` | | year, event, driver | Pit stops with pit-lane time (not stationary time) and team averages |
| `get_speed_data` | | year, event, driver | Speed trap and intermediate speed data |
| `get_championship_standings` | | year, round | Driver and constructor championship standings (optionally after a given round) |
| `get_season_stats` | | year | Aggregate season performance (fastest laps, top speeds) |
| `get_team_comparison` | | year, team1, team2, event | Team head-to-head: qualifying, race pace, sectors |
| `get_driver_comparison` | | year, driver1, driver2, event | Driver head-to-head: qualifying H2H, race H2H, pace delta |
| `get_tire_analysis` | | year, event, driver | Tire strategy, stint lengths, and degradation rates |

See `references/commands.md` and `references/schemas.md` for detailed parameter descriptions and return schemas.

## Session Types

| Code | Session |
|---|---|
| `R` | Race |
| `Q` | Qualifying |
| `FP1` | Free Practice 1 |
| `FP2` | Free Practice 2 |
| `FP3` | Free Practice 3 |

## Year Selection Rules

The F1 season runs roughly March–December.
- **January or February**: Use `year = current_year - 1` (pre-season; new season not started).
- **March onward**: Use `current_year` (season has started or is imminent).
- Always derive from the system prompt's `currentDate`.
