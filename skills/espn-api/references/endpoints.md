# ESPN API Endpoint Catalog

Complete reference of every ESPN API endpoint organized by domain and resource type.

## Site API v2 (Scores, Teams, News)

**Pattern:** `https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/{resource}`

### Scoreboard & Schedule

| Endpoint | Description |
|----------|-------------|
| `scoreboard` | Live and scheduled events with scores |
| `scoreboard?dates={YYYYMMDD}` | Scores for a specific date |
| `scoreboard?dates={YYYYMMDD}-{YYYYMMDD}` | Scores for a date range |
| `scoreboard?week={n}&seasontype={t}` | Scores by week (football) |
| `summary?event={id}` | Full game summary: boxscore, plays, leaders, broadcasts |
| `calendar` | Full season calendar |
| `calendar/offseason` | Offseason date range |
| `calendar/regular-season` | Regular season weeks |
| `calendar/postseason` | Postseason date ranges |

### Teams

| Endpoint | Description |
|----------|-------------|
| `teams` | All teams in the league |
| `teams/{id}` | Single team detail |
| `teams/{id}/roster` | Team roster with player details |
| `teams/{id}/schedule` | Team schedule |
| `teams/{id}/record` | Team win/loss record |
| `teams/{id}/depthcharts` | Depth chart by position |
| `teams/{id}/injuries` | Team injury report |
| `teams/{id}/transactions` | Recent team transactions/moves |
| `teams/{id}/history` | Franchise historical record |
| `teams/{id}/news` | Team news |
| `teams/{id}/leaders` | Team statistical leaders |

### Athletes

| Endpoint | Description |
|----------|-------------|
| `athletes/{id}` | Individual athlete profile |
| `athletes/{id}/gamelog` | Game-by-game log |
| `athletes/{id}/splits` | Statistical splits |
| `athletes/{id}/news` | Athlete news |
| `athletes/{id}/bio` | Athlete bio |

### League-Wide Data

| Endpoint | Description |
|----------|-------------|
| `injuries` | League-wide injury report (all teams). Works for NBA, NFL, NHL, MLB, Soccer. Returns 500 for MMA, Tennis, Golf. |
| `transactions` | Recent signings, trades, waivers |
| `groups` | Conferences and divisions |
| `news` | Latest news articles |
| `rankings` | Poll rankings (college sports only) |
| `standings` | **Returns stub only.** Use `/apis/v2/` path instead (see below) |
| `statistics` | League statistical leaders |
| `draft` | Draft board (NBA only) |

---

## Standings (Special Path)

**The `/apis/site/v2/` standings endpoint returns only a stub.** Use this path instead:

```
https://site.api.espn.com/apis/v2/sports/{sport}/{league}/standings
```

Optional params: `?season={year}`

---

## Site API v3 (Enriched Scoreboard)

**Pattern:** `https://site.api.espn.com/apis/site/v3/sports/{sport}/{league}/{resource}`

| Endpoint | Description |
|----------|-------------|
| `scoreboard` | Scoreboard with enriched v3 schema |
| `summary?event={id}` | Enriched game summary (v3 schema) |

---

## Core API v2 (Athletes, Stats, Events, Odds)

**Pattern:** `https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}/{resource}`

### Athletes

| Endpoint | Description |
|----------|-------------|
| `athletes` | Full athlete list with pagination (`?limit=100&page=1`) |
| `athletes?active=true` | Active athletes only |
| `athletes/{id}` | Single athlete profile |
| `athletes/{id}/statistics` | Career statistics |
| `athletes/{id}/statisticslog` | Game-by-game stats log |
| `athletes/{id}/eventlog` | Event history |
| `athletes/{id}/contracts` | Contract info |
| `athletes/{id}/awards` | Awards |
| `athletes/{id}/seasons` | Seasons played |
| `athletes/{id}/records` | Career records |
| `athletes/{id}/hotzones` | Hot zones (baseball) |
| `athletes/{id}/injuries` | Athlete injury history |
| `athletes/{id}/vsathlete/{opponentId}` | Head-to-head stats |

### Events & Games

