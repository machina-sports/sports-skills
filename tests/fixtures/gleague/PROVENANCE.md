# G League fixtures: provenance

Captured from ESPN's public API (sport path `basketball/nba-development`,
league id 69) and saved by the PR author on 2026-10-29 UTC. Pruned by hand:
fields were removed, never edited or invented.

| File | Source URL | Pruning |
|------|------------|---------|
| `scoreboard_20260410.json` | `site.api.espn.com/apis/site/v2/sports/basketball/nba-development/scoreboard?dates=20260410` | Dropped `leagues[].calendar`/`logos`, competitor `statistics`/`leaders`, `series`, `geoBroadcasts`, `links`, `highlights`, dark logos. Event 401867657 (G League Finals Game 2) is otherwise intact. |
| `roster_team2_season2026.json` | `.../nba-development/teams/2/roster?season=2026` | Verbatim. ESPN really returns `athletes: []` for this request. |
| `standings_2026_east_excerpt.json` | `site.api.espn.com/apis/v2/sports/basketball/nba-development/standings?season=2026` | Eastern Conference only, 2 of its teams (WIS, LIN). Stats limited to the ones the normalizer reads; `links`, `seasons`, the Western Conference and the other teams were dropped. |
| `news_excerpt.json` | `.../nba-development/news` | 2 of 6 articles (the first, an NBL clip ESPN tags as G League, and the G League recap); `categories`, image metadata and extra link types dropped. |

Second capture (same day, pretty-printed pruned copies):

| File | Source URL | Pruning |
|------|------------|---------|
| `roster_team2_current.json` | `.../nba-development/teams/2/roster` (no season) | 2 of 10 athletes; `links`, `alternateIds`, `guid`, `teams` refs, `hand`, college logos dropped. ESPN labels it season 2027 (2026-27 preseason). |
| `teams_excerpt.json` | `.../nba-development/teams` | 2 teams (AUS, CAP); logos cut to the default one. |
| `schedule_team2_2026_tournament_excerpt.json` | `.../nba-development/teams/2/schedule?season=2026&seasontype=5` | Both rows kept as captured minus logos, leaders, broadcasts, links, competition `type`. Envelope `season` is 2027 while `requestedSeason` is 2026 — as ESPN sent it. |

Source validation facts (same capture): `teams/2/schedule?season=2026` returned
36 events for `seasontype=2`, 1 for `3`, 14 for `5` ("Tip-Off Tournament");
every schedule row carries its own `seasonType`. The current roster for team 2
had 10 athletes and team 24 had 19, while `?season=2026` returned none.
`teams/2/statistics` returned HTTP 404. `cdn.nba.com/.../todaysScoreboard_20.json`
did not return JSON, so no G League CDN coverage is claimed.

`summary_401867657_excerpt.json`: generated directly from the live sample of
https://site.api.espn.com/apis/site/v2/sports/basketball/nba-development/summary?event=401867657,
captured 2026-10-29 UTC. Retained `header`, `gameInfo`, `leaders` and `boxscore`;
`plays` cut to the first 3 and each boxscore athlete table to its first 2 athletes;
`logos`, `links`, `headshot`, `logo`, `href`, `images`, `uid` and `$ref` omitted
recursively. Values untouched. The synthetic summary in `tests/test_gleague.py`
(labelled `SYNTHETIC`) remains for edge cases such as a scoring play.
