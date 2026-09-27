# MLB Data — API Reference

## Commands

### get_scoreboard
Get live/recent MLB scores.
- `date` (str, optional): Date in YYYY-MM-DD format. Defaults to today.

Returns `events[]` with game info, scores (by inning), status, and competitors.

### get_standings
Get MLB standings by league and division.
- `season` (int, optional): Season year

Returns `groups[]` with AL/NL leagues and East/Central/West division standings including W-L, PCT, GB, runs scored/allowed, run differential, and streak.

### get_teams
Get all 30 MLB teams. No parameters.

Returns `teams[]` with id, name, abbreviation, logo, and location.

### get_team_roster
Get full roster for a team.
- `team_id` (str, required): ESPN team ID (e.g., "10" for Yankees)

Returns `athletes[]` with name, position, jersey number, height, weight, experience, bats/throws, and birthplace.

### get_team_schedule
Get schedule for a specific team.
- `team_id` (str, required): ESPN team ID
- `season` (int, optional): Season year

Returns `events[]` with opponent, date, score (if played), and venue.

### get_game_summary
Get detailed box score and scoring plays.
- `event_id` (str, required): ESPN event ID

Returns `game_info`, `competitors`, `boxscore` (batting/pitching stats per player), `scoring_plays`, and `leaders`.

### get_leaders
Get MLB statistical leaders (batting avg, home runs, ERA, etc.).
- `season` (int, optional): Season year

Returns `categories[]` with leader rankings per stat category.

### get_news
Get MLB news articles.
- `team_id` (str, optional): Filter by team

Returns `articles[]` with headline, description, published date, and link.

### get_play_by_play
Get full play-by-play data for a game.
- `event_id` (str, required): ESPN event ID

Returns play-by-play detail including inning, outs, batter, pitcher, play description, and scoring plays.

### get_win_probability
Get win probability chart data for a game.
- `event_id` (str, required): ESPN event ID

Returns timestamped home/away win probability percentages throughout the game.

### get_schedule
Get MLB schedule for a specific date or season.
- `date` (str, optional): Date in YYYY-MM-DD format
- `season` (int, optional): Season year (used only if no date provided)

Returns `events[]` for the specified date.

### get_injuries
Get current MLB injury reports across all teams. No parameters.

Returns `teams[]` with per-team injury lists including player name, position, status (10-Day IL/15-Day IL/60-Day IL/Day-To-Day), injury type, and detail.

### get_transactions
Get recent MLB transactions (trades, signings, DFA, IL moves).
- `limit` (int, optional): Max transactions to return. Defaults to 50.

Returns `transactions[]` with date, team, and description.

### get_futures
Get MLB futures/odds markets (World Series winner, league pennants, division winners, etc.).
- `limit` (int, optional): Max entries per market. Defaults to 10.
- `season_year` (int, optional): Season year. Defaults to current.

Returns `futures[]` with market name and entries (team/player name + odds value). Each market reports one provider: the group with usable entries and the lowest finite numeric priority. Numeric strings are accepted; missing/invalid priorities rank after numeric priorities, and ties use ESPN response order. `provider` is included only when the selected group has a name.

### get_depth_chart
Get depth chart for a specific team.
- `team_id` (str, required): ESPN team ID

Returns `charts[]` with positional depth (lineup, rotation, bullpen) and player depth order.

### get_team_stats
Get full team statistical profile for a season.
- `team_id` (str, required): ESPN team ID
- `season_year` (int, optional): Season year. Defaults to current.
- `season_type` (int, optional): 2=regular (default), 3=postseason.

Returns `categories[]` (Batting, Pitching, Fielding) with detailed stats including value, rank, and per-game averages.

### get_player_stats
Get full player statistical profile for a season.
- `player_id` (str, required): ESPN athlete ID
- `season_year` (int, optional): Season year. Defaults to current.
- `season_type` (int, optional): 2=regular (default), 3=postseason.

Returns `categories[]` with detailed stats including value, rank, and per-game averages.

## Team IDs

| Team | ID | Team | ID |
|------|-----|------|-----|
| Arizona Diamondbacks | 29 | Milwaukee Brewers | 8 |
| Atlanta Braves | 15 | Minnesota Twins | 9 |
| Baltimore Orioles | 1 | New York Mets | 21 |
| Boston Red Sox | 2 | New York Yankees | 10 |
| Chicago Cubs | 16 | Oakland Athletics | 11 |
| Chicago White Sox | 4 | Philadelphia Phillies | 22 |
| Cincinnati Reds | 17 | Pittsburgh Pirates | 23 |
| Cleveland Guardians | 5 | San Diego Padres | 25 |
| Colorado Rockies | 27 | San Francisco Giants | 26 |
| Detroit Tigers | 6 | Seattle Mariners | 12 |
| Houston Astros | 18 | St. Louis Cardinals | 24 |
| Kansas City Royals | 7 | Tampa Bay Rays | 30 |
| Los Angeles Angels | 3 | Texas Rangers | 13 |
| Los Angeles Dodgers | 19 | Toronto Blue Jays | 14 |
| Miami Marlins | 28 | Washington Nationals | 20 |

Use `get_teams` for the complete, authoritative list.
