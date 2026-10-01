# ESPN API Response Schemas

Example JSON structures for the most commonly used endpoints. All examples are truncated for brevity.

---

## Scoreboard

**Endpoint:** `GET https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard`

```json
{
  "leagues": [
    {
      "id": "46",
      "name": "National Basketball Association",
      "abbreviation": "NBA",
      "slug": "nba",
      "season": { "year": 2025, "type": 2, "slug": "regular-season" },
      "logos": [{ "href": "https://...", "width": 500, "height": 500 }]
    }
  ],
  "events": [
    {
      "id": "401765432",
      "date": "2025-03-15T00:00Z",
      "name": "Boston Celtics at Golden State Warriors",
      "shortName": "BOS @ GSW",
      "season": { "year": 2025, "type": 2 },
      "status": {
        "clock": "0.0",
        "displayClock": "0.0",
        "period": 4,
        "type": {
          "id": "3",
          "name": "STATUS_FINAL",
          "state": "post",
          "completed": true,
          "description": "Final"
        }
      },
      "competitions": [
        {
          "id": "401765432",
          "attendance": 18064,
          "venue": {
            "id": "1234",
            "fullName": "Chase Center",
            "address": { "city": "San Francisco", "state": "CA" },
            "capacity": 18064,
            "indoor": true
          },
          "broadcasts": [
            {
              "market": { "id": "1", "type": "National" },
              "media": { "shortName": "ESPN" },
              "type": { "id": "1", "shortName": "TV" }
            }
          ],
          "competitors": [
            {
              "id": "17",
              "homeAway": "home",
              "team": {
                "id": "9",
                "abbreviation": "GSW",
                "displayName": "Golden State Warriors",
                "shortDisplayName": "Warriors",
                "color": "006BB6",
                "logo": "https://..."
              },
              "score": "121",
              "winner": true,
              "records": [{ "name": "overall", "summary": "42-24" }],
              "leaders": [
                {
                  "name": "points",
                  "displayName": "Points Leader",
                  "leaders": [
                    {
                      "displayValue": "32",
                      "athlete": { "id": "3136776", "displayName": "Stephen Curry" }
                    }
                  ]
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

**Key fields:**
- `events[].id` is the event ID used in other endpoints
- `events[].competitions[].competitors[]` has home/away teams with scores
- `events[].status.type.state` is `"pre"`, `"in"`, or `"post"`
- `events[].status.type.completed` tells you if the game is final

---

## Teams

**Endpoint:** `GET https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/teams`

```json
{
  "sports": [
    {
      "leagues": [
        {
          "teams": [
            {
              "team": {
                "id": "9",
                "slug": "golden-state-warriors",
                "abbreviation": "GSW",
                "displayName": "Golden State Warriors",
                "shortDisplayName": "Warriors",
                "location": "Golden State",
                "color": "006BB6",
                "alternateColor": "FDB927",
                "isActive": true,
                "logos": [{ "href": "https://...", "width": 500, "height": 500 }]
              }
            }
          ]
        }
      ]
    }
  ]
}
```

**Key fields:**
- Teams are nested: `sports[0].leagues[0].teams[].team`
- `team.id` is the ESPN team ID used in other endpoints
- `team.abbreviation` is the 2-3 letter code (GSW, LAL, BOS)

---

## Team Roster

**Endpoint:** `GET .../teams/{id}/roster`

```json
{
  "team": { "id": "9", "abbreviation": "GSW", "displayName": "Golden State Warriors" },
  "athletes": [
    {
      "position": "G",
      "items": [
        {
          "id": "3136776",
          "firstName": "Stephen",
          "lastName": "Curry",
          "displayName": "Stephen Curry",
          "jersey": "30",
          "position": { "abbreviation": "SG" },
          "age": 36,
          "height": 74,
          "weight": 185,
          "experience": { "years": 15 },
          "status": { "name": "Active", "type": "active" },
          "headshot": { "href": "https://..." }
        }
      ]
    }
  ],
  "coach": [{ "id": "6010", "firstName": "Steve", "lastName": "Kerr" }]
}
```

**Key fields:**
- Athletes grouped by position category
- `athletes[].items[].id` is the ESPN athlete ID
- Height is in inches, weight in pounds

---

## Game Summary

**Endpoint:** `GET .../summary?event={id}`

This is the richest single-request endpoint. Returns:

```json
{
  "boxscore": {
    "teams": [
      {
        "team": { "id": "9", "displayName": "Golden State Warriors" },
        "statistics": [
          { "name": "assists", "displayValue": "28" },
          { "name": "rebounds", "displayValue": "41" },
          { "name": "fieldGoalPct", "displayValue": "48.5" }
        ],
        "players": [
          {
            "statistics": [
              {
                "names": ["MIN", "FG", "3PT", "FT", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "PF", "+/-", "PTS"],
                "athletes": [
                  {
                    "athlete": { "id": "3136776", "displayName": "Stephen Curry" },
                    "stats": ["36", "12-24", "4-10", "4-4", "0", "5", "5", "7", "1", "0", "2", "2", "+8", "32"]
                  }
                ]
              }
            ]
          }
        ]
      }
    ]
  },
  "plays": [
    {
      "id": "4017654340001",
      "text": "S. Curry makes 2-pt jump shot from 14 ft",
      "clock": { "displayValue": "11:42" },
      "period": { "number": 1 },
      "team": { "id": "9" },
      "scoreValue": 2,
      "scoringPlay": true
    }
  ],
  "leaders": [
    {
      "name": "points",
      "leaders": [
        {
          "displayValue": "32",
          "athlete": { "id": "3136776", "displayName": "Stephen Curry" }
        }
      ]
    }
  ],
  "broadcasts": [{ "market": "national", "names": ["ESPN"] }],
  "predictor": {
    "homeTeam": { "gameProjection": "63.4" }
  }
}
```

**Key fields:**
- `boxscore.teams[].players[].statistics[].names` is the header row
- `boxscore.teams[].players[].statistics[].athletes[].stats` is the data row (parallel array)
- Stats are strings, not numbers

---

## Standings

**Endpoint:** `GET https://site.api.espn.com/apis/v2/sports/{sport}/{league}/standings`

