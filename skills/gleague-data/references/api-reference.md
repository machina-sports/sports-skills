# NBA G League Data — API Reference

Sources:
- ESPN public API, sport path `basketball/nba-development` (ESPN league id 69): `get_teams` … `get_news`.
- NBA Stats (stats.nba.com) with `LeagueID=20`: `find_nba_player`, `get_nbastats_*`.
- The G League live CDN (cdn-gleague.nba.com): `get_live_boxscore`, `get_live_playbyplay`.

Every command returns `{"status": bool, "data": ..., "message": str}`; failures have
`status: false`, a readable `message`, and `status_code` when ESPN or the CDN sent one. An empty
result (no games that day, an empty roster, an empty stats table) is `status: true` with an empty list.

## IDs and seasons

- ESPN commands: team ids are ESPN **G League** ids and overlap NBA ids (`2` = Austin Spurs here,
  Boston Celtics in the NBA); event ids are ESPN event ids (e.g. `401867657`); `season` is the
  **ending** year (2025-26 = `2026`).
- Official commands: game ids are 10 ASCII digits starting with `20` (e.g. `2022500001`; the third
  digit is the phase, 2 regular / 4 playoffs / 5 Showcase); player ids are NBA.com person ids
  (e.g. `1630644`); `season` is the **starting** year (2025-26 = `2025` or `"2025-26"`), as in `nba-data`.

## ESPN commands

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

## NBA Stats commands (stats.nba.com, `LeagueID=20`)

Same parameters and row shapes as the `nba-data` commands of the same name. Every response carries
`provider: "nba-stats"` and `league_id: "20"`. Rows keep NBA Stats' lowercase column names, and
numeric zeros are kept. Unlike `nba-data`, rows carry no `team_abbreviation_espn`: G League
tricodes (`WCB`, `RAP`, …) have no verified ESPN spelling, and team filters never translate NBA
spellings (`GS` matches nothing here).

Shared params:
- `season`: starting year or `"YYYY-YY"`; defaults to the current season.
- `season_type`: `regular` (default) / `2`, `playoffs` / `4`, `preseason` / `1`, or
  `showcase` / `Showcase Cup` / `tournament` (sent as the verified upstream value `Showcase`).
  `playin` / `5` are rejected to avoid confusing G League tournaments with the NBA play-in.
- `sort_by`, `descending`, `limit`, `fields`: optional row shaping. Responses then add `total_rows`
  and `returned_rows`.

A response for another league, a missing or malformed result table, or a row from a non-G League
game is an error. stats.nba.com throttles by letting requests time out; that error says to wait.

### find_nba_player
- `name` (required). Searches the G League registry (`commonallplayers`). Returns `players[]`
  (`player_id`, `name`, `is_active`, `team`, `from_year`, `to_year`), `query`, `count`.

### get_nbastats_game_log
- `season`, `season_type`, `team` (G League abbreviation), `player_or_team` (`team` default),
  `player` (name or person id; implies player rows), shaping params.

Team rows (`leaguegamelog`): `season_id`, `team_id`, `team_abbreviation`, `team_name`, `game_id`,
`game_date`, `matchup`, `wl`, `min`, shooting splits, rebounds, `ast`, `stl`, `blk`, `tov`, `pf`,
`pts`, `plus_minus`. Player rows (`playergamelog`) add `player_id`, ISO `game_date`, `opponent`,
`home_away`, in date order, plus top-level `player_id` / `player` when one player is selected.
`player_or_team="player"` without `player` returns league-wide player rows from `leaguegamelog`.

### get_nbastats_player_career
- `player_id` or `player`, `per_mode` (`totals` default, `per_game`, `per_36`).

Returns `seasons[]` (the `SeasonTotalsRegularSeason` table; a `TOT` row follows a mid-season
team change) and `career_totals` (`CareerTotalsRegularSeason`, or null). College, Showcase and
playoff tables in the same response are not returned.

### get_nbastats_team_stats
- `season`, `season_type`, `measure` (`base` default, `advanced`, `four_factors`, `misc`, `scoring`,
  `opponent`, `defense`), `per_mode`, `team`, shaping params.

