# NFL Data — API Reference

## Commands

### get_scoreboard
Get live/recent NFL scores.
- `date` (str, optional): Date in YYYY-MM-DD format
- `week` (int, optional): Week number (1-18 regular season, 19-23 postseason)
- `season` (int, optional): Season year for `week` (e.g. 2024). Defaults to current; ignored with `date`.

Returns `events[]` with game info, scores, status, and competitors.

### get_standings
Get NFL standings by conference and division.
- `season` (int, optional): Season year

Returns `groups[]` with AFC/NFC conferences, divisions, and team standings including W-L-T, PCT, PF, PA.

### get_teams
Get all 32 NFL teams. No parameters.

Returns `teams[]` with id, name, abbreviation, logo, location, `conference` (e.g. `"AFC"`) and `division` (e.g. `"AFC East"`).

### get_team_roster
Get full roster for a team.
- `team_id` (str, required): ESPN team ID (e.g., "12" for Chiefs)

Returns `athletes[]` with name, position, jersey number, height, weight, experience.

### get_team_schedule
Get schedule for a specific team.
- `team_id` (str, required): ESPN team ID
- `season` (int, optional): Season year

Returns `events[]` with opponent, date, score (if played), and venue.

### get_game_summary
Get detailed box score and scoring plays.
- `event_id` (str, required): ESPN event ID

Returns `game_info`, `competitors`, `boxscore` (passing/rushing/receiving stats), `scoring_plays`, and `leaders`.

### get_leaders
Get NFL statistical leaders (passing, rushing, receiving).
- `season` (int, optional): Season year

Returns `categories[]` with leader rankings per stat category.

### get_news
Get NFL news articles.
- `team_id` (str, optional): Filter by team

Returns `articles[]` with headline, description, published date, and link, plus `count` and `total_articles`.

With `team_id`, articles are matched on ESPN's own team tags (`categories[]` of type `team`), not on the headline text — a league-wide story that covers the team is included, and a story that merely names it is not. `total_articles` is the unfiltered count. A malformed or unserved response is an error, distinct from a genuine empty feed (`count: 0`).

### get_game_summary odds
`get_game_summary` now returns an `odds` block (home/away American moneyline, `provider`, `line` = close/current/open, `captured_at: null` — ESPN publishes no capture time) and `game_info.start_time`. Both sides always come from one bookmaker; `odds` is `null` when no provider published a complete pair.

### get_play_by_play
Get full play-by-play data for a game.
- `event_id` (str, required): ESPN event ID

Returns `drives[]` with play-by-play detail including down, distance, yard line, play description, and scoring plays.

### get_win_probability
Get win probability chart data for a game.
- `event_id` (str, required): ESPN event ID

Returns timestamped home/away win probability percentages throughout the game.

### get_schedule
Get NFL season schedule by week.
- `season` (int, optional): Season year
- `week` (int, optional): Week number (1-18 regular season, 19-23 postseason)

Returns `events[]` for the specified week/season.

### get_injuries
Get current NFL injury reports across all teams. No parameters.

Returns `teams[]` with per-team injury lists including player name, position, status (Out/Doubtful/Questionable/Day-To-Day), injury type, and detail.

### get_transactions
Get recent NFL transactions (trades, signings, waivers).
- `limit` (int, optional): Max transactions to return. Defaults to 50.

Returns `transactions[]` with date, team, and description.

### get_futures
Get NFL futures/odds markets (Super Bowl winner, MVP, etc.).
- `limit` (int, optional): Max entries per market. Defaults to 10.
- `season_year` (int, optional): Season year. Defaults to current.

Returns `futures[]` with market name and entries (team/player name + odds value). Each market reports one provider: the group with usable entries and the lowest finite numeric priority. Numeric strings are accepted; missing/invalid priorities rank after numeric priorities, and ties use ESPN response order. `provider` is included only when the selected group has a name.

### get_depth_chart
Get depth chart for a specific team.
- `team_id` (str, required): ESPN team ID

Returns `charts[]` with offense/defense/special teams positions and player depth order.

### get_team_stats
Get full team statistical profile for a season.
- `team_id` (str, required): ESPN team ID
- `season_year` (int, optional): Season year. Defaults to current.
- `season_type` (int, optional): 1=preseason, 2=regular (default), 3=postseason.

Returns `categories[]` (Passing, Rushing, Receiving, etc.) with detailed stats including value, rank, and per-game averages.

### get_player_stats
Get full player statistical profile for a season.
- `player_id` (str, required): ESPN athlete ID
- `season_year` (int, optional): Season year. Defaults to current.
- `season_type` (int, optional): 1=preseason, 2=regular (default), 3=postseason.

Returns `categories[]` with detailed stats including value, rank, and per-game averages.

### get_nflverse_schedule
Get schedules/results through the nflverse backend.
- `season` (int, optional): Season year
- `week` (int, optional): NFL week filter
- `sort_by` (str, optional): Column to sort by, e.g. `total`. Numeric-aware; missing values last
- `descending` (bool, optional): Sort direction with `sort_by`; default `true`
- `limit` (int, optional): Max rows to return, applied after `sort_by`
- `fields` (str, optional): Comma-separated columns to keep; always keeps `game_id`, `week`, `away_team`, `home_team`

