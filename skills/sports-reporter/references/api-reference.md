# Sports Reporter — API Reference

CLI commands organized by article type. For full details on each command (parameters, return shapes), refer to the `api-reference.md` of the corresponding skill.

---

## Preview (Pre-game)

### Discover upcoming games

| Sport | Command | Parameters |
|-------|---------|-----------|
| NFL | `sports-skills nfl get_schedule` | `--season=YYYY` `--week=N` |
| NBA | `sports-skills nba get_schedule` | `--date=YYYY-MM-DD` `--season=YYYY` |
| WNBA | `sports-skills wnba get_schedule` | `--date=YYYY-MM-DD` |
| NHL | `sports-skills nhl get_schedule` | `--date=YYYY-MM-DD` |
| MLB | `sports-skills mlb get_schedule` | `--date=YYYY-MM-DD` |
| CFB | `sports-skills cfb get_schedule` | `--season=YYYY` `--week=N` |
| CBB | `sports-skills cbb get_schedule` | `--date=YYYY-MM-DD` |
| Tennis | `sports-skills tennis get_scoreboard` | `--tour=atp\|wta` `--date=YYYY-MM-DD` |
| Golf | `sports-skills golf get_schedule` | `--tour=pga\|lpga` |
| Football | `sports-skills football get_daily_schedule` | `--date=YYYY-MM-DD` |
| F1 | `sports-skills f1 get_race_schedule` | `--year=YYYY` |

### Recent form and context

```bash
# Table position
sports-skills {sport} get_standings [--season=YYYY]

# Team's recent games (filter finished ones)
sports-skills {sport} get_team_schedule --team_id=X [--season=YYYY]

# Injured / unavailable players
sports-skills {sport} get_injuries                                    # All sports
sports-skills football get_missing_players --season_id=premier-league-YYYY  # PL only

# Probable lineup (football — available close to kickoff)
sports-skills football get_event_lineups --event_id=X
```

---

## Live Report

### Live scoreboard

```bash
sports-skills nfl get_scoreboard
sports-skills nba get_scoreboard
sports-skills nba get_live_scoreboard          # NBA CDN — more granular and faster
sports-skills wnba get_scoreboard
sports-skills nhl get_scoreboard
sports-skills mlb get_scoreboard
sports-skills cfb get_scoreboard
sports-skills cbb get_scoreboard
sports-skills tennis get_scoreboard --tour=atp|wta
sports-skills golf get_leaderboard --tour=pga|lpga
sports-skills football get_daily_schedule      # Football — includes live status
```

### Live game details

```bash
# Play-by-play (after obtaining event_id/game_id from the scoreboard)
sports-skills nfl get_play_by_play --event_id=X
sports-skills nba get_live_playbyplay --game_id=X [--scoring_only=false]
sports-skills nhl get_play_by_play --event_id=X
sports-skills mlb get_play_by_play --event_id=X
sports-skills cfb get_play_by_play --event_id=X
sports-skills cbb get_play_by_play --event_id=X

# Win probability (NFL, NBA, MLB, CBB, WNBA)
sports-skills {sport} get_win_probability --event_id=X

# Live box score (NBA CDN)
sports-skills nba get_live_boxscore --game_id=X

# Live player stats (NBA CDN)
sports-skills nba get_player_live_stats --player_name="Player Name"
```

---

## Match Report (Post-game)

### Find a finished game

```bash
# By date
sports-skills {sport} get_scoreboard --date=YYYY-MM-DD
sports-skills football get_daily_schedule --date=YYYY-MM-DD

# By team (search in schedule)
sports-skills {sport} get_team_schedule --team_id=X
```

### Finished match data

```bash
# Box score / full summary (all sports)
sports-skills {sport} get_game_summary --event_id=X
# Returns: final score, per-player stats, scoring plays, leaders

# Full play-by-play (all sports except Tennis/Golf)
sports-skills {sport} get_play_by_play --event_id=X

# European football — extra data (run in parallel)
sports-skills football get_event_statistics --event_id=X      # Possession, shots, passes, fouls
sports-skills football get_event_timeline --event_id=X        # Goals, cards, substitutions with minute
sports-skills football get_event_xg --event_id=X              # xG per shot (top-5 leagues only)
sports-skills football get_event_players_statistics --event_id=X  # Individual stats + xG
```

