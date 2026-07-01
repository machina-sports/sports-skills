# Cricket Data — API Reference

Two backends. ESPN provides live-ish series data; Cricsheet provides historical ball-by-ball data. They share no IDs except at the match level (Cricsheet `match_id` = ESPNcricinfo match ID).

## ESPN backend

Undocumented public ESPN endpoints — no auth, no API key. URL templates (`{seriesId}` is a numeric ESPN series ID from `get_series`, `{eventId}` a match ID):

- Active series header: `https://site.web.api.espn.com/apis/personalized/v2/scoreboard/header?sport=cricket`
- Scoreboard: `https://site.api.espn.com/apis/site/v2/sports/cricket/{seriesId}/scoreboard`
- Summary: `https://site.api.espn.com/apis/site/v2/sports/cricket/{seriesId}/summary?event={eventId}`
- News: `https://site.api.espn.com/apis/site/v2/sports/cricket/{seriesId}/news`

Status values are normalized through the shared `ESPN_STATUS_MAP` (e.g. `not_started`, `live`, `closed`); the raw ESPN status name passes through when unmapped.

### get_series
List currently-active cricket series.
- (no params)

Returns:
- `series[]` — each with `series_id`, `name`, `abbreviation`, `is_tournament` (bool), `event_count`, and `events[]`.
- Each event: `event_id`, `name`, `date`, `status`, `summary`.
- `count`.

Use the returned `series_id` for every other ESPN command. IDs are season-specific — never hardcode.

### get_scoreboard
Matches + scores + status for one series.
- `series_id` (str, required): ESPN series ID. Discover via `get_series`.
- `date` (str, optional): `YYYYMMDD` or `YYYY-MM-DD`. Defaults to the current window.

Returns:
- `series` — `series_id`, `name`, `abbreviation`.
- `events[]` — each with `event_id`, `name`, `short_name`, `date`, `description`, `status` (mapped), `status_detail`, `venue`, `note`, and `competitors[]`.
- Each competitor: `team_id`, `team`, `abbreviation`, `home_away`, `winner` (bool), `score` (e.g. `"161/5"`), and `innings[]`.
- Each innings linescore: `innings` (period number), `runs`, `wickets`, `overs`, `is_batting` (bool), `description` (e.g. `"161/5 (18/20 ov, target 156)"`).
- `count`.

### get_standings
Points table for a series, extracted from the scoreboard payload.
- `series_id` (str, required).

Returns:
- `series_id`.
- `standings[]` — each with `team_id`, `team`, `abbreviation`, and `stats` (a dict of stat-name → value, e.g. wins/losses/points/net run rate as published by ESPN).
- `count`.
- When no table is published (common for bilateral tours): `standings: []`, `count: 0`, and a `message` explaining it.

### get_game_summary
Full match detail. Fields are passed through largely as ESPN returns them.
- `series_id` (str, required).
- `event_id` (str, required): from `get_scoreboard` or `get_series`.

Returns: `event_id`, `series_id`, `header`, `game_info`, `notes[]`, `rosters[]`, `leaders[]`, `matchcards`, `article`.

### get_news
News articles for a series.
- `series_id` (str, required).

Returns: `header`, `articles[]` (each with `headline`, `description`, `published`, `type`, `link`), `count`.

## Cricsheet backend

Open data from cricsheet.org, distributed as per-competition zipped JSON files plus a player-registry CSV. License: **ODC-BY 1.0** — attribution required, so every response includes an `attribution` field (`"Data from Cricsheet (cricsheet.org), ODC-BY 1.0"`). Data covers **completed matches only** and lags live play by roughly a day.

Zip URL template: `https://cricsheet.org/downloads/{code}_json.zip`. Registry: `https://cricsheet.org/register/people.csv`.

### get_competitions
List supported competition codes.
- (no params)

Returns: `competitions[]` (each `code` + `name`), `count`, `attribution`. See `references/competitions.md` for the full table.

### get_matches
Completed matches for a competition, newest first.
- `competition` (str, required): Cricsheet code (e.g. `ipl`, `tests`).
- `season` (int, optional): start year. Prefix-matched, so `2020` matches Cricsheet's `"2020/21"`.

Returns: `competition`, `matches[]`, `count`, `attribution`, and `stale: true` if a stale cached copy was served.
- Each match: `match_id` (= ESPNcricinfo match ID), `date`, `teams[]`, `venue`, `city`, `season`, `match_type`, `gender`, `event` (tournament name), `winner`, `outcome` (raw outcome block).

### get_match_deliveries
Ball-by-ball deliveries for one match.
- `competition` (str, required).
- `match_id` (str, required): from `get_matches`.
- `innings` (int, optional): restrict to one innings (1–4).

Returns: `match` (same shape as a `get_matches` entry), `innings[]`, `attribution`, optional `stale`.
- Each innings: `innings` (number), `team`, `deliveries[]`, `count`.
- Each delivery: `over`, `ball`, `batter`, `bowler`, `non_striker`, `runs` (raw Cricsheet block, e.g. `{batter, extras, total}`), and — when present — `extras` and `wickets[]`.

### get_player_stats
Aggregate batting and bowling stats for one player across a competition.
- `competition` (str, required).
- `player` (str, required): **exact** Cricsheet name (resolve with `find_player`).
- `season` (int, optional): start year filter.

Returns: `player`, `competition`, `season`, `matches`, `batting`, `bowling`, `attribution`, optional `stale`.
- `batting`: `runs`, `balls`, `fours`, `sixes`, `dismissals`, `strike_rate`, `average` (`null` if never dismissed).
- `bowling`: `balls`, `runs_conceded`, `wickets`, `economy` (`null` if no balls bowled), `overs` (string like `"4.2"`).

Aggregation conventions:
- Batting balls faced **exclude wides** (no-balls are counted as faced).
- Bowling balls **exclude wides and no-balls**.
- Bowler concedes **batter runs + wides + no-balls** — not byes, leg-byes, or penalty runs.
- Wickets are credited to the bowler **only** for: bowled, caught, lbw, stumped, hit wicket, caught and bowled (run-outs etc. are not credited).
- `economy = runs_conceded / (balls / 6)`.
- Returns an error if the player name matches no match (names must match Cricsheet exactly).

### find_player
Search the player registry by case-insensitive name substring (matches both `name` and `unique_name`). Returns up to 25 results.
- `name` (str, required): substring (e.g. `kohli`).

Returns: `players[]`, `count`, `attribution`, optional `stale`.
- Each player: `cricsheet_id` (registry identifier), `name`, `unique_name`, `cricinfo_id` (ESPNcricinfo ID — bridges Cricsheet to ESPN match data).

## Cache behavior

- **ESPN**: in-memory cache, TTL ~120s (the active-series header is cached; per-series scoreboards via the shared ESPN request layer).
- **Cricsheet**: on-disk cache at `~/.cache/sports-skills/cricsheet/` (override base with `XDG_CACHE_HOME`). Competition zips live 24h; the player registry CSV lives 7 days. Downloads are atomic (`.tmp` then rename).
- **Stale fallback**: if a Cricsheet download fails but a previously cached copy exists, that copy is served and the response carries `stale: true`. If no cached copy exists, the response is an error dict.
