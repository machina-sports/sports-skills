# ESPN API Gotchas and Common Pitfalls

Things that will trip you up when working with the ESPN API.

---

## 1. Standings Use a Different Path

The most common mistake. The standard site API v2 path for standings returns only a stub object with a link:

```bash
# WRONG: Returns stub { "fullViewLink": {...} }
curl "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/standings"

# CORRECT: Returns full standings with records and stats
curl "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings"
```

Note the difference: `/apis/v2/` vs `/apis/site/v2/`.

---

## 2. CDN Endpoints Require `?xhr=1`

Without the `xhr=1` parameter, CDN endpoints return HTML instead of JSON:

```bash
# WRONG: Returns HTML page
curl "https://cdn.espn.com/core/nba/game?gameId=401765432"

# CORRECT: Returns JSON with gamepackageJSON key
curl "https://cdn.espn.com/core/nba/game?xhr=1&gameId=401765432"
```

---

## 3. CDN Uses League Slugs, Not Sport Slugs

CDN paths use the league abbreviation, not the sport category:

```bash
# WRONG
curl "https://cdn.espn.com/core/basketball/scoreboard?xhr=1"

# CORRECT
curl "https://cdn.espn.com/core/nba/scoreboard?xhr=1"
```

For soccer, you also need a `league` parameter:
```bash
curl "https://cdn.espn.com/core/soccer/scoreboard?xhr=1&league=eng.1"
```

---

## 4. Core API v2 Uses `/leagues/` in the Path

The Site API and Core API have different path structures:

```bash
# Site API: /sports/{sport}/{league}/
curl "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"

# Core API: /sports/{sport}/leagues/{league}/
curl "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/teams"
```

Note the extra `/leagues/` segment in the Core API.

---

## 5. Competition ID Usually Equals Event ID

For most endpoints that require both `event_id` and `competition_id`, they are the same value:

```bash
# event_id = competition_id = 401765432
curl "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/401765432/competitions/401765432/odds"
```

---

## 6. Date Format is YYYYMMDD (No Dashes)

ESPN dates use compact format without separators:

```bash
# WRONG
curl ".../scoreboard?dates=2025-03-15"

# CORRECT
curl ".../scoreboard?dates=20250315"

# Date ranges use a dash between two compact dates
curl ".../scoreboard?dates=20250301-20250331"
```

---

## 7. Paginated Responses Default to Small Limits

Many Core API endpoints return only 25 items by default. Always specify `limit`:

```bash
# Gets only 25 athletes
curl ".../athletes"

# Gets 100 athletes (up to 1000 on some endpoints)
curl ".../athletes?limit=100&page=1"
```

Check `count`, `pageIndex`, and `pageCount` in the response to know if more pages exist.

---

## 8. Core API Athletes Return `$ref` Links, Not Inline Data

The Core API v2 often returns reference links instead of inline data:

```json
{
  "team": {
    "$ref": "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/teams/9"
  }
}
```

You need to follow these `$ref` URLs with additional requests to get the full data. The Site API and Web API v3 endpoints return inline data and are usually more convenient.

---

## 9. Web API v3 Athlete Endpoints Have Sport-Specific Availability

Not all Web API v3 athlete endpoints work for every sport:

| Endpoint | NBA | NFL | NHL | MLB | Soccer |
|----------|-----|-----|-----|-----|--------|
| `overview` | Yes | Yes | Yes | Yes | Minimal |
| `stats` | Yes | Yes | Yes | Yes | 404 |
| `gamelog` | Yes | Yes | 404 | Yes | 400 |
| `splits` | Yes | Yes | Yes | Yes | No |
| `statistics/byathlete` | Yes | Yes | Yes | Yes | No |

---

## 10. League-Wide Injury Endpoints Fail for Some Sports

The `/injuries` endpoint returns HTTP 500 for individual sports:

- Works: NBA, NFL, NHL, MLB, Soccer
- Fails (500): MMA, Tennis, Golf

---

## 11. Season Year Meaning Varies by Sport

- **NFL, College Football:** Season year is the *start* year (2024 season = fall 2024)
- **NBA, NHL:** Season year can mean the *end* year (2024-25 season = `2025` in some endpoints)
- **MLB:** Season year matches the calendar year

Always check the `season` object in responses to confirm which convention is used.

---

## 12. Soccer League Slugs Use Dots

Soccer slugs are different from other sports and use dot notation:

```bash
# Other sports use plain slugs
curl ".../sports/basketball/nba/..."

# Soccer uses dot notation
curl ".../sports/soccer/eng.1/..."      # EPL
curl ".../sports/soccer/uefa.champions/..."  # Champions League
curl ".../sports/soccer/usa.1/..."      # MLS
```

---

## 13. Rugby Uses Numeric League IDs

Unlike other sports, rugby league slugs are numeric:

```bash
# Rugby World Cup
curl ".../sports/rugby/leagues/164205/..."

# Six Nations
curl ".../sports/rugby/leagues/180659/..."
```

---

## 14. No Official Rate Limits, But They Exist

ESPN does not publish rate limits, but they will block excessive requests (HTTP 429). Best practices:

- Cache responses that change infrequently (teams, rosters, standings)
- Do not poll scoreboards more than once per minute
- Use exponential backoff on 429 responses
- Set a descriptive `User-Agent` header

---

## 15. Game Summary is the Most Useful Single Endpoint

If you need comprehensive game data from one request, use:

```bash
curl "https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/summary?event={id}"
```

This returns boxscore, plays, leaders, broadcasts, predictor, and more in a single response. The CDN `/game` endpoint is even richer (includes win probability and drives for football).

---

## 16. Finding ESPN IDs

ESPN IDs for teams and athletes are not always obvious. Strategies:

- **Teams:** Fetch all teams first, find the ID from the response
- **Athletes:** Use the search endpoint: `https://site.web.api.espn.com/apis/search/v2?query=Stephen+Curry&sport=basketball`
- **Events:** Get from the scoreboard for a specific date
- **From URLs:** ESPN website URLs contain IDs (e.g., `espn.com/nba/team/_/id/9/golden-state-warriors` means team ID = 9)