### Championship impact

```bash
# Update table after the game
sports-skills {sport} get_standings [--season=YYYY]

# Teams' upcoming games
sports-skills {sport} get_team_schedule --team_id=X
```

---

## Team Analysis

### Resolve team_id

```bash
sports-skills nfl get_teams
sports-skills nba get_teams
sports-skills nhl get_teams
sports-skills mlb get_teams
sports-skills wnba get_teams
sports-skills cfb get_teams
sports-skills cbb get_teams
sports-skills football search_team --query="Team Name" [--competition_id=premier-league]
```

### Team data (run in parallel after obtaining team_id)

```bash
# Position and table
sports-skills {sport} get_standings [--season=YYYY]

# Schedule and form (filter last 5 and next 5)
sports-skills {sport} get_team_schedule --team_id=X [--season=YYYY]

# Team statistics
sports-skills {sport} get_team_stats --team_id=X [--season_year=YYYY]

# Roster
sports-skills {sport} get_team_roster --team_id=X

# Injured players
sports-skills {sport} get_injuries

# Depth chart (NFL, NBA, MLB)
sports-skills {sport} get_depth_chart --team_id=X

# Recent news
sports-skills {sport} get_news --team_id=X

# Football: profile and unavailable players
sports-skills football get_team_profile --team_id=X [--league_slug=premier-league]
sports-skills football get_missing_players --season_id=premier-league-YYYY   # PL only
```

---

## Player Profile

### Resolve player_id

```bash
# Football
sports-skills football search_player --query="Player Name"

# Other sports: via team roster
sports-skills {sport} get_team_roster --team_id=X
# → locate player_id in the response by name
```

### Player data (run in parallel after obtaining player_id)

```bash
# Season statistics (all sports)
sports-skills {sport} get_player_stats --player_id=X [--season_year=YYYY]

# Football — extra data
sports-skills football get_player_profile --player_id=X    # FPL + Transfermarkt
sports-skills football get_player_season_stats --player_id=X [--league_slug=premier-league]

# News
sports-skills {sport} get_news [--team_id=X]               # Filter by player name
```

---

## Daily Roundup

### Scoreboard for all sports (run in parallel)

```bash
sports-skills nfl get_scoreboard
sports-skills nba get_scoreboard
sports-skills nhl get_scoreboard
sports-skills mlb get_scoreboard
sports-skills wnba get_scoreboard
sports-skills cfb get_scoreboard
sports-skills cbb get_scoreboard
sports-skills tennis get_scoreboard --tour=atp
sports-skills tennis get_scoreboard --tour=wta
sports-skills golf get_leaderboard --tour=pga
sports-skills football get_daily_schedule --date=YYYY-MM-DD
```

**Optimization:** Before calling all of them, check `currentDate` and call only sports in season — see `references/sport-mapping.md` for the schedule by sport.

---

## Return types by command

| Command | Main field | Highlights |
|---------|------------|-----------|
| `get_scoreboard` | `events[]` | status, scores, competitors |
| `get_standings` | `groups[]` | conference, division, W-L, PCT |
| `get_game_summary` | `boxscore`, `scoring_plays`, `leaders` | per-player stats |
| `get_play_by_play` | `drives[]` / `plays[]` | play sequence |
| `get_win_probability` | `items[]` | homeWinPercentage per play |
| `get_injuries` | `teams[].injuries[]` | status, type, return estimate |
| `get_team_stats` | `categories[]` | stats by category with rank |
| `get_player_stats` | `categories[]` | stats with rank and per_game |
| `get_event_statistics` (football) | `teams[]` | possession, shots, passes, fouls |
| `get_event_timeline` (football) | `entries[]` | goals, cards, subs with minute |
| `get_event_xg` (football) | `home_xg`, `away_xg`, `shots[]` | xG per shot and total |
| `get_live_scoreboard` (NBA) | `games[]` | score, period, clock |
| `get_live_playbyplay` (NBA) | `plays[]` | action, player, score |
