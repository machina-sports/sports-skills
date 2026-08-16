"""Markets orchestration — connects ESPN schedules with prediction markets.

Bridges ESPN live schedules (NBA, NFL, MLB, NHL, WNBA, CFB, CBB) with
Kalshi and Polymarket prediction markets. Provides entity matching,
odds normalization, and cross-platform search.

Uses stdlib only (difflib for fuzzy matching). Network calls go through
the existing kalshi, polymarket, and sport-specific modules.
"""

from __future__ import annotations

import difflib
import logging
import re

logger = logging.getLogger("sports_skills.markets")


# ============================================================
# 2A. Sport-to-Platform Mapping Tables
# ============================================================

KALSHI_SERIES = {
    # US sports
    "nfl": "KXNFL",
    "nba": "KXNBA",
    "mlb": "KXMLB",
    "nhl": "KXNHL",
    "wnba": "KXWNBA",
    "cfb": "KXCFB",
    "cbb": "KXCBB",
    # Football
    "epl": "KXEPLGAME",
    "ucl": "KXUCL",
    "laliga": "KXLALIGA",
    "bundesliga": "KXBUNDESLIGA",
    "seriea": "KXSERIEA",
    "ligue1": "KXLIGUE1",
    "mls": "KXMLSGAME",
    # FIFA World Cup 2026 match winners. The kalshi module's KALSHI_SERIES
    # covers the full set of WC series (winner, groups, futures); this
    # single-ticker map points at the match-market series.
    "worldcup": "KXWCGAME",
}

# Maps common sport codes to Polymarket sport codes for the /sports endpoint.
# Polymarket covers far more leagues; these are the shared ones.
POLYMARKET_SPORTS = {
    # US sports (shared with ESPN)
    "nfl": "nfl",
    "nba": "nba",
    "mlb": "mlb",
    "nhl": "nhl",
    "wnba": "wnba",
    "cfb": "cfb",
    "cbb": "cbb",
    # Football
    "epl": "epl",
    "ucl": "ucl",
    "laliga": "lal",
    "bundesliga": "bun",
    "seriea": "sea",
    "ligue1": "fl1",
    "mls": "mls",
    # FIFA World Cup 2026 (Polymarket series 11433)
    "worldcup": "fifwc",
}

SCOREBOARD_SPORTS = {"nfl", "nba", "mlb", "nhl", "wnba", "cfb", "cbb"}

# Meta-sports fan out across multiple league codes when the caller wants
# "all of X" rather than a single league. The classic case is football: both
# Polymarket and Kalshi list per-league markets (EPL, UCL, …) plus tournament
# markets (FIFA World Cup, qualifiers) that aren't sport-tagged on either
# venue's API and are only reachable via keyword search. A `sport="football"`
# query against `get_sport_markets` should surface all of those at once.
META_SPORTS = {
    "football": {
        # Per-league codes that already exist in KALSHI_SERIES / POLYMARKET_SPORTS.
        "leagues": ["epl", "ucl", "laliga", "bundesliga", "seriea", "ligue1", "mls", "worldcup"],
        # Polymarket keyword fallbacks — these surface tournament markets that
        # aren't tagged with a sport code (FIFA World Cup futures, qualifiers,
        # international friendlies). "FIFA" is the discriminating keyword that
        # appears in every World-Cup market title.
        "polymarket_keywords": ["FIFA"],
    },
}

# Common aliases — accept these as synonyms for the canonical META_SPORTS key.
META_SPORT_ALIASES = {
    "soccer": "football",
}

# ESPN sport module name → SPORT_PATH mapping (for reference)
_SPORT_MODULES = {
    "nfl": "nfl",
    "nba": "nba",
    "mlb": "mlb",
    "nhl": "nhl",
    "wnba": "wnba",
    "cfb": "cfb",
    "cbb": "cbb",
}


# ============================================================
# 2B. Entity Matching (stdlib difflib.SequenceMatcher)
# ============================================================

_PUNCT_RE = re.compile(r"[^\w\s]")
_SPACE_RE = re.compile(r"\s+")

MATCH_THRESHOLD = 0.55


def _normalize_name(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    name = name.lower()
    name = _PUNCT_RE.sub("", name)
    name = _SPACE_RE.sub(" ", name).strip()
    return name


def _match_score(query: str, candidate: str) -> float:
    """0-1 similarity. Substring containment = fast path (0.85+)."""
    nq = _normalize_name(query)
    nc = _normalize_name(candidate)

    if not nq or not nc:
        return 0.0

    # Exact match
    if nq == nc:
        return 1.0

    # Substring containment — common case like "Chiefs" in "Kansas City Chiefs"
    if nq in nc or nc in nq:
        shorter = min(len(nq), len(nc))
        longer = max(len(nq), len(nc))
        return 0.85 + 0.15 * (shorter / longer)

    # SequenceMatcher for fuzzy matching
    return difflib.SequenceMatcher(None, nq, nc).ratio()


def _best_matches(query: str, candidates: list[dict], key: str, limit: int = 5) -> list[dict]:
    """Return candidates sorted by match score, filtered by threshold."""
    scored = []
    for item in candidates:
        text = item.get(key, "")
        score = _match_score(query, text)
        if score >= MATCH_THRESHOLD:
            scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limit]]


# ============================================================
# Response Helpers
# ============================================================


def _success(data, message=""):
    return {"status": True, "data": data, "message": message}


def _error(message, data=None):
    return {"status": False, "data": data, "message": message}


def _success_partial(data, warnings, message=""):
    """status=True as long as at least one source returned data. Failures go in data.warnings."""
    if warnings:
        data["warnings"] = warnings
    return {"status": True, "data": data, "message": message}


# ============================================================
# 2C. Schedule Fetching Abstraction
# ============================================================


def _load_sport_module(sport: str):
    """Lazy-import a sport module. Returns the module or None."""
    try:
        if sport == "nfl":
            from sports_skills import nfl

            return nfl
        elif sport == "nba":
            from sports_skills import nba

            return nba
        elif sport == "mlb":
            from sports_skills import mlb

            return mlb
        elif sport == "nhl":
            from sports_skills import nhl

            return nhl
        elif sport == "wnba":
            from sports_skills import wnba

            return wnba
        elif sport == "cfb":
            from sports_skills import cfb

            return cfb
        elif sport == "cbb":
            from sports_skills import cbb

            return cbb
    except ImportError:
        return None
    return None


def _extract_games(sport: str, scoreboard_data: dict) -> list[dict]:
    """Extract normalized game dicts from a scoreboard response."""
    if not scoreboard_data.get("status"):
        return []

    data = scoreboard_data.get("data", {})
    events = data.get("events", [])
    games = []

    for event in events:
        competitors = event.get("competitors", [])
        home = {}
        away = {}
        for c in competitors:
            team = c.get("team", {})
            entry = {
                "name": team.get("name", ""),
                "abbreviation": team.get("abbreviation", ""),
                "id": team.get("id", ""),
            }
            if c.get("home_away") == "home":
                home = entry
            else:
                away = entry

        espn_odds = event.get("odds", {})

        games.append(
            {
                "sport": sport,
                "event_id": event.get("id", ""),
                "name": event.get("name", ""),
                "short_name": event.get("short_name", ""),
                "start_time": event.get("start_time", ""),
                "status": event.get("status", ""),
                "status_detail": event.get("status_detail", ""),
                "home": home,
                "away": away,
                "espn_odds": espn_odds,
            }
        )

    return games


def _fetch_schedule(sport: str, date: str | None) -> list[dict]:
    """Lazy-import sport module, call get_scoreboard(date=...), extract games."""
    mod = _load_sport_module(sport)
    if mod is None:
        return []

    kwargs = {}
    if date:
        kwargs["date"] = date

    try:
        result = mod.get_scoreboard(**kwargs)
    except Exception as exc:
        logger.warning("Failed to fetch %s scoreboard: %s", sport, exc)
        return []

    return _extract_games(sport, result)


def _fetch_all_schedules(sports: list[str], date: str | None) -> tuple[list[dict], list[str]]:
    """Iterate sports, aggregate games. Returns (games, warnings)."""
    all_games = []
    warnings = []

    for sport in sports:
        if sport not in SCOREBOARD_SPORTS:
            warnings.append(f"Unknown sport '{sport}', skipping")
            continue
        try:
            games = _fetch_schedule(sport, date)
            all_games.extend(games)
        except Exception as exc:
            warnings.append(f"Failed to fetch {sport}: {exc}")

    return all_games, warnings


# ============================================================
# 2D. Cross-Platform Entity Search
# ============================================================


def _search_kalshi(entity: str, sport: str | None) -> list[dict]:
    """Use kalshi.search_markets for sport-filtered search with fuzzy matching."""
    try:
        from sports_skills import kalshi
    except ImportError:
        logger.warning("kalshi module not available")
        return []

    try:
        result = kalshi.search_markets(sport=sport, query=entity)
    except Exception as exc:
        logger.warning("Kalshi search failed: %s", exc)
        return []

    if not result.get("status"):
        return []

    data = result.get("data", {})
    markets = data.get("markets", [])
    if not isinstance(markets, list):
        markets = []

    # Group markets by event_ticker for consistent output
    events_map: dict[str, dict] = {}
    for m in markets:
        event_ticker = m.get("event_ticker", "")
        if event_ticker not in events_map:
            events_map[event_ticker] = {
                "source": "kalshi",
                "event_ticker": event_ticker,
                "title": m.get("event_title", ""),
                "status": m.get("status", ""),
                "markets": [],
            }
        events_map[event_ticker]["markets"].append(
            {
                "ticker": m.get("ticker", ""),
                "title": m.get("title", ""),
                "yes_price": m.get("yes_bid", m.get("last_price", 0)),
                "no_price": m.get("no_bid", 0),
                "volume": m.get("volume", 0),
            }
        )

    return list(events_map.values())


