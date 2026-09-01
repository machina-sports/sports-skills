# Tennis Data — API Reference

## Commands

### get_scoreboard
Get live/recent tennis scores for a tour.
- `tour` (str, required): "atp" or "wta"

Returns current tournament info with matches organized by round including player names, set scores, and match status.

### get_rankings
Get ATP or WTA player rankings.
- `tour` (str, required): "atp" or "wta"
- `limit` (int, optional): Number of players to return. Defaults to 50.

Returns `rankings[]` with rank, name, country, ranking points, and trend (movement since last week).

### get_calendar
Get full season tournament calendar.
- `tour` (str, required): "atp" or "wta"
- `year` (int, optional): Season year. Defaults to current.

Returns `tournaments[]` with tournament name, dates, location, surface, and prize money. Use this to find when specific tournaments are scheduled.

### get_player_info
Get individual tennis player profile.
- `player_id` (str, required): ESPN athlete ID
- `tour` (str, optional): "atp" or "wta". Defaults to "atp".

Returns player details: name, nationality, birthplace, height, turned pro year, career titles, and recent match history.

### get_news
Get tennis news articles for a tour.
- `tour` (str, required): "atp" or "wta".

Returns news articles for the selected tour.

## Important: Tennis is Not a Team Sport

- **Tournaments, not games**: Events are multi-day tournaments containing many matches.
- **Individual athletes**: Competitors are individual players (singles) or pairs (doubles), not teams.
- **Set-based scoring**: Scores are per-set game counts (e.g., 6-4, 7-5), not quarters.
- **Rankings, not standings**: Players have ATP/WTA ranking points, not team records.
- **No rosters or team schedules**: Tennis has no team-level commands.

## The `tour` Parameter

- **ATP**: Men's professional tennis tour
- **WTA**: Women's professional tennis tour

If the user just says "tennis" without specifying a tour, ask which one or show both by calling the command twice.

## Notable Tournaments

See `references/grand-slams.md` for Grand Slam tournament details and `references/scoring.md` for scoring format reference. See `references/player-ids.md` for extended player ID list.
