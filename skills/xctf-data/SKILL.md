---
name: xctf-data
description: |
  NCAA cross country and track & field athlete data via TFRRS (tfrrs.org) and news via The Stride Report. Fetch athlete profiles including all personal records (PRs), eligibility year, school, full season-by-season results history, and XC/TF news. Zero config, no API keys.

  Use when: user asks about NCAA cross country, NCAA track and field, college running, TFRRS athlete profiles, personal records, PRs, XC or TF season results, individual athlete performance history, or XC/TF news.
  Don't use when: user asks about professional track, Diamond League, or other sports — use nfl-data, nba-data, wnba-data, nhl-data, mlb-data, golf-data, cfb-data, cbb-data, tennis-data, fastf1, or volleyball-data. For betting use polymarket or kalshi.
license: MIT
compatibility: Requires Python 3.10+ and internet access to tfrrs.org and thestridereport.com. No API keys required.
metadata:
  author: machina-sports
  version: "0.1.0"
---

# XC/TF Data (TFRRS — NCAA Cross Country & Track and Field)

Before writing queries, consult `references/api-reference.md` for parameters, URL conventions, and return shapes.

## Setup

Before first use, check if the CLI is available:
```bash
which sports-skills || pip install sports-skills
```
If `pip install` fails, install from GitHub:
```bash
pip install git+https://github.com/machina-sports/sports-skills.git
```
Requires Python 3.10+. No API keys required. All data comes from TFRRS public pages and The Stride Report RSS feed.

## Quick Start

CLI (preferred):
```bash
sports-skills xctf get_athlete_profile --athlete_id=8579610 --school=California_Baptist --name=Lamiae_Mamouni
sports-skills xctf get_news --limit=5
```

Python SDK:
```python
from sports_skills import xctf

profile = xctf.get_athlete_profile(
    athlete_id="8579610",
    school="California_Baptist",
    name="Lamiae_Mamouni",
)
```

## CRITICAL: Before Any Query

All three parameters are required and must match the athlete's TFRRS URL exactly:

```
https://www.tfrrs.org/athletes/{athlete_id}/{school}/{name}.html
```

- `athlete_id` — numeric ID (e.g. `8579610`)
- `school` — school slug with underscores, not spaces (e.g. `California_Baptist`)
- `name` — athlete name slug (e.g. `Lamiae_Mamouni`)

Do NOT guess slugs. Find them by navigating to the athlete on tfrrs.org and copying the URL.

## Commands

| Command | Description |
|---|---|
| `search_athlete` | Search the current team roster by name; returns `athlete_id`, `school`, and `name` slugs for use with `get_athlete_profile`. Searches both genders automatically. Current athletes only — graduated athletes require a direct TFRRS URL |
| `get_athlete_profile` | Athlete name, school, eligibility, all PRs, and full season-by-season meet results |
| `get_team_roster` | Full XC and/or TF roster for a team |
| `get_meet_results` | All event results and team scores from a TFRRS meet |
| `get_news` | Recent XC/TF articles from The Stride Report (thestridereport.com) |

See `references/api-reference.md` for full parameter details and return shapes.

## Examples

Example 1: Look up a current athlete's PRs
User says: "What are Lamiae Mamouni's PRs?"
Actions:
1. Call `search_athlete(name="Lamiae Mamouni", school="CA_college_f_California_Baptist")`
   Result: `data.matches` contains entries with `athlete_id`, `school`, `name` slugs
2. Call `get_athlete_profile(athlete_id="8579610", school="California_Baptist", name="Lamiae_Mamouni")`
Result: `data.prs` contains all personal records by event (e.g. `{"1500": "4:31.80", "5K (XC)": "18:25.5", ...}`)

Example 2: Get a runner's cross country season
User says: "Show me Lamiae Mamouni's 2025 XC season results"
Actions:
1. Call `search_athlete(name="Lamiae Mamouni", school="CA_college_f_California_Baptist")`
2. Call `get_athlete_profile` with the matched athlete params
3. Filter `data.meets` for entries whose `date` falls in the fall of 2025 (Sep–Nov 2025)
Result: List of meets with dates, events, marks, and places

Example 3: Graduated or transferred athlete
User says: "What are Katelyn Vuong's PRs from UC Davis?"
Actions:
1. Call `search_athlete(name="Katelyn Vuong", school="CA_college_f_UC_Davis")`
   Result: `data.matches` is empty — athlete has graduated
2. Tell the user: "Katelyn Vuong is not on UC Davis's current roster. Please find her profile URL on tfrrs.org (e.g. search 'Katelyn Vuong UC Davis tfrrs') and share it."
3. User provides: `https://www.tfrrs.org/athletes/7899206/UC_Davis/Katelyn_Vuong.html`
4. Extract params from the URL and call `get_athlete_profile(athlete_id="7899206", school="UC_Davis", name="Katelyn_Vuong")`
Note: TFRRS creates separate profiles for XC and TF. If both exist, fetch both IDs for complete PRs.

Example 4: Get a team's current roster
User says: "Show me the UC Davis women's XC roster"
Actions:
1. Call `get_team_roster(school="CA_college_f_UC_Davis", sport="xc")`
Result: List of athletes with name, year, and profile slugs

Example 5: Get results from a meet
User says: "Show me the results from the Stanford Invitational"
Actions:
1. Find the meet on tfrrs.org and copy the meet_id and slug from the URL (e.g. tfrrs.org/results/95890/Stanford_Invitational)
2. Call `get_meet_results(meet_id="95890", slug="Stanford_Invitational")`
Result: All event results and team scores from the meet

Example 6: Get the latest XC/TF news
User says: "What's the latest college track news?"
Actions:
1. Call `get_news(limit=10)`
Result: Recent articles from The Stride Report with title, date, summary, and link

## Commands that DO NOT exist — never call these

- ~~`get_team_rankings`~~ — does not exist. Use `get_athlete_profile` for individual data.
- ~~`search_athletes`~~ — does not exist. The correct command is `search_athlete` (no trailing 's').
- ~~`fetch_news`~~ — does not exist. The correct command is `get_news`.

If a command is not listed in the Commands table above, it does not exist.

## Error Handling

When a command fails, **do not surface raw errors to the user**. Instead:
1. For `get_athlete_profile`: confirm `athlete_id`, `school`, and `name` match the TFRRS URL exactly (case-sensitive)
2. For `search_athlete`: verify the team slug is correct by checking the team's TFRRS page URL
3. For `get_meet_results`: verify the `meet_id` and `slug` match the meet's TFRRS URL exactly
4. For `get_team_roster`: verify the school slug is correct
5. For `get_news`: if the feed fails, inform the user that The Stride Report may be temporarily unavailable
6. Report failure with a clean message only after exhausting alternatives

## Troubleshooting

**`sports-skills` command not found**
Run `pip install sports-skills` or install from GitHub (see Setup above).

**HTTP 404 on athlete profile**
The `school` or `name` slug does not match the TFRRS URL exactly. Slugs are case-sensitive and use underscores. Copy directly from tfrrs.org.

**`prs` returns empty dict**
The athlete's profile page may be very new or structured differently. Check the URL directly on tfrrs.org.

**`search_athlete` returns empty matches**
The athlete is likely graduated or transferred. See Example 3 above for how to handle this.

**`get_meet_results` returns no events**
The `meet_id` or `slug` may be incorrect. Copy both directly from the meet's TFRRS URL.

**`get_news` fails or returns no articles**
The Stride Report RSS feed may be temporarily unavailable. Try again later.

**Connection errors or timeouts**
TFRRS may be temporarily unavailable. Requests are throttled to 1 per second automatically — wait a moment and retry.
