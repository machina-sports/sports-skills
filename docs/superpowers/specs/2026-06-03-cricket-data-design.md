# cricket-data Skill — Design

**Date:** 2026-06-03
**Status:** Approved design, pending implementation plan

## Goal

Add a `cricket-data` skill to sports-skills: zero-config, no-API-key cricket data via a hybrid of two free sources — ESPN's public site API (live-ish: series, scoreboards, standings, match summaries, news) and Cricsheet.org (historical ball-by-ball, ODC-BY 1.0 licensed).

## Background (research findings, verified 2026-06-03)

- ESPN's site API serves cricket with the same zero-auth surface used by the repo's other skills. Cricket has no single "league": each series/competition has a numeric ID used in the league slot of the URL.
  - Verified working: `site.web.api.espn.com/apis/personalized/v2/scoreboard/header?sport=cricket` (active-series discovery), `site.api.espn.com/apis/site/v2/sports/cricket/{seriesId}/scoreboard` (events + embedded standings), `.../summary?event={id}` (rosters, leaders, matchcards, gameInfo), `.../news`.
  - Verified NOT available: `sports.core.api.espn.com` (no cricket), `/teams` (404), global cricket scoreboard without series ID (404), rankings (no endpoint found).
- ESPNcricinfo's own APIs are not viable: `hs-consumer-api.espncricinfo.com` is Akamai bot-blocked (403 even with browser UA); the legacy `matches/engine/match/{id}.json` is dead (403).
- Cricsheet.org: ball-by-ball JSON for ~21,900+ matches (Tests, ODIs, T20Is, IPL, BBL, PSL, CPL, The Hundred, county cricket, extensive women's coverage). Distributed as zipped bulk downloads per competition, updated ~within a day of match completion. License: ODC-BY 1.0 — commercial use permitted, attribution required. Its player registry maps ~18k players to ESPNcricinfo IDs.
- CricAPI/cricketdata.org: disqualified (API key required, free tier prohibits commercial use).
- ICC rankings: no free source exists (icc-cricket.com has no API; ESPN exposes no cricket rankings). v1 ships without rankings — documented limitation.

## Architecture (Approach A — chosen)

One `cricket` module, two internal backend files:

```
src/sports_skills/cricket/
  __init__.py        # public API: re-exports all commands from both backends
  _espn.py           # live-ish backend — uses _espn_base.py shared infra
  _cricsheet.py      # historical backend — zip download/cache, aggregation, registry

skills/cricket-data/
  SKILL.md
  references/
    api-reference.md     # ESPN endpoints + Cricsheet formats, ID conventions
    competitions.md      # Cricsheet competition codes + ESPN series-ID guidance
  scripts/
    validate_params.sh   # mirrors tennis-data

tests/test_cricket.py
tests/fixtures/          # tiny trimmed Cricsheet zip + captured ESPN payloads
```

CLI: one `"cricket"` entry in the `cli.py` command registry + module loader, plus mention in the CLI description/help strings.

Rejected alternatives: (B) single `_connector.py` for both backends — would exceed ~1,000 lines doing two unrelated jobs; (C) separate `cricket` and `cricsheet` modules — two namespaces for one sport, YAGNI.

## Command set

Naming follows the repo convention: team-sport canonical names (`get_scoreboard`, `get_standings`, `get_game_summary --event_id`, `get_news`, `get_player_stats`) wherever a direct equivalent exists; `--series_id` is the required scoping param (analogue of tennis `--tour`); cricket-specific commands get domain names (volleyball/xctf precedent).

### ESPN-backed (live-ish)

| Command | Params | Source |
|---|---|---|
| `get_series` | — | scoreboard header → active series with IDs and live events |
| `get_scoreboard` | `--series_id` req, `--date` opt | `.../cricket/{id}/scoreboard` |
| `get_standings` | `--series_id` req | extracted from scoreboard's embedded `standings` |
| `get_game_summary` | `--series_id` req, `--event_id` req | `.../summary?event=` — rosters, leaders, matchcards, gameInfo |
| `get_news` | `--series_id` req | `.../cricket/{id}/news` |

### Cricsheet-backed (historical, ODC-BY 1.0)

| Command | Params | Notes |
|---|---|---|
| `get_competitions` | — | static map of supported Cricsheet codes (ipl, bbl, psl, cpl, tests, odis, t20is, the_hundred, county, wbbl, wpl, …) |
| `get_matches` | `--competition` req, `--season` opt | match list (ids, teams, venue, result) from cached zip metadata |
| `get_match_deliveries` | `--competition` req, `--match_id` req, `--innings` opt | delivery-level data for one match |
| `get_player_stats` | `--competition` req, `--player` req, `--season` opt | batting (runs, balls, SR, 4s/6s, dismissals) + bowling (balls, runs conceded, wickets, economy) aggregated in-connector |
| `find_player` | `--name` req | Cricsheet registry (`people.csv`) lookup → IDs incl. ESPNcricinfo mapping |

Disambiguation rule (stated in SKILL.md): `get_series` = live ESPN series with numeric IDs; `get_competitions` = static Cricsheet competition codes. The two backends' ID spaces only intersect at the match level: Cricsheet `match_id` (filename stem, e.g. `1359507`) IS the ESPNcricinfo match ID.

### Param conventions

- `series_id`, `event_id`, `match_id`, `competition`, `player`, `name`: strings.
- `season`: int (already in `_INT_PARAMS` globally). Cricsheet cross-year seasons (`"2020/21"`) are matched by prefix: `--season=2020` matches `2020/21`.
- `innings`: int (1–4; add to `_INT_PARAMS`).
- `date`: `YYYYMMDD`, same as other ESPN skills.

## Cricsheet fetch & cache (new pattern for the repo)

- Stdlib only (`urllib` + `zipfile`), matching `_espn_base.py`'s zero-dependency style.
- Download `https://cricsheet.org/downloads/{code}_json.zip` to `~/.cache/sports-skills/cricsheet/`. TTL: 24h for competition zips, 7 days for the registry CSV (`https://cricsheet.org/register/people.csv`). Re-download only on TTL expiry.
- Read match JSONs directly from the zip in place (no extraction to disk).
- Every Cricsheet-backed response includes `"attribution": "Data from Cricsheet (cricsheet.org), ODC-BY 1.0"` — required by the license for public use.

## Error handling & resilience

- Repo idiom: `{"error": True, "message": "..."}` for bad params, unknown competition codes, match not found, network failures.
- ESPN calls go through `_espn_base.espn_request` (existing retry / rate-limit / TTL cache).
- Cricsheet download failure with a stale cached zip present → serve stale data plus `"stale": true` flag rather than erroring.
- Param validation mirrors tennis's `_validate_tour` style (`_validate_competition`, `_validate_series_id`).

## Docs

`SKILL.md` follows tennis-data structure:
- Frontmatter: same description / Use-when / Don't-use-when format, MIT license, `author: machina-sports`, `version: "0.1.0"`.
- Quick-start CLI examples for both backends.
- "CRITICAL: Before Any Query" gotchas: series IDs are per-series not per-league (discover via `get_series`); Cricsheet covers completed matches only (~1-day lag); no rankings in v1 (no free source); `get_series` vs `get_competitions` disambiguation.
- ODC-BY attribution note.

Cross-referencing: update the "Don't use when" routing line in the other skills' SKILL.md files to point cricket queries at cricket-data (established pattern; one line per skill).

## Testing

- Pure-logic tests for aggregation math against a tiny fixture zip (2–3 trimmed Cricsheet matches) in `tests/fixtures/`.
- Mocked-HTTP tests for ESPN response parsing using captured real payloads.
- No live network calls in CI.
- `tests/test_imports.py` should pick up the new module automatically; verify.

## Known limitations (v1)

- No ICC rankings (no free source).
- ESPN endpoints are undocumented — same stability/ToS risk profile as every other ESPN-backed skill in the repo; documented, accepted.
- Cricsheet zips for large competitions (e.g., all Tests) are tens of MB — first call per competition per day pays the download cost.
- No play-by-play from ESPN in v1 (`playByPlayAvailable` flag exists on events but the endpoint shape is unverified); ball-by-ball needs come from Cricsheet. Revisit if demand appears.
