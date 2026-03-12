# Volleyball — Competition IDs

All available `competition_id` values for the `volleyball` module. These map to Nevobo poules in the Dutch volleyball pyramid.

## Eredivisie (Top Tier — 8 teams each)

The highest level of Dutch professional volleyball.

| competition_id | Name | Gender | Teams |
|---|---|---|---|
| `nevobo-eredivisie-heren` | Eredivisie Heren | Men | 8 |
| `nevobo-eredivisie-dames` | Eredivisie Dames | Women | 8 |

## Topdivisie (Second Tier — 10 teams per pool)

Split into two pools (A and B) per gender.

| competition_id | Name | Gender | Teams |
|---|---|---|---|
| `nevobo-topdivisie-heren-a` | Topdivisie Heren A | Men | 10 |
| `nevobo-topdivisie-heren-b` | Topdivisie Heren B | Men | 10 |
| `nevobo-topdivisie-dames-a` | Topdivisie Dames A | Women | 10 |
| `nevobo-topdivisie-dames-b` | Topdivisie Dames B | Women | 10 |

## Superdivisie (Third Tier — 10 teams each)

| competition_id | Name | Gender | Teams |
|---|---|---|---|
| `nevobo-superdivisie-heren` | Superdivisie Heren | Men | 10 |
| `nevobo-superdivisie-dames` | Superdivisie Dames | Women | 10 |

## Lower Divisions & Regional Leagues

For divisions below Superdivisie (1e Divisie, 2e Divisie, 3e Divisie, regional leagues, youth, beach), use the `get_poules` command to discover available poules:

```bash
# National-level poules (115 total): 1e/2e/3e Divisie, cups, playoffs
sports-skills volleyball get_poules --regio=nationale-competitie --limit=20

# Regional poules (by region)
sports-skills volleyball get_poules --regio=regio-noord --limit=20
sports-skills volleyball get_poules --regio=regio-west --limit=20
sports-skills volleyball get_poules --regio=regio-oost --limit=20
sports-skills volleyball get_poules --regio=regio-zuid --limit=20

# Championships
sports-skills volleyball get_poules --regio=kampioenschappen --limit=20

# All poules (6,400+ across the entire pyramid)
sports-skills volleyball get_poules --limit=30
```

## Naming Convention

Competition IDs follow the pattern: `nevobo-<league>-<gender>[-<pool>]`
- `nevobo` — data source prefix (Nevobo API)
- `<league>` — eredivisie, topdivisie, superdivisie
- `<gender>` — heren (men), dames (women)
- `<pool>` — optional pool letter (a, b) for split divisions like Topdivisie

## Dutch Volleyball Pyramid

```
Eredivisie          (Tier 1)  — 8 teams, professional
Topdivisie          (Tier 2)  — 2 pools x 10 teams
Superdivisie        (Tier 3)  — 10 teams
1e Divisie          (Tier 4)  — multiple pools
2e Divisie          (Tier 5)  — multiple pools
3e Divisie          (Tier 6)  — multiple pools
Regional leagues    (Tier 7+) — organized by regio
```