def _search_polymarket(entity: str, sport: str | None = None) -> list[dict]:
    """Use polymarket.search_markets with sport filtering when available."""
    try:
        from sports_skills import polymarket
    except ImportError:
        logger.warning("polymarket module not available")
        return []

    try:
        kwargs = {"query": entity, "tag_id": 1}
        # Use sport-based filtering for much better results
        if sport and sport in POLYMARKET_SPORTS:
            kwargs["sport"] = POLYMARKET_SPORTS[sport]
        result = polymarket.search_markets(**kwargs)
    except Exception as exc:
        logger.warning("Polymarket search failed: %s", exc)
        return []

    if not result.get("status"):
        return []

    data = result.get("data", {})
    markets = data.get("markets", [])
    if not isinstance(markets, list):
        markets = []

    results = []
    for market in markets:
        # Outcomes come from the normalized market structure
        outcomes = []
        for o in market.get("outcomes", []):
            outcomes.append(
                {
                    "token_id": o.get("clob_token_id", ""),
                    "outcome": o.get("name", ""),
                    "price": o.get("price", 0),
                }
            )

        results.append(
            {
                "source": "polymarket",
                "market_id": market.get("id", ""),
                "title": market.get("question", ""),
                "slug": market.get("slug", ""),
                "volume": market.get("volume", 0),
                "sports_market_type": market.get("sports_market_type", ""),
                "outcomes": outcomes,
            }
        )

    return results


def _prophetx_outcome_odds(outcome: dict) -> dict | None:
    """Extract top-of-book American odds from a normalized ProphetX outcome.

    Selections are optional on the public surface (empty/suspended books come
    back null); when present they are a dict or a list of price levels.
    """
    selection = outcome.get("selections")
    if isinstance(selection, list):
        selection = selection[0] if selection else None
    for candidate in (selection, outcome):
        if isinstance(candidate, dict) and candidate.get("odds_american") is not None:
            raw = candidate.get("_raw") or {}
            label = outcome.get("name") or raw.get("displayName") or raw.get("name") or ""
            return {
                "outcome": label,
                "odds_american": candidate.get("odds_american"),
                "implied_probability": candidate.get("implied_probability"),
            }
    return None


def _search_prophetx(entity: str, sport: str | None = None) -> list[dict]:
    """Use prophetx.search_markets for exchange market discovery.

    ProphetX's public API always exposes market structure (markets/lines/
    outcomes plus totalStake); odds appear per market only when a public order
    book exists (``selections_available``) — empty/suspended books carry no
    prices. Top-of-book odds are surfaced per outcome when available.
    """
    try:
        from sports_skills import prophetx
    except ImportError:
        logger.warning("prophetx module not available")
        return []

    try:
        kwargs = {"query": entity}
        if sport:
            kwargs["sport"] = sport
        result = prophetx.search_markets(**kwargs)
    except Exception as exc:
        logger.warning("ProphetX search failed: %s", exc)
        return []

    if not result.get("status"):
        return []

    data = result.get("data", {})
    markets = data.get("markets", [])
    if not isinstance(markets, list):
        return []

    events_map: dict[str, dict] = {}
    for m in markets:
        event_id = m.get("event_id")
        if event_id not in events_map:
            events_map[event_id] = {
                "source": "prophetx",
                "event_id": event_id,
                "title": m.get("event_name", ""),
                "scheduled": m.get("event_scheduled", ""),
                "tournament": m.get("tournament", ""),
                "markets": [],
            }
        outcomes = []
        if m.get("selections_available"):
            for outcome in m.get("outcomes", []) or []:
                odds = _prophetx_outcome_odds(outcome)
                if odds:
                    outcomes.append(odds)
        events_map[event_id]["markets"].append(
            {
                "market_key": m.get("market_key", ""),
                "title": m.get("name", ""),
                "type": m.get("type", ""),
                "total_stake": m.get("total_stake", 0),
                "selections_available": m.get("selections_available", False),
                "outcomes": outcomes,
            }
        )

    results = list(events_map.values())
    for event in results:
        if not any(m["selections_available"] for m in event["markets"]):
            event["note"] = (
                "no public order book currently exposed for this event's "
                "markets — structure/stake only (odds require an open book "
                "or the authenticated Affiliate API)"
            )
    return results


# ============================================================
# 2E. Odds Normalization
# ============================================================


def _normalize_price(price: float, source: str) -> dict:
    """Convert any source format to {implied_probability, american, decimal}.

    source="polymarket": price is 0-1, use betting.convert_odds(from_format="probability")
    source="kalshi":     price is 0-100 int, divide by 100 then convert
    source="espn":       price is American odds, use betting.convert_odds(from_format="american")
    source="prophetx":   price is American odds (exchange odds — from public
                         selections when an order book is exposed, or from the
                         authenticated Affiliate surface)
    """
    from sports_skills.betting._calcs import convert_odds

    if source == "polymarket":
        if price <= 0 or price >= 1:
            return {"implied_probability": price, "american": 0.0, "decimal": 0.0, "source": source}
        result = convert_odds({"params": {"odds": price, "from_format": "probability"}})
    elif source == "kalshi":
        prob = price / 100.0 if price > 1 else price
        if prob <= 0 or prob >= 1:
            return {"implied_probability": prob, "american": 0.0, "decimal": 0.0, "source": source}
        result = convert_odds({"params": {"odds": prob, "from_format": "probability"}})
    elif source in ("espn", "prophetx"):
        result = convert_odds({"params": {"odds": price, "from_format": "american"}})
    else:
        return {"implied_probability": 0.0, "american": 0.0, "decimal": 0.0, "source": source}

    if not result.get("status"):
        return {"implied_probability": 0.0, "american": 0.0, "decimal": 0.0, "source": source}

    data = result["data"]
    return {
        "implied_probability": data.get("implied_probability", 0.0),
        "american": data.get("american", 0.0),
        "decimal": data.get("decimal", 0.0),
        "source": source,
    }


# ============================================================
# Schedule + Market Orchestration
# ============================================================


def get_todays_markets(request_data: dict) -> dict:
    """Fetch ESPN schedule, search both exchanges, return unified dashboard.

    Params:
        sport (str): Sport key (nba, nfl, etc.). Omit for all sports.
        date (str): Date in YYYY-MM-DD format. Defaults to today.
    """
    params = request_data.get("params", {})
    sport = params.get("sport")
    date = params.get("date")

    if sport:
        sport = str(sport).lower()
        if sport not in SCOREBOARD_SPORTS:
            return _error(f"Unknown sport '{sport}'. Available: {', '.join(sorted(SCOREBOARD_SPORTS))}")
        sports = [sport]
    else:
        sports = sorted(SCOREBOARD_SPORTS)

    games, warnings = _fetch_all_schedules(sports, date)

    if not games:
        return _success_partial(
            {"games": [], "count": 0, "markets_searched": False},
            warnings,
            "No games found for the selected sport(s) and date.",
        )

    # Search prediction markets for each game
    dashboard = []
    for game in games:
        home_name = game["home"].get("name", "")
        away_name = game["away"].get("name", "")
        search_query = f"{away_name} {home_name}" if away_name and home_name else game.get("name", "")

        kalshi_matches = []
        poly_matches = []
        prophetx_matches = []

        try:
            kalshi_matches = _search_kalshi(search_query, game["sport"])
        except Exception as exc:
            warnings.append(f"Kalshi search failed for '{search_query}': {exc}")

        try:
            poly_matches = _search_polymarket(search_query, game["sport"])
        except Exception as exc:
            warnings.append(f"Polymarket search failed for '{search_query}': {exc}")

        try:
            prophetx_matches = _search_prophetx(search_query, game["sport"])
        except Exception as exc:
            warnings.append(f"ProphetX search failed for '{search_query}': {exc}")

        game_entry = {
            **game,
            "kalshi_markets": kalshi_matches,
            "polymarket_markets": poly_matches,
            "prophetx_markets": prophetx_matches,
        }
        dashboard.append(game_entry)

    return _success_partial(
        {
            "games": dashboard,
            "count": len(dashboard),
            "markets_searched": True,
        },
        warnings,
        f"Found {len(dashboard)} game(s) with market data.",
    )


def search_entity(request_data: dict) -> dict:
    """Search Kalshi + Polymarket for a team/player/event name.

    Params:
        query (str): Search query (team name, player name, etc.).
        sport (str): Optional sport key to scope Kalshi search.
    """
    params = request_data.get("params", {})
    query = params.get("query", "")
    sport = params.get("sport")

    if not query:
        return _error("query is required")

    if sport:
        sport = str(sport).lower()

    kalshi_results = []
    poly_results = []
    prophetx_results = []
    warnings = []

    try:
        kalshi_results = _search_kalshi(query, sport)
    except Exception as exc:
        warnings.append(f"Kalshi search failed: {exc}")

    try:
        poly_results = _search_polymarket(query, sport)
    except Exception as exc:
        warnings.append(f"Polymarket search failed: {exc}")

    try:
        prophetx_results = _search_prophetx(query, sport)
    except Exception as exc:
        warnings.append(f"ProphetX search failed: {exc}")

    total = len(kalshi_results) + len(poly_results) + len(prophetx_results)

    return _success_partial(
        {
            "query": query,
            "sport": sport,
            "kalshi": kalshi_results,
            "polymarket": poly_results,
            "prophetx": prophetx_results,
            "total_results": total,
        },
        warnings,
        f"Found {total} market(s) matching '{query}'.",
    )


