# College Football (CFB) — API Reference

## Commands

### get_scoreboard
Get live/recent college football scores.
- `date` (str, optional): Date in YYYY-MM-DD format. Defaults to today.
- `week` (int, optional): CFB week number.
- `group` (int, optional): Conference group ID to filter.
- `limit` (int, optional): Max events to return.

Returns `events[]` with game info, scores, competitor names, and ranked status.

### get_standings
Get college football standings by conference.
- `season` (int, optional): Season year. Defaults to current.
- `group` (int, optional): Conference ID to filter.

Returns conference standings with W-L records.

### get_teams
Get all FBS college football teams (750+ teams). No parameters.

Returns `teams[]` with id, name, abbreviation, logo, and location.

### get_team_roster
Get full roster for a college football team.
- `team_id` (str, required): ESPN team ID.

Returns `athletes[]` with name, position, jersey number, height, weight.

### get_team_schedule
Get schedule for a specific college football team.
- `team_id` (str, required): ESPN team ID.
- `season` (int, optional): Season year. Defaults to current.

Returns `events[]` with opponent, date, score (if played), and venue.

### get_game_summary
Get detailed game summary with box score, scoring plays, and leaders.
- `event_id` (str, required): ESPN event ID.

Returns `game_info`, `competitors`, `boxscore`, `scoring_plays`, and `leaders`.

### get_rankings
Get college football rankings — AP Top 25, Coaches Poll, CFP rankings.
- `season` (int, optional): Season year. Defaults to current.
- `week` (int, optional): Week number for historical rankings.

Returns `polls[]` with poll name and `teams[]` containing rank, previous rank, record, points, and first-place votes.

### get_news
Get college football news articles.
- `team_id` (str, optional): ESPN team ID to filter news by team.

Returns `articles[]` with headline, description, published date, and link.

### get_play_by_play
Get full play-by-play data for a game.
- `event_id` (str, required): ESPN event ID.

Returns `drives[]` with play-by-play detail including down, distance, yard line, play description, and scoring plays.

### get_win_probability
Get the win probability timeline for a college football game.
- `event_id` (str, required): ESPN event ID.

Returns `timeline[]` and `count`. Each timeline entry contains the ESPN `play_id`, `home_win_pct`, and `tie_pct`; percentages are on a 0–100 scale and rounded to one decimal place.

```json
{
  "timeline": [
    {
      "play_id": "4018644942",
      "home_win_pct": 59.0,
      "tie_pct": 0.0
    }
  ],
  "count": 1
}
```

If ESPN returns no summary for the event, the command returns an error with `No data found for event <event_id>`. If the summary has no win probability entries, it returns an error with `No win probability data available for this game` rather than an empty timeline.

### get_schedule
Get college football schedule by week.
- `season` (int, optional): Season year. Defaults to current.
- `week` (int, optional): CFB week number.
- `group` (int, optional): Conference group ID to filter.

Returns `events[]` for the specified week/season.

### get_injuries
Get current college football injury reports across all teams. No parameters.

Returns `teams[]` with per-team injury lists including player name, position, status, injury type, and detail.

### get_futures
Get college football futures/odds markets (National Championship, Heisman, etc.).
- `limit` (int, optional): Max entries per market. Defaults to 25.
- `season_year` (int, optional): Season year. Defaults to current.

Returns `futures[]` with market name and entries (team/player name + odds value).

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

## Conference IDs (group parameter)

| Conference | Group ID | Conference | Group ID |
|-----------|----------|-----------|----------|
| ACC | 1 | Big 12 | 4 |
| SEC | 8 | Big Ten | 9 |
| Pac-12 | 15 | American | 151 |
| Mountain West | 17 | Sun Belt | 37 |
| MAC | 15 | Conference USA | 12 |

**Note:** Conference IDs may change across seasons. Use `get_standings` without a group to see all conferences and their current structure.

## Common Team IDs

| Team | ID | Team | ID |
|------|-----|------|-----|
| Alabama | 333 | Ohio State | 194 |
| Georgia | 61 | Michigan | 130 |
| Texas | 251 | USC | 30 |
| Oregon | 2483 | Penn State | 213 |
| Clemson | 228 | LSU | 99 |
| Florida State | 52 | Oklahoma | 201 |
| Notre Dame | 87 | Tennessee | 2633 |
| Florida | 57 | Auburn | 2 |

Use `get_teams` for all 750+ FBS team IDs.

## Season Structure

- **Regular Season**: Late August – early December (Weeks 1–15)
- **Conference Championships**: Early December
- **Bowl Season**: Mid-December – early January
- **College Football Playoff**: December – January
