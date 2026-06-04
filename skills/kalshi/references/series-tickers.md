# Sport Codes & Series Tickers

## Sport Codes (use with search_markets, get_todays_events)

### US Sports

| Sport | Code | Series Ticker(s) |
|---|---|---|
| NBA | `nba` | KXNBA |
| NFL | `nfl` | KXNFL |
| MLB | `mlb` | KXMLB |
| NHL | `nhl` | KXNHL |
| WNBA | `wnba` | KXWNBA |
| College Football | `cfb` | KXCFB |
| College Basketball | `cbb` | KXCBB |

### Football

| League | Code | Series Ticker(s) |
|---|---|---|
| English Premier League | `epl` | KXEPLGAME, KXEPLTOTAL, KXEPLBTTS, KXEPLSPREAD, KXEPLGOAL |
| Champions League | `ucl` | KXUCL, KXUEFAGAME |
| La Liga | `laliga` | KXLALIGA |
| Bundesliga | `bundesliga` | KXBUNDESLIGA |
| Serie A | `seriea` | KXSERIEA |
| Ligue 1 | `ligue1` | KXLIGUE1 |
| MLS | `mls` | KXMLSGAME |
| FIFA World Cup 2026 | `worldcup` | KXMENWORLDCUP, KXWCGAME, KXWCGROUPQUAL, KXWCGROUPORDER, KXWCSTAGE, KXWCHOSTSTAGE, KXWCBESTHOST, KXWCNOEURSA, KXWCREGIONKO, KXWCEVERYTEAMGOAL |

Use `get_sports_config()` to see all available codes.

**Football leagues have multiple series per league.** The `sport` parameter queries all of them automatically. For example, `search_markets(sport='epl')` queries KXEPLGAME, KXEPLTOTAL, KXEPLBTTS, KXEPLSPREAD, and KXEPLGOAL in one call.

## Other Football Series Tickers (raw API only)

**Note:** On Kalshi's API, "Football" = American Football (NFL). Football leagues are categorized under "Soccer" in Kalshi's taxonomy.

| League | Series Ticker | Notes |
|---|---|---|
| FA Cup | `KXFACUP` | Futures |
| Europa League | `KXUEL` | Futures |
| Conference League | `KXUECL` | Futures |

Not all football leagues have futures/winner markets. Use `get_sports_filters()` to discover all available competitions.