def compare_odds(request_data: dict) -> dict:
    """ESPN odds + prediction market prices, normalized side-by-side + arb check.

    Params:
        sport (str): Sport key (nba, nfl, etc.).
        event_id (str): ESPN event ID.
    """
    params = request_data.get("params", {})
    sport = str(params.get("sport") or "").lower()
    event_id = params.get("event_id", "")

    if not sport:
        return _error("sport is required")
    if not event_id:
        return _error("event_id is required")
    if sport not in SCOREBOARD_SPORTS:
        return _error(f"Unknown sport '{sport}'. Available: {', '.join(sorted(SCOREBOARD_SPORTS))}")

    # Fetch ESPN game summary
    mod = _load_sport_module(sport)
    if mod is None:
        return _error(f"Could not load module for sport '{sport}'")

    try:
        summary = mod.get_game_summary(event_id=event_id)
    except Exception as exc:
        return _error(f"Failed to fetch game summary: {exc}")

    if not summary.get("status"):
        return _error(f"ESPN returned error: {summary.get('message', 'unknown')}")

    summary_data = summary.get("data", {})

    # Extract competitors and odds
    competitors = summary_data.get("competitors", [])
    odds = summary_data.get("odds", {})

    home_team = ""
    away_team = ""
    for c in competitors:
        team = c.get("team", {})
        if c.get("home_away") == "home":
            home_team = team.get("name", "")
        else:
            away_team = team.get("name", "")

    search_query = f"{away_team} {home_team}" if away_team and home_team else ""

    # Normalize ESPN odds
    espn_home_odds = odds.get("home_odds")
    espn_away_odds = odds.get("away_odds")
    espn_comparison = {}

    if espn_home_odds is not None:
        espn_comparison["home"] = _normalize_price(float(espn_home_odds), "espn")
        espn_comparison["home"]["team"] = home_team
    if espn_away_odds is not None:
        espn_comparison["away"] = _normalize_price(float(espn_away_odds), "espn")
        espn_comparison["away"]["team"] = away_team

    # Search prediction markets
    warnings = []
    kalshi_matches = []
    poly_matches = []
    prophetx_matches = []

    if search_query:
        try:
            kalshi_matches = _search_kalshi(search_query, sport)
        except Exception as exc:
            warnings.append(f"Kalshi search failed: {exc}")

        try:
            poly_matches = _search_polymarket(search_query, sport)
        except Exception as exc:
            warnings.append(f"Polymarket search failed: {exc}")

        try:
            prophetx_matches = _search_prophetx(search_query, sport)
        except Exception as exc:
            warnings.append(f"ProphetX search failed: {exc}")

    # Check for arbitrage if we have matching market prices
    arb_check = None
    all_probs = []
    all_labels = []

    if espn_comparison.get("home") and espn_comparison["home"]["implied_probability"] > 0:
        all_probs.append(espn_comparison["home"]["implied_probability"])
        all_labels.append(f"espn_{home_team}")

    if espn_comparison.get("away") and espn_comparison["away"]["implied_probability"] > 0:
        all_probs.append(espn_comparison["away"]["implied_probability"])
        all_labels.append(f"espn_{away_team}")

    # Add best market prices for arb check
    for pm in poly_matches:
        for outcome in pm.get("outcomes", []):
            price = outcome.get("price", 0)
            if 0 < price < 1:
                all_probs.append(price)
                all_labels.append(f"poly_{outcome.get('outcome', '')}")

    # ProphetX exposes odds only when a public order book exists; moneyline
    # markets keep this comparison apples-to-apples with the ESPN home/away odds.
    for px in prophetx_matches:
        for market in px.get("markets", []):
            if market.get("type") != "moneyline":
                continue
            for outcome in market.get("outcomes", []):
                prob = outcome.get("implied_probability") or 0
                if 0 < prob < 1:
                    all_probs.append(prob)
                    all_labels.append(f"prophetx_{outcome.get('outcome', '')}")

    if len(all_probs) >= 2:
        try:
            from sports_skills.betting._calcs import find_arbitrage

            arb_result = find_arbitrage(
                {
                    "params": {
                        "market_probs": all_probs,
                        "labels": all_labels,
                    }
                }
            )
            if arb_result.get("status"):
                arb_check = arb_result["data"]
        except Exception as exc:
            warnings.append(f"Arbitrage check failed: {exc}")

    return _success_partial(
        {
            "sport": sport,
            "event_id": event_id,
            "home_team": home_team,
            "away_team": away_team,
            "espn_odds": espn_comparison,
            "kalshi_markets": kalshi_matches,
            "polymarket_markets": poly_matches,
            "prophetx_markets": prophetx_matches,
            "arbitrage_check": arb_check,
        },
        warnings,
        f"Odds comparison for {away_team} @ {home_team}.",
    )


def _get_meta_sport_markets(sport: str, status: str, limit: int) -> dict:
    """Fan-out aggregator for sports that span multiple leagues + tournaments.

    A single-league lookup (`sport="epl"`) hits one Kalshi series and one
    Polymarket sport code. A meta-sport lookup (`sport="football"`) unions:
      - every per-league code in ``META_SPORTS[sport]["leagues"]``
      - every keyword in ``META_SPORTS[sport]["polymarket_keywords"]`` —
        used to surface tournament markets that aren't sport-tagged on the
        Polymarket /sports endpoint (FIFA World Cup futures, qualifiers).

    Polymarket markets are deduplicated by ``id`` (the raw key in
    Polymarket payloads; older code paths also surface it as ``market_id``,
    so both are checked) so the FIFA keyword pass doesn't double-list
    anything already returned by the per-league lookups. Each leaf call is
    capped at ``limit`` and the final union is trimmed to ``limit`` to keep
    the response bounded.
    """
    spec = META_SPORTS[sport]
    warnings: list[str] = []
    kalshi_markets: list = []
    poly_markets: list = []
    seen_poly_ids: set = set()

    for league in spec.get("leagues", []):
        if league in KALSHI_SERIES:
            try:
                from sports_skills import kalshi

                result = kalshi.get_markets(
                    series_ticker=KALSHI_SERIES[league],
                    status=status,
                    limit=limit,
                )
                if result.get("status"):
                    items = result.get("data", {}).get("markets", []) or []
                    if isinstance(items, list):
                        kalshi_markets.extend(items)
            except Exception as exc:
                warnings.append(f"Kalshi {league} fetch failed: {exc}")

        if league in POLYMARKET_SPORTS:
            try:
                from sports_skills import polymarket

                result = polymarket.search_markets(
                    sport=POLYMARKET_SPORTS[league],
                    limit=limit,
                )
                if result.get("status"):
                    items = result.get("data", {}).get("markets", []) or []
                    if isinstance(items, list):
                        for m in items:
                            mid = m.get("id") or m.get("market_id")
                            if mid and mid not in seen_poly_ids:
                                seen_poly_ids.add(mid)
                                poly_markets.append(m)
            except Exception as exc:
                warnings.append(f"Polymarket {league} fetch failed: {exc}")

    for keyword in spec.get("polymarket_keywords", []):
        try:
            from sports_skills import polymarket

            result = polymarket.search_markets(query=keyword, limit=limit)
            if result.get("status"):
                items = result.get("data", {}).get("markets", []) or []
                if isinstance(items, list):
                    for m in items:
                        mid = m.get("id") or m.get("market_id")
                        if mid and mid not in seen_poly_ids:
                            seen_poly_ids.add(mid)
                            poly_markets.append(m)
        except Exception as exc:
            warnings.append(f"Polymarket keyword '{keyword}' fetch failed: {exc}")

    kalshi_markets = kalshi_markets[:limit]
    poly_markets = poly_markets[:limit]

    return _success_partial(
        {
            "sport": sport,
            "kalshi": kalshi_markets,
            "polymarket": poly_markets,
            "kalshi_count": len(kalshi_markets),
            "polymarket_count": len(poly_markets),
        },
        warnings,
        f"Found {len(kalshi_markets)} Kalshi + {len(poly_markets)} Polymarket market(s) for {sport}.",
    )


def get_sport_markets(request_data: dict) -> dict:
    """Sports-filtered market listing on both platforms.

    Params:
        sport (str): Sport key (nba, nfl, etc.). Also accepts meta-sport
            keys like "football" (alias: "soccer") that fan out across
            multiple league codes — see META_SPORTS.
        status (str): Market status filter (default: "open").
        limit (int): Max results per platform (default: 20).
    """
    params = request_data.get("params", {})
    sport = str(params.get("sport") or "").lower()
    status = params.get("status", "open")
    limit = int(params.get("limit", 20))

    if not sport:
        return _error("sport is required")

    # Resolve aliases (e.g. "soccer" → "football") before any lookup.
    sport = META_SPORT_ALIASES.get(sport, sport)

    # Meta-sport: union of per-league lookups + tournament keyword searches.
    if sport in META_SPORTS:
        return _get_meta_sport_markets(sport, status, limit)

    warnings = []
    kalshi_markets = []
    poly_markets = []

    # Kalshi: filter by series_ticker
    if sport in KALSHI_SERIES:
        try:
            from sports_skills import kalshi

            result = kalshi.get_markets(
                series_ticker=KALSHI_SERIES[sport],
                status=status,
                limit=limit,
            )
            if result.get("status"):
                kalshi_markets = result.get("data", {}).get("markets", [])
                if not isinstance(kalshi_markets, list):
                    kalshi_markets = []
        except Exception as exc:
            warnings.append(f"Kalshi fetch failed: {exc}")

    # Polymarket: filter by sport code via series_id
    if sport in POLYMARKET_SPORTS:
        try:
            from sports_skills import polymarket

            result = polymarket.search_markets(sport=POLYMARKET_SPORTS[sport], limit=limit)
            if result.get("status"):
                poly_markets = result.get("data", {}).get("markets", [])
                if not isinstance(poly_markets, list):
                    poly_markets = []
        except Exception as exc:
            warnings.append(f"Polymarket fetch failed: {exc}")

    return _success_partial(
        {
            "sport": sport,
            "kalshi": kalshi_markets,
            "polymarket": poly_markets,
            "kalshi_count": len(kalshi_markets),
            "polymarket_count": len(poly_markets),
        },
        warnings,
        f"Found {len(kalshi_markets)} Kalshi + {len(poly_markets)} Polymarket market(s) for {sport}.",
    )


