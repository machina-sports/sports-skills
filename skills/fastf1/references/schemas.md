# FastF1 — Return Schemas

## get_race_results

Returns `data[]` list. Fields: `position` (int), `driver` (abbreviation), `full_name`, `team`, `grid_position` (int), `points` (int), `status`, `time`, `fastest_lap` (bool), `fastest_lap_time`.

Note: `fastest_lap` and `fastest_lap_time` are not always populated by FastF1. To find the actual fastest lap, use `get_lap_data()` and find the minimum `lap_time` across all drivers.

## get_driver_info

Returns `data` as a **list** of driver objects (not a dict). Fields: `driver_number`, `driver_code`, `full_name`, `team_name`, `country_code`, `headshot_url`.

## get_team_info

Returns `data` as a **list** of team objects. Fields: `team_name`, `team_color`, `drivers[]`.

## get_championship_standings

Returns `data.driver_standings[]` with fields: `position`, `driver_code`, `full_name`, `team`, `points`, `wins`, `podiums`.

Returns `data.constructor_standings[]` with fields: `position`, `team`, `points`, `wins`.

## get_race_schedule

Returns schedule entries with event names, dates, circuits, and session times.

## get_session_data

Returns detailed session data including lap times, sector times, and speed trap data for qualifying, race, or practice sessions.

## get_lap_data

Returns lap-by-lap timing data with lap numbers, lap times, sector times, and compound information.

## get_pit_stops

Returns pit stop data with pit-in/pit-out times, durations, and lap numbers.

## get_speed_data

Returns speed trap data with intermediate speeds, speed trap values, and finish line speeds.

## get_season_stats

Returns aggregated season statistics: fastest laps, top speeds, points, wins, and podiums per driver/team.

## get_team_comparison

Returns head-to-head comparison data: qualifying deltas, race pace differences, sector comparisons, and points.

## get_teammate_comparison

Returns intra-team comparison data: qualifying H2H record, race H2H record, and pace deltas.

## get_tire_analysis

Returns tire strategy data: compound usage, stint lengths, degradation rates, and pit stop strategies.
