# Football Data — JSON Schemas

## get_current_season

Returns `data.competition` and `data.season`:
```json
{"competition": {"id": "premier-league", "name": "Premier League"}, "season": {"id": "premier-league-2025", "name": "2025-26 English Premier League", "year": "2025"}}
```

## get_season_standings

Returns `data.standings[].entries[]`:
```json
{
  "position": 1,
  "team": {"id": "359", "name": "Arsenal", "short_name": "Arsenal", "abbreviation": "ARS", "crest": "https://..."},
  "played": 26, "won": 17, "drawn": 6, "lost": 3,
  "goals_for": 50, "goals_against": 18, "goal_difference": 32, "points": 57
}
```

## get_season_leaders

Returns `data.leaders[]` — note: player name is nested under `.player.name`:
```json
{
  "player": {"id": "223094", "name": "Erling Haaland", "first_name": "Erling", "last_name": "Haaland", "position": "Forward"},
  "team": {"id": "43", "name": "Man City"},
  "goals": 22, "assists": 6, "penalties": 0, "played_matches": 25
}
```
Returns empty for non-PL leagues.

## get_daily_schedule

Returns `data.date` and `data.events[]`:
```json
{
  "id": "748381", "status": "not_started", "start_time": "2026-02-16T20:00Z",
  "competition": {"id": "la-liga", "name": "La Liga"},
  "season": {"id": "la-liga-2025", "year": "2025"},
  "venue": {"name": "Estadi Montilivi", "city": "Girona"},
  "competitors": [
    {"team": {"id": "9812", "name": "Girona", "abbreviation": "GIR"}, "qualifier": "home", "score": 0},
    {"team": {"id": "83", "name": "Barcelona", "abbreviation": "BAR"}, "qualifier": "away", "score": 0}
  ],
  "scores": {"home": 0, "away": 0}
}
```
Status values: `"not_started"`, `"live"`, `"halftime"`, `"closed"`, `"postponed"`.

## get_event_lineups

Returns `data.lineups[]`:
```json
{
  "team": {"id": "364", "name": "Liverpool", "abbreviation": "LIV"},
  "qualifier": "home",
  "formation": "4-3-3",
  "starting": [{"id": "275599", "name": "Caoimhin Kelleher", "position": "Goalkeeper", "shirt_number": 1}],
  "bench": [{"id": "...", "name": "...", "position": "...", "shirt_number": 62}]
}
```

## get_event_statistics

Returns `data.teams[]`:
```json
{
  "team": {"id": "244", "name": "Brentford"},
  "qualifier": "home",
  "statistics": {"ball_possession": "40.8", "shots_total": "10", "shots_on_target": "3", "fouls": "12", "corners": "4"}
}
```

## get_event_xg

Returns `data.teams[]` and `data.shots[]`:
```json
{"team": {"id": "244", "name": "Brentford"}, "qualifier": "home", "xg": 1.812}
```
`data.shots[]` contains individual shot data with xG per shot. Note: very recent matches (last 24-48h) may not be indexed on Understat yet.

## get_event_players_statistics

Returns `data.teams[].players[]`:
```json
{
  "id": "...", "name": "Bukayo Saka", "position": "Midfielder", "shirt_number": 7, "starter": true,
  "statistics": {"appearances": "1", "shotsTotal": "3", "shotsOnTarget": "1", "foulsCommitted": "1", "xg": "0.45", "xa": "0.12"}
}
```
`xg` and `xa` fields only present for top 5 leagues.

## get_missing_players

Returns `data.teams[].players[]`:
```json
{
  "id": "463748", "name": "Mikel Merino Zazon", "web_name": "Merino",
  "position": "Midfielder", "status": "injured",
  "news": "Foot injury - Unknown return date",
  "chance_of_playing_this_round": 0, "chance_of_playing_next_round": 0
}
```
Status values: `"injured"`, `"unavailable"`, `"doubtful"`, `"suspended"`.

## get_season_transfers

Returns `data.transfers[]`:
```json
{
  "player_tm_id": "433177", "date": "2019-07-01", "season": "19/20",
  "from_team": {"name": "Arsenal U23", "image": "https://..."},
  "to_team": {"name": "Arsenal", "image": "https://..."},
  "fee": "-", "market_value": "-"
}
```

## get_player_profile

With `tm_player_id`, returns `data.player` with:
```json
{
  "market_value": {"value": 130000000, "currency": "EUR", "formatted": "EUR130.00m", "date": "09/12/2025", "age": "24", "club": "Arsenal FC"},
  "market_value_history": [{"value": 7000000, "formatted": "EUR7.00m", "date": "23/09/2019", "club": "Arsenal FC"}],
  "transfer_history": [
    {"player_tm_id": "433177", "date": "2019-07-01", "season": "19/20", "from_team": {"name": "Arsenal U23"}, "to_team": {"name": "Arsenal"}, "fee": "-"}
  ]
}
```
With `fpl_id`, also includes `data.player.fpl_data` with FPL stats (points, form, ICT index, ownership, etc.).

## search_team

Returns `data.results[]` with `team`, `competition`, and `season` for each match:
```json
{"team": {"id": "874", "name": "Corinthians"}, "competition": {"id": "serie-a-brazil", "name": "Serie A Brazil"}, "season": {"id": "serie-a-brazil-2025", "year": "2025"}}
```
