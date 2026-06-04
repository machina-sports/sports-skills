# Markets Orchestration — API Reference

## Commands

| Command | Required | Optional | Description |
|---|---|---|---|
| `get_todays_markets` | | sport, date | Fetch ESPN schedule → search both exchanges with sport context → unified dashboard |
| `search_entity` | query | sport | Search Kalshi + Polymarket for a team/player/event name (passes sport to both platforms) |
| `compare_odds` | sport, event_id | | ESPN odds + prediction market prices → normalized side-by-side + arb check |
| `get_sport_markets` | sport | status, limit | Sport-filtered market listing on both platforms (uses sport code, not text query) |
| `get_sport_schedule` | | sport, date | Unified ESPN schedule across one or all sports |
| `normalize_price` | price, source | | Convert any source format to common {implied_prob, american, decimal} |
| `evaluate_market` | sport, event_id | token_id, kalshi_ticker, outcome | ESPN odds + market price → devig → edge → Kelly |

## Supported Sports

### US Sports (with ESPN schedules)

| Sport | Key | Kalshi Series | Polymarket Code |
|---|---|---|---|
| NFL | `nfl` | KXNFL | `nfl` |
| NBA | `nba` | KXNBA | `nba` |
| MLB | `mlb` | KXMLB | `mlb` |
| NHL | `nhl` | KXNHL | `nhl` |
| WNBA | `wnba` | KXWNBA | `wnba` |
| College Football | `cfb` | KXCFB | `cfb` |
| College Basketball | `cbb` | KXCBB | `cbb` |

### Football (prediction markets only — no ESPN schedule)

| League | Key | Kalshi Series | Polymarket Code |
|---|---|---|---|
| English Premier League | `epl` | KXEPLGAME | `epl` |
| Champions League | `ucl` | KXUCL | `ucl` |
| La Liga | `laliga` | KXLALIGA | `lal` |
| Bundesliga | `bundesliga` | KXBUNDESLIGA | `bun` |
| Serie A | `seriea` | KXSERIEA | `sea` |
| Ligue 1 | `ligue1` | KXLIGUE1 | `fl1` |
| MLS | `mls` | KXMLSGAME | `mls` |
| FIFA World Cup 2026 | `worldcup` | KXWCGAME | `fifwc` |

## Price Normalization

Different sources use different formats. `normalize_price` converts any format to a common structure.

| Source | Format | Example | Meaning |
|---|---|---|---|
| ESPN | American odds | `-150` | Favorite, implied 60% |
| Polymarket | Probability (0-1) | `0.65` | 65% implied probability |
| Kalshi | Integer (0-100) | `65` | 65% implied probability |

**Normalized output shape:**
```json
{
  "implied_probability": 0.65,
  "american": -185.7,
  "decimal": 1.5385,
  "source": "polymarket"
}
```

## Partial Results Behavior

If one source is unavailable, the module returns what it has with warnings:
```json
{
  "status": true,
  "data": {
    "games": [],
    "warnings": ["Kalshi search failed: connection timeout"]
  }
}
```
