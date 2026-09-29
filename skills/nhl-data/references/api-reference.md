# NHL Data — API Reference

## Commands

### get_scoreboard
Get live/recent NHL scores.
- `date` (str, optional): Date in YYYY-MM-DD format. Defaults to today.

Returns `events[]` with game info, scores, status, and competitors.

### get_standings
Get NHL standings by conference and division.
- `season` (int, optional): Season year

Returns `groups[]` with Eastern/Western conferences and division standings including W-L-OTL, points, regulation wins, goals for/against, and streak.

### get_teams
Get all NHL teams. No parameters.

Returns `teams[]` with id, name, abbreviation, logo, and location.

### get_team_roster
Get full roster for a team.
- `team_id` (str, required): ESPN team ID (e.g., "21" for Maple Leafs)

Returns `athletes[]` with name, position, jersey number, height, weight, experience, birthplace, and shoots/catches.

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
Get NHL statistical leaders (goals, assists, points, etc.).
- `season` (int, optional): Season year

Returns `categories[]` with leader rankings per stat category.

### get_news
Get NHL news articles.
- `team_id` (str, optional): Filter by team

Returns `articles[]` with headline, description, published date, and link.

### get_play_by_play
Get full play-by-play data for a game.
- `event_id` (str, required): ESPN event ID

Returns play-by-play detail including period, clock, team, play type, and scoring plays.

### get_schedule
Get NHL games for a specific date.
- `date` (str, optional): Date in YYYY-MM-DD format
- `season` (int, optional): Not a filter: ESPN's scoreboard has none. With `date` it is ignored; alone it returns an error. For a season use `get_team_schedule(team_id, season)`.

Returns `events[]` for the specified date.

### get_injuries
Get current NHL injury reports across all teams. No parameters.

Returns `teams[]` with per-team injury lists including player name, position, status (Out/Day-To-Day/IR), injury type, and detail.

### get_transactions
Get recent NHL transactions (trades, signings, waivers).
- `limit` (int, optional): Max transactions to return. Defaults to 50.

Returns `transactions[]` with date, team, and description.

### get_futures
Get NHL futures/odds markets (Stanley Cup winner, Hart Trophy, etc.).
- `limit` (int, optional): Max entries per market. Defaults to 10.
- `season_year` (int, optional): Season year. Defaults to current.

Returns `futures[]` with market name and entries (team/player name + odds value). Each market reports one provider: the group with usable entries and the lowest finite numeric priority. Numeric strings are accepted; missing/invalid priorities rank after numeric priorities, and ties use ESPN response order. `provider` is included only when the selected group has a name.

### get_team_stats
Get full team statistical profile for a season.
- `team_id` (str, required): ESPN team ID
- `season_year` (int, optional): Season year. Defaults to current.
- `season_type` (int, optional): 2=regular (default), 3=postseason.

Returns `categories[]` with detailed stats including value, rank, and per-game averages.

### get_player_stats
Get full player statistical profile for a season.
- `player_id` (str, required): ESPN athlete ID
- `season_year` (int, optional): Season year. Defaults to current.
- `season_type` (int, optional): 2=regular (default), 3=postseason.

Returns `categories[]` with detailed stats including value, rank, and per-game averages.

### get_nhlstats_player_game_log
Get one player's games in a season via the NHL API (`/v1/player/{id}/game-log/{season}/{type}`).
- `player_id` (str, optional): NHL player id (e.g. `8478402`). Find it with `find_nhl_player`.
- `player` (str, optional): Player name to resolve instead of `player_id`. Must match exactly one player.
- `season` (int or str, optional): Season starting year (`2025`) or NHL form (`"20252026"`). Defaults to current.
- `season_type` (str, optional): `regular` (default) or `playoffs`.
- `sort_by`, `descending`, `limit`, `fields` (optional): Row shaping (`sort_by` then `limit`; `fields` always keeps `game_id`, `game_date`, `team_abbreviation`, `opponent`). Stat keys (`points`, `toi`) are addressable directly. With any set, the response adds `total_rows` and `returned_rows`.

Returns `games[]`, oldest first: `game_id`, `game_date`, `opponent` (abbreviation), `home_away`, `result` (`W`/`L`), `decided_by` (`REG`/`OT`/`SO`), `team_score`, `opponent_score`, `team_abbreviation`, `team_abbreviation_espn`, and `stats` (skaters: `goals`, `assists`, `points`, `plusMinus`, `shots`, `toi`, ...; goalies: `decision`, `shotsAgainst`, `goalsAgainst`, `savePctg`, ...). The game log has no scores, so `result` and the scores come from each team's `club-schedule-season` (one more cached request per team); if that fails they are `null` and `warnings` says why. Connor McDavid (8478402) has 82 regular-season rows in 2025-26.

## Team IDs

| Team | ID | Team | ID |
|------|-----|------|-----|
| Anaheim Ducks | 25 | Nashville Predators | 27 |
| Boston Bruins | 1 | New Jersey Devils | 11 |
| Buffalo Sabres | 2 | New York Islanders | 12 |
| Calgary Flames | 3 | New York Rangers | 13 |
| Carolina Hurricanes | 7 | Ottawa Senators | 14 |
| Chicago Blackhawks | 4 | Philadelphia Flyers | 15 |
| Colorado Avalanche | 17 | Pittsburgh Penguins | 16 |
| Columbus Blue Jackets | 29 | San Jose Sharks | 18 |
| Dallas Stars | 9 | Seattle Kraken | 124292 |
| Detroit Red Wings | 5 | St. Louis Blues | 19 |
| Edmonton Oilers | 6 | Tampa Bay Lightning | 20 |
| Florida Panthers | 26 | Toronto Maple Leafs | 21 |
| Los Angeles Kings | 8 | Utah Mammoth | 129764 |
| Minnesota Wild | 30 | Vancouver Canucks | 22 |
| Montreal Canadiens | 10 | Vegas Golden Knights | 37 |
| | | Washington Capitals | 23 |
| | | Winnipeg Jets | 28 |

Use `get_teams` for the complete, authoritative list.
