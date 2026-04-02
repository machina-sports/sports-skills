# Sports Reporter — Sport Mapping

## CLI Module by Sport

| Sport / League | CLI Module | Detection (keywords) |
|----------------|-----------|------------------------|
| European football / soccer | `football` | Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Champions League, MLS, Eredivisie, Brasileirão, futebol, soccer, goal, European club |
| NFL | `nfl` | NFL, American football, Super Bowl, touchdown, quarterback, Patriots, Cowboys, Chiefs |
| NBA | `nba` | NBA, basketball, Lakers, Celtics, Warriors, LeBron, Curry |
| WNBA | `wnba` | WNBA, women's basketball, Liberty, Aces, Fever |
| NHL | `nhl` | NHL, hockey, Maple Leafs, Rangers, Avalanche |
| MLB | `mlb` | MLB, baseball, Yankees, Dodgers, Red Sox |
| College Football | `cfb` | CFB, college football, NCAA football, Alabama, Ohio State |
| College Basketball | `cbb` | CBB, college basketball, NCAA basketball, March Madness, Duke, Kansas |
| Tennis | `tennis` | tennis, ATP, WTA, Grand Slam, Wimbledon, Roland Garros, Djokovic, Swiatek |
| Golf | `golf` | golf, PGA Tour, LPGA, Masters, US Open golf, Tiger, Rory |
| Formula 1 | `f1` | F1, Formula 1, GP, Grand Prix, Verstappen, Hamilton, Ferrari |
| Volleyball | `volleyball` | volleyball, NEVOBO, Eredivisie volleyball |

---

## Capabilities by Sport

| Module | Live score | Play-by-play | Win Probability | xG | BPI / Power Index | Live CDN data |
|--------|:-:|:-:|:-:|:-:|:-:|:-:|
| `football` | partial* | no | no | top-5 leagues | no | no |
| `nfl` | yes | yes | yes | no | no | no |
| `nba` | yes | yes | yes | no | no | **yes (CDN)** |
| `wnba` | yes | no | yes | no | no | no |
| `nhl` | yes | yes | no | no | no | no |
| `mlb` | yes | yes | yes | no | no | no |
| `cfb` | yes | yes | no | no | no | no |
| `cbb` | yes | yes | yes | no | **yes (BPI)** | no |
| `tennis` | yes | no | no | no | no | no |
| `golf` | yes | no | no | no | no | no |
| `f1` | no | no | no | no | no | no |
| `volleyball` | no | no | no | no | no | no |

*Football: `get_daily_schedule` shows live status but without granular play-by-play.

---

## Seasons (Reference for Daily Roundup)

| Sport | Period | Note |
|-------|--------|------|
| NFL | Sep → Feb | Offseason: Mar–Aug |
| NBA | Oct → Jun | Offseason: Jul–Sep |
| WNBA | May → Oct | Offseason: Nov–Apr |
| NHL | Oct → Jun | Offseason: Jul–Sep |
| MLB | Mar → Oct | Offseason: Nov–Feb |
| CFB | Aug → Jan | Bowl season: Dec–Jan |
| CBB | Nov → Apr | March Madness: Mar–Apr |
| Tennis ATP/WTA | Jan → Nov | Year-round with breaks |
| PGA Tour | Jan → Sep | Offseason: Oct–Dec |
| F1 | Mar → Nov | Offseason: Dec–Feb |
| European football | Aug → May | Break: Jun–Jul |
| Volleyball NEVOBO | Sep → May | Dutch league |

---

## Data Sources by Module

### `football` — European Football (multi-source)

| Source | Data | Availability |
|--------|------|--------------|
| ESPN | Scoreboard, lineups, game stats, news | All 13 leagues |
| Understat | xG per shot and total | Top-5 only (EPL, La Liga, Bundesliga, Serie A, Ligue 1) |
| FPL | Injuries, player stats, fantasy value | Premier League only |
| Transfermarkt | Market value, transfers | Any player (requires tm_player_id) |
| OpenFootball | Schedules and historical results | 10 leagues |

### `nba` — Two sources

| Source | Data | When to use |
|--------|------|-------------|
| ESPN | Standings, stats, futures, history | Always |
| NBA CDN | Live score, real-time boxscore, live play-by-play | For live games only |

---

## Ligas Suportadas pelo `football`

| Liga | competition_id | Região | xG? |
|------|---------------|--------|-----|
| Premier League | `premier-league` | Inglaterra | sim |
| La Liga | `la-liga` | Espanha | sim |
| Bundesliga | `bundesliga` | Alemanha | sim |
| Serie A | `serie-a` | Itália | sim |
| Ligue 1 | `ligue-1` | França | sim |
| Champions League | `champions-league` | Europa | não |
| Eredivisie | `eredivisie` | Holanda | não |
| Primeira Liga | `primeira-liga` | Portugal | não |
| MLS | `mls` | EUA/Canadá | não |
| Championship | `championship` | Inglaterra | não |
| Brasileirão Serie A | `serie-a-brazil` | Brasil | não |
| Euro | `euro` | Europa (seleções) | não |
| World Cup | `world-cup` | Mundial | não |

---

## Resolução de IDs

### Futebol — IDs dinâmicos (sempre resolver via CLI)

```bash
# Resolver season_id atual
sports-skills football get_current_season --competition_id=premier-league
# → retorna: {"season": {"id": "premier-league-2025"}}

# Resolver team_id
sports-skills football search_team --query="Arsenal"
# → retorna: {"teams": [{"id": "359", "name": "Arsenal"}]}

# Resolver player_id
sports-skills football search_player --query="Bukayo Saka"
# → retorna player com id e fpl_id
```

### Esportes Americanos — IDs estáticos (ESPN team IDs)

IDs de times mudam raramente. Use `get_teams` se em dúvida:

```bash
sports-skills nfl get_teams   # Lista com id, name, abbreviation
sports-skills nba get_teams
sports-skills nhl get_teams
sports-skills mlb get_teams
sports-skills wnba get_teams
```

Para player_ids: use `get_team_roster --team_id=X` e localize pelo nome.