def get_sport_schedule(request_data: dict) -> dict:
    """Unified ESPN schedule across one or all sports.

    Params:
        sport (str): Sport key. Omit for all sports.
        date (str): Date in YYYY-MM-DD format. Defaults to today.
    """
    params = request_data.get("params", {})
    sport = params.get("sport")
    date = params.get("date")

    if sport:
        sport = sport.lower()
        if sport not in SCOREBOARD_SPORTS:
            return _error(f"Unknown sport '{sport}'. Available: {', '.join(sorted(SCOREBOARD_SPORTS))}")
        sports = [sport]
    else:
        sports = sorted(SCOREBOARD_SPORTS)

    games, warnings = _fetch_all_schedules(sports, date)

    return _success_partial(
        {
            "games": games,
            "count": len(games),
        },
        warnings,
        f"Found {len(games)} game(s).",
    )


def normalize_price(request_data: dict) -> dict:
    """Convert any source format to common {implied_prob, american, decimal}.

    Params:
        price (float): The price/odds value.
        source (str): Source platform — "polymarket", "kalshi", "espn", or
            "prophetx" (American odds, from public selections when an order
            book is exposed or from the authenticated Affiliate surface).
    """
    params = request_data.get("params", {})

    try:
        price = float(params.get("price", 0))
    except (TypeError, ValueError) as e:
        return _error(f"Invalid price: {e}")

    source = str(params.get("source", "")).lower()
    if source not in ("polymarket", "kalshi", "espn", "prophetx"):
        return _error(f"Unknown source '{source}'. Use 'polymarket', 'kalshi', 'espn', or 'prophetx'.")

    result = _normalize_price(price, source)
    return _success(result, f"Normalized {source} price {price}")


def evaluate_market(request_data: dict) -> dict:
    """All-in-one: ESPN odds + market price, devig, edge, Kelly.

    Pipes to betting.evaluate_bet for the computation.

    Params:
        sport (str): Sport key (nba, nfl, etc.).
        event_id (str): ESPN event ID.
        token_id (str): Polymarket token ID (optional).
        kalshi_ticker (str): Kalshi market ticker (optional).
        outcome (int): Which outcome to evaluate (0=home, 1=away, default: 0).
    """
    params = request_data.get("params", {})
    sport = str(params.get("sport") or "").lower()
    event_id = params.get("event_id", "")
    token_id = params.get("token_id")
    kalshi_ticker = params.get("kalshi_ticker")
    outcome = int(params.get("outcome", 0))

    if not sport:
        return _error("sport is required")
    if not event_id:
        return _error("event_id is required")
    if sport not in SCOREBOARD_SPORTS:
        return _error(f"Unknown sport '{sport}'. Available: {', '.join(sorted(SCOREBOARD_SPORTS))}")

    # Fetch ESPN game summary for odds
    mod = _load_sport_module(sport)
    if mod is None:
        return _error(f"Could not load module for sport '{sport}'")

    try:
        summary = mod.get_game_summary(event_id=event_id)
    except Exception as exc:
        return _error(f"Failed to fetch game summary: {exc}")

    if not summary.get("status"):
        return _error(f"ESPN returned error: {summary.get('message', 'unknown')}")

    summary_data = summary.get("data", {})
    odds = summary_data.get("odds", {})
    competitors = summary_data.get("competitors", [])

    # Extract ESPN American odds
    home_odds = odds.get("home_odds")
    away_odds = odds.get("away_odds")

    if home_odds is None or away_odds is None:
        return _error("ESPN odds not available for this event")

    book_odds_str = f"{home_odds},{away_odds}"

    # Get market probability from prediction market
    market_prob = None
    market_source = None
    warnings = []

    if token_id:
        try:
            from sports_skills import polymarket

            price_result = polymarket.get_market_prices(token_id=token_id)
            if price_result.get("status"):
                price_data = price_result.get("data", {})
                market_prob = float(price_data.get("price", 0))
                market_source = "polymarket"
        except Exception as exc:
            warnings.append(f"Polymarket price fetch failed: {exc}")

    if market_prob is None and kalshi_ticker:
        try:
            from sports_skills import kalshi
            from sports_skills.kalshi._connector import _price_cents

            market_result = kalshi.get_market(ticker=kalshi_ticker)
            if market_result.get("status"):
                market_data = market_result.get("data", {})
                # Kalshi raw payloads migrated to *_dollars string fields;
                # _price_cents reads either form and returns 0-100 cents.
                # Leave market_prob as None on a zero/missing price so the
                # search fallback below still runs.
                yes_price = _price_cents(market_data, "yes_bid") or _price_cents(market_data, "last_price")
                if yes_price:
                    market_prob = float(yes_price) / 100.0
                    market_source = "kalshi"
        except Exception as exc:
            warnings.append(f"Kalshi price fetch failed: {exc}")

    if market_prob is None:
        # Try to find market via search
        home_team = ""
        away_team = ""
        for c in competitors:
            team = c.get("team", {})
            if c.get("home_away") == "home":
                home_team = team.get("name", "")
            else:
                away_team = team.get("name", "")

        search_query = f"{away_team} {home_team}" if away_team and home_team else ""

        if search_query:
            poly_matches = []
            try:
                poly_matches = _search_polymarket(search_query, sport)
            except Exception as exc:
                warnings.append(f"Polymarket search failed: {exc}")

            for pm in poly_matches:
                for oc in pm.get("outcomes", []):
                    price = oc.get("price", 0)
                    if 0 < price < 1:
                        market_prob = price
                        market_source = "polymarket"
                        break
                if market_prob is not None:
                    break

    if market_prob is None or not (0 < market_prob < 1):
        return _success_partial(
            {
                "espn_odds": {"home": home_odds, "away": away_odds},
                "market_prob": None,
                "evaluation": None,
            },
            warnings,
            "Could not find a matching prediction market price to evaluate against.",
        )

    # Use betting.evaluate_bet for the computation
    from sports_skills.betting._calcs import evaluate_bet

    eval_result = evaluate_bet(
        {
            "params": {
                "book_odds": book_odds_str,
                "market_prob": market_prob,
                "book_format": "american",
                "outcome": outcome,
            }
        }
    )

    return _success_partial(
        {
            "espn_odds": {"home": home_odds, "away": away_odds},
            "market_prob": market_prob,
            "market_source": market_source,
            "evaluation": eval_result.get("data") if eval_result.get("status") else None,
        },
        warnings,
        eval_result.get("message", ""),
    )


# ============================================================
# 2E. Cross-Venue Game Matching & Unified Prices
# ============================================================

# Kalshi single-game event tickers encode the matchup deterministically:
#   KXMLBGAME-26JUN062210NYMSD   -> 2026-06-06, 22:10, NYM @ SD
#   KXWCGAME-26JUN27JORARG       -> 2026-06-27, JOR vs ARG (no time part)
# The trailing letters are both team codes concatenated; they are compared
# as one blob against the Polymarket slug's joined team parts, so no
# per-league team table is needed.
_KALSHI_GAME_RE = re.compile(r"^KX[A-Z0-9]*GAME-(\d{2})([A-Z]{3})(\d{2})(?:\d{4})?([A-Z]+)$")

# Polymarket single-game slugs: {league}-{away}-{home}-{YYYY-MM-DD}[-suffix]
_POLY_GAME_RE = re.compile(r"^[a-z0-9]+-([a-z0-9]+)-([a-z0-9]+)-(\d{4}-\d{2}-\d{2})(?:-|$)")

_TICKER_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

_VS_RE = re.compile(r"\s+vs\.?\s+", re.IGNORECASE)


def _parse_kalshi_game_event(event_ticker: str) -> tuple[str, str] | None:
    """Parse a Kalshi game event ticker -> (date 'YYYY-MM-DD', team_concat)."""
    m = _KALSHI_GAME_RE.match(event_ticker or "")
    if not m:
        return None
    yy, mon, dd, teams = m.groups()
    month = _TICKER_MONTHS.get(mon)
    if not month:
        return None
    return f"20{yy}-{month:02d}-{int(dd):02d}", teams


def _parse_poly_game_slug(slug: str) -> tuple[str, str, str] | None:
    """Parse a Polymarket game slug -> (date 'YYYY-MM-DD', away, home)."""
    m = _POLY_GAME_RE.match(slug or "")
    if not m:
        return None
    away, home, date = m.groups()
    return date, away, home


def _split_matchup_title(title: str) -> tuple[str, str] | None:
    """'Milwaukee vs Colorado' / 'Brazil vs. Morocco' -> (side1, side2)."""
    parts = _VS_RE.split(title or "")
    if len(parts) != 2:
        return None
    a, b = parts[0].strip(), parts[1].strip()
    if not a or not b:
        return None
    return a, b


def _titles_match(kalshi_title: str, poly_title: str) -> bool:
    """Fuzzy team-by-team comparison of two 'X vs Y' titles.

    Sides may be listed in opposite order across venues, so both
    orientations are scored and the better one must clear the threshold
    on BOTH legs.
    """
    k = _split_matchup_title(kalshi_title)
    p = _split_matchup_title(poly_title)
    if not k or not p:
        return False
    straight = min(_match_score(k[0], p[0]), _match_score(k[1], p[1]))
    crossed = min(_match_score(k[0], p[1]), _match_score(k[1], p[0]))
    return max(straight, crossed) >= MATCH_THRESHOLD