| Endpoint | Description |
|----------|-------------|
| `events` | All events with pagination |
| `events?dates={YYYYMMDD}` | Events on a specific date |
| `events/{id}` | Single event detail |
| `events/{id}/competitions/{id}/odds` | Betting odds (spread, moneyline, over/under) |
| `events/{id}/competitions/{id}/odds?provider.priority={n}` | Filter by sportsbook |
| `events/{id}/competitions/{id}/probabilities` | Win probabilities |
| `events/{id}/competitions/{id}/plays` | Play-by-play data |
| `events/{id}/competitions/{id}/plays?limit=400` | All plays (increase limit) |
| `events/{id}/competitions/{id}/situation` | Current game situation (down/distance/possession) |
| `events/{id}/competitions/{id}/broadcasts` | Broadcast network info |
| `events/{id}/competitions/{id}/predictor` | ESPN game predictor |
| `events/{id}/competitions/{id}/powerindex` | ESPN Power Index for game |
| `events/{id}/competitions/{id}/officials` | Game officials |
| `events/{id}/competitions/{id}/competitors/{id}/linescores` | Period-by-period scores |
| `events/{id}/competitions/{id}/competitors/{id}/statistics` | Competitor stats |

**Note:** `competition_id` is usually the same as `event_id`.

### Seasons

| Endpoint | Description |
|----------|-------------|
| `seasons` | Season list |
| `seasons/{year}` | Season detail |
| `seasons/{year}/teams` | Teams in a season |
| `seasons/{year}/athletes` | Athletes for a season |
| `seasons/{year}/coaches` | Coaching staff |
| `seasons/{year}/draft` | Draft data |
| `seasons/{year}/futures` | Futures odds |
| `seasons/{year}/freeagents` | Free agents |
| `seasons/{year}/powerindex` | Season-level Power Index / BPI |
| `seasons/{year}/powerindex/leaders` | Power Index leaders |
| `seasons/{year}/powerindex/{teamId}` | Power Index by team |

### Standings, Leaders, Rankings

| Endpoint | Description |
|----------|-------------|
| `standings` | League standings |
| `leaders` | Statistical leaders |
| `rankings` | Rankings |

### Teams, Venues, Coaches

| Endpoint | Description |
|----------|-------------|
| `teams` | All teams (detailed, with pagination) |
| `teams/{id}` | Single team detail |
| `venues` | Venues/stadiums |
| `franchises` | Franchise history |
| `coaches` | All coaches |
| `coaches/{id}` | Individual coach profile |
| `coaches/{id}/record/{type}` | Coaching record by type |

### Betting

| Endpoint | Description |
|----------|-------------|
| `seasons/{year}/futures` | Season futures |
| `seasons/{year}/types/{type}/teams/{id}/ats` | ATS records |
| `seasons/{year}/types/{type}/teams/{id}/odds-records` | Team odds records |

### Specialized (Football Only)

| Endpoint | Description |
|----------|-------------|
| `seasons/{year}/types/{type}/groups/{group}/qbr/{split}` | ESPN QBR by season |
| `seasons/{year}/types/{type}/weeks/{week}/qbr/{split}` | ESPN QBR by week |

QBR `split` values: `0` = totals, `1` = home, `2` = away

### Other

| Endpoint | Description |
|----------|-------------|
| `positions` | Position definitions |
| `countries` | Countries |
| `providers` | Data providers |
| `franchises` | Franchise data |
| `tournaments` | Tournament data |
| `recruiting` | Recruiting data (college) |
| `season` | Current season info |

---

## Core API v3 (Enriched Schema)

**Pattern:** `https://sports.core.api.espn.com/v3/sports/{sport}/{league}/{resource}`

| Endpoint | Description |
|----------|-------------|
| `athletes` | Athletes with enriched data |
| `athletes?active=true&limit=1000` | All active athletes |
| `athletes/{id}` | Single athlete (enriched) |
| `athletes/{id}/statisticslog` | Game log (enriched) |
| `athletes/{id}/plays` | Athlete play history |
| `leaders` | Statistical leaders |

---

## Web API v3 (Player Stats, Gamelogs, Splits)

**Pattern:** `https://site.web.api.espn.com/apis/common/v3/sports/{sport}/{league}/{resource}`

These endpoints return the richest player statistical data. Confirmed working for NFL, NBA, NHL, MLB. Soccer has limited support.

| Endpoint | Description |
|----------|-------------|
| `athletes/{id}/overview` | Stats snapshot, next game, rotowire notes, recent news |
| `athletes/{id}/stats` | Full season stats with categories, labels, glossary |
| `athletes/{id}/stats?season={year}&seasontype={type}` | Stats for specific season |
| `athletes/{id}/gamelog` | Game-by-game log with stats per game |
| `athletes/{id}/gamelog?season={year}` | Gamelog for specific season |
| `athletes/{id}/splits` | Home/away/opponent splits |
| `athletes/{id}/splits?season={year}&seasontype={type}` | Splits for specific season |
| `statistics/byathlete` | Ranked leaderboard across all athletes |
| `statistics/byathlete?category={cat}&sort={field}:desc` | Filtered/sorted leaderboard |

