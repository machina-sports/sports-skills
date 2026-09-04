# NBA Data — API Reference

## Commands

### get_scoreboard
Get live/recent NBA scores.
- `date` (str, optional): Date in YYYY-MM-DD format. Defaults to today.

Returns `events[]` with game info, scores, status, and competitors.

### get_standings
Get NBA standings by conference.
- `season` (int, optional): Season year

Returns `groups[]` with Eastern/Western conferences and team standings including W-L, PCT, GB, streak, home/away/conference records, and PPG.

### get_teams
Get all 30 NBA teams. No parameters.

Returns `teams[]` with id, name, abbreviation, logo, and location.

### get_team_roster
Get full roster for a team.
- `team_id` (str, required): ESPN team ID (e.g., "13" for Lakers)

Returns `athletes[]` with name, position, jersey number, height, weight, experience.

### get_team_schedule
Get schedule for a specific team.
- `team_id` (str, required): ESPN team ID
- `season` (int, optional): Season year

Returns `events[]` with opponent, date, score (if played), and venue.

### get_game_summary
Get detailed box score and scoring plays.
- `event_id` (str, required): ESPN event ID

Returns `game_info`, `competitors`, `boxscore` (stats per player), `scoring_plays`, and `leaders`.

### get_leaders
Get NBA statistical leaders (points, rebounds, assists, etc.).
- `season` (int, optional): Season year

Returns `categories[]` with leader rankings per stat category.

### get_news
Get NBA news articles.
- `team_id` (str, optional): Filter by team

Returns `articles[]` with headline, description, published date, and link.

### get_play_by_play
Get full play-by-play data for a game.
- `event_id` (str, required): ESPN event ID

Returns play-by-play detail including period, clock, team, play description, and scoring plays.

### get_win_probability
Get win probability chart data for a game.
- `event_id` (str, required): ESPN event ID

Returns timestamped home/away win probability percentages throughout the game.

### get_schedule
Get NBA schedule for a specific date or season.
- `date` (str, optional): Date in YYYY-MM-DD format
- `season` (int, optional): Season year (used only if no date provided)

Returns `events[]` for the specified date.

### get_injuries
Get current NBA injury reports across all teams. No parameters.

Returns `teams[]` with per-team injury lists including player name, position, status (Out/Doubtful/Questionable/Day-To-Day), injury type, and detail.

### get_transactions
Get recent NBA transactions (trades, signings, waivers).
- `limit` (int, optional): Max transactions to return. Defaults to 50.

Returns `transactions[]` with date, team, and description.

### get_futures
Get NBA futures/odds markets (Championship winner, MVP, etc.).
- `limit` (int, optional): Max entries per market. Defaults to 10.
- `season_year` (int, optional): Season year. Defaults to current.

Returns `futures[]` with market name and entries (team/player name + odds value). Each market reports one provider: the group with usable entries and the lowest finite numeric priority. Numeric strings are accepted; missing/invalid priorities rank after numeric priorities, and ties use ESPN response order. `provider` is included only when the selected group has a name.

### get_depth_chart
Get depth chart for a specific team.
- `team_id` (str, required): ESPN team ID

Returns `charts[]` with positional depth and player depth order.

### get_team_stats
Get full team statistical profile for a season.
- `team_id` (str, required): ESPN team ID
- `season_year` (int, optional): Season year. Defaults to current.
- `season_type` (int, optional): 1=preseason, 2=regular (default), 3=postseason.

Returns `categories[]` with detailed stats including value, rank, and per-game averages.

### get_player_stats
Get full player statistical profile for a season.
- `player_id` (str, required): ESPN athlete ID
- `season_year` (int, optional): Season year. Defaults to current.
- `season_type` (int, optional): 1=preseason, 2=regular (default), 3=postseason.

Returns `categories[]` with detailed stats including value, rank, and per-game averages.

### get_live_scoreboard
Get real-time NBA scores from NBA CDN, with ESPN as a fallback. No parameters.

Returns today's games with live status and scores.

### get_live_boxscore
Get a real-time NBA box score from NBA CDN, with ESPN as a fallback.
- `game_id` (str, required): NBA game ID, for example `0022400001`.

Returns game information and the current player box score.

### get_live_playbyplay
Get real-time NBA play-by-play with the most recent plays first.
- `game_id` (str, required): NBA game ID.
- `limit` (int, optional): Maximum plays to return. Defaults to 25.
- `scoring_only` (bool, optional): Return only scoring plays. Defaults to false.

Returns recent play actions for the game.

### get_player_live_stats
Get real-time stats for one player in today's games.
- `player_name` (str, required): Full or partial player name.

Returns the matching player's current box-score line.

## Team IDs

| Team | ID | Team | ID |
|------|-----|------|-----|
| Atlanta Hawks | 1 | Memphis Grizzlies | 29 |
| Boston Celtics | 2 | Miami Heat | 14 |
| Brooklyn Nets | 17 | Milwaukee Bucks | 15 |
| Charlotte Hornets | 30 | Minnesota Timberwolves | 16 |
| Chicago Bulls | 4 | New Orleans Pelicans | 3 |
| Cleveland Cavaliers | 5 | New York Knicks | 18 |
| Dallas Mavericks | 6 | Oklahoma City Thunder | 25 |
| Denver Nuggets | 7 | Orlando Magic | 19 |
| Detroit Pistons | 8 | Philadelphia 76ers | 20 |
| Golden State Warriors | 9 | Phoenix Suns | 21 |
| Houston Rockets | 10 | Portland Trail Blazers | 22 |
| Indiana Pacers | 11 | Sacramento Kings | 23 |
| LA Clippers | 12 | San Antonio Spurs | 24 |
| Los Angeles Lakers | 13 | Toronto Raptors | 28 |
| Utah Jazz | 26 | Washington Wizards | 27 |

Use `get_teams` for the complete, authoritative list.
