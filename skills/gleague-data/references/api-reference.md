# NBA G League Data — API Reference

Source: ESPN public API, sport path `basketball/nba-development` (ESPN league id 69).
Every command returns `{"status": bool, "data": ..., "message": str}`; failures have
`status: false`, a readable `message`, and `status_code` when ESPN sent one. An empty
result (no games that day, an empty roster) is `status: true` with an empty list.

## IDs and seasons

- Team ids are ESPN **G League** ids and overlap NBA ids (`2` = Austin Spurs here, Boston Celtics in the NBA).
- Event ids are ESPN event ids (e.g. `401867657`).
- `season` is the ending year: 2025-26 = `2026`.

## Commands

### get_teams
No params. Returns `teams[]` (`id`, `name`, `abbreviation`, `nickname`, `location`, `color`, `logo`, `is_active`) and `count`.

### get_scoreboard
- `date` (optional, `YYYY-MM-DD`): defaults to ESPN's current game day.

Returns `events[]`, `day`, `count`. Each event: `id`, `name`, `short_name`, `status`, `status_detail`,
`start_time` (ISO), `start_ts` (epoch seconds or null), `season_type` (`tournament` / `regular` /
`postseason`), `venue`, `competitors[]` (`team`, `home_away`, `score` as a string, `period_scores`,
`record`, `winner`), `odds`, `broadcasts`.

### get_schedule
- `date` (optional, `YYYY-MM-DD`).
- `season` (optional): not a filter. A season without a date is an error; use `get_team_schedule`.

Same shape as `get_scoreboard`.

### get_standings
- `season` (optional, ending year). Omitted, an upcoming season with no games yet is skipped for the
  prior one, reported in `defaulted_from` and `note`.

Returns `groups[]` (`conference`, `division`, `entries[]`), `season`, `season_type`, `season_status`.
Entries: `team`, `wins`, `losses`, `win_pct`, `games_back`, `streak`, `home_record`, `away_record`,
`neutral_record`, `conference_record`, `division_record`, `last_ten`, `points_per_game`,
`opp_points_per_game`, `diff`, `playoff_seed`, `clinch`, `division`. A league-wide table, conference
tables, and group tables nested in a conference all appear as groups.

### get_team_roster
- `team_id` (required).

Only the roster ESPN currently returns; historical rosters are unverified and not supported by this
module. The response `season` is ESPN's label and does not prove the roster is fresh. Returns `team`, `season`,
`athletes[]` (`id`, `name`, `jersey`, `position`, `age`, `height`, `weight`, `experience`, `college`,
`status`), `count`.

### get_team_schedule
- `team_id` (required).
- `season` (optional, ending year). Omitted, ESPN selects the season; `season` in the response is ESPN's
  `requestedSeason`, not its envelope `season` (which is the current one).
- `season_type` (optional): `regular` / `2`, `postseason` / `playoffs` / `3`, `tournament` / `showcase` / `5`
  (Tip-Off Tournament), `all` (5 + 2 + 3 merged in date order). `playin` is rejected.

Returns `team`, `events[]` (event shape above), `season`, `count`.

### get_game_summary
- `event_id` (required).

Returns `game_info` (`id`, `status`, `status_detail`, `start_time`, `start_ts`, `season_type`, `venue`),
`competitors[]` (scores as strings, `linescores`), `boxscore[]` (`team`, `team_stats`, player
`statistics`), `scoring_plays[]`, `leaders[]`, `odds`.

### get_play_by_play
- `event_id` (required).

Returns `plays[]` (`id`, `text`, `type`, `period`, `clock`, `home_score`, `away_score`, `scoring_play`,
`score_value`, `team_id`, `shooting_play`, optional `coordinate`) and `count`. A summary without plays
returns an empty list.

### get_news
- `limit` (optional, positive integer).

Returns `articles[]` (`headline`, `description`, `published`, `type`, `premium`, `link`, `images`),
`count`, and `caveats` (the feed mixes in other leagues' stories).

## Not supported

Not supported by this module: team/player statistics (the ESPN team statistics endpoint returned 404
when checked), win probability (absent from the summary checked), leaders, injuries, transactions,
futures, depth charts, and NBA CDN / NBA Stats data. Data is ESPN's cached feed, not guaranteed real-time.

## Input validation

`team_id` and `event_id` must be ASCII digits (string or int, not bool); `date` must be a real
`YYYY-MM-DD` date. Invalid input returns an error before any request. A summary whose header does not
identify the requested game is an error, not an empty success.
