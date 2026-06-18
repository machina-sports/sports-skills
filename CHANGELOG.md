## [0.27.0]

### Added
- **`sports-skills premium` command:** detects `machina-cli` (or installs it with `--install`) and prints the next setup steps to connect to licensed and real-time data feeds. Supports `--json` for machine-readable output.
- **`upgrade` field on rate-limited responses:** when a public API returns HTTP 429, the JSON response now includes an additive `upgrade` field pointing at `sports-skills premium`. Existing response data is unchanged. Suppress with `SPORTS_SKILLS_NO_UPGRADE_HINTS=1`.

## [0.26.6]

### Fixed
- **Polymarket WC (and other sports) winner markets were invisible — only props returned:** `search_markets`, `get_todays_events`, and the keyword event search queried Gamma `/events` with `order=startDate&ascending=false`. Many Polymarket events carry placeholder start dates (a World Cup 1X2 event for a June 15 game shows an April date), so startDate-desc sorting buried the liquid moneyline/1X2 winner events past the 100-event limit — callers got only the prop events (first-to-score, corners, totals) and concluded "no winner market exists." Empirically, `/events?series_id=11433&order=startDate&ascending=false` returned **0** events with a moneyline market while `order=volume` returned **56**. Switched those event queries to `order=volume&ascending=false`, which surfaces the liquid tradeable markets first (also a better default for traders). `get_todays_events(sport="fifwc")` now returns 33 moneyline markets where it returned 0; `search_markets(query="Spain", sport="fifwc", sports_market_types="moneyline")` now returns "Will Spain win on 2026-06-15?" @ 0.925 etc. with CLOB token ids.

## [0.26.5]

### Fixed
- **Polymarket trading was completely broken by the CLOB v2 migration:** every order through `polymarket.create_order` / `market_order` died with `order_version_mismatch` ("invalid order version, please use the latest clob-client") after Polymarket's late-April-2026 CLOB v2 migration. The old `py_clob_client` SDK was archived and is permanently broken against the migrated backend. Migrated all trading to **`py-clob-client-v2`** (the `polymarket` extra now depends on `py-clob-client-v2>=1.0.1` instead of `py_clob_client`). API changes handled internally: `create_and_post_order` / `create_and_post_market_order` with `PartialCreateOrderOptions(tick_size=...)`, `Side`/`OrderType` enums, `create_or_derive_api_key`, `get_open_orders`, `cancel_orders([id])`. Verified end-to-end with real matched on-chain orders (EOA, signature_type 0). Also adds `funder` support (env `POLYMARKET_FUNDER_ADDRESS` or `configure(funder=...)`) for proxy/email wallets. Read-only market data (prices, order books, events) was unaffected and is unchanged.

## [0.26.4]

### Fixed
- **`polymarket get_order_book` reported garbage best prices on liquid books:** the CLOB `/book` endpoint returns price levels with the BEST price at the END of each array (bids ascending, asks descending), but the parser took index 0 of both — so a deeply liquid 0.23/0.24 book (618k shares at the bid) was reported as `best_bid=0.01 / best_ask=0.99 / spread=0.98`. Any consumer using the tool for liquidity checks (e.g. trading agents gating on spread) would wrongly reject every liquid market. Best bid/ask are now computed as max(bids)/min(asks) with no ordering assumption, and the returned `bids`/`asks` arrays are sorted best-first so consumers reading `[0]` get the touch.

## [0.26.3]

### Fixed
- **`betting devig` was unusable through the CLI:** the CLI's `_FLOAT_PARAMS` coercion force-floated every `--odds` value, but `devig` takes comma-separated odds for ALL outcomes (e.g. `--odds=-230,+330,+750`), so any multi-outcome call died with `Invalid value for --odds … (expected a number)` — including for agents calling through tool bridges (the sportsclaw engine invokes commands via this CLI). Comma-separated values now pass through as strings; single values still coerce to float for `convert_odds`. Commands validate the shape downstream and fail gracefully either way.
- **Kalshi `/events` pagination — the soonest games were silently dropped:** `kalshi.search_markets` and `kalshi.get_todays_events` fetched a single un-paged `/events` page per series (Kalshi caps pages at 200 items) and clamped `limit` at 200 total. For multi-series sports like `worldcup` (500+ open markets) the tail of the response — the EARLIEST matchdays, e.g. Brazil vs Morocco on 2026-06-13 with $300k+ volume — never appeared in results while later matchdays did. Both commands now follow Kalshi's cursor until each series is exhausted, and `limit` accepts up to 1000 (default unchanged at 50). A later-page failure returns the partial result instead of nothing.

