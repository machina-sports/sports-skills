---
name: espn-api
description: |
  Query ESPN's public API for live scores, standings, rosters, player stats, odds, play-by-play, injuries, transactions, news, and more across 17 sports and 139 leagues. Use when the user needs sports data from ESPN, wants to build a sports app, fetch scores or schedules, look up player or team stats, get betting odds, or pull any structured sports data. Triggers on mentions of ESPN, sports scores, standings, box scores, player stats, game data, or league data.

  Don't use when: a dedicated skill covers the league and the user just wants the data (use nba-data, wnba-data, nfl-data, nhl-data, mlb-data, cfb-data, cbb-data, football-data, golf-data, tennis-data, or cricket-data). Use this skill for leagues those skills do not cover (e.g. MMA, lacrosse, rugby, Australian football) or when writing code against ESPN's endpoints directly.
license: MIT
metadata:
  author: sejaldua
  version: "1.0"
  source: https://github.com/pseudo-r/Public-ESPN-API
compatibility: Requires network access to ESPN API endpoints. Works with any language that can make HTTP requests (curl, Python, JavaScript, etc.).
---

# ESPN Public API Skill

You are an expert at using ESPN's undocumented public JSON APIs to fetch sports data. These APIs power espn.com and the ESPN mobile app. They require no authentication and return JSON.

**Important:** These are unofficial, undocumented APIs. They may change without notice. Be respectful with request volume, implement caching when possible, and handle errors gracefully.

## How to Use This Skill

1. **Identify what the user needs** (scores, standings, player stats, odds, etc.)
2. **Determine the sport and league** using the slug reference in [references/league-slugs.md](references/league-slugs.md)
3. **Pick the right API domain and endpoint** from [references/endpoints.md](references/endpoints.md)
4. **Construct the URL** and fetch the data
5. **Parse the JSON response** using patterns from [references/response-schemas.md](references/response-schemas.md)
6. **Watch for common pitfalls** documented in [references/gotchas.md](references/gotchas.md)

## API Domains

There are six ESPN API domains. Choose based on your data need:

| Domain | Base URL | Use For |
|--------|----------|---------|
| **Site API** | `https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/` | Scores, teams, rosters, news, injuries, game summaries |
| **Site API v2** | `https://site.api.espn.com/apis/v2/sports/{sport}/{league}/` | Standings only (the site/v2 path returns a stub for standings) |
| **Core API v2** | `https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}/` | Athletes, detailed stats, odds, play-by-play, venues, coaches |
| **Core API v3** | `https://sports.core.api.espn.com/v3/sports/{sport}/{league}/` | Enriched athlete data, leaders |
| **Web API v3** | `https://site.web.api.espn.com/apis/common/v3/sports/{sport}/{league}/` | Player season stats, gamelogs, splits, leaderboards |
| **CDN** | `https://cdn.espn.com/core/{league-abbrev}/` | Full game packages (boxscore + plays + win prob). Requires `?xhr=1` |
| **Now API** | `https://now.core.api.espn.com/v1/sports/news` | Real-time news feed |

## Quick Start Recipes

### Get today's scores for any league
```bash
curl "https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard"
# Example: NBA scores today
curl "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
# Scores for a specific date
curl "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20250315"
```

### Get standings
```bash
# IMPORTANT: Use /apis/v2/ NOT /apis/site/v2/ (the latter returns a stub)
curl "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings"
curl "https://site.api.espn.com/apis/v2/sports/football/nfl/standings"
```

### Get all teams
```bash
curl "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
```

### Get a team's roster
```bash
# Team IDs: look them up from the teams endpoint first
curl "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/13/roster"
```

### Get a full game summary (boxscore + plays + leaders)
```bash
curl "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401765432"
```

### Get player season stats
```bash
# Uses the Web API v3 domain. Works for NFL, NBA, NHL, MLB.
curl "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/3136776/stats"
```

### Get player game log
```bash
curl "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/3136776/gamelog"
```

### Get betting odds for a game
```bash
curl "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/{eventId}/competitions/{eventId}/odds"
```

### Get league-wide injury report
```bash
curl "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"
```

### Get real-time news
```bash
curl "https://now.core.api.espn.com/v1/sports/news?sport=basketball&league=nba&limit=20"
```

### Get full game package via CDN (richest data)
```bash
# Returns gamepackageJSON with drives, plays, win probability, boxscore, odds
curl "https://cdn.espn.com/core/nba/game?xhr=1&gameId=401765432"
curl "https://cdn.espn.com/core/nfl/boxscore?xhr=1&gameId=401671793"
```

## Common Query Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `dates` | Date filter (YYYYMMDD or range) | `20250315` or `20250301-20250331` |
| `season` | Season year | `2025` |
| `seasontype` | 1=preseason, 2=regular, 3=postseason, 4=offseason | `2` |
| `week` | Week number | `1` |
| `limit` | Results per page | `100` |
| `page` | Page number | `1` |
| `groups` | Conference ID (college sports) | `8` (SEC) |
| `xhr` | Required for CDN endpoints | `1` |
| `active` | Filter active athletes | `true` |

## Season Types

| Type | Value | Description |
|------|-------|-------------|
| Preseason | `1` | Exhibition/preseason games |
| Regular Season | `2` | Regular season |
| Postseason | `3` | Playoffs/postseason |
| Off Season | `4` | Off season |

## Betting Provider IDs

When filtering odds by provider:

| Provider | ID |
|----------|----|
| Caesars | 38 |
| FanDuel | 37 |
| DraftKings | 41 |
| BetMGM | 58 |
| ESPN BET | 68 |
| Bet365 | 2000 |

## Writing Code

When the user wants to write code that calls the ESPN API:

### Python (requests or httpx)
```python
import requests

def get_nba_scoreboard(date=None):
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    params = {}
    if date:
        params["dates"] = date  # YYYYMMDD format
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["events"]
```

### JavaScript/TypeScript (fetch)
```typescript
async function getNBAScoreboard(date?: string) {
  const url = new URL("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard");
  if (date) url.searchParams.set("dates", date);
  const resp = await fetch(url.toString());
  if (!resp.ok) throw new Error(`ESPN API error: ${resp.status}`);
  const data = await resp.json();
  return data.events;
}
```

### Best practices for ESPN API code
- Always set a timeout (30s recommended)
- Implement caching for data that does not change frequently (teams, standings, rosters)
- Handle 404s gracefully (invalid IDs, offseason endpoints)
- Handle 429s (rate limiting) with exponential backoff
- The API is undocumented, so always validate response shape before accessing nested fields
- Use `User-Agent` header to identify your app

## For Deeper Reference

- **Full endpoint catalog:** [references/endpoints.md](references/endpoints.md)
- **All sport and league slugs:** [references/league-slugs.md](references/league-slugs.md)
- **JSON response schemas with examples:** [references/response-schemas.md](references/response-schemas.md)
- **Common pitfalls and gotchas:** [references/gotchas.md](references/gotchas.md)
- **Python fetch helper:** [scripts/espn_fetch.py](scripts/espn_fetch.py)
- **Bash fetch helper:** [scripts/espn_fetch.sh](scripts/espn_fetch.sh)