def _poly_moneyline_markets(event: dict) -> list[dict]:
    """Moneyline markets from a Polymarket event.

    US-league games carry one moneyline market with team-named outcomes;
    soccer games carry several binary ones (home win / away win / draw).
    Returns an empty list when the event has no moneyline markets.
    """
    return [m for m in (event.get("markets") or []) if m.get("sports_market_type") == "moneyline"]


def match_markets(request_data: dict) -> dict:
    """Pair the same game across Kalshi and Polymarket.

    Single-game markets encode {date, away, home} deterministically in
    Kalshi event tickers and Polymarket slugs, so games are joined on
    date + concatenated team codes — with fuzzy title matching as a
    fallback for leagues where the two venues use different team code
    conventions.

    Params:
        sport (str): League code present on both venues (e.g. 'mlb',
            'nfl', 'nba', 'nhl', 'epl', 'worldcup').
        date (str): Optional YYYY-MM-DD filter. Omit for all upcoming.
    """
    params = request_data.get("params", {})
    sport = str(params.get("sport") or "").lower()
    date_filter = params.get("date")

    if not sport:
        return _error("sport is required")
    if sport not in KALSHI_SERIES or sport not in POLYMARKET_SPORTS:
        both = sorted(set(KALSHI_SERIES) & set(POLYMARKET_SPORTS))
        return _error(f"Sport '{sport}' is not available on both venues. Available: {', '.join(both)}")

    warnings: list[str] = []

    # --- Kalshi game events ---
    kalshi_events = []
    try:
        from sports_skills import kalshi

        result = kalshi.get_todays_events(sport=sport, limit=200)
        if result.get("status"):
            kalshi_events = result.get("data", {}).get("events", []) or []
        else:
            warnings.append(f"Kalshi fetch failed: {result.get('message', '')}")
    except Exception as exc:
        warnings.append(f"Kalshi fetch failed: {exc}")

    kalshi_games = []
    for ev in kalshi_events:
        parsed = _parse_kalshi_game_event(ev.get("event_ticker", ""))
        if not parsed:
            continue  # winner/futures/props series — not single games
        date, concat = parsed
        if date_filter and date != date_filter:
            continue
        kalshi_games.append({"event": ev, "date": date, "concat": concat.lower()})

    # --- Polymarket game events ---
    poly_events = []
    try:
        from sports_skills import polymarket

        result = polymarket.get_todays_events(sport=POLYMARKET_SPORTS[sport], limit=100)
        if result.get("status"):
            poly_events = result.get("data", {}).get("events", []) or []
        else:
            warnings.append(f"Polymarket fetch failed: {result.get('message', '')}")
    except Exception as exc:
        warnings.append(f"Polymarket fetch failed: {exc}")

    poly_games: dict[tuple[str, str], dict] = {}
    for ev in poly_events:
        parsed = _parse_poly_game_slug(ev.get("slug", ""))
        if not parsed:
            continue
        date, away, home = parsed
        if date_filter and date != date_filter:
            continue
        key = (date, f"{away}{home}")
        # Slug variants ("-more-markets", props) parse to the same key;
        # prefer the event that carries moneyline markets.
        current = poly_games.get(key)
        if current is None or (_poly_moneyline_markets(ev) and not _poly_moneyline_markets(current)):
            poly_games[key] = ev

    matches = []
    matched_poly_keys = set()
    unmatched_kalshi = []

    for kg in kalshi_games:
        ev = kg["event"]
        # Tier 1: deterministic code join — kalshi team concat equals the
        # polymarket slug's away+home joined, same date.
        key = (kg["date"], kg["concat"])
        poly_ev = poly_games.get(key)
        method = "code"

        # Tier 2: fuzzy title match within the same date.
        if poly_ev is None:
            for pkey, pev in poly_games.items():
                if pkey[0] != kg["date"] or pkey in matched_poly_keys:
                    continue
                if _titles_match(ev.get("title", ""), pev.get("title", "")):
                    poly_ev = pev
                    key = pkey
                    method = "title"
                    break

        if poly_ev is None:
            unmatched_kalshi.append(ev.get("event_ticker", ""))
            continue

        matched_poly_keys.add(key)
        moneylines = _poly_moneyline_markets(poly_ev)

        # Variant events (exact-score, halftime, ...) can crowd the
        # canonical game event out of the listing window. If the matched
        # event has no moneyline, look up the canonical slug directly.
        if not moneylines:
            canonical = re.match(r"^(.*?\d{4}-\d{2}-\d{2})", poly_ev.get("slug", ""))
            if canonical and canonical.group(1) != poly_ev.get("slug"):
                try:
                    from sports_skills import polymarket

                    detail = polymarket.get_event_details(slug=canonical.group(1))
                    if detail.get("status"):
                        candidate = detail.get("data", {})
                        candidate_mls = _poly_moneyline_markets(candidate)
                        if candidate_mls:
                            poly_ev, moneylines = candidate, candidate_mls
                except Exception as exc:
                    warnings.append(f"Canonical event lookup failed for {canonical.group(1)}: {exc}")

        matches.append(
            {
                "date": kg["date"],
                "title": poly_ev.get("title") or ev.get("title", ""),
                "match_method": method,
                "kalshi": {
                    "event_ticker": ev.get("event_ticker", ""),
                    "title": ev.get("title", ""),
                    "market_tickers": [m.get("ticker", "") for m in (ev.get("markets") or [])],
                },
                "polymarket": {
                    "slug": poly_ev.get("slug", ""),
                    "event_id": poly_ev.get("id"),
                    "title": poly_ev.get("title", ""),
                    "markets": [
                        {
                            "question": m.get("question", ""),
                            "token_ids": m.get("clob_token_ids") or [],
                            "outcomes": m.get("outcomes") or [],
                        }
                        for m in moneylines
                    ],
                },
            }
        )

    unmatched_poly = [ev.get("slug", "") for key, ev in poly_games.items() if key not in matched_poly_keys]

    return _success_partial(
        {
            "sport": sport,
            "date": date_filter,
            "matches": matches,
            "match_count": len(matches),
            "unmatched": {
                "kalshi": unmatched_kalshi,
                "polymarket": unmatched_poly,
            },
        },
        warnings,
        f"Matched {len(matches)} game(s) across venues for {sport}.",
    )


def _parse_at_time(value) -> int | None:
    """Accept a Unix timestamp (int / numeric str) or ISO 8601 string."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    if s.isdigit():
        return int(s)
    from datetime import datetime, timezone

    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _candle_close(candle: dict) -> float | None:
    """Yes price (0-1) from a Kalshi candlestick's close."""
    price = candle.get("price") or {}
    raw = price.get("close_dollars")
    if raw not in (None, ""):
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None
    legacy = price.get("close")
    if legacy not in (None, ""):
        try:
            return float(legacy) / 100.0
        except (TypeError, ValueError):
            return None
    return None


def _price_pair(yes_price: float, at_time: int) -> dict:
    """Both sides of a binary market from the yes price."""
    yes = round(float(yes_price), 4)
    return {
        "yes": {"price": yes, "at_time": at_time},
        "no": {"price": round(1.0 - yes, 4), "at_time": at_time},
    }


def _kalshi_price_at(ticker: str, at_time: int) -> tuple[float, int] | None:
    """Yes price (0-1) as of a timestamp, from Kalshi candlesticks.

    Tries hourly candles over the prior week, then daily over the prior
    31 days. Returns (price, candle_end_ts) or None.
    """
    from sports_skills import kalshi

    series_ticker = ticker.split("-", 1)[0]
    for period, lookback in ((60, 7 * 86400), (1440, 31 * 86400)):
        result = kalshi.get_market_candlesticks(
            series_ticker=series_ticker,
            ticker=ticker,
            start_ts=at_time - lookback,
            end_ts=at_time,
            period_interval=period,
        )
        if not result.get("status"):
            continue
        candles = result.get("data", {}).get("candlesticks", []) or []
        candles = [c for c in candles if c.get("end_period_ts")]
        candles.sort(key=lambda c: c["end_period_ts"])
        for candle in reversed(candles):
            price = _candle_close(candle)
            if price is not None:
                return price, int(candle["end_period_ts"])
    return None


