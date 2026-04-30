# sports-skills

https://sports-skills.sh

A lightweight, zero-config Python SDK and CLI for live sports data and prediction markets. 

Built natively for AI agents, but works perfectly as a standalone Python library for developers. Wraps publicly available sports data sources and APIs into unified, deterministic commands.

**Zero API keys. Zero signup. Just works.**

---

## 📦 Installation

Install as a global CLI tool (recommended for agents):

```bash
uv tool install sports-skills
# or
pip install sports-skills
```

Base install includes all sports modules.

Install as a Python library:

```bash
uv add sports-skills
# or
pip install sports-skills
```

Optional extras:

```bash
pip install "sports-skills[all]"
pip install "sports-skills[dev]"
```

---

## ⚡ What's Included

- **Football (Soccer)**: ESPN, Understat, FPL, Transfermarkt — 21 commands across 30 leagues
- **US Sports**: NFL, NBA, WNBA, NHL, MLB, College Football (CFB), College Basketball (CBB) — live scores, standings, depth charts, injuries, and leaders
- **Tennis**: ATP and WTA tournament scores, rankings, calendars, and player profiles
- **Golf**: PGA, LPGA, and DP World tour scorecards and leaderboards
- **College XC/TF**: NCAA cross country and track & field — athlete profiles, personal records, meet results, and news via The Stride Report
- **Volleyball**: Nevobo — Dutch volleyball (Eredivisie, Topdivisie, Superdivisie) standings, schedules, results, clubs
- **Racing**: Formula 1 (via FastF1) — lap times, telemetry, and race results
- **Prediction Markets**: Polymarket & Kalshi live odds and order books
- **News**: Multi-sport news aggregators

---

## 💻 CLI Usage

The package exposes a `sports-skills` binary. 

List all supported sports:
```bash
sports-skills --help
```

List commands for a specific sport:
```bash
sports-skills nfl --help
```

Execute a command:
```bash
sports-skills nfl get_scoreboard --date 2026-02-24
sports-skills football get_current_season --competition_id premier-league
sports-skills polymarket get_markets --query "super bowl"
sports-skills news fetch_items --query "Lando Norris" --limit 5
sports-skills xctf get_news --limit 5
sports-skills xctf search_athlete --name "Jane Hedengren" --school "UT_college_f_BYU"
```

All CLI output is printed as strict JSON, making it perfect for AI agents (Claude, GPT, Gemini) to parse and reason over.

---

## 🐍 Python SDK Usage

You can use the exact same commands directly in your Python code:

```python
from sports_skills import nfl, football, polymarket, xctf

# Get live NFL scores
scores = nfl.get_scoreboard(date="2026-02-24")
print(scores["data"]["events"])

# Get Premier League standings
table = football.get_season_standings(season_id="premier-league-2025")
print(table["data"]["standings"])

# Fetch live odds from Polymarket
markets = polymarket.get_markets(query="bitcoin")
print(markets["data"]["markets"])

# Get latest NCAA XC/TF news from The Stride Report
news = xctf.get_news(limit=5)
print(news["data"]["articles"])

# Look up an athlete's PRs
profile = xctf.get_athlete_profile(athlete_id="9230145", school="BYU", name="Jane_Hedengren")
print(profile["data"]["prs"])
```

## 🏗️ AI Agent Integration

`sports-skills` is built on the Anthropic Level-3 Agent capability spec. Every command is deterministic and automatically generates its own JSON Schema.

To extract the OpenAI/Anthropic compatible tool schema for any module:

```python
from sports_skills import nfl
import json

# Returns a list of dicts formatted exactly like Anthropic/OpenAI tools
schema = nfl.generate_schema()
print(json.dumps(schema, indent=2))
```

## License
MIT