Returns `events[]` with `game_id`, teams, scores, date/time, line fields, and location.

Cross-provider identifiers on each event:
- `espn_event_id` — the ESPN event ID for the same game. Pass it as `event_id` to `get_game_summary`, `get_play_by_play`, or `get_win_probability`.
- `pfr_game_id`, `gsis_game_id` — Pro-Football-Reference and GSIS identifiers.

Score vs. market fields: `total` is the combined points actually scored; `total_line` is the betting over/under. `result` is the home margin, `spread_line` the closing spread.

### get_nflverse_weekly_rosters
Get weekly roster snapshots through the nflverse backend.
- `season` (int, optional): Season year
- `week` (int, optional): NFL week filter
- `team` (str, optional): Team abbreviation filter (e.g. `KC`)
- `sort_by` (str, optional): Column to sort by, e.g. `weight`. Numeric-aware; missing values last
- `descending` (bool, optional): Sort direction with `sort_by`; default `true`
- `limit` (int, optional): Max rows to return, applied after `sort_by`
- `fields` (str, optional): Comma-separated columns to keep; always keeps `player_id`, `player_name`, `team`, `position`

Returns `players[]` with normalized roster fields: team, player_id, player_name, position, jersey_number, status, college, and experience fields when available.

### get_nflverse_player_stats
Get normalized nflverse player stat rows. **Returns regular-season totals by default.**
- `season` (int, optional): Season year
- `player_id` (str, optional): nflverse/GSIS player identifier
- `team` (str, optional): Team abbreviation filter
- `position` (str, optional): Position filter
- `week` (int, optional): NFL week filter. Implies per-game rows.
- `summary_level` (str, optional): `reg` (default), `post`, `reg+post`, or `week`
- `sort_by` (str, optional): Column to sort by, e.g. `passing_yards`. Numeric-aware; missing values last
- `descending` (bool, optional): Sort direction with `sort_by`; default `true`
- `limit` (int, optional): Max rows to return, applied after `sort_by`
- `fields` (str, optional): Comma-separated columns to keep; always keeps `player_id`, `player_name`, `position`, `team`, `week`

Returns `players[]`, each with identity fields (`player_id`, `player_name`, `position`, `team`) plus a `stats` object containing backend columns (completions, passing_yards, passing_tds, rushing_yards, etc.). Season aggregates include `games`; only `summary_level="week"` rows carry `week`, `game_id`, and `opponent_team`.

### get_nflverse_team_stats
Get normalized nflverse team stat rows. **Returns regular-season totals by default.**
- `season` (int, optional): Season year
- `team` (str, optional): Team abbreviation filter
- `week` (int, optional): NFL week filter. Implies per-game rows.
- `summary_level` (str, optional): `reg` (default), `post`, `reg+post`, or `week`
- `sort_by` (str, optional): Column to sort by, e.g. `passing_yards`. Numeric-aware; missing values last
- `descending` (bool, optional): Sort direction with `sort_by`; default `true`
- `limit` (int, optional): Max rows to return, applied after `sort_by`
- `fields` (str, optional): Comma-separated columns to keep; always keeps `team`, `season`, `week`, `game_id`

Returns `teams[]`, each with team/season context plus a `stats` object containing backend columns. Requires the `nflreadpy` backend (Python 3.10+); on `nfl_data_py` this returns an explanatory error, because that backend has no team-stat table.

### get_nflverse_play_by_play
Get normalized nflverse play-by-play rows.
- `season` (int, optional): Season year
- `week` (int, optional): Week filter
- `team` (str, optional): Team abbreviation filter
- `game_id` (str, optional): nflverse game identifier
- `limit` (int, optional): Max rows to return, applied after `sort_by`
- `sort_by` (str, optional): Column to sort by, e.g. `epa`. Numeric-aware; missing values last
- `descending` (bool, optional): Sort direction with `sort_by`; default `true`
- `fields` (str, optional): Comma-separated columns to keep; always keeps `play_id`, `game_id`

Returns `plays[]` with game/play identifiers, quarter/clock, teams, down/distance, description, EPA, WP/WPA, and score state.

Notes:
- `sort_by`/`limit`/`fields` apply after the fetch. When any is set the response adds `total_rows` (before `limit`) and `returned_rows`; an unknown column returns an error listing the valid ones. Stat columns inside `stats` are addressable by name.
- The nflverse backend requires the `[nfl]` optional extra: `pip install sports-skills[nfl]`. On Python 3.10+ this installs `nflreadpy` (preferred); on Python 3.9 it installs `nfl_data_py`, which cannot serve `get_nflverse_team_stats`.
- These commands keep `nfl-data` as the user-facing skill while exposing table-style datasets under the same module.
- The ESPN-backed commands (e.g. `get_scoreboard`, `get_standings`) work with zero extra dependencies. The nflverse commands provide deeper historical/analytical data (seasonal aggregates, EPA, win probability per play) but require the optional install.
- Parquet support (`pyarrow` or `fastparquet`) is needed for most nflverse data beyond schedules.
- Team abbreviations: the `team` filters accept ESPN spellings (`LAR`, `WSH`) and translate them to nflverse's (`LA`, `WAS`). A `team` filter that matches nothing returns a `warnings[]` entry rather than a silently empty list.
- Player IDs are not portable between the two backends: ESPN athlete IDs and nflverse GSIS IDs (`00-0033873`) are unrelated and there is no crosswalk. Match on name plus team.

