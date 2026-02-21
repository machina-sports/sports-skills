# FastF1 — Valid Commands & Common Mistakes

## Valid Commands

These are the ONLY valid commands. Do not invent or guess command names:
- `get_race_schedule`
- `get_race_results`
- `get_session_data`
- `get_driver_info`
- `get_team_info`
- `get_lap_data`
- `get_pit_stops`
- `get_speed_data`
- `get_championship_standings`
- `get_season_stats`
- `get_team_comparison`
- `get_teammate_comparison`
- `get_tire_analysis`

## Commands That DO NOT Exist (Commonly Hallucinated)

- ~~`get_driver_results`~~ — use `get_race_results` and filter by driver, or use `get_lap_data` with the `driver` parameter.
- ~~`get_standings`~~ — use `get_championship_standings`.
- ~~`get_fastest_laps`~~ — use `get_lap_data` and find the minimum `lap_time`, or use `get_season_stats` for season-wide fastest laps.
- ~~`get_tire_strategy`~~ — use `get_tire_analysis` for full tire strategy and degradation data.
- ~~`get_circuit_info`~~ — circuit details are included in `get_race_schedule` output.

If you're unsure whether a command exists, check this list. Do not try commands that aren't listed above.

## Command Parameter Reference

### get_race_schedule
- `year` (int, required): Season year

### get_race_results
- `year` (int, required): Season year
- `event` (str, required): Event name (e.g., "Monza", "Silverstone")

### get_session_data
- `session_year` (int, required): Year
- `session_name` (str, required): Event name
- `session_type` (str, optional): "Q" (qualifying), "R" (race), "FP1", etc. Default: "Q"

### get_driver_info
- `year` (int, required): Season year
- `driver` (str, optional): Driver code or name. Omit for all drivers.

### get_team_info
- `year` (int, required): Season year
- `team` (str, optional): Team name. Omit for all teams.

### get_lap_data
- `year` (int, required): Season year
- `event` (str, required): Event name
- `session_type` (str, optional): Session type. Default: "R"
- `driver` (str, optional): Driver code. Omit for all drivers.

### get_pit_stops
- `year` (int, required): Season year
- `event` (str, optional): Event name. Omit for full season.
- `driver` (str, optional): Driver code. Omit for all drivers.

### get_speed_data
- `year` (int, required): Season year
- `event` (str, optional): Event name. Omit for full season.
- `driver` (str, optional): Driver code. Omit for all drivers.

### get_championship_standings
- `year` (int, required): Season year

### get_season_stats
- `year` (int, required): Season year

### get_team_comparison
- `year` (int, required): Season year
- `team1` (str, required): First team name (e.g., "Red Bull")
- `team2` (str, required): Second team name (e.g., "McLaren")
- `event` (str, optional): Event name. Omit for full season.

### get_teammate_comparison
- `year` (int, required): Season year
- `team` (str, required): Team name (e.g., "McLaren")
- `event` (str, optional): Event name. Omit for full season.

### get_tire_analysis
- `year` (int, required): Season year
- `event` (str, optional): Event name. Omit for full season.
- `driver` (str, optional): Driver code. Omit for all drivers.
