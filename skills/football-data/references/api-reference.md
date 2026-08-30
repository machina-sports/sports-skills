# Football Data — API Reference

## ID Conventions

- **season_id**: `{league-slug}-{year}` e.g. `"premier-league-2025"`, `"la-liga-2025"` (year = start year of the season)
- **competition_id**: league slug e.g. `"premier-league"`, `"serie-a"`, `"champions-league"`
- **team_id**: ESPN team ID (numeric string) e.g. `"359"` (Arsenal), `"86"` (Real Madrid)
- **event_id**: ESPN event ID (numeric string) e.g. `"740847"`
- **fpl_id**: FPL element ID or code (PL players only)
- **tm_player_id**: Transfermarkt player ID e.g. `"433177"` (Saka), `"342229"` (Mbappe)

## Data Coverage by League

| Command | All 13 leagues | Top 5 only | PL only |
|---------|:-:|:-:|:-:|
| get_season_standings | x | | |
| get_daily_schedule | x | | |
| get_season_schedule | x | | |
| get_season_teams | x | | |
| search_team | x | | |
| get_team_schedule | x | | |
| get_team_profile | x | | |
| get_event_summary | x | | |
| get_event_lineups | x | | |
| get_event_statistics | x | | |
| get_event_timeline | x | | |
| get_current_season | x | | |
| get_competitions | x | | |
| get_event_xg | | x | |
| get_event_players_statistics (with xG) | | x | |
| get_season_leaders | | | x |
| get_missing_players | | | x |

**Top 5 leagues** (Understat): EPL, La Liga, Bundesliga, Serie A, Ligue 1.
**PL only** (FPL): Premier League — injury news, player stats, ownership, ICT index.
**All leagues**: via ESPN — scores, standings, schedules, match summaries, lineups, team stats.

## Data Sources

| Source | What it provides | League coverage |
|--------|-----------------|-----------------|
| ESPN | Scores, standings, schedules, lineups, match stats, timelines | All 13 leagues |
| openfootball | Schedules, standings, team lists (fallback) | 10 leagues (all except CL, Euros, World Cup) |
| Understat | xG per match, xG per shot, player xG/xA | Top 5 (EPL, La Liga, Bundesliga, Serie A, Ligue 1) |
| FPL | Top scorers, injuries, player stats, ownership | Premier League only |
| Transfermarkt | Market values, transfer history | Any player (requires tm_player_id) |
| football-data.co.uk | Head-to-head history, historical results + match stats | 11 European domestic leagues, 1993+ |
| ClubElo | Team strength (Elo rating), fixture-difficulty control, match forecasts | European clubs |

## Commands (Detailed)

### get_current_season
Detect current season for a competition. Works for all leagues.
- `competition_id` (str, required): Competition slug

Returns `data.competition` and `data.season`:
```json
{"competition": {"id": "premier-league"}, "season": {"id": "premier-league-2025", "year": "2025"}}
```

### get_competitions
List available competitions with current season info. No params. Works for all leagues.

Returns `data.competitions[]` with `id`, `name`, `code`, `current_season`.

### get_competition_seasons
Get available seasons for a competition.
- `competition_id` (str, required): Competition slug

### get_season_schedule
Get full season match schedule.
- `season_id` (str, required): Season slug

Returns `data.schedules[]`.

### get_season_standings
Get league table for a season.
- `season_id` (str, required): Season slug

Returns `data.standings[].entries[]`:
```json
{
  "position": 1,
  "team": {"id": "359", "name": "Arsenal", "abbreviation": "ARS"},
  "played": 26, "won": 17, "drawn": 6, "lost": 3,
  "goals_for": 50, "goals_against": 18, "goal_difference": 32, "points": 57
}
```

### get_season_leaders
Get top scorers/leaders for a season. **Premier League only** (via FPL).
- `season_id` (str, required): Season slug (must be `premier-league-*`)

Returns `data.leaders[]` with nested `player.name`, `team.name`, goals, assists, played_matches.

### get_season_teams
Get teams in a season.
- `season_id` (str, required): Season slug

### search_team
Search for a team by name across all leagues. Uses fuzzy matching.
- `query` (str, required): Team name
- `competition_id` (str, optional): Limit to one league

Returns `data.results[]` with `team`, `competition`, `season` for each match.

### search_player
Search for a football player by name.
- `query` (str, required): Player name

Returns `data.results[]` with `tm_player_id`, `espn_id`, `name`, `team`, `competition`.

### get_team_profile
Get basic team info (name, crest, venue). Does NOT return squad.
- `team_id` (str, required): ESPN team ID
- `league_slug` (str, optional): League hint

### get_daily_schedule
Get all matches for a specific date across all leagues.
- `date` (str, optional): YYYY-MM-DD. Defaults to today.

Returns `data.date` and `data.events[]`:
```json
{
  "id": "748381", "status": "not_started", "start_time": "2026-02-16T20:00Z",
  "competition": {"id": "la-liga"}, "season": {"id": "la-liga-2025"},
  "competitors": [
    {"team": {"id": "9812", "name": "Girona", "abbreviation": "GIR"}, "qualifier": "home", "score": 0},
    {"team": {"id": "83", "name": "Barcelona", "abbreviation": "BAR"}, "qualifier": "away", "score": 0}
  ]
}
```
Status values: `"not_started"`, `"live"`, `"halftime"`, `"closed"`, `"postponed"`.

