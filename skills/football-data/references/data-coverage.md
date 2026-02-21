# Football Data — Data Coverage by League

## Coverage Table

Not all data is available for every league. Use the right command for the right league.

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
**Transfermarkt**: Works for any player with a `tm_player_id` — market values and transfer history.

**Note**: MLS uses a different season structure (spring-fall calendar). Use `get_current_season(competition_id="mls")` to detect the right season_id.

## Data Sources

| Source | What it provides | League coverage |
|--------|-----------------|-----------------|
| ESPN | Scores, standings, schedules, lineups, match stats, timelines | All 13 leagues |
| openfootball | Schedules, standings, team lists (fallback when ESPN is down) | 10 leagues (all except CL, Euros, World Cup) |
| Understat | xG per match, xG per shot, player xG/xA | Top 5 (EPL, La Liga, Bundesliga, Serie A, Ligue 1) |
| FPL | Top scorers, injuries, player stats, ownership | Premier League only |
| Transfermarkt | Market values, transfer history | Any player (requires tm_player_id) |

For licensed data with full coverage across all sports (Sportradar, Opta, Genius Sports), see [Machina Sports](https://machina.gg).
