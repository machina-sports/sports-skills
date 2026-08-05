## [Unreleased]

### Fixed
- **Every `site.api.espn.com`-backed command returned "Access Denied" (11 skills):** the shared `_USER_AGENT` was a partial browser string, which ESPN's edge rejects with a 403 while serving honest client User-Agents normally. Verified across `nfl`, `nba`, `wnba`, `nhl`, `mlb`, `cfb`, `cbb`, `golf`, `tennis`, `football`, and `cricket` — 41 zero-argument commands were failing, plus `golf.get_leaderboard`/`get_schedule` and `cricket.get_news`. Only `site.api.espn.com` was affected; `site.web.api`, `sports.core.api`, `www.espn.com`, and `cdn.espn.com` were fine, which is why `get_standings` was the lone survivor. The User-Agent is now derived from the running interpreter (so it never misreports the client), identifies the project, and is overridable per deployment via `SPORTS_SKILLS_USER_AGENT`. `football` no longer carries a duplicate copy of the constant; `polymarket` deliberately keeps its own, because its edge rejects what ESPN's requires.
- **A single denied host took out every ESPN command:** `espn_request` (and football's private equivalent) now retry a denied request against `site.web.api.espn.com`, which serves the identical `/apis/site/v2/...` surface — same paths, query semantics, and response shapes, verified across 7 resources and 3 sports. Only access-denial codes trigger the retry; a 404 does not, since a missing resource is missing everywhere.
- **`tennis.get_scoreboard` reported success on total failure:** the combined ATP+WTA path logged each tour's error and returned `status=True` with `count=0`, indistinguishable from "no tournaments today". It now errors when every tour fails, and flags `partial=True` with `warnings[]` when only some do.
- **`football.get_daily_schedule` silently served ~55% of fixtures:** when the ESPN leg failed it fell through to the openfootball fallback, which covers far fewer competitions, and reported plain success (43 events / 8 competitions vs. 95 / 19 for the same date). Degraded responses now carry `partial=True` and a `warnings[]` entry naming what was lost.
- **Upstream error bodies reached callers verbatim:** an HTML block page arrived as several hundred bytes of markup, and a JSON envelope as `{"error":{"message":"No stats found.","code":404}}` — which reads as data rather than a failure. Both are now collapsed to one line carrying the status, host, and the upstream's own sentence. `kalshi` shared the JSON leak and routes through the same helper.
- **Season-scoped stats returned nothing for months every offseason (7 sports, 20 call sites):** `get_team_stats`, `get_player_stats`, and `get_futures` derived their season from the calendar year, so between a season's end and its successor's first game they queried a year with no data and returned a bare upstream 404. A shared `fetch_season` helper now steps an *implied* season back one year and reports the substitution in `warnings[]`, while an explicitly requested season still surfaces its own error rather than quietly answering about a different year.
- **`get_team_schedule`, `get_standings`, and `get_rankings` reported the wrong season (7 sports, 16 call sites):** the echoed `season` came from ESPN's response envelope, which always names the *current* season regardless of the filter applied to the events. Requesting 2024 returned correct 2024 events labelled `season: 2026` (2027 for basketball). The requested season now wins.
- **`pip install sports-skills[nfl]` failed outright on Python 3.12+:** `nfl-data-py` pins `pandas<2`, whose last release has no wheels for 3.12/3.13, so installation died building pandas from source. It also silently downgraded pandas to 1.5.3 on 3.11, and the `[all]` extra demanded `pandas>=2.0` and `nfl-data-py` simultaneously — an unsatisfiable pair. `nfl-data-py` is now scoped to `python_version < '3.10'`, where it is the only available backend; 3.10+ installs `nflreadpy` and keeps pandas 2.x.
- **`get_nflverse_player_stats` / `get_nflverse_team_stats` returned weekly rows labelled as season stats:** both passed `stat_type="season"`, which is not a parameter of nflreadpy's loaders (the keyword is `summary_level`), so the `except TypeError` branch swallowed it and silently fell back to per-game rows. Both now return regular-season aggregates by default and accept `summary_level` (`reg`/`post`/`reg+post`/`week`) plus a `week` filter; an aggregate level combined with `week` is reported rather than silently dropped. Both new params are exposed through the CLI.
- **`get_nflverse_team_stats` returned schedule rows as team stats on the `nfl_data_py` backend:** that backend has no team-stat table, and the loader substituted `import_schedules`, so callers got game metadata (`gameday`, `weekday`, moneylines) inside a `stats` object with `status=True`. It now returns an explanatory error.
- **Four `get_nflverse_*` functions failed on their default season every offseason:** nflverse publishes the upcoming season's schedule months before its rosters, player stats, team stats, and play-by-play exist for it, so the derived tables failed with a raw `ValueError: Season must be between 1999 and 2025`. An implied season now steps back a year and reports the substitution; an explicitly requested season still surfaces the upstream error.
- **nflverse and ESPN data could not be joined:** nflverse schedules carry an `espn` column holding the exact ESPN event ID, but the normalizer discarded it along with `pfr` and `gsis`. Schedule events now expose `espn_event_id`, `pfr_game_id`, and `gsis_game_id`, so an nflverse row feeds straight into `get_game_summary` / `get_play_by_play` / `get_win_probability`. Numeric ids are coerced so the float-valued backend yields `"401671789"` rather than `"401671789.0"`.
- **ESPN team abbreviations matched nothing in nflverse filters:** ESPN spells two clubs `LAR` and `WSH` where nflverse uses `LA` and `WAS`, so those filters returned an empty success. The `team` filters now translate both spellings. Relocations (`OAK`/`LV`, `SD`/`LAC`, `STL`/`LA`) are deliberately not aliased, since nflverse uses the era-correct abbreviation and mapping them would corrupt historical queries. A `team` filter matching no rows now reports `warnings[]` instead of an empty list, and `limit` on play-by-play flags `truncated`.
- **Schedule rows exposed the result total as a betting field:** `total` (combined points scored) sat beside `spread_line` and the moneylines while `total_line` (the actual over/under) was dropped, so market code de-vigged against the wrong number. Both fields are now present and documented.
- **`get_nflverse_*` raised on a missing optional dependency:** the `ImportError` from the provider loader propagated as an unhandled traceback, contrary to the project rule that agent-facing skills fail with readable messages. All five now return `status=False` with the install hint.

### Added
- **`tests/test_espn_transport.py`:** offline coverage for User-Agent construction and the env override, HTML and JSON error collapsing, host-fallback behaviour (including that a 404 does not retry and that query params survive), the season-fallback contract, and echoed-season resolution across all 7 sports.
- **`tests/test_nfl.py`:** the NFL skill had no functional tests, which is why the above went unnoticed. Offline coverage for team-abbreviation translation, identifier coercion, summary-level resolution, the season-fallback contract, the schedule id bridge, empty-filter warnings, provider selection, and graceful failure.
- **Skill docs:** `nfl-data/SKILL.md` gains a "Using ESPN and nflverse Together" section covering the `espn_event_id` bridge, the two abbreviations that differ, the absence of any player-ID crosswalk, and the `total` vs `total_line` distinction.
## [0.29.0]

### Added
- **`markets` momentum data layer (4 new commands):** primitives for detecting a prediction-market price swing mid-game and resolving the play that caused it, across NFL, MLB, NBA, NHL, WNBA, CFB, and CBB. `get_live_tick` fuses an ESPN summary (teams, clock) with the live Kalshi home price for an in-progress game; `resolve_game_market` resolves an ESPN event to its open/settled Kalshi winner-market ticker, structurally rather than by fuzzy title (both sides of a winner market share one location-based title, so the home side is identified from the ticker suffix), handling doubleheaders by embedded start time; `get_plays_near_timestamp` returns the ESPN play window `[timestamp - window, timestamp]` parsed from real UTC wallclocks; `get_mock_tick` is a deterministic timeline-slice reader for fixtures. MLB and WNBA are verified against live ESPN + Kalshi data; the other five leagues were out of season and are covered by unit tests and fixtures.
- **`football` head-to-head (`get_head_to_head`):** historical H2H results plus match stats (shots, corners, cards) via football-data.co.uk, with an aggregated win/draw/goal summary. Covers 11 European domestic leagues (EPL, Championship, La Liga, Serie A, Bundesliga, Ligue 1, Eredivisie, Primeira Liga, Scottish, Belgian, Turkish); same-division meetings only. Replaces the old "unavailable" stub. ESPN remains the fixture authority.
- **`football` team strength (`get_team_strength`):** ClubElo Elo rating for one team or a two-team comparison (Elo difference + favorite). European clubs; country-scoped name resolution that drops reserve teams and reports unresolved teams rather than guessing.
- **`football` match forecast (`get_match_forecast`):** ClubElo win/draw/loss + most-likely-scoreline forecast for a team's upcoming fixtures (~week-ahead horizon); a model-free baseline that pairs with the `kalshi`/`polymarket` skills.
- **Russian Premier League competition:** ESPN (standings/schedule/teams/match data) + ClubElo strength. Understat has no RFPL data, so xG is intentionally disabled.

### Improved
- **Coverage-aware skill docs:** `football-data/SKILL.md` gains a Coverage & Source Map (which endpoint has data where), a Combining Endpoints playbook (match preview, report, form, rivalry, odds check), and gotchas (pass IDs not ambiguous names, ClubElo off-season snapshot gaps, forecast horizon, H2H same-division-only).
- **Name resolution:** consolidated free-source name matching into one documented, per-provider overrides map (exceptions only, not a full team DB), backed by an offline drift-guard test over a committed ClubElo snapshot fixture. `_normalize_name` now strips apostrophes ("Nott'm Forest" → "Nottingham Forest").

### Fixed
- **Kalshi winner-market prices could be inverted (`markets`):** a `yes_cents <= 1 → ×100` shim meant to tolerate 0-1 probabilities also caught a genuine **1 cent** price and rescaled it to 100c. Real settled Kalshi markets quote the losing side at exactly 1c, so `resolve_game_market` reported teams that **lost** at a 100% win probability — verified against four real MLB games (COL@MIL, CHC@PIT, NYY@PHI, LAD@NYM, all home losses, all reported as 100c). Now reuses the migration-tolerant `_price_cents` helper already used by `get_market_price`/`get_live_tick`, so integer-cent and `*_dollars` payloads share one unit.
- **A Kalshi market from a different date could be paired with the game (`markets`):** the start-time disambiguation only ran when more than one candidate matched, so a lone candidate was accepted regardless of its date. Asking for a finished game returned the same teams' *next* game (the only market still open) fused with the finished game's ESPN frame. Candidates whose embedded start is more than 12h from the ESPN start are now rejected, and no match returns a clean error rather than a plausible tick built from two different games.
- **Time-less Kalshi event tickers failed to parse (`markets`):** the ticker-tail pattern required a 4-digit HHMM segment, but some series omit it (e.g. the real `KXWNBAGAME-26JUL17SEAIND`), so those tails yielded no team pair and matching silently fell back to title-only. The time segment is now optional; only start-time doubleheader disambiguation degrades for such series.
- **`uv` could not resolve the project on Python 3.9:** `nflreadpy` requires >=3.10 while the project declared >=3.9, so locking failed outright. `nflreadpy` is now gated behind a `python_version >= '3.10'` marker (3.9 falls back to `nfl-data-py`, which the provider loader already prefers-then-falls-back through), and `requires-python` is `>=3.9.10` because `py-clob-client-v2` requires it.
- **`nflverse` commands returned no data on Python >=3.10:** `nflreadpy` returns polars frames and the normalizer converts them with `.to_pandas()`, which needs `pyarrow` — undeclared, so every `get_nflverse_*` call raised `ModuleNotFoundError`. `pyarrow` now ships with the `nfl`/`all` extras under the same >=3.10 marker, and a declaration guard test keeps the pairing from drifting again.
- **Soccer summary normalizers could raise on a null boxscore (`football`):** `summary.get("boxscore", {})` returns `None` when the key is present with a null value, so `.get` on it would raise. Both the statistics and lineup normalizers now coerce defensively. ESPN's soccer endpoints send a stub `boxscore: {"teams": [...]}` rather than a null, so this is a defensive guard rather than a fix for observed behavior.
- Uncovered leagues on the new football endpoints degrade gracefully with an informative message instead of returning empty/erroring silently.

## [0.28.1]

### Improved
- **Agent/Hermes safety contract:** added root `AGENTS.md` and `.hermes.md`, plus machine-readable `skills/catalog.json`, so autonomous agents can default to read-only sports data and identify high-risk premium/trading workflows.
- **Polymarket namespace split:** kept `polymarket` read-only for market discovery/prices/order books, and moved wallet-backed order management to the explicit `polymarket-trading` skill and CLI namespace.
- **Premium install guidance:** replaced default `curl | bash` instructions with `pipx` / `uv tool` / pip installs and an inspect-before-run fallback.

### Fixed
- **Agent contract regression tests:** added tests that ensure read-only catalog skills do not expose financial-execution verbs and that read-only Polymarket docs do not include wallet-secret guidance.

## [0.28.0]

### Added
- **`esports` skill (keyless, stdlib-only):** Dota 2 via OpenDota (`get_pro_matches`, `get_leagues`, `get_pro_teams`, `get_match`) and League of Legends esports via Leaguepedia Cargo (`get_lol_tournaments` + a generic `lol_cargo_query`). Handles Leaguepedia's in-body `ratelimited` response on HTTP 200 and its CC-BY-SA / custom-User-Agent requirements; token-bucket rate limiting and a TTL cache throughout.
- **Esports odds on the prediction-market skills:** `kalshi.get_esports_odds` (CS2/LoL/Dota2 — implied probability + derived decimal odds; prices on the same 0-100 cent scale as every other kalshi command via the migration-tolerant `_price_cents`/`_volume_units` helpers) and `polymarket.get_esports_events` (`tag_slug=esports`, prices via the existing `_normalize_event`).

### Fixed
- **`get_game_summary` returned a hollow box score and empty scoring plays across ESPN sports:** player rows live under `boxscore["players"]` (not `boxscore["teams"]`, which carries only team aggregates), and ESPN omits the top-level `scoringPlays` key for basketball/hockey/baseball — so the box score `athletes` and `scoring_plays` came back empty while the call still reported success. Added shared `normalize_boxscore` / `normalize_scoring_plays` helpers in `_espn_base.py` (box score now reads the `players` sub-tree and preserves team aggregates as `team_stats`; scoring plays fall back to the `plays[]` array, backfilling team identity) and routed **all seven** ESPN game-summary connectors through them — NBA, NHL, MLB, WNBA, and now NFL, CFB, and CBB. The helpers also tolerate `null` `boxscore`/`plays` payloads (not-started games) instead of raising. Thanks @Squidy247-goat for the original NBA/NHL/MLB/WNBA fix.

## [0.27.1]

### Added
- **`catalog` advertises the premium tier:** `sports-skills catalog` gains an additive `tiers` block describing the `open` (MIT) and `premium` (Machina) tiers alongside the existing `modules` list. Top-level `modules` is unchanged — byte-identical, back-compat verified — so downstream consumers (e.g. sportsclaw's `discoverAvailableSkills`) are unaffected. `premium_tier()` is static metadata only (skills, `activate`, `requires`, a local `which machina` check, docs URL); no secrets, no network.
- **`licensed_data` upgrade trigger:** registered in `_premium.TRIGGERS`, so `build_hint("licensed_data")` returns a structured upgrade block (the stub previously returned `None`). Not yet auto-emitted at runtime — `attach()` still fires only on HTTP 429.

### Fixed
- **Machina docs URL now uses HTTPS** (`http://docs.machina.gg/` → `https://docs.machina.gg/`).

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