Returns `teams[]` (`leaguedashteamstats` columns plus `team_abbreviation`). The abbreviation comes
from the same season's G League game log (a second, cached request) and is null for a team without
game-log rows. `team` matches a G League abbreviation, the official team name, or the NBA.com team id.
Only `measure=base` with `per_mode=per_game` was captured.

### get_nbastats_shot_chart
- `player_id` or `player`, `season`, `season_type`, shaping params.

Returns `shots[]` (`game_id`, `game_date`, `period`, `minutes_remaining`, `seconds_remaining`,
`action_type`, `shot_type`, `shot_zone`, `shot_area`, `shot_distance`, `loc_x`, `loc_y`, `made`);
`truncated` and a warning when `limit` cut rows.

### get_nbastats_play_by_play
- `game_id` (required, official `20…` id), `limit`.

Returns `plays[]` (`action_number`, `period`, `clock`, `team`, `player`, `action_type`, `sub_type`,
`description`, `score_home`, `score_away`, `shot_value`, `loc_x`, `loc_y`). A response naming another
game is an error.

### get_nbastats_advanced_boxscore
- `game_id` (required).

Returns `home` / `away` (`team_id`, `team`, `team_name`, `stats`, `players[]` with `player_id`,
`name`, `position`, `minutes`, `stats` holding the ratings, pace, usage and PIE as sent).

### get_nbastats_leaders
G League only; `nba-data` has no equivalent.
- `season`, `season_type`, `per_mode` (`per_game` default, `totals`, `per_36`), `stat_category`
  (`PTS` default; also `REB`, `AST`, `STL`, `BLK`, `TOV`, `EFF`, `MIN`, `OREB`, `DREB`, `FGM`, `FGA`,
  `FG_PCT`, `FG3M`, `FG3A`, `FG3_PCT`, `FTM`, `FTA`, `FT_PCT`), shaping params.

Returns `leaders[]` (`player_id`, `rank`, `player`, `team`, `gp`, `min`, shooting splits, `reb`,
`ast`, `stl`, `blk`, `tov`, `pts`, `eff`), `stat_category`, `per_mode`. Only `PTS` per game was
captured.

## Live CDN commands (cdn-gleague.nba.com)

Same shape as the `nba-data` commands of the same name, plus `provider: "nba-cdn"` and
`league_id: "20"`. One request with the standard project CDN headers and no retry. A refusal
(HTTP 403/429) or a payload for another game is an error, never replaced by ESPN data. The shape is
tested against archived captures of this CDN; access from a given host and live freshness are not
guaranteed. There is no `get_live_scoreboard`: the CDN schedule answered HTTP 403 when checked.

### get_live_boxscore
- `game_id` (required).

Returns `game_info` (`id`, `game_code`, `status`, `status_text`, `period`, `game_clock`,
`game_time_utc`) and `teams[]` (`team`, `home_away`, `score`, `period_scores`, `statistics`,
`players[]` with `points`, `rebounds`, `assists`, shooting splits as `"made-attempted"`, `minutes`,
`plus_minus`, `starter`, `on_court`).

### get_live_playbyplay
- `game_id` (required), `limit` (default 25), `scoring_only` (default false).

Returns `actions[]` most recent first (`action_number`, `period`, `clock`, `action_type`, `sub_type`,
`description`, `team_id`, `team_tricode`, `person_id`, `player_name`, `score_home`, `score_away`,
`is_field_goal`, `scoring_play`, optional `shot_result` / `points` / `shot_distance`), `count`, `order`.

## Not supported

Not supported by this module: ESPN team/player statistics (the ESPN team statistics endpoint returned
404 when checked; use the `get_nbastats_*` commands), win probability (absent from the summary checked),
injuries, transactions, futures, depth charts, a G League live scoreboard and an official CDN schedule.

## Input validation

`team_id` and `event_id` must be ASCII digits (string or int, not bool); `date` must be a real
`YYYY-MM-DD` date. Official `game_id`s must be 10 ASCII digits starting with `20`, and `player_id`s
ASCII digits. Invalid input returns an error before any request. A summary whose header does not
identify the requested game is an error, not an empty success.
