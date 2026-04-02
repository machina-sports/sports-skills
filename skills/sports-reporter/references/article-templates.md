# Sports Reporter — Article Templates

Each template defines the expected narrative structure. The content of each section is filled with real data collected via CLI. **Sections marked with `[if available]` should be silently omitted if the data is not available — never fill them with fabrications.**

---

## Preview (Pre-game)

```
## [Team A] vs [Team B] — [Competition] | [Date and Time]

**[Lead: impactful sentence about the importance of the matchup]**

### The Matchup
[1-2 paragraphs contextualizing the game: what is at stake, point in the season,
teams' positions in the table.]

### Recent Form
**[Team A]:** [Results of the last 5 games — e.g.: W W D L W] — [brief analysis]
**[Team B]:** [Results of the last 5 games] — [brief analysis]

### Absences and Returns
**[Team A]:** [List of injured, suspended, and possible returnees]
**[Team B]:** [List of injured, suspended, and possible returnees]
[if available] If no confirmed absences: omit or indicate "no confirmed absences"

### [if available] Probable Lineups
[Team A]: [Formation and confirmed players]
[Team B]: [Formation and confirmed players]

### What to Watch
[2-3 matchups/tactical aspects to follow, based on stats and recent form]

### Where to Watch
[Venue, time, broadcast — if available in the data]
```

---

## Live Report

```
## LIVE | [Team A] [score] vs [score] [Team B] — [Minute/Period]

**[Lead: description of the current game moment — who is ahead, the pace of play]**

### Current Situation
- **Score:** [Team A] [X] vs [Y] [Team B]
- **[Period/Half/Quarter]:** [current status]
- **[if available] Win probability:** [Team A]: X% | [Team B]: Y%

### Goals / Points Scored
[Chronology of goals/points: Minute — Player — Description]
[If 0-0 or game just started: "No points scored yet"]

### Recent Plays
[5-10 most recent plays from the play-by-play in chronological order]

### [if available] Individual Highlights
[Players who have stood out so far with their numbers]

### [if available] Partial Statistics
[Possession, shots, passes — football / Rebounds, assists — basketball / etc.]
```

---

## Match Report (Post-game)

```
## [Team A] [score] vs [score] [Team B] — [Competition] | [Date]

**[Lead: most important fact of the game in one sentence — the result and its meaning]**

### How the Game Went
[2-3 paragraphs describing how the match unfolded by period/half.
Based on the play-by-play and timeline. Mention the decisive moments.]

### Goals and Decisive Moments
[Chronology: Minute — Player — Goal/play type — Context]

### Statistics
| Stat | [Team A] | [Team B] |
|------|----------|----------|
| [Possession / Shots / etc.] | X | Y |

[if available] **xG:** [Team A] X.XX — [Team B] X.XX
[Note: if xG > result, indicate who "deserved more" by volume of play]

### Match Star
**[Player Name]** — [Position, Team]
[Individual game stats: goals, assists, passes, or points/rebounds/assists depending on the sport]

### Table Impact
[How the result affects the standings — both teams' positions after the game]

### Next Games
**[Team A]:** [Next opponent and date]
**[Team B]:** [Next opponent and date]
```

---

## Team Analysis

```
## [Team Name] — Season Analysis

**[Lead: team's current situation in one sentence — position, form, trend]**

### Season Standing
[Table position, conference/division, points/wins, gap to the leader and to the relegation/playoff zone]

### Recent Form
[Results of the last 5 games with opponent, result, and score]
[Trend: rising, falling, stable]

### Team Numbers
**Attack:** [Main offensive stats — goals scored, points per game, yards, etc.]
**Defense:** [Main defensive stats — goals conceded, points allowed, etc.]
[if available] **Ranking:** [Position in the league's attack and defense rankings]

### Squad Highlights
[3-5 key players with their season stats]

### Injured / Unavailable
[List of injured players with status and expected return — if available]
[If no confirmed injuries: omit section]

### Schedule
**Last 5 results:** [W/L/D vs Opponent]
**Next 5 games:** [Date vs Opponent — home/away]

### Analysis
[1-2 paragraphs summarizing the team's situation, strengths, weaknesses, and outlook]
```

---

## Player Profile

```
## [Player Name] — [Position] | [Team] | [League]

**[Lead: who the player is and why they are relevant right now]**

### Profile
- **Position:** [Position]
- **Team:** [Current team]
- **Seasons in the league:** [Years of experience]
[if available] **Market value:** [Value — football only via Transfermarkt]

### Current Season ([Year])
[Key stats in highlight format: goals, assists / points, rebounds, assists / passes, yards, TDs — depending on the sport]

| Category | Value | League Rank |
|----------|-------|------------|
| [Stat 1] | X | [if available] #N |
| [Stat 2] | Y | [if available] #N |

### [if available] Team Impact
[How the player's numbers compare to the team average / what they represent for the collective]

### [if available] Recent History
[Last 5 games: performance and trend — only if available via player_stats]

### [if available] Recent News
[Main headlines about the player in recent days]

### [if available — football] Transfer Market
[Market value, transfer history, contract situation]
```

---

## Daily Roundup

```
## Sports Roundup — [Full date]

**[Lead: highlight of the day — the most important game or most surprising result]**

---

### ⚽ Football
[List of the day's games: Team A X vs Y Team B — [Status/Time]]
[For finished games: highlight in 1 sentence]
[For live games: current score and minute]
[For upcoming games: kickoff time]

### 🏈 NFL
[Same structure]

### 🏀 NBA
[Same structure]

### 🏒 NHL
[Same structure]

### ⚾ MLB
[Same structure]

[Include only sports with games on the day — omit sports with no activity]

---

### Highlights of the Day
[3-5 most important moments/facts of the day in bullet points]
```

---

## General Style Rules

1. **Lead always in bold** — captures the most important fact
2. **Sections with `[if available]`** — silently omit if data is absent
3. **Data always with implicit source** — comes from the CLI, not invented
4. **Table context always present** — the reader needs to understand the implications
5. **Language adapted to the user** — PT-BR by default; adapt if the user writes in another language
6. **Sport emojis in the daily roundup** — only in that format; do not use in others
7. **Neutral tone** — no favoritism between teams; present the facts
8. **Decimal numbers** — use period as separator (international standard)
