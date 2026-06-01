# XC/TF Data — API Reference

Data source: [tfrrs.org](https://www.tfrrs.org) (Track & Field Results Reporting System)

---

## URL Convention

All athlete data is fetched from a single URL pattern:

```
https://www.tfrrs.org/athletes/{athlete_id}/{school}/{name}.html
```

| Component | Description | Example |
|---|---|---|
| `athlete_id` | Numeric TFRRS ID | `9230145` |
| `school` | School name slug (underscores, Title_Case) | `BYU` |
| `name` | Athlete name slug (underscores, Title_Case) | `Jane_Hedengren` |

Slugs are **case-sensitive** and must match the TFRRS URL exactly. Find them by navigating to the athlete's profile on tfrrs.org.

---

## `search_athlete`

```bash
sports-skills xctf search_athlete --name=<name> --school=<team_slug>
```

Searches the current XC and TF team roster pages for athletes matching the given name.

> **Note:** Only covers athletes on the current-season roster. Graduated or transferred athletes will not appear — use `get_athlete_profile` directly with their `athlete_id` from their TFRRS profile URL.

### Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Athlete name to search for (e.g. `"Jane Hedengren"`) |
| `school` | string | Yes | TFRRS team slug from the team page URL (e.g. `"UT_college_f_BYU"`) |

The team page URL pattern is:
```
https://www.tfrrs.org/teams/{xc|tf}/{school}.html
```

Note: the team slug (e.g. `CA_college_f_UC_Davis`) differs from the athlete profile school slug (e.g. `UC_Davis`). The `matches` results include the athlete profile school slug ready to pass to `get_athlete_profile`.

### Return shape

```json
{
  "status": true,
  "message": "",
  "data": {
    "matches": [
      {
        "athlete_id": "9230145",
        "school": "BYU",
        "name": "Jane_Hedengren",
        "sport": "xc",
        "url": "https://www.tfrrs.org/athletes/9230145/BYU/Jane_Hedengren.html"
      },
      {
        "athlete_id": "9230145",
        "school": "BYU",
        "name": "Jane_Hedengren",
        "sport": "tf",
        "url": "https://www.tfrrs.org/athletes/9230145/BYU/Jane_Hedengren.html"
      }
    ]
  }
}
```

### Field notes

| Field | Notes |
|---|---|
| `matches` | Empty list if no athletes match the name on the current roster. |
| `matches[].sport` | `"xc"` or `"tf"` — an athlete may appear in both if listed on both rosters. |
| `matches[].athlete_id` | Use this directly as `athlete_id` in `get_athlete_profile`. |
| `matches[].school` | Athlete profile school slug (e.g. `BYU`) — use as `school` in `get_athlete_profile`. |
| `matches[].name` | Athlete name slug (e.g. `Jane_Hedengren`) — use as `name` in `get_athlete_profile`. |

### Error response

```json
{
  "status": false,
  "message": "HTTP 404: Not Found",
  "data": null
}
```

Common causes: incorrect team slug. Verify the slug from the team's TFRRS page URL.

---

## `get_athlete_profile`

```bash
sports-skills xctf get_athlete_profile --athlete_id=<id> --school=<school> --name=<name>
```

### Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `athlete_id` | string | Yes | Numeric TFRRS athlete ID |
| `school` | string | Yes | School slug as it appears in the TFRRS URL |
| `name` | string | Yes | Athlete name slug as it appears in the TFRRS URL |

### Return shape

```json
{
  "status": true,
  "message": "",
  "data": {
    "athlete_id": "9230145",
    "url": "https://www.tfrrs.org/athletes/9230145/BYU/Jane_Hedengren.html",
    "name": "Jane Hedengren",
    "school": "BYU",
    "eligibility": "FR-1",
    "prs": {
      "1500": "4:10.24",
      "MILE": "4:22.22",
      "3000": "8:34.98",
      "5000": "14:44.79",
      "10,000": "30:46.80",
      "6K (XC)": "18:29.6"
    },
    "meets": [
      {
        "meet": "Big 12 Outdoor Track & Field Championships",
        "date": "May 14-16, 2026",
        "results": [
          { "event": "1500", "mark": "4:10.24", "place": "3rd (F)" },
          { "event": "5000", "mark": "15:26.94", "place": "1st (F)" }
        ]
      },
      {
        "meet": "NCAA Division I Indoor Track & Field Championships",
        "date": "Mar 13-14, 2026",
        "results": [
          { "event": "3000", "mark": "8:36.61", "place": "1st (F)" },
          { "event": "5000", "mark": "15:00.12", "place": "1st (F)" }
        ]
      },
      {
        "meet": "NCAA Division I Cross Country Championships",
        "date": "Nov 22, 2025",
        "results": [
          { "event": "6k", "mark": "18:38.9", "place": "2nd" }
        ]
      }
    ]
  }
}
```

### Field notes

| Field | Notes |
|---|---|
| `school` | Short school abbreviation as shown on TFRRS (e.g. `CBU`, not the full name) |
| `eligibility` | Year-in-school code: `FR-1`, `SO-2`, `JR-3`, `SR-4`, or a graduate/transfer variant |
| `prs` | All-time personal records from the summary table at the top of the profile. Keys are event names exactly as TFRRS labels them. |
| `meets` | Flat list of all meets, ordered most recent first. |
| `meets[].date` | Date string as it appears on TFRRS — may be a single date (`"Mar 13, 2026"`) or a range (`"May 9-11, 2024"`). |
| `meets[].results` | Each result has `event` and `mark`. `place` is included when available (e.g. `"1st (F)"` = 1st in final, `"3rd (P)"` = 3rd in prelim). |

### Error response

```json
{
  "status": false,
  "message": "HTTP 404: Not Found",
  "data": null
}
```

Common causes: incorrect `school` or `name` slug, athlete profile not yet on TFRRS.

---

---

## `get_news`

```bash
sports-skills xctf get_news
sports-skills xctf get_news --limit=5
```

Fetches recent articles from The Stride Report RSS feed (`thestridereport.com/blog-feed.xml`).

### Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `limit` | int | No | Max number of articles to return. Omit for all available. |

### Return shape

```json
{
  "status": true,
  "message": "",
  "data": {
    "source": "The Stride Report",
    "count": 10,
    "articles": [
      {
        "title": "First Thoughts: McFarland Runs 3:33...",
        "link": "https://www.thestridereport.com/post/first-thoughts-...",
        "date": "Sun, 19 Apr 2026 00:27:30 GMT",
        "summary": "Look, there was A LOT of chaos that took place this weekend...",
        "categories": ["D1", "OUTDOORS"],
        "author": "Admin (Garrett Zatlin)",
        "image": "https://static.wixstatic.com/media/..."
      }
    ]
  }
}
```

### Field notes

| Field | Notes |
|---|---|
| `articles[].categories` | List of topic tags from the feed (e.g. `["D1", "OUTDOORS"]`, `["XC"]`). May be empty. |
| `articles[].image` | URL of the article's lead image from the RSS enclosure. Empty string if none. |
| `articles[].summary` | Short excerpt — typically truncated with "...". Not the full article body. |
| `articles[].date` | RFC 822 timestamp string as published in the feed. |

---

## Notes on TFRRS data

- **Relay results** appear as events like `4x800` or `DMR` with a split/relay time.
- **DNF / DNS** marks appear as the mark value when no time was recorded.
- **Wind readings** may appear alongside marks (e.g. `2:10.30 (-0.3)`) — these are included in the raw mark string.
- **XC distances** vary by meet and division: common values are `5k`, `6k`, `8k` (women), `10k` (men).
- **Requests are throttled** to 1 per second and cached for 5 minutes to be respectful of the TFRRS server.
