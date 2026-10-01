# ESPN Sport and League Slugs

Complete mapping of every sport and league available through the ESPN API. Use these slugs in URL paths.

## How Slugs Work

ESPN endpoints require two slugs: a **sport** slug and a **league** slug.

- **Site API pattern:** `.../sports/{sport}/{league}/...`
- **Core API pattern:** `.../sports/{sport}/leagues/{league}/...`

---

## Football (sport: `football`)

| League | Slug | Abbreviation |
|--------|------|--------------|
| NFL | `nfl` | NFL |
| NCAA Football | `college-football` | NCAAF |
| Canadian Football League | `cfl` | CFL |
| United Football League | `ufl` | UFL |
| XFL | `xfl` | XFL |

---

## Basketball (sport: `basketball`)

| League | Slug | Abbreviation |
|--------|------|--------------|
| NBA | `nba` | NBA |
| WNBA | `wnba` | WNBA |
| NBA G League | `nba-development` | GLEA |
| NCAA Men's Basketball | `mens-college-basketball` | NCAAM |
| NCAA Women's Basketball | `womens-college-basketball` | NCAAW |
| FIBA World Cup | `fiba` | FIBA |
| NBL (Australia) | `nbl` | NBL |
| Olympics Men's Basketball | `mens-olympics-basketball` | OLY |
| Olympics Women's Basketball | `womens-olympics-basketball` | OLY |
| Las Vegas Summer League | `nba-summer-las-vegas` | LVSL |
| California Classic Summer League | `nba-summer-california` | NBASL |
| Golden State Summer League | `nba-summer-golden-state` | GSSL |
| Orlando Summer League | `nba-summer-orlando` | OSL |
| Sacramento Summer League | `nba-summer-sacramento` | SASL |
| Salt Lake City Summer League | `nba-summer-utah` | SLSL |

---

## Baseball (sport: `baseball`)

| League | Slug | Abbreviation |
|--------|------|--------------|
| MLB | `mlb` | MLB |
| NCAA Baseball | `college-baseball` | NCAAB |
| NCAA Softball | `college-softball` | NCAAS |
| World Baseball Classic | `world-baseball-classic` | WBC |
| Dominican Winter League | `dominican-winter-league` | DWL |
| Mexican League | `mexican-winter-league` | MLM |
| Puerto Rican Winter League | `puerto-rican-winter-league` | PRWL |
| Venezuelan Winter League | `venezuelan-winter-league` | VWL |
| Caribbean Series | `caribbean-series` | CAR |
| Little League Baseball | `llb` | LLB |
| Little League Softball | `lls` | LLS |
| Olympics Men's Baseball | `olympics-baseball` | OLY |

---

## Hockey (sport: `hockey`)

| League | Slug | Abbreviation |
|--------|------|--------------|
| NHL | `nhl` | NHL |
| NCAA Men's Ice Hockey | `mens-college-hockey` | NCAAH |
| NCAA Women's Hockey | `womens-college-hockey` | NCAAWH |
| World Cup of Hockey | `hockey-world-cup` | WCOH |
| Olympics Men's Ice Hockey | `olympics-mens-ice-hockey` | OLY |
| Olympics Women's Ice Hockey | `olympics-womens-ice-hockey` | OLY |

---

## Soccer (sport: `soccer`)

| League | Slug | Abbreviation |
|--------|------|--------------|
| English Premier League | `eng.1` | EPL |
| Spanish LALIGA | `esp.1` | LIGA |
| German Bundesliga | `ger.1` | BUN |
| Italian Serie A | `ita.1` | SA |
| French Ligue 1 | `fra.1` | L1 |
| MLS | `usa.1` | MLS |
| Liga MX | `mex.1` | LIGAMX |
| UEFA Champions League | `uefa.champions` | UCL |
| UEFA Europa League | `uefa.europa` | UEL |
| UEFA Conference League | `uefa.europa.conf` | UECL |
| FIFA World Cup | `fifa.world` | WC |
| FIFA Women's World Cup | `fifa.wwc` | WWC |
| NWSL | `usa.nwsl` | NWSL |
| NWSL Challenge Cup | `usa.nwsl.cup` | NWSLCC |
| English FA Cup | `eng.fa` | FAC |
| English Carabao Cup | `eng.league_cup` | ELC |
| Spanish Supercopa | `esp.super_cup` | SC |
| Spanish Copa del Rey | `esp.copa_del_rey` | CDR |
| German Cup | `ger.dfb_pokal` | DFB |
| Coppa Italia | `ita.coppa_italia` | CI |
| Leagues Cup | `concacaf.leagues.cup` | LC |
| Campeones Cup | `campeones.cup` | CC |
| SheBelieves Cup | `fifa.shebelieves` | SBC |
| UEFA Women's Champions League | `uefa.wchampions` | UWCL |
| FIFA Women's Champions Cup | `fifa.w.champions_cup` | WCC |

