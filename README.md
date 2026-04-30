# sports-skills.sh

https://sports-skills.sh

Open-source agent skills for live sports data and prediction markets. Built for the [Agent Skills](https://agentskills.io/specification) spec. Works with [sportsclaw](https://sportsclaw.gg), OpenClaw, Claude Code, Cursor, Copilot, Gemini CLI, and every major AI agent.

**Zero API keys. Zero signup. Just works.**

```bash
npx skills add machina-sports/sports-skills
```

Python package users:

```bash
pip install sports-skills
```

Includes all sports modules in the base package.

To upgrade to the latest version, run the same command with the `--yes` flag:

```bash
npx skills add machina-sports/sports-skills --yes
```

---

## What This Is

A collection of agent skills that wrap **publicly available** sports data sources and APIs. These skills don't provide proprietary data — they give AI agents a structured interface to data that's already freely accessible on the web:

- **Football**: ESPN, Understat, FPL, Transfermarkt — 21 commands across 13 leagues
- **NFL**: ESPN — scores, standings, rosters, schedules, game summaries, leaders, news
- **NBA**: ESPN + NBA CDN — real-time live scores, play-by-play, box scores, standings, rosters, schedules
- **WNBA**: ESPN — scores, standings, rosters, schedules, game summaries, leaders, news
- **NHL**: ESPN — scores, standings, rosters, schedules, game summaries, leaders, news
- **MLB**: ESPN — scores, standings, rosters, schedules, game summaries, leaders, news
- **Tennis**: ESPN — ATP and WTA tournament scores, rankings, calendars, player profiles, news
- **College Football (CFB)**: ESPN — scores, standings, rosters, schedules, AP/Coaches rankings, news
- **College Basketball (CBB)**: ESPN — scores, standings, rosters, schedules, AP/Coaches rankings, news
- **Golf**: ESPN — PGA Tour, LPGA, DP World Tour leaderboards, schedules, player profiles, news
- **Volleyball**: Nevobo — Dutch volleyball (Eredivisie, Topdivisie, Superdivisie) standings, schedules, results, clubs
- **XC/TF**: TFRRS and The Stride Report — NCAA cross country and track & field athlete profiles, personal records, team rosters, meet results, news
- **Formula 1**: FastF1 open-source library — sessions, lap data, race results
- **Prediction Markets**: Kalshi and Polymarket public APIs — markets, prices, order books
- **Sports News**: RSS feeds and Google News — any public feed
- **Metadata**: TheSportsDB — team logos, player photos, stadium info (100+ leagues)

Each skill is a SKILL.md file that any compatible AI agent can load and use immediately. Data comes from third-party public sources and is subject to their respective terms of use.

> **Personal use only.** These open-source skills rely on third-party public APIs and are intended for personal, non-commercial use. For commercial or production workloads with licensed data, SLAs, and enterprise support, see [machina.gg](https://machina.gg).

---

## Available Skills

### Sports Data

| Skill | Sport | Commands | Data Sources |
|-------|-------|----------|-------------|
| `football-data` | Football | 21 | ESPN, FPL, Understat, Transfermarkt |
| `nfl-data` | NFL | 9 | ESPN |
| `nba-data` | NBA | 12 | ESPN, NBA CDN |
| `wnba-data` | WNBA | 9 | ESPN |
| `nhl-data` | NHL | 9 | ESPN |
| `mlb-data` | MLB | 9 | ESPN |
| `tennis-data` | Tennis (ATP + WTA) | 5 | ESPN |
| `cfb-data` | College Football (CFB) | 9 | ESPN |
| `cbb-data` | College Basketball (CBB) | 9 | ESPN |
| `golf-data` | Golf (PGA/LPGA/DP World) | 4 | ESPN |
| `volleyball-data` | Volleyball (Dutch) | 10 | Nevobo |
| `xctf-data` | Cross Country & Track | 5 | TFRRS, The Stride Report |
| `fastf1` | Formula 1 | 6 | FastF1 (free library) |
| `sports-news` | Multi-sport | 2 | Any RSS feed, Google News |
| `metadata` | Multi-sport | 5 | TheSportsDB (free API) |

### Prediction Markets

| Skill | Platform | Commands | Coverage |
|-------|----------|----------|----------|
| `kalshi` | Kalshi | 12+ | Soccer, Basketball, Baseball, Tennis, NFL, Hockey |
| `polymarket` | Polymarket | 10 | NFL, NBA, MLB, Soccer, Tennis, Cricket, MMA, Esports |

### Football Data Coverage

| Competition | League | Live Scores | Standings | Player Stats | xG | Transfers |
|------------|--------|-------------|-----------|-------------|-----|-----------|
| Premier League | England | Yes | Yes | Yes | Yes | Yes |
| La Liga | Spain | Yes | Yes | Yes | Yes | Yes |
| Bundesliga | Germany | Yes | Yes | Yes | Yes | Yes |
| Serie A | Italy | Yes | Yes | Yes | Yes | Yes |
| Ligue 1 | France | Yes | Yes | Yes | Yes | Yes |
| Champions League | Europe | Yes | Yes | Yes | - | - |
| FIFA World Cup | International | Yes | Yes | Yes | - | - |
| Championship | England | Yes | Yes | Yes | - | Yes |
| Eredivisie | Netherlands | Yes | Yes | Yes | - | Yes |
| Primeira Liga | Portugal | Yes | Yes | Yes | - | Yes |
| Serie A Brazil | Brazil | Yes | Yes | Yes | - | Yes |
| MLS | USA | Yes | Yes | Yes | - | Yes |
| European Championship | Europe | Yes | Yes | Yes | - | - |

---

## Quick Start

### Install a skill

```bash
npx skills add machina-sports/sports-skills
```

### Use with your AI agent

Once installed, your agent can call commands directly:

**Get today's matches:**
> "Show me all Premier League matches today"

**Get NFL scores:**
> "What are today's NFL scores?"

**Get NBA standings:**
> "Show me the current NBA standings"

**Get WNBA roster:**
> "Show me the Las Vegas Aces roster"

**Get NHL scores:**
> "What are today's NHL scores?"
**Get MLB scores:**
> "What are today's MLB scores?"

**Get ATP rankings:**
> "Show me the current ATP tennis rankings"
**Get college football rankings:**
> "Show me the AP Top 25 college football rankings"
**Get college basketball scores:**
> "What are today's college basketball scores?"
**Get PGA leaderboard:**
> "What's the PGA Tour leaderboard right now?"

**Get Dutch volleyball standings:**
> "Show me the Eredivisie volleyball standings"

**Check prediction market odds:**
> "What are the Polymarket odds for the Champions League final?"

**Get F1 race results:**
> "Show me the lap data from the last Monaco Grand Prix"

### Install Individual Skills

Pick the sports you need. Each skill installs independently.

#### Sports Data

| Skill | Sport | Install | Link |
|-------|-------|---------|------|
| `football-data` | Football (Soccer) | `npx skills add machina-sports/sports-skills@football-data` | [skills.sh](https://skills.sh/machina-sports/sports-skills/football-data) |
| `nfl-data` | NFL | `npx skills add machina-sports/sports-skills@nfl-data` | [skills.sh](https://skills.sh/machina-sports/sports-skills/nfl-data) |
| `nba-data` | NBA | `npx skills add machina-sports/sports-skills@nba-data` | [skills.sh](https://skills.sh/machina-sports/sports-skills/nba-data) |
| `wnba-data` | WNBA | `npx skills add machina-sports/sports-skills@wnba-data` | [skills.sh](https://skills.sh/machina-sports/sports-skills/wnba-data) |
| `nhl-data` | NHL | `npx skills add machina-sports/sports-skills@nhl-data` | [skills.sh](https://skills.sh/machina-sports/sports-skills/nhl-data) |
| `mlb-data` | MLB | `npx skills add machina-sports/sports-skills@mlb-data` | [skills.sh](https://skills.sh/machina-sports/sports-skills/mlb-data) |
| `tennis-data` | Tennis (ATP + WTA) | `npx skills add machina-sports/sports-skills@tennis-data` | [skills.sh](https://skills.sh/machina-sports/sports-skills/tennis-data) |
| `cfb-data` | College Football | `npx skills add machina-sports/sports-skills@cfb-data` | [skills.sh](https://skills.sh/machina-sports/sports-skills/cfb-data) |
| `cbb-data` | College Basketball | `npx skills add machina-sports/sports-skills@cbb-data` | [skills.sh](https://skills.sh/machina-sports/sports-skills/cbb-data) |
| `golf-data` | Golf (PGA/LPGA/DP World) | `npx skills add machina-sports/sports-skills@golf-data` | [skills.sh](https://skills.sh/machina-sports/sports-skills/golf-data) |
| `volleyball-data` | Volleyball (Dutch) | `npx skills add machina-sports/sports-skills@volleyball-data` | [skills.sh](https://skills.sh/machina-sports/sports-skills/volleyball-data) |
| `xctf-data` | XC & Track & Field | `npx skills add machina-sports/sports-skills@xctf-data` | — |
| `fastf1` | Formula 1 | `npx skills add machina-sports/sports-skills@fastf1` | [skills.sh](https://skills.sh/machina-sports/sports-skills/fastf1) |
| `sports-news` | Multi-sport News | `npx skills add machina-sports/sports-skills@sports-news` | [skills.sh](https://skills.sh/machina-sports/sports-skills/sports-news) |

#### Prediction Markets

| Skill | Platform | Install | Link |
|-------|----------|---------|------|
| `kalshi` | Kalshi (CFTC-regulated) | `npx skills add machina-sports/sports-skills@kalshi` | [skills.sh](https://skills.sh/machina-sports/sports-skills/kalshi) |
| `polymarket` | Polymarket | `npx skills add machina-sports/sports-skills@polymarket` | [skills.sh](https://skills.sh/machina-sports/sports-skills/polymarket) |

---

## Skills Reference

### football-data

Community football data skill. Aggregates publicly accessible web sources (ESPN, Understat, FPL, Transfermarkt). Data is sourced from these third-party sites and is subject to their respective terms of use.

**Commands:**

| Command | Description |
|---------|-------------|
| `get_competitions` | List all 12 supported competitions |
| `get_current_season` | Detect current season for a competition |
| `get_season_schedule` | All fixtures for a season |
| `get_daily_schedule` | All matches across competitions for a date |
| `get_season_standings` | League table (home/away/total) |
| `get_season_leaders` | Top scorers, assist leaders, card leaders |
| `get_season_teams` | All teams in a season |
| `search_team` | Fuzzy search for a team by name across all leagues |
| `get_team_profile` | Team info, crest, venue |
| `get_team_schedule` | Upcoming and recent matches for a team |
| `get_head_to_head` | H2H history between two teams (unavailable) |
| `get_event_summary` | Match summary with scores |
| `get_event_lineups` | Starting lineups and formations |
| `get_event_statistics` | Team-level match stats (possession, shots, passes) |
| `get_event_timeline` | Goals, cards, substitutions, VAR decisions |
| `get_event_xg` | Expected goals with shot maps |
| `get_event_players_statistics` | Individual player match stats |
| `get_missing_players` | Injured and suspended players |
| `get_player_profile` | Biography, career stats, market value |
| `get_season_transfers` | Transfer history |
| `get_competition_seasons` | Available seasons for a competition |

### nfl-data

NFL data via ESPN public endpoints. Scores, standings, rosters, schedules, game summaries, and more.

| Command | Description |
|---------|-------------|
| `get_scoreboard` | Live/recent NFL scores |
| `get_standings` | Standings by conference and division |
| `get_teams` | All 32 NFL teams |
| `get_team_roster` | Full roster for a team |
| `get_team_schedule` | Schedule for a specific team |
| `get_game_summary` | Detailed box score and scoring plays |
| `get_leaders` | Statistical leaders (passing, rushing, receiving) |
| `get_news` | NFL news articles |
| `get_schedule` | Season schedule by week |

### nba-data

NBA data via ESPN public endpoints. Scores, standings, rosters, schedules, game summaries, and more.

| Command | Description |
|---------|-------------|
| `get_scoreboard` | Live/recent NBA scores |
| `get_standings` | Standings by conference |
| `get_teams` | All 30 NBA teams |
| `get_team_roster` | Full roster for a team |
| `get_team_schedule` | Schedule for a specific team |
| `get_game_summary` | Detailed box score and scoring plays |
| `get_leaders` | Statistical leaders (points, rebounds, assists) |
| `get_news` | NBA news articles |
| `get_schedule` | Schedule for a date |

### wnba-data

WNBA data via ESPN public endpoints. Scores, standings, rosters, schedules, game summaries, and more.

| Command | Description |
|---------|-------------|
| `get_scoreboard` | Live/recent WNBA scores |
| `get_standings` | Standings by conference |
| `get_teams` | All WNBA teams |
| `get_team_roster` | Full roster for a team |
| `get_team_schedule` | Schedule for a specific team |
| `get_game_summary` | Detailed box score and scoring plays |
| `get_leaders` | Statistical leaders (points, rebounds, assists) |
| `get_news` | WNBA news articles |
| `get_schedule` | Schedule for a date |

### nhl-data

NHL data via ESPN public endpoints. Scores, standings, rosters, schedules, game summaries, and more.

| Command | Description |
|---------|-------------|
| `get_scoreboard` | Live/recent NHL scores |
| `get_standings` | Standings by conference and division |
| `get_teams` | All 32 NHL teams |
| `get_team_roster` | Full roster for a team |
| `get_team_schedule` | Schedule for a specific team |
| `get_game_summary` | Detailed box score and scoring plays |
| `get_leaders` | Statistical leaders (goals, assists, points) |
| `get_news` | NHL news articles |
### mlb-data

MLB data via ESPN public endpoints. Scores, standings, rosters, schedules, game summaries, and more.

| Command | Description |
|---------|-------------|
| `get_scoreboard` | Live/recent MLB scores |
| `get_standings` | Standings by league and division |
| `get_teams` | All 30 MLB teams |
| `get_team_roster` | Full roster for a team |
| `get_team_schedule` | Schedule for a specific team |
| `get_game_summary` | Detailed box score and scoring plays |
| `get_leaders` | Statistical leaders (batting avg, home runs, ERA) |
| `get_news` | MLB news articles |
| `get_schedule` | Schedule for a date |

### tennis-data

ATP and WTA tennis data via ESPN public endpoints. Tournament scores, rankings, calendars, player profiles, and news.

| Command | Description |
|---------|-------------|
| `get_scoreboard` | Active tournaments with current matches |
| `get_calendar` | Full season tournament schedule |
| `get_rankings` | Current ATP or WTA rankings |
| `get_player_info` | Individual player profile |
| `get_news` | Tennis news articles |
### cfb-data

College Football (CFB) data via ESPN public endpoints. 750+ FBS teams with AP/Coaches/CFP rankings.

| Command | Description |
|---------|-------------|
| `get_scoreboard` | Live/recent college football scores |
| `get_standings` | Standings by conference |
| `get_teams` | All 750+ FBS teams |
| `get_team_roster` | Full roster for a team |
| `get_team_schedule` | Schedule for a specific team |
| `get_game_summary` | Detailed box score and scoring plays |
| `get_rankings` | AP Top 25, Coaches Poll, CFP rankings |
| `get_news` | College football news articles |
| `get_schedule` | Schedule by week and conference |

### cbb-data

College Basketball (CBB) data via ESPN public endpoints. 360+ D1 teams with AP/Coaches rankings and March Madness.

| Command | Description |
|---------|-------------|
| `get_scoreboard` | Live/recent college basketball scores |
| `get_standings` | Standings by conference |
| `get_teams` | All 360+ D1 teams |
| `get_team_roster` | Full roster for a team |
| `get_team_schedule` | Schedule for a specific team |
| `get_game_summary` | Detailed box score and player stats |
| `get_rankings` | AP Top 25, Coaches Poll |
| `get_news` | College basketball news articles |
| `get_schedule` | Schedule by date and conference |

### golf-data

PGA Tour, LPGA, and DP World Tour golf data via ESPN public endpoints. Tournament leaderboards, season schedules, golfer profiles, and news.

| Command | Description |
|---------|-------------|
| `get_leaderboard` | Current tournament leaderboard with all golfer scores |
| `get_schedule` | Full season tournament schedule |
| `get_player_info` | Individual golfer profile |
| `get_news` | Golf news articles |

### volleyball-data

Dutch volleyball data via the Nevobo (Nederlandse Volleybalbond) open API. Covers Eredivisie, Topdivisie, Superdivisie, and 6,400+ lower-division poules.

| Command | Description |
|---------|-------------|
| `get_competitions` | List all available competitions and leagues |
| `get_standings` | League table (rank, team, matches, points) |
| `get_schedule` | Upcoming matches (teams, venue, date) |
| `get_results` | Match results (score, set-by-set scores) |
| `get_clubs` | List volleyball clubs (name, city, province) |
| `get_club_schedule` | Club's upcoming matches across all teams |
| `get_club_results` | Club's results across all teams |
| `get_poules` | Browse Nevobo poules (lower divisions discovery) |
| `get_tournaments` | Tournament calendar |
| `get_news` | Federation news |

### xctf-data

NCAA cross country and track & field athlete data via [TFRRS](https://www.tfrrs.org) (Track & Field Results Reporting System) and news via [The Stride Report](https://www.thestridereport.com). Athlete profiles, personal records, full results history, and XC/TF news. No API keys required.

| Command | Description |
|---------|-------------|
| `search_athlete` | Roster lookup by name; returns slugs for `get_athlete_profile` (agent-facing) |
| `get_athlete_profile` | Athlete PRs, eligibility, school, and full meet results history |
| `get_team_roster` | Full XC and/or TF roster for a team |
| `get_meet_results` | All event results and team scores from a TFRRS meet |
| `get_news` | XC/TF news articles |

### fastf1

Formula 1 data via the [FastF1](https://github.com/theOehrly/Fast-F1) open-source library.

| Command | Description |
|---------|-------------|
| `get_session_data` | Session metadata (practice, qualifying, race) |
| `get_driver_info` | Driver details or full grid |
| `get_team_info` | Team details or all teams |
| `get_race_schedule` | Full calendar for a year |
| `get_lap_data` | Lap times, sectors, tire data |
| `get_race_results` | Final classification and fastest laps |

### kalshi

Kalshi's [official public API](https://trading-api.readme.io/reference/getmarkets). No API key needed for read-only market data.

| Command | Description |
|---------|-------------|
| `get_series_list` | All series filtered by sport tag |
| `get_series` | Single series details |
| `get_markets` | Markets with bid/ask/volume/open interest |
| `get_market` | Single market details |
| `get_events` | Events with pagination |
| `get_event` | Single event details |
| `get_trades` | Trade history |
| `get_market_candlesticks` | OHLCV price data (1min/1hr/1day) |
| `get_sports_filters` | Sports-specific filters and competitions |
| `get_exchange_status` | Exchange active/trading status |
| `get_exchange_schedule` | Exchange operating schedule |

### polymarket

Polymarket's official public APIs ([Gamma](https://gamma-api.polymarket.com) + [CLOB](https://docs.polymarket.com)). No API key needed for read-only data.

| Command | Description |
|---------|-------------|
| `get_sports_markets` | Active sports markets with type filtering |
| `get_sports_events` | Sports events by series/league |
| `get_series` | All series (NBA, NFL, MLB leagues) |
| `get_market_details` | Single market by ID or slug |
| `get_event_details` | Single event with nested markets |
| `get_market_prices` | Real-time midpoint, bid, ask from CLOB |
| `get_order_book` | Full order book with spread calculation |
| `get_sports_market_types` | 58+ market types (moneyline, spreads, totals, props) |
| `search_markets` | Full-text search across markets |
| `get_price_history` | Historical price data (1d, 1w, 1m, max) |
| `get_last_trade_price` | Most recent trade price |

### sports-news

RSS feed aggregation for sports news.

| Command | Description |
|---------|-------------|
| `fetch_feed` | Full feed with metadata and entries |
| `fetch_items` | Filtered items (date range, language, country) |

Supports any RSS/Atom feed URL and Google News queries.
If you pass `query` without `url`, it automatically uses Google News.

---

## Architecture

```
sports-skills.sh
├── skills/                            # SKILL.md files (agent instructions)
│   ├── football-data/SKILL.md         # 21 commands, 13 leagues
│   ├── nfl-data/SKILL.md             # NFL scores, standings, rosters
│   ├── nba-data/SKILL.md             # NBA scores, standings, rosters
│   ├── wnba-data/SKILL.md            # WNBA scores, standings, rosters
│   ├── nhl-data/SKILL.md             # NHL scores, standings, rosters
│   ├── mlb-data/SKILL.md             # MLB scores, standings, rosters
│   ├── tennis-data/SKILL.md          # ATP + WTA tennis
│   ├── cfb-data/SKILL.md             # College football scores, rankings
│   ├── cbb-data/SKILL.md             # College basketball scores, rankings
│   ├── golf-data/SKILL.md            # Golf leaderboards, schedules, profiles
│   ├── volleyball-data/SKILL.md      # Dutch volleyball standings, results, clubs
│   ├── xctf-data/SKILL.md            # NCAA XC/TF results, PRs, profiles, news
│   ├── fastf1/SKILL.md               # F1 sessions, laps, results
│   ├── kalshi/SKILL.md               # Prediction markets (CFTC)
│   ├── polymarket/SKILL.md           # Prediction markets (crypto)
│   └── sports-news/SKILL.md          # RSS + Google News
├── src/sports_skills/                 # Python runtime (used by skills)
├── site/                              # Landing page (sports-skills.sh)
├── LICENSE
└── README.md
```

Each skill follows the [Agent Skills specification](https://agentskills.io/specification):

```yaml
---
name: football-data
description: |
  Football (soccer) data across 13 leagues — standings, schedules, match stats, xG, transfers, player profiles.
  Use when: user asks about football/soccer standings, fixtures, match stats, xG, lineups, transfers, or injury news.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
---

# Football Data

Instructions for the AI agent...
```

---

## Compatibility

Works with every agent that supports the SKILL.md format:

- [sportsclaw](https://sportsclaw.gg)
- Claude Code
- OpenClaw (clawdbot / moltbot)
- Cursor
- GitHub Copilot
- VS Code Copilot
- Gemini CLI
- Windsurf
- OpenCode
- Kiro
- Roo
- Trae

---

## Coming Soon

Licensed data skills — coming soon via [Machina Sports](https://machina.gg):

| Provider | Coverage | Status |
|----------|----------|--------|
| Sportradar | 1,200+ competitions, real-time feeds | Coming Soon |
| Stats Perform (Opta) | Advanced analytics, event-level data | Coming Soon |
| API-Football | 900+ leagues, live scores, odds | Coming Soon |
| Data Sports Group | US sports, player props, projections | Coming Soon |

These will ship as additional skills that drop in alongside the open-source ones. Same interface, same JSON envelope — just licensed data underneath. Built for commercial and production use with proper data licensing, SLAs, and enterprise support.

For early access or enterprise needs, see [machina.gg](https://machina.gg).

---

## Contributing

We're actively expanding to cover more sports and data sources — and always looking for contributions. Whether it's a new sport, a new league, a better data source, or improvements to existing skills, PRs are welcome.

1. Fork the repo
2. Create a skill in `skills/<your-skill>/SKILL.md`
3. Follow the SKILL.md spec (YAML frontmatter + Markdown instructions)
4. Open a PR

See the existing SKILL.md files and the [Agent Skills spec](https://agentskills.io/specification) for format details.

Join the [Machina Sports Discord](https://discord.gg/PBYd6FbBSK) to discuss ideas, get help, or coordinate on new skills.

---

## Data Sources & Disclaimer

This project does not own, license, or redistribute any sports data. Each skill is a thin wrapper that accesses publicly available third-party sources on behalf of the user.

| Source | Access Method | Official API |
|--------|--------------|--------------|
| ESPN | Public web endpoints | No — undocumented, may change without notice |
| Understat | Public web data | No — community access, subject to their ToS |
| FPL | Public API | Semi-official — widely used by the community |
| Transfermarkt | Public web data | No — subject to their ToS |
| openfootball | Open-source dataset | Yes — [football.json](https://github.com/openfootball/football.json) (CC0/Public Domain) |
| FastF1 | Open-source library | Yes — [FastF1](https://github.com/theOehrly/Fast-F1) (MIT) |
| Kalshi | Official public API | Yes — [Trade API v2](https://trading-api.readme.io) |
| Polymarket | Official public APIs | Yes — [Gamma](https://gamma-api.polymarket.com) + [CLOB](https://docs.polymarket.com) |
| Nevobo | Official public API | Yes — [Nevobo API](https://api.nevobo.nl) (open, unauthenticated) |
| TFRRS | Public web data | No — community access, subject to their ToS |
| The Stride Report | Public RSS feed | No — standard RSS syndication, subject to their ToS |
| RSS / Google News | Standard RSS protocol | Yes — RSS is designed for syndication |

**Important:**
- This project is intended for **personal, educational, and research use**.
- You are responsible for complying with each data source's terms of service.
- Data from unofficial sources (ESPN, Understat, Transfermarkt) may break without notice if those sites change their structure.
- For commercial or production use with properly licensed data, see [machina.gg](https://machina.gg).
- This project is not affiliated with or endorsed by any of the data sources listed above.

---

## Acknowledgments

This project is built on top of great open-source work and public APIs:

- **[ESPN](https://www.espn.com)** — for keeping their web endpoints accessible. Powers 11 of our 15 skills: Football (13 leagues), NFL, NBA, WNBA, NHL, MLB, Tennis, College Football, College Basketball, and Golf.
- **[Nevobo](https://www.nevobo.nl)** — the Nederlandse Volleybalbond, for their open API providing Dutch volleyball data across the full pyramid (6,400+ poules, 1,737 clubs).
- **[Fantasy Premier League](https://fantasy.premierleague.com)** — for their community API powering injury news, player stats, ownership data, and ICT index for Premier League players.
- **[Transfermarkt](https://www.transfermarkt.com)** — for player market values, transfer history, and the richest player data in football.
- **[Understat](https://understat.com)** — for xG data across the top 5 European leagues.
- **[openfootball](https://github.com/openfootball/football.json)** — open public domain football data (CC0). Used as a fallback for schedules, standings, and team lists when ESPN is unavailable. Covers 10 leagues.
- **[FastF1](https://github.com/theOehrly/Fast-F1)** — the backbone of our Formula 1 skill. Thanks to theOehrly and contributors.
- **[TFRRS](https://www.tfrrs.org)** — Track & Field Results Reporting System, for NCAA cross country and track & field athlete profiles, personal records, rosters, and meet results.
- **[The Stride Report](https://www.thestridereport.com)** — for NCAA XC/TF news coverage via their public RSS feed.
- **[feedparser](https://github.com/kurtmckee/feedparser)** — reliable RSS/Atom parsing for the news skill.
- **[Kalshi](https://kalshi.com)** and **[Polymarket](https://polymarket.com)** — for their public market data APIs.
- **[skills.sh](https://skills.sh)** — the open agent skills directory and CLI.
- **[Agent Skills](https://agentskills.io)** — the open spec that makes skills interoperable across agents.

---

## License

MIT — applies to the skill code and wrappers in this repository. Does not grant any rights to the underlying third-party data.

---

Built by [Machina Sports](https://machina.gg). The Operating System for sports AI.
