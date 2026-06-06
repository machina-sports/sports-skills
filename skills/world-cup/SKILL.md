---
name: world-cup
description: |
  Premium FIFA World Cup 2026 market & match intelligence — a hosted, read-only
  layer that fuses official match truth (fixtures, standings, squads, injuries,
  player performance) with live prediction markets (Kalshi + Polymarket: prices,
  order books, price history, movers, cross-venue edges) and AI-grounded context
  (prematch briefs, move explanations, fan/social pulse). Every entity carries a
  canonical machina URN cross-walked across api-football, sportradar, opta, entain
  and ESPN, so a market resolves to a fixture resolves to two teams.

  This skill is prompt-only and premium: it routes the agent to the hosted World Cup
  Intelligence project (a per-project Machina MCP server) via `machina-cli`. It runs
  no code locally and ships no API keys.

  Use when: the user wants World Cup 2026 odds + match context together, asks "what
  moved and why", wants a grounded market brief or fan-sentiment read on a fixture,
  or needs one stable id that joins markets ↔ fixtures ↔ teams across providers.
  Don't use when: the user wants free snapshot data from public APIs (use the
  `football-data`, `kalshi`, `polymarket`, or `markets` skills), or wants to place a
  bet/trade — this layer is read-only intelligence and never executes orders.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
  premium: true
  billing: metered
---

# World Cup 2026 Intelligence (Premium)

A hosted, **read-only** intelligence layer for the FIFA World Cup 2026. It joins
three things that are normally separate — **official match truth**, **live
prediction-market state**, and **AI-grounded context** — under one canonical id
space, so an agent can go from a market to the fixture to the teams in a single
hop and reason about *why* a price is moving.

