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

ESPN has no light calendar endpoint: the only source is the full-year scoreboard (about 19 MB for ATP 2026, 25 MB for WTA), so the first call is slow. The result is cached for 6 hours per tour and year.

### get_player_info
Get individual tennis player profile.
- `player_id` (str, required): ESPN athlete ID
- `tour` (str, optional): "atp" or "wta". Defaults to "atp".

Returns player details: name, nationality, birthplace, height, turned pro year, career titles, and recent match history.

### get_news
Get tennis news articles for a tour.
- `tour` (str, required): "atp" or "wta".

Returns news articles for the selected tour.

## WTA API Commands

These two commands read the public WTA API (`https://api.wtatennis.com/tennis/...`) instead of ESPN and take the WTA's **native numeric ids**. ESPN athlete/event ids do not work and are not mapped. Ids must be positive decimal numbers written without leading zeros (e.g. `"901"`, not `"0901"`; no paths, signs, or spaces); anything else is rejected before a request is made, never rewritten.

Both responses are cached for 10 minutes per URL and carry a `source` block:
- `provider`, `url`
- `replay_mode`: the active `SPORTS_SKILLS_REPLAY` mode (`off`, `record`, `replay`, `fill`)
- `fetched_at`: UTC time the response was obtained live from the WTA API (a cached hit reports its original fetch time). Set only in `off` and `record` mode; `null` in `replay` and `fill`, where the response may come from a local recording whose fetch time is not known
- `served_at`: UTC time this result was returned. In `replay`/`fill` it is local serving time only
- `note`: states the above. Neither timestamp is when the WTA last updated the data or when a match was played, so neither is event freshness

With `SPORTS_SKILLS_REPLAY` set to `record`, `replay`, or `fill`, the cache is skipped so every call goes through the replay layer. Results are WTA-published snapshots; they are not guaranteed complete or current.

Failures return `{"status": false, "message": ...}`: invalid parameters, HTTP errors (with `status_code`), invalid JSON, or a response that is not the expected shape. Rows that cannot be read are skipped and reported in `skipped_rows` / `warnings`; if every row is unreadable the call fails rather than returning an empty success.

### get_wta_entry_list
Entry list for one WTA tournament edition. Source: `GET /tennis/tournaments/{tournament_id}/{year}/players`.
- `tournament_id` (str, required): native WTA tournament id, e.g. `"901"`
- `year` (int, required): tournament year

Returns:
- `tournament_id`, `year`
- `events[]`, one per event in the provider response:
  - `event_type_code`: provider code, raw (e.g. `"LS"`, `"LD"`)
  - `description`: provider description, or `null`
  - `format`: `"singles"` or `"doubles"`, derived from team sizes (1 or 2 players per entry); `null` if sizes are mixed or there are no entries
  - `entries[]`: `players[]` (`id`, `name`, `country_code`), `seed` (int, or raw text, or `null`), `entry_type` (raw provider code, `null` when blank), `eliminated`, `winner`, `runner_up` (booleans as published, `null` if absent)
  - `count`: entries in the event
- `count` (events), `entry_count` (entries across events)
- `note`: freshness caveat. When the provider returns no events, the note says the list may not be published or the id/year pair may not exist; `count` is `0`.
- `source`

An entry list is not a draw: it changes as players withdraw, qualify, or enter late.

### get_wta_player_results
A bounded window of a player's most recent match results. Source: one request to `GET /tennis/players/{player_id}/matches?page=0&pageSize={limit+1}&sort=desc`, plus `year={year}` first when given. (The bare endpoint returns only the player's oldest few matches, so it is not used.) There is no pagination and no total career count.
- `player_id` (str, required): native WTA player id, e.g. `"320760"`
- `year` (int, optional): sent to the WTA API as its `year` filter. Every returned match must have that tournament year (the provider's tournament year, falling back to the start date's year); if any does not, the provider ignored the filter and the call fails as inconclusive instead of returning a misleading result
- `limit` (int, optional): matches to return, 1–200. Defaults to 20. One extra row is requested only to set `has_more`

Returns:
- `player`: `id`, `name`, `country_code` (from the provider; only `id` when absent)
- `year`, `limit`
- `matches[]`:
  - `tournament_start_date` (`YYYY-MM-DD`): the **tournament's** start date. The provider gives no per-match date, so this is not when the match was played
  - `tournament`: `id`, `name`, `title`, `level`, `year`, `end_date`, `surface`, `in_outdoor`, `city`, `country`
  - `round`: provider round name, raw (e.g. `"R32"`, `"QF"`)
  - `format`: `"singles"` or `"doubles"`, derived from participant count (1 or 2 players per side); `null` if the sides differ
  - `match_type_code` (`s_d_flag`) and `draw_code` (`qpm_flag`): provider codes, raw and uninterpreted
  - `partner` (doubles only) and `opponents[]`: `id`, `name`, `country_code`
  - `score`: the provider's score string with whitespace collapsed (e.g. `"6-1 6-2"`). Its orientation (winner's or player's perspective) is not documented
  - `winner_code`: the provider's raw `winner` value. No win/loss is derived from it: which side it names relative to the requested player is not publicly documented
  - `player_seed`, `opponent_seed`, `player_entry_type`, `opponent_entry_type`, `reason_code`: provider values, raw
- `count`: matches returned (rows the provider sent within `limit`, minus skipped malformed rows)
- `has_more`: `true` when the provider sent more than `limit` rows, i.e. at least one further match exists beyond this window. It is not a count
- `history_complete`: always `false` — this is a recent-results window, never a full career history
- `ordering`: as delivered by the provider for `sort=desc` (newest first); not re-sorted. Matches within one tournament are not guaranteed to be in playing order
- `note`, `source`

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
