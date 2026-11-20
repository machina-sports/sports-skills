# sports-skills usage notes

Usage notes for sports-skills. For an overview, see the [README](../README.md). Per-skill commands live in [`skills/<skill>/SKILL.md`](../skills/) and its `references/` folder; release notes are in the [changelog](../CHANGELOG.md).

## Record & Replay

Record a run once against live sources, then replay it later with zero network access — useful for evaluations, regression tests, and reproducible bug reports.

```bash
# 1. Record: fetch live and save every upstream response
SPORTS_SKILLS_REPLAY=record SPORTS_SKILLS_REPLAY_DIR=./replays/2026-09-23 \
  sports-skills nba get_scoreboard --date=2026-01-01

# 2. Replay: serve only from the directory; nothing touches the network
SPORTS_SKILLS_REPLAY=replay SPORTS_SKILLS_REPLAY_DIR=./replays/2026-09-23 \
  sports-skills nba get_scoreboard --date=2026-01-01
```

- `off` (default) is the normal live behaviour. There is no default directory: `record` and `replay` require `SPORTS_SKILLS_REPLAY_DIR`.
- `fill` serves what is recorded and fetches + records only what is missing, never rewriting existing entries (useful to grow a benchmark corpus without drift; `record` rewrites).
- A request that was never recorded returns an error with `replay_miss: true` instead of falling back to the network.
- Entries are readable JSON keyed by method + URL (query order normalized), stored byte-for-byte with a SHA-256 integrity check.
- Deterministic 4xx responses are recorded so fallback paths replay exactly. Transient failures (5xx, 429, timeouts) are never recorded.
- Coverage: all ESPN-backed modules (NFL, NBA, WNBA, NHL, MLB, college, golf, tennis, cricket via ESPN), football (ESPN, Understat, FPL, Transfermarkt, openfootball), Kalshi, Polymarket and ProphetX public reads, esports (OpenDota, Leaguepedia), Cricsheet, volleyball (Nevobo API and RSS), XCTF (TFRRS, The Stride Report), metadata (TheSportsDB), RSS/Google News feeds, nflverse (schedules, weekly rosters, player and team stats, play-by-play) and FastF1 (schedules, session results, laps). Polymarket trading (`polymarket-trading`) is never recorded. Local feed files passed to `news` are read directly.
- Not covered: the `espn-api` skill's raw helper scripts (`skills/espn-api/scripts/espn_fetch.py` and `espn_fetch.sh`) bypass the package and are never recorded or replayed. They exit with an error, before any network access, when `SPORTS_SKILLS_REPLAY` is `record`, `replay`, `fill`, or any value other than `off`. Use the package runtime for offline or replay evaluations.
- nflverse and FastF1 are read through libraries, so they are recorded at the loader: each DataFrame is stored as Parquet with a JSON sidecar (loader, arguments, provider version, SHA-256), keyed by loader + arguments. This needs `pyarrow` (included in the `nfl` extra; `pip install pyarrow` for F1); without it `record`/`replay` of these calls returns a `replay_error`.
- Recorded payloads come from third-party sources and stay subject to their terms. Check them before sharing a replay directory.

## Machina Sports Schema (canonical output)

Football event commands and `nba get_event_summary` can emit the **Machina Sports Schema** envelope instead of the native payload: one provider's observation of one event, serialized as JSON-LD against the [IPTC Sport Schema](https://sportschema.org) 1.1 profile, with a provider-id crosswalk, a capability report, and a provenance block naming the pinned upstream commit.

```bash
# One event → one envelope, printed directly
sports-skills football get_event_summary --event_id=740000 \
  --format=machina-canonical --observed-at=2026-03-01T22:05:00+00:00

# A day's fixtures → {provider, format, events}, every event a full envelope
sports-skills football scores --date=2026-03-01 \
  --canonical --observed-at=2026-03-01T22:05:00+00:00
```

`--canonical` is an alias for `--format=machina-canonical`. It is supported on `football get_event_summary`, `football get_daily_schedule` (also reachable as `scores`) and `nba get_event_summary`; every other command refuses the flag by name rather than wrapping data the schema does not describe. From Python:

```python
from sports_skills import canonical, football

event = football.get_event_summary(event_id="740000")["data"]["event"]
document = canonical.canonicalize_event(event, observed_at="2026-03-01T22:05:00+00:00")
```

**NBA: one game with its plays, and a declared start precision.** `nba get_event_summary` returns a game as its scoreboard event plus its play-by-play, and it is the one NBA command the mode accepts:

```bash
sports-skills nba get_event_summary --event_id=401859967 --canonical \
  --observed-at=2026-06-14T03:30:00+00:00 --start-time-precision=minute
```

From Python, with normalized ESPN event and play-by-play values:

```python
from sports_skills import canonical

document = canonical.canonicalize_nba_event(
    event,
    plays,
    observed_at="2026-06-14T03:30:00Z",
    start_time_precision="minute",
)
```

`--start-time-precision` (`minute`, `second` or `fractional_second`) is required there and refused everywhere else. ESPN states an NBA start to the minute, so the envelope carries a 60-second window (`temporal_evidence`) and no `sport_schema_graph`: the schema refuses an interoperability graph when no exact start exists. Every play is in `event_view.actions`; minute values retain their source text.

**`--observed-at` is required and must carry a UTC offset.** It is never read from the clock. It is the one input that makes the document reproducible, and the cross-repository reference fixtures this output is tested byte-for-byte against depend on it being stated rather than guessed.

**Rights: prototype only.** Every envelope carries `rights: {"data_class": "open-public", "prototype_only": true, "commercial_use": false}`. `open-public` classifies the *source* — ESPN's public endpoints, read live — and is not an entitlement; the two booleans are the licence claim, and they are constants this package cannot be asked for a better version of. Gate a consumer against them with `--consumer-tier`:

```bash
sports-skills football get_event_summary --event_id=740000 --canonical \
  --observed-at=2026-03-01T22:05:00+00:00 --consumer-tier=production
# → refused: rights-prototype-only, exit status 1
```

