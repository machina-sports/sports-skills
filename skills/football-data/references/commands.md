# Football Data — Valid Commands & Common Mistakes

## Valid Commands

These are the ONLY valid commands. Do not invent or guess command names:
- `get_current_season`
- `get_competitions`
- `get_competition_seasons`
- `get_season_schedule`
- `get_season_standings`
- `get_season_leaders`
- `get_season_teams`
- `search_team`
- `get_team_profile`
- `get_daily_schedule`
- `get_event_summary`
- `get_event_lineups`
- `get_event_statistics`
- `get_event_timeline`
- `get_team_schedule`
- `get_head_to_head`
- `get_event_xg`
- `get_event_players_statistics`
- `get_missing_players`
- `get_season_transfers`
- `get_player_profile`

## Commands That DO NOT Exist (Commonly Hallucinated)

- ~~`get_standings`~~ — the correct command is `get_season_standings` (requires `season_id`).
- ~~`get_live_scores`~~ — not available. Use `get_daily_schedule()` for today's matches; status field shows "live" for in-progress games.
- ~~`get_team_squad`~~ / ~~`get_team_roster`~~ — `get_team_profile` does NOT return players. Use `get_season_leaders` for PL player IDs, then `get_player_profile` for individual data.
- ~~`get_transfers`~~ — the correct command is `get_season_transfers` (requires `season_id` + `tm_player_ids`).
- ~~`get_match_results`~~ / ~~`get_match`~~ — use `get_event_summary` with an `event_id`.
- ~~`get_player_stats`~~ — use `get_event_players_statistics` for match-level stats, or `get_player_profile` for career data.

## Other Common Mistakes

- Using `get_season_leaders` or `get_missing_players` on non-PL leagues — they return empty. Check the Data Coverage table.
- Using `get_event_xg` on leagues outside the top 5 — returns empty. Only works for EPL, La Liga, Bundesliga, Serie A, Ligue 1.
- Guessing `team_id` or `event_id` instead of discovering them via `search_team`, `get_daily_schedule`, or `get_season_schedule`.

If you're unsure whether a command exists, check this list. Do not try commands that aren't listed above.

## Command Parameter Reference

### get_current_season
- `competition_id` (str, required): Competition slug

### get_competitions
No parameters.

### get_competition_seasons
- `competition_id` (str, required): Competition slug

### get_season_schedule
- `season_id` (str, required): Season slug (e.g., "premier-league-2025")

### get_season_standings
- `season_id` (str, required): Season slug

### get_season_leaders
- `season_id` (str, required): Season slug (must be `premier-league-*`)

### get_season_teams
- `season_id` (str, required): Season slug

### search_team
- `query` (str, required): Team name to search
- `competition_id` (str, optional): Limit search to one league

### get_team_profile
- `team_id` (str, required): ESPN team ID
- `league_slug` (str, optional): League hint

### get_daily_schedule
- `date` (str, optional): Date in YYYY-MM-DD format. Defaults to today.

### get_event_summary
- `event_id` (str, required): Match/event ID

### get_event_lineups
- `event_id` (str, required): Match/event ID

### get_event_statistics
- `event_id` (str, required): Match/event ID

### get_event_timeline
- `event_id` (str, required): Match/event ID

### get_team_schedule
- `team_id` (str, required): ESPN team ID
- `league_slug` (str, optional): League hint
- `season_year` (str, optional): Season year filter
- `competition_id` (str, optional): Filter to a single competition

### get_head_to_head
**UNAVAILABLE** — requires licensed data. Do not call this command.
- `team_id` (str, required): First team ID
- `team_id_2` (str, required): Second team ID

### get_event_xg
- `event_id` (str, required): Match/event ID. Top 5 leagues only.

### get_event_players_statistics
- `event_id` (str, required): Match/event ID

### get_missing_players
- `season_id` (str, required): Season slug (must be `premier-league-*`)

### get_season_transfers
- `season_id` (str, required): Season slug
- `tm_player_ids` (list, required): Transfermarkt player IDs

### get_player_profile
- `fpl_id` (str, optional): FPL player ID (PL players only)
- `tm_player_id` (str, optional): Transfermarkt player ID (any league)
At least one ID required.
