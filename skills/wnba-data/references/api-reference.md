# WNBA Data — API Reference

## Commands

### get_scoreboard
Get live/recent WNBA scores.
- `date` (str, optional): Date in YYYY-MM-DD format. Defaults to today.

Returns `events[]` with game info, scores, status, and competitors.

### get_standings
Get WNBA standings by conference.
- `season` (int, optional): Season year

Returns `groups[]` with Eastern/Western conferences and team standings including W-L, PCT, GB, and streak.

### get_teams
Get all WNBA teams. No parameters.

Returns `teams[]` with id, name, abbreviation, logo, and location.

### get_team_roster
Get full roster for a team.
- `team_id` (str, required): ESPN team ID (e.g., "5" for Indiana Fever)

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
Get WNBA statistical leaders (points, rebounds, assists, etc.).
- `season` (int, optional): Season year. Defaults to most recently completed season.

Returns `categories[]` with leader rankings per stat category.

### get_news
Get WNBA news articles.
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
Get WNBA schedule for a specific date or season.
- `date` (str, optional): Date in YYYY-MM-DD format
- `season` (int, optional): Season year (used only if no date provided)

Returns `events[]` for the specified date.

### get_injuries
Get current WNBA injury reports across all teams. No parameters.

Returns `teams[]` with per-team injury lists including player name, position, status, injury type, and detail.

### get_transactions
Get recent WNBA transactions (trades, signings, waivers).
- `limit` (int, optional): Max transactions to return. Defaults to 50.

Returns `transactions[]` with date, team, and description.

### get_futures
Get WNBA futures/odds markets (Championship winner, MVP, etc.).
- `limit` (int, optional): Max entries per market. Defaults to 10.
- `season_year` (int, optional): Season year. Defaults to current.

Returns `futures[]` with market name and entries (team/player name + odds value).

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

| Team | ID |
|------|----|
| Atlanta Dream | 3 |
| Chicago Sky | 4 |
| Connecticut Sun | 6 |
| Dallas Wings | 8 |
| Indiana Fever | 5 |
| Las Vegas Aces | 9 |
| Los Angeles Sparks | 14 |
| Minnesota Lynx | 16 |
| New York Liberty | 17 |
| Phoenix Mercury | 21 |
| Seattle Storm | 26 |
| Washington Mystics | 30 |

Use `get_teams` for the complete, authoritative list.
