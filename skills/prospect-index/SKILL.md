---
name: prospect-index
description: |
  MPI (Machina Prospect Index) — a continuous, decomposable score for football players
  who don't have a market price yet. Every player opens at 7,500 and moves by a FACT
  component (what he did on the pitch, published weights) plus a PROJECTION component
  (backtest-calibrated probability of reaching a professional-value threshold, converted
  to points). v0 ships one fully-resolved retrospective cohort (FIFA U-17 World Cup 2015,
  11-year outcome window) so every score can be checked against what actually happened.

  Use when: user asks about young player prospects, youth cohort valuation, "who was the
  best prospect of a generation", prospect index scores, index methodology, or wants a
  calibrated prior for a young player's chance of "making it".
  Don't use when: user wants CURRENT market values or transfers (use football-data),
  live odds (polymarket/kalshi), or senior player stats (football-data). This is a
  research/benchmark index, not live market data.
license: MIT
metadata:
  author: machina-sports
  version: "0.1.0"
  risk:
    mode: compute
    money_movement: false
    secrets_required: false
    external_mcp: false
    cloud_upload: false
    requires_explicit_confirmation: false
---

# Prospect Index (MPI)

A prospect index in the mold of the composite indexes launched in 2026 (Kalshi's KPOW,
FutureSports' FSPI): base value + a fact half + a projection half, with a published
methodology. The gap it covers: **84% of the world's best U-17 players have no market
value at all at 17** — the market's first valuation lands around age 19. The MPI is a
number for exactly that window.

All data is embedded (no network, no keys). No third-party market values are
redistributed — outcomes appear only as a derived boolean.

## Quick Start

```bash
sports-skills prospects get_methodology
sports-skills prospects list_cohorts
sports-skills prospects get_cohort_index --limit=10
sports-skills prospects get_cohort_index --position=FW --country=BRA
sports-skills prospects get_player_index --query="Christian Pulisic"
```

Python SDK:

```python
from sports_skills import prospects

top = prospects.get_cohort_index(limit=10)
pulisic = prospects.get_player_index(query="Christian Pulisic")
```

## How to read a score

- **7,500** = the whole cohort's starting line ("nothing proven beyond the average promise").
- The distance above 7,500 splits into `fact_points` (production) and `projection_points`
  (expectation). The `decomposition.projection_share` field says which one dominates:
  a score that is mostly projection is fragile; mostly fact is solid.
- `segment` + `p_reach` show the calibrated prior behind the projection — these are
  **measured backtest rates** (e.g., scored + not-market-aware → 25% reached a €5M peak),
  not fitted parameters.
- In the v0 retrospective cohort, `outcome_reached_eur5m_peak` lets you check every
  score against what actually happened over 11 years.

## Honest limits (tell the user when relevant)

- v0 has ONE cohort (FIFA U-17 WC 2015) and ONE fact feature (tournament goals) —
  it is a calibration demo, not a live index.
- The `scored_and_market_aware` segment has tiny n (6 players); flag it.
- Goals as the only fact feature under-scores defenders and goalkeepers by construction.
- Methodology and backtest: https://github.com/RodrigoAlbe/machina-market-radar
