---
name: metadata
description: |
  Sports metadata via TheSportsDB free API (key=3). Team logos and badges, player photos, stadium info, league info, and biographical data across 100+ leagues. No API key required, zero config.

  Use when: user asks for a team logo, crest, badge, banner, jersey, kit, player photo or headshot, stadium info, club description, or wants to search for teams or players by name across sports. Good for enriching responses from other skills with images and visual identifiers.
  Don't use when: user asks for scores, standings, fixtures, stats, or odds — use the sport-specific skill instead: football-data (soccer), nfl-data (NFL), nba-data (NBA), wnba-data (WNBA), nhl-data (NHL), mlb-data (MLB), tennis-data (tennis), golf-data (golf), cricket-data (cricket), cfb-data (college football), cbb-data (college basketball), fastf1 (F1), volleyball-data (Dutch volleyball), xctf-data (NCAA XC/TF). Don't use for prediction markets — use polymarket or kalshi.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# Sports Metadata

Wraps the free [TheSportsDB](https://www.thesportsdb.com) API for team logos, player photos, and stadium info. No API key, no signup.

## Quick Start

```bash
sports-skills metadata get_team_logo --team_name="Arsenal"
sports-skills metadata get_team_info --team_name="Real Madrid"
sports-skills metadata get_player_photo --player_name="Messi"
sports-skills metadata search_teams --query="Manchester"
sports-skills metadata search_players --query="LeBron"
```

Python SDK:

```python
from sports_skills import metadata

metadata.get_team_logo(team_name="Arsenal")
metadata.get_team_info(team_name="Real Madrid")
metadata.get_player_photo(player_name="Messi")
metadata.search_teams(query="Manchester")
metadata.search_players(query="LeBron")
```

## CRITICAL: Before Any Query

CRITICAL: Before calling any metadata command, verify:
- Team names use the **full official name** — especially for NBA (e.g., `"Los Angeles Lakers"`, **not** `"Lakers"`).
- For `get_team_logo`, the `sport` parameter defaults to `"Soccer"`. Pass `sport="Basketball"`, `"American Football"`, `"Baseball"`, `"Ice Hockey"`, `"Motorsport"`, or `"Cricket"` when the team is not a soccer team — otherwise the lookup falls back to "first result regardless of sport," which may return the wrong team.
- Player searches use just the player name (e.g., `"Messi"`, `"LeBron James"`, `"Tiger Woods"`).

## Coverage

**Teams (logos, banners, stadium info):**
- Soccer: 100+ leagues worldwide (Premier League, La Liga, Bundesliga, Serie A, MLS, and many more)
- NFL (American Football)
- NBA (Basketball) — requires full team names
- MLB (Baseball)
- NHL (Ice Hockey)
- F1 (Motorsport)
- Cricket (IPL, international)

**Players (photos, bios):**
- All team sports above
- Tennis (ATP/WTA players)
- Golf (PGA/LPGA players)

**Not covered:** MMA/UFC, Rugby, Esports, Boxing.

## Commands

| Command | Required | Optional | Description |
|---|---|---|---|
| `get_team_logo` | team_name | sport | Team logo / badge URL |
| `get_team_info` | team_name | | Full team info: stadium, description, social links, banner |
| `get_player_photo` | player_name | | Player photo URL |
| `search_teams` | query | | Fuzzy search for teams across sports |
| `search_players` | query | | Fuzzy search for players across sports |

## Workflows

### Enrich a Standings Response

1. Call the sport-specific skill (e.g., `football get_season_standings`) for the standings table.
2. For each team in the standings, call `get_team_logo --team_name=<name>` to attach a badge URL.
3. Render the standings with logos alongside team names.

### Build a Team Profile Page

1. Call `get_team_info --team_name="<name>"` for stadium, description, founding year, social links.
2. The same response includes `badge` and `banner` URLs — no second call needed.

### Resolve an Ambiguous Team Name

1. Call `search_teams --query="<partial-name>"` to disambiguate.
2. Use the exact `name` field from the result for follow-up `get_team_info` calls.

## Examples

Example 1: Get a Premier League team logo
User says: "What does the Arsenal logo look like?"
Actions:
1. Call `get_team_logo(team_name="Arsenal")` — `sport` defaults to "Soccer", which is correct here.
Result: Logo URL, sport, league, and country.

Example 2: NBA team — full name required
User says: "Get the Lakers logo"
Actions:
1. Call `get_team_logo(team_name="Los Angeles Lakers", sport="Basketball")` — both the full name AND the sport filter are needed.
Result: Lakers badge from the NBA branch of TheSportsDB.

Example 3: Player photo
User says: "Show me a photo of Messi"
Actions:
1. Call `get_player_photo(player_name="Messi")`.
Result: Player photo URL, sport, team, and nationality.

Example 4: Disambiguate "Manchester"
User says: "Find me Manchester teams"
Actions:
1. Call `search_teams(query="Manchester")`.
Result: List of teams matching "Manchester" — Manchester United, Manchester City, etc. — each with sport, league, and country.

## Commands that DO NOT exist — never call these

- ~~`get_stadium_info`~~ — does not exist. Stadium info is included in `get_team_info`.
- ~~`get_league_logo`~~ — does not exist. Use `get_team_logo` for team badges only.
- ~~`get_player_stats`~~ — does not exist on this skill. TheSportsDB metadata does not include stats; use the sport-specific skill (e.g., `football get_player_profile`, `nba get_player_stats`).
- ~~`search_leagues`~~ — does not exist.

If a command is not listed in the Commands table above, it does not exist.

## Troubleshooting

Error: `get_team_logo` returns the wrong team
Cause: A short or ambiguous team name (e.g., "Lakers", "Arsenal") matched a different sport first
Solution: Pass an explicit `sport` parameter and use the team's full official name

Error: `get_player_photo` returns null / empty
Cause: Player not in TheSportsDB, or the name spelling differs (e.g., "Cristiano Ronaldo" vs "Ronaldo")
Solution: Use `search_players --query=<partial>` first to find the canonical spelling, then retry

Error: Logo URL works but the image is low resolution
Cause: TheSportsDB returns the badge as-is from contributors
Solution: This is an upstream limitation. Most badges are 200×200 or larger; very small icons indicate a low-quality submission. No workaround.
