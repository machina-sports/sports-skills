# College Basketball (CBB) — API Reference

## Commands

### get_scoreboard
Get live/recent college basketball scores.
- `date` (str, optional): Date in YYYY-MM-DD format. Defaults to today.
- `group` (int, optional): Conference group ID to filter.
- `limit` (int, optional): Max events to return.

Returns `events[]` with game info, scores, competitor names, and ranked status.

### get_standings
Get college basketball standings by conference.
- `season` (int, optional): Season year. Defaults to current.
- `group` (int, optional): Conference ID to filter.

Returns conference standings with W-L records.

### get_teams
Get all D1 men's college basketball teams (360+ teams). No parameters.

Returns `teams[]` with id, name, abbreviation, logo, and location.

### get_team_roster
Get full roster for a college basketball team.
- `team_id` (str, required): ESPN team ID.

Returns `athletes[]` with name, position, jersey number, height, weight.

### get_team_schedule
Get schedule for a specific college basketball team.
- `team_id` (str, required): ESPN team ID.
- `season` (int, optional): Season year. Defaults to current.

Returns `events[]` with opponent, date, score (if played), and venue.

### get_game_summary
Get detailed game summary with box score and player stats.
- `event_id` (str, required): ESPN event ID.

Returns `game_info`, `competitors`, `boxscore` (stats per player), `scoring_plays`, and `leaders`.

### get_rankings
Get college basketball rankings — AP Top 25, Coaches Poll.
- `season` (int, optional): Season year. Defaults to current.
- `week` (int, optional): Week number for historical rankings.

Returns `polls[]` with poll name and `teams[]` containing rank, previous rank, record, points, and first-place votes.

### get_news
Get college basketball news articles.
- `team_id` (str, optional): ESPN team ID to filter news by team.

Returns `articles[]` with headline, description, published date, and link.

### get_play_by_play
Get full play-by-play data for a game.
- `event_id` (str, required): ESPN event ID.

Returns play-by-play detail including period, clock, team, play description, and scoring plays.

### get_win_probability
Get win probability chart data for a game.
- `event_id` (str, required): ESPN event ID.

Returns timestamped home/away win probability percentages throughout the game.

### get_schedule
Get college basketball schedule.
- `date` (str, optional): Date in YYYY-MM-DD format.
- `season` (int, optional): Season year. Defaults to current.
- `group` (int, optional): Conference group ID to filter.

Returns `events[]` for the specified date or season.

### get_futures
Get college basketball futures/odds markets (National Championship, Player of the Year, etc.).
- `limit` (int, optional): Max entries per market. Defaults to 10.
- `season_year` (int, optional): Season year. Defaults to current.

Returns `futures[]` with market name and entries (team/player name + odds value). Each market reports one provider: the group with usable entries and the lowest finite numeric priority. Numeric strings are accepted; missing/invalid priorities rank after numeric priorities, and ties use ESPN response order. `provider` is included only when the selected group has a name.

### get_team_stats
Get full team statistical profile for a season.
- `team_id` (str, required): ESPN team ID.
- `season_year` (int, optional): Season year. Defaults to current.
- `season_type` (int, optional): 2=regular (default), 3=postseason.

Returns `categories[]` with detailed stats including value, rank, and per-game averages.

### get_player_stats
Get full player statistical profile for a season.
- `player_id` (str, required): ESPN athlete ID.
- `season_year` (int, optional): Season year. Defaults to current.
- `season_type` (int, optional): 2=regular (default), 3=postseason.

Returns `categories[]` with detailed stats including value, rank, and per-game averages.

### get_power_index
Get BPI (Basketball Power Index) ratings for D1 teams.
- `team_id` (str, optional): ESPN team ID to filter to one team.
- `limit` (int, optional): Max teams to return. Defaults to 25.
- `page` (int, optional): Page number for pagination. Defaults to 1.

Returns BPI ratings and rankings for the selected teams.

### get_tournament_projections
Get NCAA tournament projections with seeds, regions, and advancement probabilities.
- `limit` (int, optional): Max teams to return. Defaults to the 68-team tournament field.

Returns projected tournament teams with seed, region, and advancement probabilities.

### compare_teams
Compare two teams using BPI ratings and season stats.
- `team_a_id` (str, required): ESPN team ID for team A.
- `team_b_id` (str, required): ESPN team ID for team B.

Returns a side-by-side comparison of both teams.

### find_upset_candidates
Find potential upsets based on BPI versus seed differential.
- `min_seed` (int, optional): Minimum seed to consider. Defaults to 10.
- `max_seed` (int, optional): Maximum seed to consider. Defaults to 16.

Returns potential upset candidates and their BPI-versus-seed differential.

## Conference IDs (group parameter)

| Conference | Group ID | Conference | Group ID |
|-----------|----------|-----------|----------|
| ACC | 2 | Big 12 | 8 |
| SEC | 23 | Big Ten | 7 |
| Big East | 4 | Pac-12 | 21 |
| American | 62 | Mountain West | 44 |
| Atlantic 10 | 3 | West Coast | 26 |
| Missouri Valley | 18 | Colonial | 10 |

**Note:** Conference IDs are different from CFB conference IDs.

## Common Team IDs

| Team | ID | Team | ID |
|------|-----|------|-----|
| Duke | 150 | Kansas | 2305 |
| Kentucky | 96 | North Carolina | 153 |
| UConn | 41 | Gonzaga | 2250 |
| Villanova | 222 | UCLA | 26 |
| Michigan State | 127 | Arizona | 12 |
| Purdue | 2509 | Houston | 248 |
| Tennessee | 2633 | Auburn | 2 |
| Baylor | 239 | Creighton | 156 |

Use `get_teams` for the complete list of all 360+ D1 teams.

## Season Structure

- **Non-Conference Season**: November – December
- **Conference Play**: January – early March
- **Conference Tournaments**: Early–mid March
- **NCAA Tournament (March Madness)**: Mid-March – early April (First Four, First/Second Round, Sweet 16, Elite 8, Final Four, Championship)