### get_fantasy_trending
Get NFL players trending in Sleeper fantasy adds or drops. Public Sleeper API, no key.
- `trend_type` (str, optional): `add` (default) or `drop`
- `lookback_hours` (int, optional): Lookback window in whole hours, 1-168. Default 24
- `limit` (int, optional): Players to return, 1-100. Default 10

Booleans, floats (even `24.0`) and out-of-range values return an error before any request is made. Digit strings (`"48"`) are accepted.

Upstream:
- `GET https://api.sleeper.app/v1/players/nfl/trending/{add|drop}?lookback_hours=<h>&limit=<n>` — rows of `{player_id, count}`
- `GET https://api.sleeper.app/v1/players/nfl` — the player catalog used to resolve names, keyed by Sleeper player ID

Returns:
```json
{
  "provider": "sleeper",
  "sport": "nfl",
  "trend_type": "add",
  "lookback_hours": 24,
  "limit": 10,
  "players": [
    {
      "rank": 1,
      "sleeper_player_id": "90001",
      "name": "Example Player",
      "name_resolved": true,
      "team": "KC",
      "position": "RB",
      "count": 12345
    }
  ],
  "count": 1,
  "unresolved_count": 0,
  "catalog_status": "loaded",
  "source": {
    "trending_url": "https://api.sleeper.app/v1/players/nfl/trending/add?lookback_hours=24&limit=10",
    "trending_fetched_at": "2026-10-05T12:00:00Z",
    "players_url": "https://api.sleeper.app/v1/players/nfl",
    "players_fetched_at": "2026-10-05T08:00:00Z"
  },
  "note": "count is the add/drop tally Sleeper's trending API reports ..."
}
```

Notes:
- `count` (per player) is the add/drop tally Sleeper's trending API reports for the window, passed through as given — popularity among Sleeper users, not a projection, ranking, or betting edge. Top-level `count` is the number of rows.
- `sleeper_player_id` is Sleeper's ID; keep it as the identifier. No ESPN or nflverse ID is attached, none should be inferred, and a name or team match against another provider is not a confirmed identity.
- `name_resolved: false` means the catalog had no name for that ID; it is listed in `warnings[]`. `team` and `position` are resolved independently, so they can still be set when `name` is null; all three are null when the ID is missing from the catalog. Free agents have `team: null`.
- `catalog_status`: `loaded`, `unavailable` (catalog fetch failed or changed shape; every row is unresolved and `warnings[]` gives the reason), or `not_needed` (no trending rows).
- Caching: trending results are cached in memory for 5 minutes, per process only (each CLI call re-fetches them). The player catalog, trimmed to IDs, names, teams and positions, is cached in memory and on disk at `$XDG_CACHE_HOME/sports-skills/sleeper/players-nfl.json` (default `~/.cache/sports-skills/sleeper/`), so separate processes share it until 24 hours after it was fetched (Sleeper asks for at most one catalog fetch a day). Expired, future-dated, corrupt or unreadable cache files are ignored and the catalog is fetched again. Disk writes are best effort: a write failure does not fail the call, and the next process simply re-fetches. The `*_fetched_at` timestamps are when the data was fetched, so they stay the same on a cache hit. With `SPORTS_SKILLS_REPLAY` set, the memory and disk caches are neither read nor written, so every request is recorded or replayed, and a warning notes that `fetched_at` is the replay time.
- Errors: HTTP failures (including 429 after retries), invalid JSON, or a trending payload that is not a list of `{player_id, count}` objects return `status: false` with a message naming the problem — never an empty success.

## Team IDs

| Team | ID | Team | ID |
|------|-----|------|-----|
| Cardinals | 22 | Rams | 14 |
| Falcons | 1 | Ravens | 33 |
| Bills | 2 | Bears | 3 |
| Panthers | 29 | Bengals | 4 |
| Cowboys | 6 | Browns | 5 |
| Broncos | 7 | Lions | 8 |
| Packers | 9 | Texans | 34 |
| Colts | 11 | Jaguars | 30 |
| Chiefs | 12 | Raiders | 13 |
| Chargers | 24 | Dolphins | 15 |
| Vikings | 16 | Patriots | 17 |
| Saints | 18 | Giants | 19 |
| Jets | 20 | Eagles | 21 |
| Steelers | 23 | 49ers | 25 |
| Seahawks | 26 | Buccaneers | 27 |
| Titans | 10 | Commanders | 28 |

Use `get_teams` for the complete, authoritative list.

## Week Numbers

Regular season: weeks 1-18. Postseason unified numbering: Wild Card=19, Divisional=20, Conference Championship=21, Pro Bowl=22, Super Bowl=23. The connector translates these to ESPN's internal `seasontype=3` automatically.
