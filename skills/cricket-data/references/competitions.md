# Cricket Data — Competitions & Series IDs

## Cricsheet competition codes (historical backend)

Use these codes with `get_matches`, `get_match_deliveries`, and `get_player_stats`. Get the live list any time with `get_competitions`.

| Code | Competition |
|---|---|
| `tests` | Test matches (men) |
| `odis` | One-day internationals (men) |
| `t20s` | T20 internationals (men) |
| `ipl` | Indian Premier League |
| `bbl` | Big Bash League |
| `psl` | Pakistan Super League |
| `cpl` | Caribbean Premier League |
| `hnd` | The Hundred (men) |
| `ntb` | T20 Blast |
| `cch` | County Championship |
| `sat` | SA20 |
| `msl` | Mzansi Super League |
| `lpl` | Lanka Premier League |
| `ilt` | International League T20 |
| `wbb` | Women's Big Bash League |
| `wpl` | Women's Premier League |

Codes are case-insensitive. An unknown code returns an error listing the valid codes.

## ESPN series IDs (live-ish backend)

ESPN cricket has no single league: each series/tournament has its own numeric ID, used in the league slot of the URL.

- **Always discover IDs with `get_series`.** It returns the currently-active series with their numeric IDs.
- **IDs are season-specific.** A recurring tournament (e.g. IPL) gets a new ID each season — never hardcode an ID across seasons.
- The `series_id` from `get_series` is required by `get_scoreboard`, `get_standings`, `get_game_summary`, and `get_news`.