```json
{
  "children": [
    {
      "name": "Eastern Conference",
      "abbreviation": "EAST",
      "standings": {
        "entries": [
          {
            "team": {
              "id": "2",
              "displayName": "Boston Celtics",
              "abbreviation": "BOS"
            },
            "stats": [
              { "name": "wins", "displayValue": "52" },
              { "name": "losses", "displayValue": "14" },
              { "name": "winPercent", "displayValue": ".788" },
              { "name": "gamesBehind", "displayValue": "-" },
              { "name": "streak", "displayValue": "W3" }
            ]
          }
        ]
      }
    }
  ]
}
```

**Key fields:**
- Grouped by conference/division in `children[]`
- Stats are name/value pairs in `stats[]`
- Common stat names: `wins`, `losses`, `winPercent`, `gamesBehind`, `streak`, `pointsFor`, `pointsAgainst`

---

## Athlete (Core API v2)

**Endpoint:** `GET https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}/athletes/{id}`

```json
{
  "id": "3136776",
  "firstName": "Stephen",
  "lastName": "Curry",
  "displayName": "Stephen Curry",
  "weight": 185,
  "height": 74,
  "age": 36,
  "dateOfBirth": "1988-03-14T00:00Z",
  "jersey": "30",
  "active": true,
  "position": { "abbreviation": "SG" },
  "team": { "$ref": "https://sports.core.api.espn.com/v2/.../teams/9" },
  "experience": { "years": 15 },
  "college": { "name": "Davidson" },
  "draft": { "year": 2009, "round": 1, "selection": 7 },
  "headshot": { "href": "https://..." },
  "statistics": { "$ref": "https://...athletes/3136776/statistics" }
}
```

**Key fields:**
- `team` and `statistics` are `$ref` links that need separate requests
- Height is inches, weight is pounds

---

## Athlete Stats (Web API v3)

**Endpoint:** `GET https://site.web.api.espn.com/apis/common/v3/sports/{sport}/{league}/athletes/{id}/stats`

```json
{
  "categories": [
    {
      "name": "general",
      "displayName": "General",
      "labels": ["GP", "GS", "MIN", "PTS", "REB", "AST", "STL", "BLK", "TO", "FG%", "3P%", "FT%"],
      "totals": ["56", "56", "34.2", "26.4", "4.5", "6.1", "0.9", "0.4", "3.1", ".502", ".408", ".924"]
    }
  ],
  "glossary": [
    { "abbreviation": "GP", "displayName": "Games Played" }
  ]
}
```

**Key fields:**
- `labels` and `totals` are parallel arrays
- Values are strings
- `glossary` maps abbreviations to full names

---

## Athlete Game Log (Web API v3)

**Endpoint:** `GET .../athletes/{id}/gamelog`