### Search

| Endpoint | Description |
|----------|-------------|
| `/apis/search/v2?query={q}&limit={n}` | Global ESPN search |
| `/apis/search/v2?query={q}&sport={sport}` | Sport-scoped search |

### Scoreboard Header

| Endpoint | Description |
|----------|-------------|
| `/apis/v2/scoreboard/header` | Scoreboard header/nav state |

---

## CDN API (Full Game Packages)

**Pattern:** `https://cdn.espn.com/core/{sport}/{view}?xhr=1&gameId={id}`

**The `?xhr=1` parameter is REQUIRED** to get JSON instead of HTML.

| View | Description |
|------|-------------|
| `game` | Full game package: boxscore, plays, drives, win probability, odds, scoring |
| `boxscore` | Box score only |
| `playbyplay` | Play-by-play only |
| `matchup` | Matchup comparison |
| `scoreboard` | CDN-optimized live scoreboard |

For soccer scoreboards, add `&league={slug}` (e.g., `&league=eng.1`).

The CDN `sport` slug is the league abbreviation in lowercase (e.g., `nba`, `nfl`, `mlb`, `college-football`), not the sport category.

The response contains a `gamepackageJSON` key with all game data.

---

## Now API (Real-Time News)

**Pattern:** `https://now.core.api.espn.com/v1/sports/news`

| Parameter | Description |
|-----------|-------------|
| `?limit={n}` | Number of articles (max 50) |
| `?sport={sport}` | Filter by sport |
| `?leagues={league}` | Filter by league |
| `?team={abbrev}` | Filter by team abbreviation |
| `?offset={n}` | Pagination offset |

---

## Global / Cross-Sport Endpoints

These are not sport-scoped.

### Discovery (v2)

| Endpoint | Description |
|----------|-------------|
| `https://sports.core.api.espn.com/v2/sports` | List all sports |
| `https://sports.core.api.espn.com/v2/ontology/leagues?limit=500` | All leagues cross-sport |
| `https://sports.core.api.espn.com/v2/ontology/teams?limit=500` | All teams cross-sport |

### Discovery (v3)

| Endpoint | Description |
|----------|-------------|
| `https://sports.core.api.espn.com/v3/sports` | All sports |
| `https://sports.core.api.espn.com/v3/leagues?limit=500` | All leagues |
| `https://sports.core.api.espn.com/v3/teams?limit=1000` | All teams |
| `https://sports.core.api.espn.com/v3/teams/{teamId}` | Team by ID |
| `https://sports.core.api.espn.com/v3/athletes/{athleteId}` | Athlete by ID |
| `https://sports.core.api.espn.com/v3/coaches/{coachId}` | Coach by ID |
| `https://sports.core.api.espn.com/v3/events?limit=100&dates={YYYYMMDD}` | Events by date |
| `https://sports.core.api.espn.com/v3/events/{eventId}` | Event by ID |

### Bracketology (NCAA Tournament)

| Endpoint | Description |
|----------|-------------|
| `.../v2/tournament/{tournamentId}/seasons/{year}/bracketology` | Live bracket projections |
| `.../v2/tournament/{tournamentId}/seasons/{year}/bracketology/{iteration}` | Bracket at specific iteration |

Common tournament IDs: `22` = NCAA Men's, `23` = NCAA Women's

### Recruiting (College)

| Endpoint | Description |
|----------|-------------|
| `.../seasons/{year}/recruits` | Recruit rankings by year |
| `.../seasons/{year}/classes/{teamId}` | Recruiting class by team |

---

## Fantasy Sports API

**Base URL:** `https://fantasy.espn.com/apis/v3/games/{sport_code}/seasons/{year}`

### Sport Codes

| Sport | Code |
|-------|------|
| Football | `ffl` |
| Basketball | `fba` |
| Baseball | `flb` |
| Hockey | `fhl` |

### League Endpoints

```
GET /apis/v3/games/{code}/seasons/{year}/segments/0/leagues/{league_id}
```

Views (append as `?view=`): `mTeam`, `mRoster`, `mMatchup`, `mMatchupScore`, `mSettings`, `mDraftDetail`, `mScoreboard`, `mStandings`, `mStatus`, `kona_player_info`

Segments: `0` = entire season, `1` = playoff round 1, `2` = round 2, `3` = championship

**Private leagues** require cookies: `espn_s2` and `SWID`
