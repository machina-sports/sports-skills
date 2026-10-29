# Official-source G League fixtures

Excerpts of real responses used by `tests/test_gleague_official.py`. Rows and arrays were
pruned; every value that remains is unmodified.

## NBA Stats (stats.nba.com, `LeagueID=20`)

Retrieved live through this repo's existing `sports_skills.nba._stats._request` transport
(same headers, no retries) before the G League adapter was written. The full responses and
request parameters are kept outside the repo; classic endpoints echo their request in the
`parameters` block of each file. Base URL: `https://stats.nba.com/stats/<endpoint>`.

| File | Endpoint | Request | Pruning |
|---|---|---|---|
| `commonallplayers.json` | `commonallplayers` | `LeagueID=20, Season=2025-26, IsOnlyCurrentSeason=0` | Mac McClung's row plus the first 2 rows |
| `leaguegamelog.json` | `leaguegamelog` | `LeagueID=20, Season=2025-26, SeasonType=Regular Season, PlayerOrTeam=T` | first 3 rows |
| `leaguegamelog_players.json` | `leaguegamelog` | `LeagueID=20, Season=2025-26, SeasonType=Regular Season, PlayerOrTeam=P` | first 3 of 10,550 live rows |
| `leaguegamelog_showcase.json` | `leaguegamelog` | `LeagueID=20, Season=2025-26, SeasonType=Showcase, PlayerOrTeam=T` | first 3 of 434 live rows |
| `leaguedashteamstats.json` | `leaguedashteamstats` | `LeagueID=20, Season=2025-26, MeasureType=Base, PerMode=PerGame` | first 3 rows |
| `playercareerstats.json` | `playercareerstats` | `LeagueID=20, PlayerID=1630644, PerMode=PerGame` | first 3 rows per table |
| `playergamelog.json` | `playergamelog` | `LeagueID=20, PlayerID=1630644, Season=2025-26` | first 3 rows |
| `shotchartdetail.json` | `shotchartdetail` | `LeagueID=20, PlayerID=1630644, Season=2025-26` | first 3 rows per table |
| `leaders.json` | `leagueleaders` | `LeagueID=20, PerMode=PerGame, StatCategory=PTS, Season=2025-26` | first 3 rows (the source table had 297); note the singular `resultSet` |
| `playbyplayv3.json` | `playbyplayv3` | `GameID=2022500001` | first 3 actions |
| `boxscoreadvancedv3.json` | `boxscoreadvancedv3` | `GameID=2022500001` | first 2 players per team |

Caveats: `meta.time` in the v3 files is the server's timestamp, not a freshness claim. Only
the parameter sets above were verified; other `measure`, `per_mode`, `stat_category` and
`season_type` values use the same endpoints but were not captured. `SeasonType=Showcase Cup`
answered HTTP 400 when probed; the correct value `Showcase` succeeded and has its own fixture.

## G League live CDN (cdn-gleague.nba.com)

Not retrieved by this project. A request from our host for the CDN's `scheduleLeagueV2.json`
answered HTTP 403, and no further request was made. The two files below are excerpts of payloads captured by the
sportsdataverse hoopR maintainers on 2026-09-27 UTC (httr2 1.3.0) and published as public test
fixtures in https://github.com/sportsdataverse/hoopR under
`tests/testthat/fixtures/nba_live/{boxscore,playbyplay}_2052500034_gleague.json.gz`.

| File | Original URL | Original JSON bytes / md5 | Pruning |
|---|---|---|---|
| `boxscore_2052500034_gleague.json` | `https://cdn-gleague.nba.com/static/json/liveData/boxscore/boxscore_2052500034.json` | 32109 / `af0434e368b6661650e1933ab32df360` | first 2 players per team |
| `playbyplay_2052500034_gleague.json` | `https://cdn-gleague.nba.com/static/json/liveData/playbyplay/playbyplay_2052500034.json` | 437088 / `c2d9a85bd9a33daf979b3f051d20f903` | first 3 actions (of 595) |

Game `2052500034` is a 2025-26 G League game, Maine Celtics 75 @ Raptors 905 111 (2025-11-12).
These captures prove the payload shape the CDN served then; they do not show that the CDN is
reachable from any particular host today, or that a live game's data is fresh.
