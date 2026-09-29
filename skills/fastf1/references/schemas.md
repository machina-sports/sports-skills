# FastF1 — Return Schemas

## get_race_results

Returns `data[]` list. Fields: `position` (int), `driver` (abbreviation), `full_name`, `team`, `grid_position` (int), `points` (int), `status`, `time`, `fastest_lap` (bool), `fastest_lap_time`.

`fastest_lap_time` is each driver's best timed lap (deleted laps excluded), computed from the session laps; `fastest_lap` is true for the driver with the lowest one. It is empty only when FastF1 has no lap data for the race.

## get_driver_info

Returns `data` as a **list** of driver objects (not a dict). Fields: `driver_number`, `driver_code`, `full_name`, `team_name`, `country_code`, `headshot_url`.

## get_team_info

Returns `data` as a **list** of team objects. Fields: `team_name`, `team_color`, `drivers[]`.

## get_championship_standings

Returns `data.driver_standings[]` with fields: `position`, `driver_code`, `full_name`, `team`, `points`, `sprint_points`, `wins`, `podiums`. `points` includes sprint points (`sprint_points` is the sprint share); `wins`/`podiums`/`races` count Grands Prix only. With `round`, only races and sprints up to and including that round are counted; `data.after_round` echoes it (`null` when omitted) and `data.races_counted` is the number of Grands Prix summed.

Returns `data.constructor_standings[]` with fields: `position`, `team`, `points`, `wins`.

## get_race_schedule

Returns schedule entries with event names, dates, circuits, and session times.

## get_session_data

Returns detailed session data including lap times, sector times, and speed trap data for qualifying, race, or practice sessions.

Metadata fields: `session` (e.g. "2026 Season Round 13: Italian Grand Prix - Race"), `event_name` ("Italian Grand Prix"), `round` (13), `event_date` (the Grand Prix day, "2026-09-06"), `session_date` (start of this session in local track time, e.g. "2026-03-14T11:00:00+08:00" for the Chinese sprint), `session_type` ("Race", "Sprint", "Qualifying", ...), `track_name` (the event location, "Monza"), then `results[]`.

## get_lap_data

Returns lap-by-lap timing data with lap numbers, lap times, sector times, and compound information. `is_pit_in_lap` / `is_pit_out_lap` mark pit laps; those laps (and laps rebuilt from sectors) have `is_accurate: false`.

## get_pit_stops

Returns `data.pit_stops[]` (`race`, `team`, `driver`, `lap`, `duration_seconds`, `red_flag`), `data.team_summary[]` (`team`, `average_seconds`, `best_seconds`, `total_stops`) and `data.total_stops`.

A stop is a pit entry on lap N followed by a pit exit on lap N+1; a pit entry with no exit (retirement) is not listed. `duration_seconds` is **pit-lane time** (pit entry to pit exit, typically 20-30 s), not the stationary time at the box, which FastF1 does not provide; `data.duration_type` is `"pit_lane_time"`. Tyre changes made while the race was red-flagged have `red_flag: true` and a pit-lane time of the whole stoppage (about 1840 s at Monza 2026); they are listed and counted in `total_stops` but left out of `team_summary`.

## get_speed_data

Returns speed trap data with intermediate speeds, speed trap values, and finish line speeds.

## get_season_stats

Returns aggregated season statistics: fastest laps, top speeds, points, wins, and podiums per driver/team. `points` includes sprint points; `sprint_points` is the sprint share.

## get_team_comparison

Returns head-to-head comparison data: qualifying deltas, race pace differences, sector comparisons, and points. `team1`/`team2` `points` include sprint points of the compared weekends; `sprint_points` is the sprint share. `wins`/`podiums` and `per_race` points count Grands Prix only.

## get_driver_comparison

Returns head-to-head driver comparison data: qualifying H2H record, race H2H record, pace deltas, and per-race breakdowns. Works for teammates and cross-team matchups. Each driver's `points` includes sprint points of the compared weekends; `sprint_points` is the sprint share. `wins`/`podiums`/`races` and `per_race` points count Grands Prix only.

## get_tire_analysis

Returns tire strategy data: compound usage, stint lengths, degradation rates, and pit stop strategies.