### get_event_summary
Get match summary with scores.
- `event_id` (str, required): Match/event ID

### get_event_lineups
Get match lineups.
- `event_id` (str, required): Match/event ID

Returns `data.lineups[]` with team, formation, starting players, and bench.

### get_event_statistics
Get match team statistics.
- `event_id` (str, required): Match/event ID

Returns `data.teams[]` with ball_possession, shots_total, shots_on_target, fouls, corners.

### get_event_timeline
Get match timeline/key events (goals, cards, substitutions).
- `event_id` (str, required): Match/event ID

### get_team_schedule
Get schedule for a specific team (past results + upcoming fixtures).
- `team_id` (str, required): ESPN team ID
- `league_slug` (str, optional): League hint
- `season_year` (str, optional): Season year filter
- `competition_id` (str, optional): Filter to a single competition

### get_head_to_head
Head-to-head history between two teams via football-data.co.uk (free CSV).
**European domestic leagues only** (see coverage below). Returns an informative
message for other leagues (MLS, Brazil, Champions League, Euros, World Cup).
- `team_id` (str, required): First team ESPN ID
- `team_id_2` (str, required): Second team ESPN ID
- `league_slug` (str, optional): League hint; inferred from the teams when omitted
- `max_seasons` (int, optional): Recent seasons to search (default 10, max 34)

Returns `data.events[]` (per meeting: `date`, `home_team`/`away_team`, `home_score`/
`away_score`, `result` H/D/A, and a `stats` block with shots/SoT/corners when the
source has them) plus `data.summary` (`total_meetings`, per-team `wins`+`goals`,
`draws`). Only counts meetings played in a shared division; ESPN stays the fixture
authority for live/recent scores.

Each entry in `data.teams[]` carries a `resolved` flag plus `matched_as` (the
football-data.co.uk label it resolved to) or a `reason` when it did not. A club
that could not be matched is reported as such — `total_meetings: 0` with an
unresolved club means "we could not look this pair up", not "they never met".

Coverage: Premier League, Championship, La Liga, Serie A, Bundesliga, Ligue 1,
Eredivisie, Primeira Liga, Scottish Premiership, Belgian Pro League, Turkish Super Lig.

### get_team_strength
Team strength via ClubElo Elo rating (free CSV). **European clubs only** — a
strength / fixture-difficulty control, not an official result.
- `team_id` (str, required): First team ESPN ID
- `team_id_2` (str, optional): Second team ESPN ID → returns an Elo comparison
- `date` (str, optional): YYYY-MM-DD snapshot for historical Elo (default today)
- `league_slug` (str, optional): League hint; inferred from the teams when omitted

Returns `data.teams[]` with `elo`, `rank`, `country`, `level`, `as_of`, `matched_as`,
and a `resolved` flag. With two teams also returns `elo_difference` (team1 − team2)
and `favorite`. Team names are matched to ClubElo's labels (country-scoped, reserve
teams excluded); teams that cannot be confidently matched are reported, not guessed.
Coverage: the same 11 European domestic leagues as `get_head_to_head`.

### get_match_forecast
ClubElo win/draw/loss + scoreline forecast for a team's upcoming fixtures (free CSV).
**ClubElo forecasts only ~a week ahead** — empty between matchdays or off-season.
European clubs only.
- `team_id` (str, required): Team ESPN ID
- `team_id_2` (str, optional): Opponent ESPN ID → filters to fixtures against that team
- `league_slug` (str, optional): League hint; inferred from the team when omitted

Returns `data.fixtures[]` with `date`, `competition`, home/away teams, `team_side`,
`win_prob`/`draw_prob`/`loss_prob` (team perspective), and `likely_scorelines`.
Model-free probabilities derived from ClubElo's goal-difference distribution — pairs
with the betting/odds skills. Empty results carry an explanatory `message`.

### get_event_xg
Get expected goals (xG) from Understat. **Top 5 leagues only.**
- `event_id` (str, required): Match/event ID

Returns `data.teams[]` with `xg` and `data.shots[]` per shot. May lag 24-48h after a match.

### get_event_players_statistics
Get player-level match statistics with optional xG enrichment.
- `event_id` (str, required): Match/event ID

Returns `data.teams[].players[]` with statistics including `xg` and `xa` (top 5 leagues only).

### get_missing_players
Get injured/missing/doubtful players. **Premier League only** (via FPL).
- `season_id` (str, required): Season slug (must be `premier-league-*`)

Returns `data.teams[].players[]` with status (injured/unavailable/doubtful/suspended), news, chance of playing.

### get_season_transfers
Get transfer history for specific players via Transfermarkt.
- `season_id` (str, required): Season slug
- `tm_player_ids` (list, required): Transfermarkt player IDs

### get_player_season_stats
Get player season stats via ESPN.
- `player_id` (str, required): ESPN athlete ID
- `league_slug` (str, optional): League slug hint

### get_player_profile
Get player profile via FPL and/or Transfermarkt.
- `fpl_id` (str, optional): FPL player ID (PL players only)
- `tm_player_id` (str, optional): Transfermarkt player ID (any league)

Returns market value, value history, transfer history. With `fpl_id`, also returns FPL stats.

## Supported Leagues

Premier League, La Liga, Bundesliga, Serie A, Ligue 1, MLS, Championship, Eredivisie, Primeira Liga, Serie A Brazil, Champions League, European Championship, World Cup.