```json
{
  "labels": ["DATE", "OPP", "RESULT", "MIN", "FG", "3PT", "FT", "REB", "AST", "STL", "BLK", "PTS"],
  "events": [
    {
      "id": "401765000",
      "date": "2025-03-14T00:00Z",
      "opponent": { "id": "2", "abbreviation": "BOS" },
      "gameResult": "W",
      "stats": ["36", "12-24", "4-10", "4-4", "5", "7", "1", "0", "32"]
    }
  ]
}
```

---

## Betting Odds

**Endpoint:** `GET .../events/{id}/competitions/{id}/odds`

```json
{
  "items": [
    {
      "provider": { "id": "41", "name": "DraftKings", "priority": 1 },
      "details": "-3.5",
      "overUnder": 222.5,
      "spread": -3.5,
      "overOdds": -110,
      "underOdds": -110,
      "awayTeamOdds": { "favorite": false, "moneyLine": 140, "spreadOdds": -110 },
      "homeTeamOdds": { "favorite": true, "moneyLine": -165, "spreadOdds": -110 },
      "open": {
        "over": { "value": 220.0 },
        "spread": { "home": { "line": -4.5 } }
      }
    }
  ]
}
```

---

## Injuries

**Endpoint:** `GET .../injuries` (league-wide)

```json
{
  "injuries": [
    {
      "team": { "id": "9", "abbreviation": "GSW" },
      "injuries": [
        {
          "athlete": { "id": "3136776", "displayName": "Stephen Curry" },
          "type": { "name": "knee" },
          "status": "Day-To-Day",
          "date": "2025-03-20T00:00Z"
        }
      ]
    }
  ]
}
```

---

## News (Now API)

**Endpoint:** `GET https://now.core.api.espn.com/v1/sports/news`

```json
{
  "resultsCount": 1000,
  "resultsLimit": 20,
  "feed": [
    {
      "headline": "Curry scores 32, Warriors top Celtics",
      "description": "Stephen Curry scores 32 points...",
      "published": "2025-03-15T02:00:00Z",
      "type": "HeadlineNews",
      "links": { "web": { "href": "https://www.espn.com/..." } },
      "images": [{ "url": "https://...", "width": 576, "height": 324 }],
      "categories": [
        { "type": "league", "id": 46, "description": "NBA" },
        { "type": "team", "id": 9, "description": "Golden State Warriors" },
        { "type": "athlete", "id": 3136776, "description": "Stephen Curry" }
      ]
    }
  ]
}
```

---

## CDN Game Package

**Endpoint:** `GET https://cdn.espn.com/core/{sport}/game?xhr=1&gameId={id}`

The response wraps all data under `gamepackageJSON`:

```json
{
  "gameId": "401671793",
  "gamepackageJSON": {
    "header": {
      "competitions": [
        {
          "competitors": [
            { "id": "12", "homeAway": "home", "score": "27", "winner": true },
            { "id": "25", "homeAway": "away", "score": "24", "winner": false }
          ],
          "status": { "type": { "name": "STATUS_FINAL", "completed": true } }
        }
      ]
    },
    "boxscore": { "teams": [], "players": [] },
    "drives": {
      "previous": [
        {
          "description": "10 plays, 75 yards, 4:32",
          "result": "Touchdown",
          "yards": 75,
          "plays": [{ "text": "..." }]
        }
      ]
    },
    "plays": [{ "text": "...", "scoringPlay": true }],
    "winprobability": [{ "homeWinPercentage": 0.72, "playId": "..." }],
    "standings": {}
  }
}
```

**Key fields:**
- Everything lives under `gamepackageJSON`
- `drives` only present for football
- `winprobability` is an array of probability snapshots tied to plays

---

## Athlete Overview (Web API v3)

**Endpoint:** `GET .../athletes/{id}/overview`

```json
{
  "statistics": {
    "labels": ["GP", "PTS", "REB", "AST"],
    "values": [56.0, 26.4, 4.5, 6.1]
  },
  "news": { "articles": [{ "headline": "...", "published": "2025-03-14T21:00Z" }] },
  "nextGame": {
    "id": "401765999",
    "date": "2025-03-16T17:30Z",
    "name": "Golden State Warriors at Boston Celtics"
  },
  "rotowire": { "injury": null, "news": "Curry is healthy and expected to play Friday." }
}
```

---

## Rankings (College Sports)

**Endpoint:** `GET .../rankings`

```json
{
  "rankings": [
    {
      "name": "AP Top 25",
      "type": "ap",
      "ranks": [
        {
          "current": 1,
          "previous": 1,
          "points": 1575,
          "firstPlaceVotes": 63,
          "team": {
            "id": "333",
            "displayName": "Alabama Crimson Tide",
            "record": { "summary": "11-0" }
          }
        }
      ]
    }
  ]
}
```
