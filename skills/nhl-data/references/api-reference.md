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
Get NHL schedule for a specific date or season.
- `date` (str, optional): Date in YYYY-MM-DD format
- `season` (int, optional): Season year (used only if no date provided)

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
