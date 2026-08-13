# Valid Commands & Common Mistakes

## CRITICAL: this is a catalog, not an odds feed

The ProphetX public API exposes market STRUCTURE, not prices. Never invent or
estimate odds from this skill's output, and never present `total_stake`
(matched volume) as odds or available liquidity.

```
WRONG: "ProphetX has the Eagles at -150"        → odds are not in this data
RIGHT: "ProphetX lists Moneyline/Spread/Total (+189 props) for Bengals at Eagles;
        public odds aren't exposed — matched stake on the moneyline is $7,156"
```

## Sport-Aware Commands (recommended)

- `get_sports_config` — **list sport codes and live tournaments** (start here)
- `get_todays_events --sport=mlb` — today's slate
- `search_markets --sport=nfl --query="Eagles"` — markets of the soonest matching events

## Raw API Commands

- `get_tournaments [--sport=soccer] [--limit=50] [--next=<cursor>]`
- `get_events --tournament_id=109 [--status=not_started]`
- `get_markets --event_id=19742 [--api_version=v2] [--market_type=moneyline]`
- `get_market --event_id=19742 --market_id=219` (also accepts `--market_id=19742:219`)

## Common mistakes

- Using market `id` as a unique key — it's the market-TYPE id (219 = Moneyline
  everywhere). Use `market_key` (`event_id:market_id`).
- Expecting odds in `outcomes`/`selections` — check `selections_available`
  first (currently always `False` publicly).
- Forgetting `api_version=v2` when the user asks about player props or
  alternate lines — v1 only carries the core catalog.
- Passing a league code where a sport is needed: `epl`/`mls`/`worldcup` alias
  to `soccer` and return ALL soccer tournaments — filter by tournament name
  from the results.