def get_market_price(request_data: dict) -> dict:
    """Current or point-in-time price for a market on either venue.

    Returns both sides of the binary market as 0-1 probabilities in a
    single shape regardless of venue.

    Params:
        venue (str): 'kalshi' or 'polymarket'.
        ticker (str): Kalshi market ticker (required for kalshi).
        token_id (str): Polymarket CLOB token ID (required for polymarket).
        at_time: Optional Unix timestamp or ISO 8601 datetime for a
            historical price. Omit for the live price.
    """
    import time as _time

    params = request_data.get("params", {})
    venue = str(params.get("venue") or "").lower()
    ticker = params.get("ticker", "")
    token_id = params.get("token_id", "")

    if venue not in ("kalshi", "polymarket"):
        return _error("venue must be 'kalshi' or 'polymarket'")
    try:
        at_time = _parse_at_time(params.get("at_time"))
    except ValueError:
        return _error(
            "at_time must be a Unix timestamp or ISO 8601 datetime (e.g. 1780500000 or '2026-06-01T12:00:00+00:00')"
        )

    if venue == "kalshi":
        if not ticker:
            return _error("ticker is required for venue 'kalshi'")
        identifier = ticker

        if at_time is not None:
            found = _kalshi_price_at(ticker, at_time)
            if found is None:
                return _error(f"No Kalshi price found for {ticker} at or before {at_time} (searched 31 days back)")
            yes_price, ts = found
            source = "candlestick"
        else:
            from sports_skills import kalshi
            from sports_skills.kalshi._connector import _price_cents

            result = kalshi.get_market(ticker=ticker)
            if not result.get("status"):
                return _error(f"Kalshi market fetch failed: {result.get('message', '')}")
            market = result.get("data", {})
            cents = _price_cents(market, "last_price") or _price_cents(market, "yes_bid")
            if not cents:
                return _error(f"No price available for Kalshi market {ticker}")
            yes_price, ts = cents / 100.0, int(_time.time())
            source = "last_price"

    else:  # polymarket
        if not token_id:
            return _error("token_id is required for venue 'polymarket'")
        identifier = token_id

        from sports_skills import polymarket

        if at_time is not None:
            result = polymarket.get_price_history(token_id=token_id, interval="max")
            if not result.get("status"):
                return _error(f"Polymarket history fetch failed: {result.get('message', '')}")
            history = result.get("data", {}).get("history", []) or []
            points = [p for p in history if p.get("t") is not None and int(p["t"]) <= at_time]
            if not points:
                return _error(f"No Polymarket price found for token at or before {at_time}")
            last = max(points, key=lambda p: int(p["t"]))
            yes_price, ts = float(last.get("p", 0)), int(last["t"])
            source = "history"
        else:
            result = polymarket.get_market_prices(token_id=token_id)
            if not result.get("status"):
                return _error(f"Polymarket price fetch failed: {result.get('message', '')}")
            mid = result.get("data", {}).get("midpoint")
            if mid is None:
                return _error(f"No midpoint available for token {token_id}")
            yes_price, ts = float(mid), int(_time.time())
            source = "midpoint"

    data = {
        "venue": venue,
        "identifier": identifier,
        "requested_at_time": at_time,
        "source": source,
    }
    data.update(_price_pair(yes_price, ts))
    return _success(
        data,
        f"{venue} yes price {data['yes']['price']:.2f}" + (f" as of {ts}" if at_time is not None else ""),
    )


_HISTORY_INTERVALS = {"1m": 1, "1h": 60, "1d": 1440}


def get_price_history(request_data: dict) -> dict:
    """Price history for a market on either venue, in one shape.

    Points are (timestamp, yes price 0-1) regardless of venue.

    Params:
        venue (str): 'kalshi' or 'polymarket'.
        ticker (str): Kalshi market ticker (required for kalshi).
        token_id (str): Polymarket CLOB token ID (required for polymarket).
        interval (str): '1m', '1h', or '1d' (default: '1d').
        start_time: Optional Unix timestamp or ISO 8601. Defaults by
            interval: 1m -> last day, 1h -> last week, 1d -> last month.
        end_time: Optional Unix timestamp or ISO 8601 (default: now).
    """
    import time as _time

    params = request_data.get("params", {})
    venue = str(params.get("venue") or "").lower()
    ticker = params.get("ticker", "")
    token_id = params.get("token_id", "")
    interval = str(params.get("interval") or "1d").lower()

    if venue not in ("kalshi", "polymarket"):
        return _error("venue must be 'kalshi' or 'polymarket'")
    if interval not in _HISTORY_INTERVALS:
        return _error("interval must be one of: 1m, 1h, 1d")
    try:
        end_time = _parse_at_time(params.get("end_time")) or int(_time.time())
        default_span = {"1m": 86400, "1h": 7 * 86400, "1d": 31 * 86400}[interval]
        start_time = _parse_at_time(params.get("start_time")) or (end_time - default_span)
    except ValueError:
        return _error("start_time/end_time must be Unix timestamps or ISO 8601 datetimes")
    if start_time >= end_time:
        return _error("start_time must be before end_time")

    points = []

    if venue == "kalshi":
        if not ticker:
            return _error("ticker is required for venue 'kalshi'")
        identifier = ticker

        from sports_skills import kalshi

        result = kalshi.get_market_candlesticks(
            series_ticker=ticker.split("-", 1)[0],
            ticker=ticker,
            start_ts=start_time,
            end_ts=end_time,
            period_interval=_HISTORY_INTERVALS[interval],
        )
        if not result.get("status"):
            return _error(f"Kalshi candlesticks fetch failed: {result.get('message', '')}")
        for candle in result.get("data", {}).get("candlesticks", []) or []:
            ts = candle.get("end_period_ts")
            price = _candle_close(candle)
            if ts is not None and price is not None:
                points.append({"timestamp": int(ts), "price": round(price, 4)})

    else:  # polymarket
        if not token_id:
            return _error("token_id is required for venue 'polymarket'")
        identifier = token_id

        from sports_skills import polymarket

        span = end_time - start_time
        clob_interval = "1d" if span <= 86400 else "1w" if span <= 7 * 86400 else "1m" if span <= 31 * 86400 else "max"
        result = polymarket.get_price_history(
            token_id=token_id,
            interval=clob_interval,
            fidelity=_HISTORY_INTERVALS[interval],
        )
        if not result.get("status"):
            return _error(f"Polymarket history fetch failed: {result.get('message', '')}")
        for p in result.get("data", {}).get("history", []) or []:
            ts = p.get("t")
            if ts is None or not (start_time <= int(ts) <= end_time):
                continue
            points.append({"timestamp": int(ts), "price": round(float(p.get("p", 0)), 4)})

    points.sort(key=lambda p: p["timestamp"])
    return _success(
        {
            "venue": venue,
            "identifier": identifier,
            "interval": interval,
            "start_time": start_time,
            "end_time": end_time,
            "points": points,
            "count": len(points),
        },
        f"Retrieved {len(points)} price point(s) from {venue}.",
    )


# ============================================================
# 2F. Momentum Explainer — mock ticks + timestamp-scoped plays
# ============================================================

# ESPN sport paths for the raw summary endpoint. Per-play UTC timestamps
# (`wallclock`) live ONLY in the raw summary payload — every sport module's
# `_normalize_plays` drops them, and PR #86's box-score fix rides that same
# shared normalizer. `get_plays_near_timestamp` therefore bypasses the
# normalized path and reads `espn_summary` directly, leaving _normalize_plays
# untouched.
_ESPN_SPORT_PATHS = {
    "nfl": "football/nfl",
    "nba": "basketball/nba",
    "mlb": "baseball/mlb",
    "nhl": "hockey/nhl",
    "wnba": "basketball/wnba",
    "cfb": "football/college-football",
    "cbb": "basketball/mens-college-basketball",
}


