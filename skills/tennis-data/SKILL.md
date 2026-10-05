---
name: tennis-data
description: |
  ATP and WTA tennis data via ESPN public endpoints — tournament scores, season calendars, player rankings, player profiles, and news. Zero config, no API keys.

  Use when: user asks about tennis scores, match results, tournament draws, ATP/WTA rankings, tennis player info, tennis news, a WTA tournament's entry list, or a WTA player's match history.
  Don't use when: user asks about other sports — use football-data (soccer), nfl-data (NFL), nba-data (NBA), wnba-data (WNBA), nhl-data (NHL), mlb-data (MLB), golf-data (golf), cricket-data (cricket), cfb-data (college football), cbb-data (college basketball), or fastf1 (F1). For betting odds use polymarket or kalshi. For news use sports-news. Don't use for live point-by-point data — scores update after each set/match.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# Tennis Data (ATP + WTA)

Before writing queries, consult `references/api-reference.md` for endpoints, ID conventions, and data shapes.

## Quick Start

Prefer the CLI — it avoids Python import path issues:
```bash
sports-skills tennis get_scoreboard --tour=atp
sports-skills tennis get_rankings --tour=wta
sports-skills tennis get_calendar --tour=atp --year=2026
sports-skills tennis get_wta_entry_list --tournament_id=901 --year=2025
sports-skills tennis get_wta_player_results --player_id=320760 --year=2025 --limit=10
```

## CRITICAL: Before Any Query

CRITICAL: Before calling any data endpoint, verify:
- The `tour` parameter is specified (`atp` or `wta`) — there is no default.
- Year is derived from the system prompt's `currentDate` — never hardcoded.

## The `tour` Parameter

Most ESPN-backed commands require `--tour=atp` or `--tour=wta`:
- **ATP**: Men's professional tennis tour
- **WTA**: Women's professional tennis tour

If the user doesn't specify, ask which tour or show both by calling the command twice.

## Commands

| Command | Description |
|---|---|
| `get_scoreboard` | Live/recent tournament scores for a tour |
| `get_rankings` | ATP or WTA player rankings |
| `get_calendar` | Full season tournament calendar |
| `get_player_info` | Individual tennis player profile |
| `get_news` | Tennis news articles |
| `get_wta_entry_list` | WTA entry list (singles players and doubles teams) for one tournament edition — WTA API |
| `get_wta_player_results` | A WTA player's most recent match results (bounded window), newest first — WTA API |

See `references/api-reference.md` for full parameter lists and return shapes.

## WTA API Commands Use Native WTA IDs

`get_wta_entry_list` and `get_wta_player_results` read the public WTA API (api.wtatennis.com), not ESPN:
- `tournament_id` and `player_id` are the WTA's own numeric ids, positive decimals with no leading zeros (e.g. tournament `901`, player `320760`). ESPN ids from `get_rankings` / `get_player_info` / `get_scoreboard` do not work here, and there is no id mapping between the two.
- `get_wta_player_results` returns a **bounded window of the most recent results** (at most `limit`, optionally within one `year`), not a career history. There is no total count: `has_more` only says further matches exist, and `history_complete` is always `false`. Never present `count` as a career or season total.
- Results are dated by **tournament start date** (`tournament_start_date`), not the day each match was played. Never present it as a match date.
- Matches within one tournament keep the provider's order, which is not guaranteed to be playing order. Don't claim exact within-tournament chronology.
- `winner_code` is the provider's raw side code; no win/loss is derived from it. Don't state who won from it.
- Both commands are WTA-published snapshots (`source.fetched_at`, cached up to 10 minutes). Don't call them complete or live. Under `SPORTS_SKILLS_REPLAY=replay`/`fill`, `source.fetched_at` is `null` and `source.served_at` is only local serving time — not data freshness.

## Workflows

### Live Tournament Check
1. `get_scoreboard --tour=<atp|wta>`
2. Present current matches by round.
3. For player info, use `get_player_info --player_id=<id>`.

### Rankings Lookup
1. `get_rankings --tour=<atp|wta> --limit=20`
2. Present rankings with points and trend.

### Season Calendar
1. `get_calendar --tour=<atp|wta> --year=<year>`
2. Filter for specific tournament.

### WTA Entry List
1. `get_wta_entry_list --tournament_id=<wta_id> --year=<year>`
2. Present each event (`format`: singles/doubles) with seeds and entry types. It is an entry list, not a draw.

### WTA Player Form
1. `get_wta_player_results --player_id=<wta_id> --year=<year> --limit=20`
2. Group by tournament; say these are the most recent `count` matches, and when `has_more` is true that earlier matches exist but were not fetched.

## Examples

Example 1: Live matches
User says: "What ATP matches are happening right now?"
Actions:
1. Call `get_scoreboard(tour="atp")`
Result: Current tournament matches organized by round with scores and status

Example 2: Women's rankings
User says: "Show me the WTA rankings"
Actions:
1. Call `get_rankings(tour="wta", limit=20)`
Result: Top 20 WTA players with rank, name, points, and trend

Example 3: Upcoming Grand Slam date
User says: "When is the French Open this year?"
Actions:
1. Derive year from `currentDate`
2. Call `get_calendar(tour="atp", year=<derived_year>)`
3. Search results for "Roland Garros" (the French Open's official name)
Result: French Open dates, location (Paris), and surface (clay)

## Commands that DO NOT exist — never call these

- ~~`get_matches`~~ — does not exist. Use `get_scoreboard` for current match scores.
- ~~`get_draw`~~ — does not exist. Tournament draw data is not available via this API.
- ~~`get_head_to_head`~~ — does not exist. Head-to-head records are not available via this API.
- ~~`get_standings`~~ — does not exist. Tennis uses `get_rankings`, not standings.
- ~~`get_match_stats`~~ — does not exist. ESPN publishes no per-match statistics for tennis (aces, double faults, break points): scoreboard `statistics` lists are empty and the per-match stats endpoint returns "No competitor stats found", even for Grand Slam finals. Only set scores are available.

If a command is not listed in the Commands table above, it does not exist.

## Troubleshooting

Error: `get_scoreboard` returns no matches
Cause: Tennis tournaments run specific weeks; no tournament may be scheduled this week
Solution: Call `get_calendar(tour=...)` to find when the next event is scheduled

Error: Rankings are empty
Cause: Rankings update weekly on Mondays; there may be a brief update window
Solution: The command auto-retries previous weeks. If still empty, retry in a few minutes

Error: Player profile fails
Cause: Player ID is incorrect
Solution: Use `get_rankings` to find player IDs from the current rankings list, or verify via ESPN tennis URLs

Error: `get_wta_entry_list` / `get_wta_player_results` rejects the id or returns HTTP 404
Cause: An ESPN id (or a non-numeric value) was passed; these commands take native WTA numeric ids only
Solution: Use the WTA's own tournament/player id. Don't substitute ESPN ids

Error: `get_wta_player_results --year=...` fails with "outside year ... inconclusive"
Cause: The WTA API returned matches from other years, so it likely ignored the year filter
Solution: Report that the season's results could not be confirmed. Don't retry without `year` and present those matches as that season

Error: `get_wta_entry_list` succeeds with `count: 0`
Cause: The WTA has not published an entry list for that tournament and year, or the id/year pair does not exist
Solution: Read the `note` field and tell the user no entry list is available — don't report an empty field of players

Error: Scores seem delayed or don't update live
Cause: Scores update after each set/match is completed, not point-by-point
Solution: This is expected behavior. Refresh `get_scoreboard` periodically for updated set scores