`prototype` (the default) is served. `production` refuses every envelope this package can produce, with one actionable finding and a nonzero exit status — including a query that returns nothing, which is refused before the provider is called, because the licence answer is the adapter's and not the result set's. The same rule is callable directly as `canonical.rights_findings(document, consumer_tier="production")`. That gate is vendored byte-exact from `machina-templates` rather than reimplemented here, so both repositories answer the question with the same code. For licensed data cleared for commercial use, see [machina.gg](https://machina.gg).

The default output of every command is unchanged: no module on the native path imports the canonical package, and the CLI reaches it only when you ask for it by name.

## Output contracts

**Large tables.** nflverse player/team stats, rosters, schedules and play-by-play; NBA Stats game logs, team stats and shot charts; and MLB Stats play-by-play accept optional `sort_by`, `descending`, `limit` and `fields`. They apply after the fetch (replay entries are unchanged) and add `total_rows` / `returned_rows`; without them output is unchanged.

**Two-source skills.** ESPN and each league's official or community backend use unrelated id systems. Each skill documents its join recipe (game date + team abbreviations/names), and passing the wrong system's id returns a guided error. `gleague-data` accepts only NBA.com tricodes on its official commands.

**NFL schedule coverage.** `nfl get_schedule` returns one week or ESPN's current window, never a whole season. `season` + `week` → that week (weeks 1-18 regular season, 19-23 postseason); `week` alone → that week of the current season; neither → ESPN's current scoreboard window. `season` alone is refused with an error pointing at `get_team_schedule`. `get_schedule` and `get_team_schedule` add a `coverage` object (`requested`, `completeness`, `reason`, `warnings`, `returned_count`, `seasons_returned`, `weeks_returned`). `completeness` is `unknown`, or `partial` when a team's postseason request failed — never `complete`, because ESPN publishes no game total to check against (a missing team is not a bye). There is no "updated at": ESPN does not stamp these responses.

**ESPN injury identity.** ESPN injury records (NFL, NBA, WNBA, NHL, MLB and CFB) add `athlete_id` (string or `null`), `identity_status` (`provider-native` or `unresolved`) and `id_namespace` (`espn` or `null`). The response adds `identity_summary: {records, provider_native, unresolved}` and `caveats`; `count` is still the number of teams. ESPN often omits `athlete.id`, so expect `unresolved` records. Names are never hashed into ids or fuzzily joined, and a player absent from the report is not confirmed healthy.

## Premium & licensed data

`sports-skills premium` hands off to [`machina-cli`](https://github.com/machina-sports/machina-cli) for licensed and real-time feeds (`--install` installs it first, `--json` for machine-readable output). This is separate from the [Machina Agent Storefront](../README.md#discover-the-machina-agent-storefront). When a public API rate-limits a request, or a request needs data the free sources cannot provide, the JSON response gains an additive `upgrade` field; suppress it with `SPORTS_SKILLS_NO_UPGRADE_HINTS=1`.

## Contributing

Add a skill in `skills/<your-skill>/SKILL.md` following the [Agent Skills spec](https://agentskills.io/specification), then open a PR. Discuss ideas on the [Machina Sports Discord](https://discord.gg/PBYd6FbBSK).

## Acknowledgments

This project is built on top of great open-source work and public APIs:

- **[ESPN](https://www.espn.com)** — for keeping their web endpoints accessible; powers most of the sports data skills.
- **[nflverse](https://github.com/nflverse)** — the community-maintained NFL data ecosystem (`nfl_data_py` / `nflreadpy`), powering schedules, weekly rosters, normalized stats, and play-by-play in the NFL skill.
- **[MLB](https://www.mlb.com)** — for the genuinely open MLB Stats API powering pitch-level play-by-play, career splits, and a century of schedules in the MLB skill.
- **[NHL](https://www.nhl.com)** — for the open NHL API powering coordinate play-by-play, career rows, and Original-Six-era history in the NHL skill.
- **[NCAA](https://www.ncaa.com)** — for the public scoreboard, game, and bracket endpoints powering the official college backend in the CFB and CBB skills.
- **Endpoint references** — [swar/nba_api](https://github.com/swar/nba_api), [zero-sum-seattle/python-mlb-statsapi](https://github.com/zero-sum-seattle/python-mlb-statsapi), [dword4/nhlapi](https://gitlab.com/dword4/nhlapi), and [henrygd/ncaa-api](https://github.com/henrygd/ncaa-api) — community documentation that mapped the request shapes our direct integrations use. Nothing from these projects is bundled; they were the maps.
- **[Nevobo](https://www.nevobo.nl)** — the Nederlandse Volleybalbond, for their open API providing Dutch volleyball data.
- **[Fantasy Premier League](https://fantasy.premierleague.com)** — for their community API powering injury news, player stats, ownership data, and ICT index.
- **[Transfermarkt](https://www.transfermarkt.com)** — for player market values and transfer history.
- **[Understat](https://understat.com)** — for xG data across the top 5 European leagues.
- **[football-data.co.uk](https://www.football-data.co.uk)** — for freely downloadable historical results and match stats.
- **[ClubElo](http://clubelo.com)** — for free Elo ratings and match forecasts covering European club football.
- **[openfootball](https://github.com/openfootball/football.json)** — open public domain football data (CC0), used as a fallback when ESPN is unavailable.
- **[FastF1](https://github.com/theOehrly/Fast-F1)** — the backbone of our Formula 1 skill. Thanks to theOehrly and contributors.
- **[TFRRS](https://www.tfrrs.org)** and **[The Stride Report](https://www.thestridereport.com)** — for NCAA cross country and track & field data and news.
- **[feedparser](https://github.com/kurtmckee/feedparser)** — reliable RSS/Atom parsing for the news skill.
- **[Kalshi](https://kalshi.com)**, **[Polymarket](https://polymarket.com)**, and **[ProphetX](https://prophetx.co)** — for their public market data APIs.
- **[skills.sh](https://skills.sh)** — the open agent skills directory and CLI.
- **[Agent Skills](https://agentskills.io)** — the open spec that makes skills interoperable across agents.