def _parse_iso_utc(value):
    """Parse an ISO 8601 timestamp (accepting a trailing 'Z') to an aware UTC datetime."""
    from datetime import datetime, timezone

    s = str(value).strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def get_mock_tick(request_data: dict) -> dict:
    """Deterministic timeline slice from a static mock game file.

    Reads a mock JSON file with a ``timeline`` array and returns the current
    tick chosen by system clock: ``(epoch // interval_seconds) % total_ticks``.
    No state files — the same wall-clock second always maps to the same tick,
    so a poller advances through the timeline as real time passes and loops.

    Params:
        mock_file_path (str): Path to the mock game JSON.
        interval_seconds (int): Seconds each tick is held (default: 5).
    """
    import json
    import time

    params = request_data.get("params", {})
    mock_file_path = params.get("mock_file_path")
    try:
        interval_seconds = int(params.get("interval_seconds") or 5)
    except (TypeError, ValueError):
        return _error("interval_seconds must be an integer")

    if not mock_file_path:
        return _error("mock_file_path is required")
    if interval_seconds <= 0:
        return _error("interval_seconds must be positive")

    try:
        with open(mock_file_path, encoding="utf-8") as fh:
            game = json.load(fh)
    except FileNotFoundError:
        return _error(f"Mock file not found: {mock_file_path}")
    except (OSError, json.JSONDecodeError) as exc:
        return _error(f"Could not read mock file {mock_file_path}: {exc}")

    timeline = game.get("timeline") or []
    total = len(timeline)
    if total == 0:
        return _error(f"Mock file {mock_file_path} has an empty timeline")

    idx = (int(time.time()) // interval_seconds) % total
    tick = timeline[idx]

    data = {
        "game_id": game.get("game_id", ""),
        "sport": game.get("sport", ""),
        "teams": game.get("teams", {}),
        "timestamp": tick.get("timestamp", ""),
        "game_clock": tick.get("game_clock", ""),
        "polymarket_home_price_cents": tick.get("polymarket_home_price_cents"),
        "play_by_play": tick.get("play_by_play", []),
        "tick_index": idx,
        "total_ticks": total,
    }
    return _success(
        data,
        f"Mock tick {idx + 1}/{total} for {game.get('game_id', 'game')} @ {data['polymarket_home_price_cents']}c home.",
    )


def _extract_play(p: dict) -> dict:
    """Pull the fields the explainer needs from a raw ESPN play, defensively.

    Raw play shapes differ by sport (NFL/NBA carry rich ``text``; MLB encodes
    the play in ``type``/``participants``), so every field defaults gracefully.
    """
    ptype = p.get("type") if isinstance(p.get("type"), dict) else {}
    period = p.get("period") if isinstance(p.get("period"), dict) else {}
    clock = p.get("clock") if isinstance(p.get("clock"), dict) else {}
    team = p.get("team") if isinstance(p.get("team"), dict) else {}
    return {
        "id": str(p.get("id", "")),
        "sequence": p.get("sequenceNumber", ""),
        "wallclock": p.get("wallclock", ""),
        "text": p.get("text", ""),
        "type": ptype.get("text", ""),
        "period": period.get("displayValue", ""),
        "game_clock": clock.get("displayValue", ""),
        "home_score": p.get("homeScore", ""),
        "away_score": p.get("awayScore", ""),
        "scoring_play": p.get("scoringPlay", False),
        "team_id": str(team.get("id", "")),
    }


def get_plays_near_timestamp(request_data: dict) -> dict:
    """Plays in the window ``[timestamp - window_seconds, timestamp]``.

    Fetches raw ESPN play-by-play, parses each play's UTC ``wallclock``, and
    returns those landing in the window ending at ``timestamp``. Used to find
    the play(s) responsible for a market move detected at ``timestamp``.

    Source selection: passing ``mock_file_path`` reads the plays embedded in
    the mock game file's timeline (no network); otherwise ``game_id`` selects
    a live fetch of the raw ESPN summary.

    Params:
        sport (str): Sport key (nfl, nba, mlb, nhl, wnba, cfb, cbb).
        game_id (str): ESPN event ID (live branch; ignored with mock_file_path).
        timestamp (str): ISO 8601 UTC instant, e.g. '2026-06-30T18:07:00Z'.
        window_seconds (int): Look-back window before timestamp (default: 120).
        mock_file_path (str): Optional mock game JSON; selects the mock branch.
    """
    from datetime import timedelta

    params = request_data.get("params", {})
    sport = str(params.get("sport") or "").lower()
    game_id = params.get("game_id")
    timestamp = params.get("timestamp")
    mock_file_path = params.get("mock_file_path")
    try:
        window_seconds = int(params.get("window_seconds") or 120)
    except (TypeError, ValueError):
        return _error("window_seconds must be an integer")

    if not sport:
        return _error("sport is required")
    if sport not in _ESPN_SPORT_PATHS:
        return _error(f"Unknown sport '{sport}'. Available: {', '.join(sorted(_ESPN_SPORT_PATHS))}")
    if not game_id and not mock_file_path:
        return _error("game_id is required (or pass mock_file_path for the mock branch)")
    if not timestamp:
        return _error("timestamp is required")
    if window_seconds <= 0:
        return _error("window_seconds must be positive")

    try:
        target = _parse_iso_utc(timestamp)
    except (ValueError, TypeError):
        return _error("timestamp must be ISO 8601 UTC, e.g. '2026-06-30T18:07:00Z'")

    window_start = target - timedelta(seconds=window_seconds)

    if mock_file_path:
        # Mock branch: the plays live inside the mock file's timeline ticks
        # (same raw-ESPN play shape the fixtures embed). No network.
        import json

        try:
            with open(mock_file_path, encoding="utf-8") as fh:
                game = json.load(fh)
        except FileNotFoundError:
            return _error(f"Mock file not found: {mock_file_path}")
        except (OSError, json.JSONDecodeError) as exc:
            return _error(f"Could not read mock file {mock_file_path}: {exc}")

        plays_raw = []
        seen_ids = set()
        for tick in game.get("timeline") or []:
            for p in tick.get("play_by_play") or []:
                pid = str(p.get("id", ""))
                if pid and pid in seen_ids:
                    continue
                seen_ids.add(pid)
                plays_raw.append(p)
        source = "mock-file"
        game_id = game_id or game.get("game_id", "")
    else:
        from sports_skills._espn_base import espn_summary

        try:
            data = espn_summary(_ESPN_SPORT_PATHS[sport], str(game_id))
        except Exception as exc:
            return _error(f"Failed to fetch play-by-play for {sport} game {game_id}: {exc}")
        if not data:
            return _error(f"No ESPN summary found for {sport} game {game_id}")

        plays_raw = data.get("plays", []) or []
        source = "espn-live"
    matched = []
    skipped_no_wallclock = 0
    for p in plays_raw:
        wc = p.get("wallclock")
        if not wc:
            skipped_no_wallclock += 1
            continue
        try:
            t = _parse_iso_utc(wc)
        except (ValueError, TypeError):
            skipped_no_wallclock += 1
            continue
        if window_start <= t <= target:
            matched.append(_extract_play(p))

    matched.sort(key=lambda x: x.get("wallclock", ""))

    return _success(
        {
            "sport": sport,
            "game_id": str(game_id),
            "source": source,
            "timestamp": timestamp,
            "window_seconds": window_seconds,
            "window_start": window_start.isoformat().replace("+00:00", "Z"),
            "window_end": target.isoformat().replace("+00:00", "Z"),
            "plays": matched,
            "count": len(matched),
            "total_plays": len(plays_raw),
            "plays_without_wallclock": skipped_no_wallclock,
        },
        f"Found {len(matched)} play(s) within {window_seconds}s before {timestamp}.",
    )


# ------------------------------------------------------------
# Kalshi game-winner market resolution (shared by get_live_tick
# and resolve_game_market)
# ------------------------------------------------------------

# Kalshi encodes the matchup in the event ticker's tail, e.g.
# "KXMLBGAME-26JUL171335TBBOSG1": date, an OPTIONAL US/Eastern HHMM time, then
# AWAYHOME team codes, then an optional Gn doubleheader suffix. Some series
# omit the time entirely (e.g. WNBA "KXWNBAGAME-26JUL17SEAIND"), so the HHMM
# group is optional; a time-less tail still yields the team pair for matching
# but no start time to disambiguate doubleheaders.
_KALSHI_EVENT_TAIL_RE = re.compile(r"^(\d{2})([A-Z]{3})(\d{2})(\d{4})?([A-Z]+?)(?:G(\d))?$")

# How far a Kalshi market's embedded start may sit from the ESPN game's start
# and still be considered the same game. Wide enough to absorb any same-day
# scheduling difference (including a doubleheader's second game, which is a
# separate candidate anyway), narrow enough to reject a different date.
_MAX_MARKET_START_SKEW = 12 * 3600  # seconds


def _parse_kalshi_event_tail(event_ticker: str):
    """Parse a game event ticker's tail into (start_utc, team_pair, game_num).

    Returns (None, None, None) when the tail doesn't match the dated game
    format, and (None, team_pair, game_num) for a time-less tail (the pair is
    still usable for matching, only start-time disambiguation is lost). The
    embedded time is US/Eastern (Kalshi's convention); it is converted to an
    aware UTC datetime.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tail = event_ticker.rsplit("-", 1)[-1] if "-" in event_ticker else event_ticker
    m = _KALSHI_EVENT_TAIL_RE.match(tail)
    if not m:
        return None, None, None
    yy, mon, dd, hhmm, pair, game_num = m.groups()
    month = _TICKER_MONTHS.get(mon)
    if month is None:
        return None, pair, game_num
    if hhmm is None:
        # Time-less ticker: keep the pair for matching, skip start-time parse.
        return None, pair, game_num
    try:
        start_et = datetime(
            2000 + int(yy),
            month,
            int(dd),
            int(hhmm[:2]),
            int(hhmm[2:]),
            tzinfo=ZoneInfo("America/New_York"),
        )
    except ValueError:
        return None, pair, game_num
    from datetime import timezone

    return start_et.astimezone(timezone.utc), pair, game_num


def _kalshi_game_search(series_ticker: str, query: str, status: str, limit: int = 200) -> list[dict]:
    """Search one Kalshi series for game markets. Thin seam for tests."""
    from sports_skills.kalshi._connector import search_markets as _kalshi_search

    result = _kalshi_search(
        {
            "params": {
                "series_ticker": series_ticker,
                "query": query,
                "status": status,
                "limit": limit,
            }
        }
    )
    if not result.get("status"):
        return []
    markets = (result.get("data") or {}).get("markets", [])
    return markets if isinstance(markets, list) else []


def _resolve_kalshi_game_market(
    sport: str,
    home: dict,
    away: dict,
    start_utc,
    statuses: tuple = ("open",),
) -> dict | None:
    """Find the Kalshi game-winner market for the HOME team of one ESPN game.

    Resolution is structural, not fuzzy, because the real Kalshi payload
    defeats title matching twice over: (1) event titles are location-based
    ("Tampa Bay vs Boston"), so a query built from ESPN display names
    ("Tampa Bay Rays Boston Red Sox") never substring-matches; and (2) BOTH
    sides of a winner market share one title ("Tampa Bay vs Boston Winner?"),
    so the home side is only identifiable from the ticker suffix.

    Steps:
      1. Search the sport's KX<SPORT>GAME series with the home team's
         *location* as the keyword (matches Kalshi's location-based titles).
      2. Keep events whose ticker team-pair equals AWAY+HOME (ESPN abbrevs)
         or whose title contains both team locations (covers abbreviation
         divergences like ESPN CHW vs Kalshi CWS).
      3. If several remain (doubleheaders), pick the event whose embedded
         US/Eastern start time is closest to the ESPN start.
      4. The home side is the market whose ticker suffix ends the team pair
         (pair "TBBOS" ends with "BOS" → -BOS is the home market).

    Returns {ticker, event_ticker, title, status, yes_cents, market_start}
    for the home market, or None when no market resolves.
    """
    series = KALSHI_SERIES.get(sport)
    if not series:
        return None
    game_series = f"{series}GAME"

    home_abbr = str(home.get("abbrev", "")).upper()
    away_abbr = str(away.get("abbrev", "")).upper()
    home_loc = str(home.get("location", "")).lower()
    away_loc = str(away.get("location", "")).lower()
    espn_pair = f"{away_abbr}{home_abbr}"

    # Collect matching events across ALL requested statuses before choosing —
    # a doubleheader can split across statuses (game 1 settled, game 2 open),
    # and stopping at the first status that returns anything would pin every
    # lookup to the open game regardless of start time.
    events: dict[str, dict] = {}
    for status in statuses:
        for m in _kalshi_game_search(game_series, home_loc, status):
            et = m.get("event_ticker", "")
            ev = events.setdefault(et, {"event_ticker": et, "title": m.get("event_title", ""), "markets": []})
            ev["markets"].append(m)
    if not events:
        return None

    candidates = []
    for ev in events.values():
        start, pair, _game_num = _parse_kalshi_event_tail(ev["event_ticker"])
        title = str(ev["title"]).lower()
        pair_match = pair == espn_pair if pair else False
        title_match = bool(home_loc) and bool(away_loc) and home_loc in title and away_loc in title
        if not (pair_match or title_match):
            continue
        candidates.append((ev, start, pair))

    if not candidates:
        return None

    # Drop candidates whose embedded start is a different day from the ESPN
    # game. The sort below only disambiguates when several candidates survive,
    # so a LONE candidate was previously accepted no matter how far off its
    # date was: asking for a finished game returned the same teams' NEXT game
    # (still the only open market), fusing that price with this game's ESPN
    # frame. Returning nothing is correct here — a clean "no market resolved"
    # beats a plausible tick built from two different games.
    # Time-less tails (start is None) can't be checked and are left in place,
    # so series without an embedded time still resolve.
    if start_utc is not None:
        candidates = [
            c
            for c in candidates
            if c[1] is None or abs((c[1] - start_utc).total_seconds()) <= _MAX_MARKET_START_SKEW
        ]
        if not candidates:
            return None

    # Doubleheaders: two events share a team pair; the embedded start time
    # disambiguates. Events without a parseable start sort last.
    if len(candidates) > 1 and start_utc is not None:
        candidates.sort(key=lambda c: abs((c[1] - start_utc).total_seconds()) if c[1] else float("inf"))
    event, market_start, pair = candidates[0]

    # Home side by ticker-suffix structure (never by title — titles are
    # identical for both sides of a winner market).
    best = None
    best_score = 0
    for m in event["markets"]:
        ticker = str(m.get("ticker", ""))
        suffix = ticker.rsplit("-", 1)[-1].upper()
        score = 0
        if suffix == home_abbr:
            score += 2
        if pair and pair.endswith(suffix):
            score += 1
        if score > best_score:
            best, best_score = m, score
    if best is None:
        return None

    # Prefer the live bid; fall back to last trade for thin or settled books.
    # _price_cents reads either the legacy integer-cent field or the newer
    # *_dollars string form and returns 0-100 cents — the same helper used by
    # get_market_price / get_live_tick — so the winner market keeps one unit
    # and a genuine 1c price is never mistaken for a 0-1 probability.
    from sports_skills.kalshi._connector import _price_cents

    yes_cents = float(_price_cents(best, "yes_bid") or _price_cents(best, "last_price") or 0.0)

    return {
        "ticker": best.get("ticker", ""),
        "event_ticker": event["event_ticker"],
        "title": best.get("title", ""),
        "status": best.get("status", ""),
        "yes_cents": round(yes_cents, 1),
        "market_start": market_start.isoformat().replace("+00:00", "Z") if market_start else None,
    }


def _espn_game_frame(sport: str, event_id: str) -> tuple[dict | None, str]:
    """Read teams, clock, state, and start time from the raw ESPN summary header.

    Returns (frame, error_message); exactly one is set. The frame's team
    entries carry abbrev/name/location — location is what Kalshi titles use.
    """
    from sports_skills._espn_base import espn_summary

    try:
        summary = espn_summary(_ESPN_SPORT_PATHS[sport], str(event_id))
    except Exception as exc:
        return None, f"Failed to fetch ESPN summary for {sport} game {event_id}: {exc}"
    if not summary:
        return None, f"No ESPN summary found for {sport} game {event_id}"

    header = summary.get("header", {}) or {}
    competitions = header.get("competitions", []) or []
    comp = competitions[0] if competitions else {}

    teams: dict = {}
    for c in comp.get("competitors", []) or []:
        team = c.get("team", {})
        if isinstance(team, list):
            team = team[0] if team else {}
        entry = {
            "abbrev": team.get("abbreviation", ""),
            "name": team.get("displayName", team.get("name", "")),
            "location": team.get("location", ""),
        }
        if c.get("homeAway") in ("home", "away"):
            teams[c["homeAway"]] = entry

    if "home" not in teams or "away" not in teams:
        return None, f"Could not determine home/away teams from ESPN summary for {sport} game {event_id}"

    status_type = comp.get("status", {}).get("type", {})
    start_utc = None
    if comp.get("date"):
        try:
            start_utc = _parse_iso_utc(comp["date"])
        except (ValueError, TypeError):
            start_utc = None

    return (
        {
            "teams": teams,
            "game_clock": status_type.get("shortDetail", ""),
            "game_state": status_type.get("state", ""),
            "start_utc": start_utc,
        },
        "",
    )


def resolve_game_market(request_data: dict) -> dict:
    """Resolve one ESPN game to its Kalshi game-winner market (home side).

    Used by the live tick (open markets) and by the finished-game replay
    runner, which needs the settled market's ticker to pull candlesticks.

    Params:
        sport (str): Sport key (nfl, nba, mlb, nhl, wnba, cfb, cbb).
        event_id (str): ESPN event ID.
        status (str): 'open', 'settled', 'closed', or 'any' (default) —
            'any' tries open → settled → closed until one resolves.
    """
    params = request_data.get("params", {})
    sport = str(params.get("sport") or "").lower()
    event_id = params.get("event_id")
    status = str(params.get("status") or "any").lower()

    if not sport:
        return _error("sport is required")
    if sport not in _ESPN_SPORT_PATHS:
        return _error(f"Unknown sport '{sport}'. Available: {', '.join(sorted(_ESPN_SPORT_PATHS))}")
    if not event_id:
        return _error("event_id is required")
    if status not in ("open", "settled", "closed", "any"):
        return _error("status must be 'open', 'settled', 'closed', or 'any'")

    frame, err = _espn_game_frame(sport, str(event_id))
    if frame is None:
        return _error(err)

    statuses = ("open", "settled", "closed") if status == "any" else (status,)
    market = _resolve_kalshi_game_market(
        sport, frame["teams"]["home"], frame["teams"]["away"], frame["start_utc"], statuses
    )
    if market is None:
        home = frame["teams"]["home"]
        away = frame["teams"]["away"]
        return _error(
            f"No Kalshi game-winner market resolved for {away['name']} @ {home['name']} "
            f"(searched {KALSHI_SERIES.get(sport, '?')}GAME, statuses {', '.join(statuses)})."
        )

    return _success(
        {
            "sport": sport,
            "game_id": str(event_id),
            "teams": frame["teams"],
            "game_state": frame["game_state"],
            "game_clock": frame["game_clock"],
            "espn_start": frame["start_utc"].isoformat().replace("+00:00", "Z") if frame["start_utc"] else None,
            "kalshi_ticker": market["ticker"],
            "kalshi_event_ticker": market["event_ticker"],
            "market_status": market["status"],
            "market_start": market["market_start"],
            "home_yes_cents": market["yes_cents"],
        },
        f"Resolved {sport} game {event_id} to Kalshi market {market['ticker']} "
        f"({market['status']}, home yes {market['yes_cents']}c).",
    )


def get_live_tick(request_data: dict) -> dict:
    """Live market tick for an in-progress game — Kalshi home price + ESPN frame.

    Pulls teams and the current game clock from the ESPN summary and the home
    team's win-probability from Kalshi, and returns them in the SAME top-level
    shape as ``get_mock_tick`` so the watcher and explainer are unchanged — the
    one difference is the source-neutral price key ``home_price_cents`` (plus
    ``price_source`` and ``kalshi_ticker``) instead of the mock's
    ``polymarket_home_price_cents``. ``game_id`` is the ESPN event id so
    ``get_plays_near_timestamp`` can fetch plays for the same game.

    Params:
        sport (str): Sport key (nfl, nba, mlb, nhl, wnba, cfb, cbb).
        event_id (str): ESPN event ID.
    """
    from datetime import datetime, timezone

    params = request_data.get("params", {})
    sport = str(params.get("sport") or "").lower()
    event_id = params.get("event_id")

    if not sport:
        return _error("sport is required")
    if sport not in _ESPN_SPORT_PATHS:
        return _error(f"Unknown sport '{sport}'. Available: {', '.join(sorted(_ESPN_SPORT_PATHS))}")
    if not event_id:
        return _error("event_id is required")

    # Teams + game clock from the raw ESPN summary header (same source
    # get_plays_near_timestamp reads, so both functions agree on the game).
    frame, err = _espn_game_frame(sport, str(event_id))
    if frame is None:
        return _error(err)

    home = frame["teams"]["home"]
    away = frame["teams"]["away"]

    market = _resolve_kalshi_game_market(sport, home, away, frame["start_utc"], ("open",))
    if market is None:
        return _error(
            f"No Kalshi game-winner market resolved for {away['name']} @ {home['name']} "
            f"(searched {KALSHI_SERIES.get(sport, '?')}GAME, status open)."
        )

    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # The returned teams keep the mock tick's {abbrev, name} entries.
    teams = {side: {"abbrev": t["abbrev"], "name": t["name"]} for side, t in frame["teams"].items()}

    data = {
        "sport": sport,
        "game_id": str(event_id),
        "teams": teams,
        "timestamp": timestamp,
        "game_clock": frame["game_clock"],
        "home_price_cents": market["yes_cents"],
        "price_source": "kalshi",
        "kalshi_ticker": market["ticker"],
    }
    return _success(
        data,
        f"Live tick for {away['name']} @ {home['name']} @ {market['yes_cents']}c home (kalshi {market['ticker']}).",
    )
