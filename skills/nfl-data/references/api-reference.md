# NFL Data — API Reference

## Commands

### get_scoreboard
Get live/recent NFL scores.
- `date` (str, optional): Date in YYYY-MM-DD format
- `week` (int, optional): Week number (1-18 regular season, 19-23 postseason)

Returns `events[]` with game info, scores, status, and competitors.

### get_standings
Get NFL standings by conference and division.
- `season` (int, optional): Season year

Returns `groups[]` with AFC/NFC conferences, divisions, and team standings including W-L-T, PCT, PF, PA.

### get_teams
Get all 32 NFL teams. No parameters.

Returns `teams[]` with id, name, abbreviation, logo, and location.

### get_team_roster
Get full roster for a team.
- `team_id` (str, required): ESPN team ID (e.g., "12" for Chiefs)

Returns `athletes[]` with name, position, jersey number, height, weight, experience.

### get_team_schedule
Get schedule for a specific team.
- `team_id` (str, required): ESPN team ID
- `season` (int, optional): Season year

Returns `events[]` with opponent, date, score (if played), and venue.

### get_game_summary
Get detailed box score and scoring plays.
- `event_id` (str, required): ESPN event ID

Returns `game_info`, `competitors`, `boxscore` (passing/rushing/receiving stats), `scoring_plays`, and `leaders`.

### get_leaders
Get NFL statistical leaders (passing, rushing, receiving).
- `season` (int, optional): Season year

Returns `categories[]` with leader rankings per stat category.

### get_news
Get NFL news articles.
- `team_id` (str, optional): Filter by team

Returns `articles[]` with headline, description, published date, and link.

### get_play_by_play
Get full play-by-play data for a game.
- `event_id` (str, required): ESPN event ID

Returns `drives[]` with play-by-play detail including down, distance, yard line, play description, and scoring plays.

### get_win_probability
Get win probability chart data for a game.
- `event_id` (str, required): ESPN event ID

Returns timestamped home/away win probability percentages throughout the game.

### get_schedule
Get NFL season schedule by week.
- `season` (int, optional): Season year
- `week` (int, optional): Week number (1-18 regular season, 19-23 postseason)

Returns `events[]` for the specified week/season.

### get_injuries
Get current NFL injury reports across all teams. No parameters.

Returns `teams[]` with per-team injury lists including player name, position, status (Out/Doubtful/Questionable/Day-To-Day), injury type, and detail.

### get_transactions
Get recent NFL transactions (trades, signings, waivers).
- `limit` (int, optional): Max transactions to return. Defaults to 50.

Returns `transactions[]` with date, team, and description.

### get_futures
Get NFL futures/odds markets (Super Bowl winner, MVP, etc.).
- `limit` (int, optional): Max entries per market. Defaults to 25.
- `season_year` (int, optional): Season year. Defaults to current.

Returns `futures[]` with market name and entries (team/player name + odds value).

### get_depth_chart
Get depth chart for a specific team.
- `team_id` (str, required): ESPN team ID

Returns `charts[]` with offense/defense/special teams positions and player depth order.

### get_team_stats
Get full team statistical profile for a season.
- `team_id` (str, required): ESPN team ID
- `season_year` (int, optional): Season year. Defaults to current.
- `season_type` (int, optional): 1=preseason, 2=regular (default), 3=postseason.

Returns `categories[]` (Passing, Rushing, Receiving, etc.) with detailed stats including value, rank, and per-game averages.

### get_player_stats
Get full player statistical profile for a season.
- `player_id` (str, required): ESPN athlete ID
- `season_year` (int, optional): Season year. Defaults to current.
- `season_type` (int, optional): 1=preseason, 2=regular (default), 3=postseason.

Returns `categories[]` with detailed stats including value, rank, and per-game averages.

### get_nflverse_schedule
Get schedules/results through the nflverse backend.
- `season` (int, optional): Season year
- `week` (int, optional): NFL week filter

Returns `events[]` with `game_id`, teams, scores, date/time, line fields, and location.

### get_nflverse_weekly_rosters
Get weekly roster snapshots through the nflverse backend.
- `season` (int, optional): Season year
- `week` (int, optional): NFL week filter
- `team` (str, optional): Team abbreviation filter (e.g. `KC`)

Returns `players[]` with normalized roster fields: team, player_id, player_name, position, jersey_number, status, college, and experience fields when available.

### get_nflverse_player_stats
Get normalized nflverse player stat rows.
- `season` (int, optional): Season year
- `player_id` (str, optional): nflverse/GSIS player identifier
- `team` (str, optional): Team abbreviation filter
- `position` (str, optional): Position filter

Returns `players[]`, each with identity fields (`player_id`, `player_name`, `position`, `team`) plus a `stats` object containing backend columns (completions, passing_yards, passing_tds, rushing_yards, etc.).

### get_nflverse_team_stats
Get normalized nflverse team stat rows.
- `season` (int, optional): Season year
- `team` (str, optional): Team abbreviation filter
- `week` (int, optional): Week filter when available

Returns `teams[]`, each with team/season context plus a `stats` object containing backend columns. Note: with `nfl_data_py`, team stats fall back to schedule data (game-by-game results) since a dedicated team stats endpoint is not available.

### get_nflverse_play_by_play
Get normalized nflverse play-by-play rows.
- `season` (int, optional): Season year
- `week` (int, optional): Week filter
- `team` (str, optional): Team abbreviation filter
- `game_id` (str, optional): nflverse game identifier
- `limit` (int, optional): Max rows to return

Returns `plays[]` with game/play identifiers, quarter/clock, teams, down/distance, description, EPA, WP/WPA, and score state.

Notes:
- The nflverse backend requires the `[nfl]` optional extra: `pip install sports-skills[nfl]`. It prefers `nflreadpy` when installed and falls back to `nfl_data_py` for compatibility.
- These commands keep `nfl-data` as the user-facing skill while exposing table-style datasets under the same module.
- The ESPN-backed commands (e.g. `get_scoreboard`, `get_standings`) work with zero extra dependencies. The nflverse commands provide deeper historical/analytical data (seasonal aggregates, EPA, win probability per play) but require the optional install.
- Parquet support (`pyarrow` or `fastparquet`) is needed for most nflverse data beyond schedules.

## Team IDs

| Team | ID | Team | ID |
|------|-----|------|-----|
| Cardinals | 22 | Rams | 14 |
| Falcons | 1 | Ravens | 33 |
| Bills | 2 | Bears | 3 |
| Panthers | 29 | Bengals | 4 |
| Cowboys | 6 | Browns | 5 |
| Broncos | 7 | Lions | 8 |
| Packers | 9 | Texans | 34 |
| Colts | 11 | Jaguars | 30 |
| Chiefs | 12 | Raiders | 13 |
| Chargers | 24 | Dolphins | 15 |
| Vikings | 16 | Patriots | 17 |
| Saints | 18 | Giants | 19 |
| Jets | 20 | Eagles | 21 |
| Steelers | 23 | 49ers | 25 |
| Seahawks | 26 | Buccaneers | 27 |
| Titans | 10 | Commanders | 28 |

Use `get_teams` for the complete, authoritative list.

## Week Numbers

Regular season: weeks 1-18. Postseason unified numbering: Wild Card=19, Divisional=20, Conference Championship=21, Pro Bowl=22, Super Bowl=23. The connector translates these to ESPN's internal `seasontype=3` automatically.
