---
name: nfl-data
description: |
  NFL data via ESPN public endpoints — scores, standings, rosters, schedules, game summaries, leaders, and news. Zero config, no API keys.

  Use when: user asks about NFL scores, standings, team rosters, schedules, game stats, box scores, or NFL news.
  Don't use when: user asks about football/soccer (use football-data), college football, or other sports. Don't use for live play-by-play — data updates post-play.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# NFL Data

## Setup

Before first use, check if the CLI is available:
```bash
which sports-skills || pip install sports-skills
```
If `pip install` fails with a Python version error, the package requires Python 3.10+. Find a compatible Python:
```bash
python3 --version  # check version
# If < 3.10, try: python3.12 -m pip install sports-skills
# On macOS with Homebrew: /opt/homebrew/bin/python3.12 -m pip install sports-skills
```
No API keys required.

## Quick Start

Prefer the CLI — it avoids Python import path issues:
```bash
sports-skills nfl get_scoreboard
sports-skills nfl get_standings --season=2025
sports-skills nfl get_teams
```

Python SDK (alternative):
```python
from sports_skills import nfl

scores = nfl.get_scoreboard({})
standings = nfl.get_standings({"params": {"season": "2025"}})
```

## Choosing the Season

Derive the current year from the system prompt's date (e.g., `currentDate: 2026-02-16` → current year is 2026).

- **If the user specifies a season**, use it as-is.
- **If the user says "current", "this season", or doesn't specify**: The NFL season runs September–February. If the current month is March–August, use `season = current_year` (upcoming season). If September–February, the active season started in the previous calendar year if you're in Jan/Feb, otherwise current year.
- **Never hardcode a season.** Always derive it from the system date.

## Commands

### get_scoreboard
Get live/recent NFL scores.
- `date` (str, optional): Date in YYYY-MM-DD format
- `week` (int, optional): Week number (1-18 regular, 19+ playoffs)
- `season` (int, optional): Season year

Returns `events[]` with game info, scores, status, and competitors.

### get_standings
Get NFL standings by conference and division.
- `season` (int, optional): Season year

Returns `groups[]` with AFC/NFC conferences, divisions, and team standings including W-L-T, PCT, PF, PA.

### get_teams
Get all 32 NFL teams. No parameters.

Returns `teams[]` with id, name, abbreviation, logo, and location.

### get_team_roster
Get full roster for a team.
- `team_id` (str, required): ESPN team ID (e.g., "12" for Broncos)

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

Returns `articles[]` with headline, description, published date, and link.

### get_schedule
Get NFL season schedule by week.
- `season` (int, optional): Season year
- `week` (int, optional): Week number

Returns `events[]` for the specified week/season.

## Team IDs (Common)

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

## Examples

**User: "What are today's NFL scores?"**
```bash
sports-skills nfl get_scoreboard
```

**User: "Show me the AFC standings"**
```bash
sports-skills nfl get_standings --season=2025
```
Then filter results for AFC conference.

**User: "Who's on the Chiefs roster?"**
```bash
sports-skills nfl get_team_roster --team_id=12
```

**User: "How did the Super Bowl go?"**
1. Find the event_id from `get_scoreboard --week=22` (Super Bowl week)
2. Call `get_game_summary --event_id=<id>` for full box score

## Error Handling

When a command fails, **do not surface raw errors to the user**. Instead:
1. Catch silently and try alternatives
2. If team name given instead of ID, use `get_teams` to find the ID first
3. Only report failure with a clean message after exhausting alternatives

## Troubleshooting

- **`sports-skills` command not found**: Run `pip install sports-skills`
- **Team not found**: Use `get_teams` to list all teams and find the correct ID
- **No data for future games**: ESPN only returns data for completed or in-progress games
- **Week numbers**: Regular season is weeks 1-18, playoffs are 19+ (Wild Card=19, Divisional=20, Conference=21, Super Bowl=22)