---

## Golf (sport: `golf`)

| Tour | Slug | Abbreviation |
|------|------|--------------|
| PGA TOUR | `pga` | PGA |
| LPGA | `lpga` | LPGA |
| DP World Tour | `eur` | DP |
| LIV Golf | `liv` | LIV |
| PGA TOUR Champions | `champions-tour` | CHAMP |
| Korn Ferry Tour | `ntw` | KFT |
| TGL | `tgl` | TGL |
| Olympic Golf (Men) | `mens-olympics-golf` | OLY |
| Olympic Golf (Women) | `womens-olympics-golf` | OLY |

---

## Racing (sport: `racing`)

| Series | Slug | Abbreviation |
|--------|------|--------------|
| Formula 1 | `f1` | F1 |
| IndyCar | `irl` | INDY |
| NASCAR Cup Series | `nascar-premier` | CUP |
| NASCAR Xfinity Series | `nascar-secondary` | XFN |
| NASCAR Truck Series | `nascar-truck` | TRUCK |

---

## Tennis (sport: `tennis`)

| Tour | Slug | Abbreviation |
|------|------|--------------|
| ATP | `atp` | ATP |
| WTA | `wta` | WTA |

---

## MMA (sport: `mma`)

ESPN tracks 25+ MMA promotions. The most commonly used:

| Promotion | Slug | Abbreviation |
|-----------|------|--------------|
| Bellator | `bellator` | BEL |
| Invicta FC | `ifc` | IFC |
| Legacy Fighting Alliance | `lfa` | LFA |
| KSW | `ksw` | KSW |
| Cage Warriors | `cage-warriors` | CW |

---

## Lacrosse (sport: `lacrosse`)

| League | Slug | Abbreviation |
|--------|------|--------------|
| Premier Lacrosse League | `pll` | PLL |
| National Lacrosse League | `nll` | NLL |
| NCAA Men's Lacrosse | `mens-college-lacrosse` | NCAML |
| NCAA Women's Lacrosse | `womens-college-lacrosse` | NCAWL |

---

## Rugby (sport: `rugby`)

Rugby uses numeric league IDs as slugs:

| League | Slug | Abbreviation |
|--------|------|--------------|
| Rugby World Cup | `164205` | RWC |
| Six Nations | `180659` | 6N |
| The Rugby Championship | `244293` | TRC |
| Super Rugby Pacific | `242041` | SRP |
| European Rugby Champions Cup | `271937` | EPCR |
| Gallagher Premiership | `267979` | PREM |
| United Rugby Championship | `270557` | URC |
| French Top 14 | `270559` | TOP14 |
| Major League Rugby | `289262` | MLR |
| British and Irish Lions Tour | `268565` | BILT |
| International Test Match | `289234` | INT |

---

## Rugby League (sport: `rugby-league`)

| League | Slug | Abbreviation |
|--------|------|--------------|
| Rugby League | `3` | RL |

---

## Australian Football (sport: `australian-football`)

| League | Slug | Abbreviation |
|--------|------|--------------|
| AFL | `afl` | AFL |

---

## Cricket (sport: `cricket`)

Cricket league slugs vary. Use the discovery endpoint to find current leagues:
```bash
curl "https://sports.core.api.espn.com/v2/sports/cricket/leagues"
```

---

## Volleyball (sport: `volleyball`)

| League | Slug | Abbreviation |
|--------|------|--------------|
| NCAA Men's Volleyball | `mens-college-volleyball` | NCAMV |
| NCAA Women's Volleyball | `womens-college-volleyball` | NCAWV |

---

## Field Hockey (sport: `field-hockey`)

| League | Slug | Abbreviation |
|--------|------|--------------|
| NCAA Women's Field Hockey | `womens-college-field-hockey` | NCAAFH |

---

## Water Polo (sport: `water-polo`)

| League | Slug | Abbreviation |
|--------|------|--------------|
| NCAA Men's Water Polo | `mens-college-water-polo` | NCAMWP |
| NCAA Women's Water Polo | `womens-college-water-polo` | NCAWWP |

---

## College Football Conference IDs

Use these with the `groups` query parameter:

| Conference | ID |
|------------|----|
| SEC | 8 |
| Big Ten | 5 |
| ACC | 1 |
| Big 12 | 4 |
| Mountain West | 17 |
| Top 25 | 80 |

---

## CDN Sport Slugs

CDN endpoints use league abbreviations, not sport categories:

| CDN Slug | Maps To |
|----------|---------|
| `nba` | Basketball / NBA |
| `nfl` | Football / NFL |
| `mlb` | Baseball / MLB |
| `nhl` | Hockey / NHL |
| `college-football` | Football / college-football |
| `mens-college-basketball` | Basketball / mens-college-basketball |
| `wnba` | Basketball / WNBA |
| `soccer` | Soccer (requires `&league=` param, e.g. `eng.1`) |