This skill itself runs no code. Like the [`machina`](https://skills.sh/machina-sports/sports-skills/machina)
gateway it builds on, it shells out to `machina-cli`, selects the hosted **World
Cup Intelligence** project, and the agent harness talks to that project's **MCP
server**. Tenant routing, provider keys, rate limits, and caching all live
server-side. You never call a raw HTTP API or hold a provider key.

> **Read-only intelligence — not advice.** Every output is informational sports
> market intelligence. **Not betting, trading, financial, or investment advice.**
> This layer has **no** order-placement, trading, or portfolio endpoints. If the
> user wants to act on a signal, that execution happens in *their own* agent, on
> *their own* account and keys — never here.

## Premium / billing

This is a paid, metered layer (Machina Credits — see your project's credit-cost
classes). Free public data does **not** flow through here. Where your agent
harness supports agent-native pay-per-call (x402), the MCP server advertises price
per tool; otherwise calls draw from the project's credit balance. If a call
returns a `402` / "payment required" / "insufficient credits" error, surface it to
the user and stop — do not retry-loop.

## Quick Start

```bash
# 1. Install the Machina CLI (one-time) — shared with the `machina` skill
pip install machina-cli
# or: curl -fsSL https://raw.githubusercontent.com/machina-sports/machina-cli/main/install.sh | bash

# 2. Authenticate
machina login                              # interactive (browser)
# machina login --api-key <project-api-key>  # non-interactive (CI/CD)

# 3. Select the World Cup Intelligence project (REQUIRED)
machina project list
machina project use <world-cup-project-id>

# 4. Connect the MCP server
#    `machina project use` (or `machina template install`) returns the MCP URL +
#    headers. Point your harness's MCP config at it (e.g. .claude/mcp.json for
#    Claude Code), then reload the harness so it re-reads the config.
```

## CRITICAL: Before Any Premium Call

Verify, in order — fix the *specific* failing step, never loop on the same call:

- `machina-cli` is installed — `which machina` / `machina version`.
- Authenticated — `machina auth whoami` returns a user.
- The **World Cup Intelligence** project is selected — `machina project use <id>`.
- The harness is connected to that project's MCP server (tools are visible).

## What you get

All tools are **read-only**. Group by job:

### Identity & fixtures (official match truth)

| Tool | Returns |
|------|---------|
| `worldcup-resolve` | Any provider id **or** canonical URN → entity + all cross-provider ids |
| `worldcup-get-schedule` | Fixtures, filter by date / team / status |
| `worldcup-get-event-context` | Enriched match context (event + grounded prematch research) |
| `worldcup-get-standings` | Group tables |
| `worldcup-get-squads` | Both teams' squads |
| `worldcup-get-injuries` | Injuries / suspensions |
| `worldcup-get-player-performance-context` | Player performance signals (official + provisional, kept separate) |

### Market intelligence (Kalshi + Polymarket, URN-linked)

| Tool | Returns |
|------|---------|
| `worldcup-search-markets` | Market search across venues, linked to fixtures/teams |
| `worldcup-get-market-state` | Live price + order-book depth + price history + trades |
| `worldcup-market-movers` | Biggest price moves over a lookback window |
| `worldcup-compare-market-sources` | Cross-venue price comparison |
| `worldcup-find-market-edges` | Informational edge / arb candidates, with caveats (AI) |
| `worldcup-explain-market-move` | Why a price moved, grounded + cited (AI) |
| `worldcup-generate-market-brief` | Grounded market-intelligence brief for a fixture (AI) |
| `worldcup-fan-sentiment-context` | Social / news pulse from live X + web (AI) |

### Conversational

- `world-cup-intelligence-agent` — full read + market context.
- `world-cup-market-analyst-agent` — market-focused analyst.

## The intelligence loop

A typical agent flow — research only, no execution:

1. **Find** the market — `worldcup-search-markets {"query":"Brazil","status":"open"}`.
2. **Anchor** it to truth — each market carries `event_urn` + `related_team_urns`;
   `worldcup-resolve` (or `worldcup-get-event-context`) expands the fixture, squads,
   standings, injuries.
3. **Read live state** — `worldcup-get-market-state` for price, order-book depth,
   history, trades; `worldcup-market-movers` / `worldcup-compare-market-sources` for
   movement and cross-venue gaps.
4. **Explain & brief** — `worldcup-explain-market-move`, `worldcup-find-market-edges`
   (informational only), `worldcup-generate-market-brief`, `worldcup-fan-sentiment-context`.
5. **Hand off** — return the signal + sources + freshness/liquidity/resolution
   caveats to the user. **Stop there.** Any trade is the user's own action elsewhere.

## Identifiers

Every entity has a **canonical machina URN**, stable across providers:

- event — `urn:machina:sport:soccer:event:{home}-vs-{away}:{YYYYMMDD}:wor`
- team — `urn:machina:sport:soccer:team:{slug}:{iso3}`
- player — `urn:machina:sport:soccer:player:{slug}:{YYYYMMDD-dob}:{iso3}`
- competition — `urn:machina:sport:soccer:competition:fifa-world-cup-2026:wor`

`iso3` is the lowercased ISO-3166 alpha-3 (UK home nations use FIFA codes `eng`/`sco`/`wal`).
Every doc also carries a uniform `provider_ids` map (one id per provider).

**Alternate key:** reads accept the canonical `event_urn` **or** `provider_event_id`
(the api-football fixture id, e.g. `1489417`) — the latter is the simplest client
handle. Markets are keyed `{source}:{source_market_id}` (e.g. `kalshi:KXWCGAME-…`,
`polymarket:2415458`).

## Freshness

- Identity / fixtures — synced; teams/events stable, players refresh daily.
- `worldcup-search-markets` — cached, refreshed every ~30 min; responses warn past 15 min.
- `worldcup-get-market-state` — live from the source.
- `worldcup-market-movers` — hourly snapshot series; needs ≥2 buckets to show movement.

## Common Errors & Recovery

| Error | Cause | Recovery |
|---|---|---|
| `command not found: machina` | CLI not installed | `pip install machina-cli` |
| `Not authenticated…` | No session | `machina login` |
| `No project selected…` | Project not chosen | `machina project list` → `machina project use <world-cup-id>` |
| `402` / `payment required` / `insufficient credits` | Metered call, no balance | Tell the user; top up credits or enable x402. **Do not retry-loop.** |
| Tools not visible after `project use` | Harness hasn't reloaded MCP config | Restart / reload the harness so it re-reads the MCP config |

## Commands that DO NOT exist — never call these

- ~~any `place`, `order`, `trade`, `buy`, `sell`, `bet` tool~~ — this layer is
  read-only; no such tool exists. Execution is the user's own, elsewhere.
- ~~raw `requests` / direct provider HTTP~~ — go through the MCP server; keys and
  the correct `searchLimit`/nested `filters` live server-side.
- ~~`machina mcp start` / `machina mcp connect`~~ — the MCP server runs on Machina
  infra; the harness connects via its own MCP config.

## Guardrails

- Never present an output as betting/trading/financial advice.
- Never use "guaranteed edge", "guaranteed profit", or "bet this" language —
  edges/movers are **informational candidates**, not recommendations.
- Always return **source, freshness, and resolution/liquidity caveats** with any
  market output.
