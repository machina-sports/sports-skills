---
name: cricket-data
description: |
  Cricket data via ESPN public endpoints and Cricsheet open data — live-ish series scoreboards, standings, match summaries and news (ESPN), plus historical ball-by-ball, player stats, and player registry (Cricsheet, ODC-BY 1.0). Zero config, no API keys.

  Use when: user asks about cricket scores, IPL/BBL/PSL/international series, points tables, match details, cricket news, ball-by-ball history, or player career stats.
  Don't use when: user asks about other sports — use football-data (soccer), nfl-data (NFL), nba-data (NBA), wnba-data (WNBA), nhl-data (NHL), mlb-data (MLB), tennis-data (tennis), golf-data (golf), cfb-data (college football), cbb-data (college basketball), or fastf1 (F1). For betting odds use polymarket or kalshi. For general news use sports-news. Don't use for ICC rankings — no free source exists (v1 limitation).
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# Cricket Data (ESPN + Cricsheet)

Before writing queries, consult `references/api-reference.md` for endpoints, ID conventions, and data shapes. See `references/competitions.md` for the Cricsheet competition codes.

## Quick Start

Prefer the CLI — it avoids Python import path issues. There are two backends: ESPN (live-ish) and Cricsheet (historical).

```bash
# ESPN backend (live-ish) — discover series first, then use its numeric ID
sports-skills cricket get_series
sports-skills cricket get_scoreboard --series_id=8048
sports-skills cricket get_standings --series_id=8048
sports-skills cricket get_game_summary --series_id=8048 --event_id=1535465
sports-skills cricket get_news --series_id=8048

# Cricsheet backend (historical, completed matches) — uses letter codes
sports-skills cricket get_competitions
sports-skills cricket get_matches --competition=ipl --season=2026
sports-skills cricket get_match_deliveries --competition=ipl --match_id=1473508
sports-skills cricket get_player_stats --competition=ipl --player="V Kohli"
sports-skills cricket find_player --name=kohli
```

## CRITICAL: Before Any Query

CRITICAL: Before calling any data endpoint, verify:

- **ESPN series IDs are per-series, not per-league.** Always discover them with `get_series` first. IDs change every season for recurring tournaments (e.g. each IPL season has a different ID). Never hardcode them — the `8048` in the examples is illustrative, not permanent.
- **Two ID spaces.** `get_series` returns ESPN IDs (live, numeric, e.g. `8048`). `get_competitions` returns Cricsheet codes (historical, letter codes, e.g. `ipl`). They are unrelated except at the match level: a Cricsheet `match_id` equals the ESPNcricinfo match ID, so it bridges the two backends.
- **Cricsheet covers completed matches only** (~1-day lag after a match finishes). For anything live or upcoming, use the ESPN commands (`get_scoreboard`, `get_series`).
- **`get_player_stats` requires the exact Cricsheet name spelling** (e.g. `"V Kohli"`, not `"Virat Kohli"`). Resolve the spelling with `find_player` first.
- **No ICC rankings** — there is no free source (v1 limitation). Series standings come from `get_standings`, which is empty for most bilateral tours (only league/group tournaments publish a points table).
- **First Cricsheet call per competition per day downloads a zip.** Large competitions (Tests, ODIs, IPL) are tens of MB. Zips are cached 24h at `~/.cache/sports-skills/cricsheet/`; later calls in the same day are fast.

Agents can run `scripts/validate_params.sh` to pre-validate `--competition`, `--series_id`, and `--date` before querying.

## Commands

### ESPN backend (live-ish)

| Command | Required params | Description |
|---|---|---|
| `get_series` | — | List currently-active cricket series with ESPN series IDs and live events |
| `get_scoreboard` | `series_id` (opt `date`) | Matches + scores + status for a series |
| `get_standings` | `series_id` | Points table for a series (empty for most bilateral tours) |
| `get_game_summary` | `series_id`, `event_id` | Match detail: rosters, leaders, matchcards, venue info |
| `get_news` | `series_id` | News articles for a series |

### Cricsheet backend (historical, ODC-BY 1.0)

| Command | Required params | Description |
|---|---|---|
| `get_competitions` | — | List Cricsheet competition codes |
| `get_matches` | `competition` (opt `season`) | Completed matches for a competition, newest first |
| `get_match_deliveries` | `competition`, `match_id` (opt `innings`) | Ball-by-ball deliveries for a completed match |
| `get_player_stats` | `competition`, `player` (opt `season`) | Aggregate batting + bowling stats for a player |
| `find_player` | `name` | Search Cricsheet player registry; returns ESPNcricinfo ID mappings |

Dates accept `YYYYMMDD` or `YYYY-MM-DD`. `season` is the start year (e.g. `2020` matches Cricsheet's `"2020/21"`). See `references/api-reference.md` for full parameter lists and return shapes.

## Workflows

### Live / recent series check
1. `get_series` → pick the series and note its `series_id`.
2. `get_scoreboard --series_id=<id>` → present matches by status and score.
3. For one match's detail: `get_game_summary --series_id=<id> --event_id=<id>`.

### Points table (league tournaments)
1. `get_series` → find the tournament's `series_id`.
2. `get_standings --series_id=<id>`. If empty, it is a bilateral tour with no published table.

### Historical player stats
1. `find_player --name=<substring>` → confirm the exact `name` spelling.
2. `get_player_stats --competition=<code> --player="<exact name>"` (optionally `--season`).

### Ball-by-ball history
1. `get_matches --competition=<code> [--season=<year>]` → find the `match_id`.
2. `get_match_deliveries --competition=<code> --match_id=<id> [--innings=N]`.

### Cricket news
Cricket news is series-scoped — there is no global feed.
1. `get_series` → pick the relevant series and note its `series_id`.
2. `get_news --series_id=<id>` → present the articles.

## Commands that DO NOT exist — never call these

- ~~`get_player`~~ / ~~`get_player_info`~~ — do not exist. Use `find_player` to resolve a name, then `get_player_stats` for career numbers.
- ~~`get_match`~~ — does not exist. Use `get_matches` (historical list) or `get_game_summary` (one ESPN match's detail).
- ~~`get_rankings`~~ — does not exist. There is no free ICC rankings source (v1 limitation).
- ~~`get_teams`~~ / ~~`get_team_roster`~~ — do not exist. Rosters come inside `get_game_summary`.
- ~~`get_play_by_play`~~ — does not exist. Use `get_match_deliveries` for ball-by-ball data on completed matches.

If a command is not listed in the Commands table above, it does not exist.

## Attribution

Cricsheet data is licensed ODC-BY 1.0. Every Cricsheet response includes an `attribution` field (`"Data from Cricsheet (cricsheet.org), ODC-BY 1.0"`). Preserve this attribution string when republishing the data.
