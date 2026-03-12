# Volleyball Data — API Reference

## Commands

### get_competitions
List all available volleyball competitions and leagues.
No parameters required.

Returns `configured_leagues[]` with competition_id, name, country, gender, and source. Also returns `api_competitions` with the full list from the Nevobo API.

### get_standings
Get league table for a volleyball competition.
- `competition_id` (str, required): League identifier (e.g. "nevobo-eredivisie-heren").

Returns `standings[]` with rank, team, matches_played, points, sets_won, sets_lost, points_for, points_against.

### get_schedule
Get upcoming match schedule for a competition.
- `competition_id` (str, required): League identifier.

Returns `matches[]` with home_team, away_team, date, and details.

### get_results
Get match results for a competition.
- `competition_id` (str, required): League identifier.

Returns `results[]` with home_team, away_team, score, set_scores[], date, and details.

### get_clubs
List volleyball clubs.
- `competition_id` (str, optional): Competition context (informational).
- `limit` (int, optional): Max clubs to return.

Returns `items[]` with club data from the Nevobo API (name, location, coordinates, contact).

### get_club_schedule
Get upcoming matches for a club across all its teams.
- `club_id` (str, required): Nevobo club identifier (e.g. "CKL5C67").

Returns `matches[]` with home_team, away_team, date, and details.

### get_club_results
Get match results for a club across all its teams.
- `club_id` (str, required): Nevobo club identifier.

Returns `results[]` with home_team, away_team, score, set_scores[], date, and details.

### get_poules
Browse Nevobo poules for advanced discovery of divisions and regional leagues.
- `competition_id` (str, optional): Filter context.
- `regio` (str, optional): Region slug (e.g. "nationale-competitie").
- `limit` (int, optional): Max poules to return.

Returns `items[]` with poule data from the Hydra API and `total` count.

### get_tournaments
Get volleyball tournament calendar.
- `limit` (int, optional): Max tournaments to return.

Returns `tournaments[]` with title, link, date, and description.

### get_news
Get volleyball federation news.
- `limit` (int, optional): Max news items to return.

Returns `news[]` with title, link, date, and summary.

## Data Source

All data comes from the Nevobo (Nederlandse Volleybalbond) open API at `https://api.nevobo.nl`. No authentication required.

Two interfaces are used:
- **JSON-LD / Hydra**: Paginated collections for competitions, poules, clubs
- **RSS Export**: Per-poule standings, schedules, results; per-club feeds

## Volleyball Scoring

- Matches are best-of-5 sets (first to 3 sets wins)
- Sets are played to 25 points (deciding set to 15)
- Set scores appear as e.g. "25-21, 25-18, 21-25, 25-20"
- Match result appears as e.g. "3-1" (sets won by each team)
- Points: 3 for a 3-0 or 3-1 win, 2 for a 3-2 win, 1 for a 2-3 loss, 0 otherwise