## [0.26.2]

### Added
- **`world-cup` premium skill (prompt-only):** routes agents to the hosted World Cup Intelligence project's MCP server via `machina-cli` — read-only fixtures/standings/squads/injuries + live Kalshi/Polymarket market state + AI-grounded briefs, joined under canonical machina URNs. Mirrors the `machina` gateway pattern: free MIT SKILL.md, no local code, no shipped keys, metered server-side.

### Improved
- **F1 session loading:** `get_session_data`, `get_driver_info`, `get_team_info`, `get_driver_comparison` (error path), and `get_race_results` now load sessions with `laps=False, telemetry=False, weather=False, messages=False` — the heavy lap/telemetry downloads were fetched and never used. `get_lap_data` keeps lap loading but skips telemetry/weather/messages. `get_session_data` now also returns a `results` list (position, driver, team, status, grid, Q1-Q3/points/time where applicable).

## [0.26.1]

### Improved
- **Tool schemas: 100% param descriptions (was 77%):** the generated tool schemas (`sports-skills <module> schema`) are what agents read to decide arguments — 107 params across betting, kalshi, polymarket, football, and f1 had no description, so models guessed argument shapes (issue #69 item 3). Every wrapper now carries a Google-style `Args:` section that flows into the schemas; a new test guard fails CI if a future command ships an undocumented param.

### Fixed
- **`polymarket.get_price_history` fidelity documented as seconds — it is minutes:** verified empirically (fidelity=60 → hourly points, 1440 → daily).

## [0.26.0]

### Added
- **`markets.match_markets(sport, date)` — cross-venue game matching:** pairs the same game across Kalshi and Polymarket. Single-game markets encode `{date, away, home}` deterministically in Kalshi event tickers (`KXMLBGAME-26JUN062210NYMSD`) and Polymarket slugs (`mlb-nym-sd-2026-06-06`); games are joined on date + team codes, with fuzzy title matching as a fallback for leagues where the venues use different code conventions (e.g. World Cup ISO vs FIFA country codes). Each match carries the Kalshi market tickers and the Polymarket moneyline token IDs, so prices can be compared directly without keyword searching.
- **`markets.get_market_price(venue, ..., at_time)` — unified point-in-time prices:** one shape for both venues — `yes`/`no` sides as 0-1 probabilities. Live price by default; pass `at_time` (Unix or ISO 8601) for the price as of any past moment (backed by Kalshi candlesticks / Polymarket price history).
- **`markets.get_price_history(venue, ..., interval)` — unified price history:** `{timestamp, price}` points (0-1 yes probability) at `1m`/`1h`/`1d` resolution, same shape regardless of venue.

### Fixed
- **CLI silently dropped space-separated flag values:** `--query FIFA` parsed the flag as a boolean and discarded the value (searching for `"true"`), returning silently-empty results. Both `--flag=value` and `--flag value` forms now work, and a value-expecting flag with no value fails loudly.
- **CLI raised a raw traceback on wrong-typed values:** `--season_year=premier-league-2026` crashed with `ValueError`. Bad values now return a structured error (`{"status": false, "message": "Invalid value for --season_year: ... (expected an integer)."}`) with exit code 1.
- **`polymarket.get_event_details(slug=...)` returned a 422:** the Gamma API resolves slugs via the `?slug=` query param, not the path (which must be a numeric id). Slug lookups now work.

## [0.25.3]

### Added
- **`kalshi.get_market_orderbook(ticker, depth)`:** wraps Kalshi's public `/markets/{ticker}/orderbook` endpoint. Returns the yes/no bid depth, preferring the current `orderbook_fp` dollar-string levels with a fallback to the legacy integer-cent `orderbook` form.

## [0.25.2]

### Fixed
- **Kalshi compact prices were all zero:** Kalshi's API migrated from integer-cent price fields (`yes_bid: 29`) to dollar-string fields (`yes_bid_dollars: "0.2900"`), and nested market objects on `/events` now carry only the dollar form — so `search_markets`' compact records returned `yes_bid`/`no_bid`/`last_price`/`volume` as 0 for **every sport**. Prices now fall back to converting the `*_dollars` strings to cents (keeping the documented 0-100 unit) and volume falls back to `volume_fp`.
- **`get_todays_events` nested markets:** the same migration left nested markets without the documented cent fields; they are now re-injected (`yes_bid`/`no_bid`/`last_price`/`volume`) alongside the raw `*_dollars` form.
- **`markets.evaluate_market` with `kalshi_ticker`:** read the dead legacy field off raw `get_market` payloads — market probability was silently 0.0, which both failed the evaluation and blocked the Polymarket search fallback. Now reads either field form, and a zero/missing price falls through to the search fallback.

## [0.25.1]

### Added
- **`worldcup` sport key for Kalshi:** FIFA World Cup 2026 markets live in dedicated series (`KXMENWORLDCUP`, `KXWCGAME`, `KXWCGROUPQUAL`, `KXWCSTAGE`, …) that were unreachable before — `kalshi.search_markets` without a sport scans a single unfiltered `/events` page (all of Kalshi: politics, weather, …), so World Cup queries always returned 0. `search_markets(sport="worldcup")` and `get_todays_events(sport="worldcup")` now fan out across 10 World Cup series.
- **`worldcup` in the cross-venue markets module:** `KALSHI_SERIES["worldcup"] = "KXWCGAME"` (match winners), `POLYMARKET_SPORTS["worldcup"] = "fifwc"` (Polymarket's FIFA World Cup sport code), and `worldcup` joins the `football`/`soccer` meta-sport fan-out — `get_sport_markets(sport="football")` now surfaces World Cup match markets on both venues.

## [0.25.0]

### Added
- **`cricket` module + `cricket-data` skill:** new sport coverage across two data planes.
  - **ESPN live-ish:** `get_series` (active series discovery), `get_scoreboard` (live/completed match scores), `get_standings` (tournament tables), `get_game_summary` (full event detail), `get_news` (series-scoped headlines).
  - **Cricsheet historical:** `get_competitions` (supported competition registry), `get_matches` (match-level results with optional season filter), `get_match_deliveries` (ball-by-ball delivery data, innings-filterable), `get_player_stats` (aggregated batting + bowling stats across a competition), `find_player` (fuzzy name lookup against the Cricsheet player registry).
  - Data is downloaded on first use and cached locally; Cricsheet data carries required ODC-BY 1.0 attribution in every response envelope.
  - CLI registered under `sports-skills cricket <command>`; skill documentation at `skills/cricket-data/SKILL.md`.

## [0.24.4]

### Added
- **`machina` skill restored:** restored the prompt-only `machina` gateway skill to the open-source repository and documentation.

## [0.24.2]

### Fixed
- **Site footer:** corrected the Discord invite URL from the broken `discord.gg/machina` placeholder to the canonical `discord.gg/PBYd6FbBSK` (matches the link in README.md).
- **Site footer:** removed the self-referential `skills.sh` link — the page is already at sports-skills.sh, so the link was a no-op.

## [0.24.1]

### Added
- **`site/build.py` — Jinja2 marketplace generator.** Replaces the hand-maintained `site/index.html` with a build system that reads SKILL.md frontmatter and emits a 21-skill marketplace under `site/dist/`. Editing a SKILL.md now auto-propagates to the published site on the next release.
- **CLI registry augmentation.** When `sports_skills` is importable in the build environment, `build.py` merges CLI-registered commands into each skill's table — so `kalshi`, `polymarket`, `nba-data`, `cbb-data`, and friends now show their full surface (e.g. polymarket: 12 → 20 commands, kalshi: 8 → 14) without anyone having to hand-edit individual SKILL.md tables.
- **`machina-templates` integration in CI.** The site build workflow now checks out the public `machina-sports/machina-templates` sibling repo so pro-tier skills (`mkn-constructor` etc.) appear in the marketplace.

### Fixed
- **`extract_commands()` handles 4-column tables.** `sports-news` and `metadata` use a wider table shape (`| Command | Required | Optional | Description |`) that the original 2-column regex skipped — now takes first cell as name + last as description.
- **`extract_commands()` falls back to Quick Start parsing.** `betting` and `markets` document commands as bash one-liners rather than tables; a fallback parser now picks up `sports-skills <module> <cmd>` invocations.
- **Templates render "prompt-only" for skills without a CLI surface** (`machina`, `sports-reporter`, `mkn-constructor`) instead of "0 commands".

## [0.24.0]

### Added
- **`skills/metadata/SKILL.md`** — restored the missing SKILL.md for the metadata module. The Python module and CLI commands have shipped since PR #31 but the SKILL.md was never written, so agents couldn't discover the skill via the standard SKILL.md spec.

### Changed
- **`skills/machina/SKILL.md`** — rewrote to add the required YAML frontmatter (was the only SKILL.md in the repo missing it), explicit project-selection step, common-errors recovery table, and an honest description of how the Machina MCP server is reached (via the agent harness's MCP config, not via `machina-cli`).
- **README** — aligned every per-skill command table with the current CLI surface. Counts updated across football, NFL (now includes nflverse-backed commands), NBA (live commands), WNBA, NHL, MLB, CFB, CBB (March Madness BPI tools), golf, F1 (telemetry / comparisons), Polymarket (CLOB trading), Kalshi, plus full sections for the previously undocumented `betting`, `markets`, `sports-reporter`, `machina`, and `metadata` skills.
- **`site/index.html`** — refreshed hero badges, stats, all 15 existing skill cards, added 6 new skill cards (xctf, metadata, betting, markets, sports-reporter, machina), and added XC&Track / Volleyball / Tools&Workflows / Metadata cards to the Coverage section.

### Fixed
- **CI:** Migrated the `Sports Skills Site Build` workflow from Docker Hub to GitHub Container Registry (ghcr.io). Pushes now use the auto-provisioned `GITHUB_TOKEN` instead of long-lived `DOCKER_USERNAME` / `DOCKER_PASSWORD` / `REGISTRY_URL` secrets, which had been rejecting pushes since v0.20.0 (five consecutive release failures). The AKS deployment's `imagePullSecret` needs to be updated cluster-side to authenticate against ghcr.io.

## [0.9.4]

### Changed
- **Docs:** Added dedicated README_PYPI.md for PyPI users showing pip/uv install and Python SDK usage

## [0.9.3] - 2026-02-25

### Fixed
- **Football:** Refactored `_params()` return shape to `{"params": {...}}` to strictly conform to the Machina sports connector contract (PR #27).

# Changelog

All notable changes to this project will be documented in this file.

## [0.7.0] - 2026-02-21

### Added
- **Cross-Sport ESPN Commands:** Added 34 new command functions across 7 US team sports (NFL, NBA, WNBA, NHL, MLB, CFB, CBB) via shared normalizers.
  - New endpoints include `get_injuries`, `get_transactions`, `get_futures`, `get_depth_chart`, `get_team_stats`, and `get_player_stats`.
- **Expanded Football Coverage:** Added 17 new leagues to the `football-data` skill, bringing the total to 30 competitions.
  - New coverage includes Men's (Liga MX, Liga Argentina, Scottish Premiership, Belgian Pro League, Turkish Super Lig, J.League, A-League Men), Women's (NWSL, WSL, Liga F, Premiere Ligue, A-League Women, UEFA Women's Champions League, FIFA Women's World Cup), and European competitions (Europa League, Conference League, Copa Libertadores).

### Changed
- **Anthropic Level-3 Skill Architecture:** Major refactor to align with Anthropic's Level-3 architecture.
  - Extracted large payloads (team IDs, season schemas) into a new `references/` directory for on-demand loading.
  - Added deterministic bash/python param validators in the `scripts/` directory to prevent hallucinated API requests.
  - Migrated `SKILL.md` files from command lists to workflow recipes to improve agent reasoning.

## [0.6.0] - 2026-02-20

### ⚠️ Breaking Changes

- **`odds` field schema change** — The `odds` field in all ESPN scoreboard responses (NFL, NBA, WNBA, NHL, MLB, CBB, CFB) has changed from a **list of dicts** to a **single dict or `None`**.

  **Before (`0.5.x`):**
  ```python
  game["odds"]  # → [{"provider": "DraftKings", "details": "NE -6.5", "over_under": 220.5}]
  ```

  **After (`0.6.0`):**
  ```python
  game["odds"]  # → {"provider": "DraftKings", "details": "NE -6.5", "moneyline": {...}, "spread_line": {...}, "total": {...}, "open": {...}} or None
  ```

  **Migration:** Replace `game["odds"][0]["over_under"]` with `game["odds"]["over_under"]` (guard with `if game["odds"]`). ESPN only ever returns one provider (DraftKings), so the list wrapper was unnecessary abstraction.

### Added
- **Enriched ESPN odds parsing** across all 7 ESPN sport connectors (NFL, NBA, WNBA, NHL, MLB, CBB, CFB) via shared `normalize_odds()` in `_espn_base`
- Full DraftKings data now extracted: moneyline (home/away), spread with juice, total with juice, opening lines for line movement tracking, and favorite/underdog designation
- Three-way moneyline support for soccer (home/draw/away)
- `normalize_odds()` returns `None` when no odds are available (games in progress, final, or pre-odds)
- **CI infrastructure** — GitHub Actions workflow running lint and tests on PRs and pushes to main
- **ruff** linting (Python 3.10 target, line-length 120)
- **pytest** suite — 56 tests covering module imports, CLI registry, response envelope, cache, retry logic, and `normalize_odds` edge cases
- `py.typed` marker for PEP 561 compliance

## [0.4.0] - 2026-02-18

### Added
- **NBA data** — 8 commands via ESPN: scoreboard, standings, teams, roster, schedule, game summary, leaders, news
- **WNBA data** — 8 commands via ESPN: scoreboard, standings, teams, roster, schedule, game summary, leaders, news
- **NFL data** — 9 commands via ESPN: scoreboard, standings, teams, roster, schedule, team schedule, game summary, leaders, news
- Season-aware statistical leaders for NBA and WNBA — auto-derives current season from system date, avoids offseason 404s
- Postseason support for NFL schedule and scoreboard (Wild Card through Super Bowl as weeks 19-23)

### Fixed
- NFL `get_teams` connector now accepts optional `request_data` arg — previously caused a positional arg error via CLI
- NBA `get_schedule` season/date param collision — `date` now takes priority over `season` (were writing to same ESPN param key)
- WNBA `get_leaders` offseason 404 — switched to season-scoped ESPN core API endpoint with regular season type

## [0.2.0] - 2026-02-16

### Added
- HTTP retry with exponential backoff across all data sources (ESPN, Understat, FPL, Transfermarkt)
- Smart retry classification: transient errors (5xx, 429, timeouts) retry up to 3 attempts; client errors (4xx) fail immediately
- Extra backoff for 429 rate-limit responses
- Structured logging via `logging` module for request failures
- Upcoming fixtures in `get_team_schedule` — ESPN's `fixture=true` param now fetched and merged with past results

### Fixed
- CLI errors now output JSON on stdout (for agents) alongside stderr text (for humans) — agents no longer see silent failures
- Standardized error dicts across all HTTP helpers (`{"error": True, "status_code": N, "message": "..."}`)
- League-probing requests (team schedule, team profile, event resolution) skip retries to avoid wasting 60+ requests on ESPN 500s for wrong team/league combos

## [0.1.0] - 2026-02-01

Initial release.

- Football data: 20 commands across 12 leagues (ESPN, FPL, Understat, Transfermarkt)
- Formula 1: 6 commands via FastF1
- Prediction markets: Kalshi (12 commands) and Polymarket (11 commands)
- Sports news: RSS/Atom feeds and Google News
- CLI (`sports-skills`) and Python SDK
