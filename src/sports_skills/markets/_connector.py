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

        games.append({
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
        })

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
        events_map[event_ticker]["markets"].append({
            "ticker": m.get("ticker", ""),
            "title": m.get("title", ""),
            "yes_price": m.get("yes_bid", m.get("last_price", 0)),
            "no_price": m.get("no_bid", 0),
            "volume": m.get("volume", 0),
        })

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
            outcomes.append({
                "token_id": o.get("clob_token_id", ""),
                "outcome": o.get("name", ""),
                "price": o.get("price", 0),
            })

        results.append({
            "source": "polymarket",
            "market_id": market.get("id", ""),
            "title": market.get("question", ""),
            "slug": market.get("slug", ""),
            "volume": market.get("volume", 0),
            "sports_market_type": market.get("sports_market_type", ""),
            "outcomes": outcomes,
        })

    return results


# ============================================================
# 2E. Odds Normalization
# ============================================================


def _normalize_price(price: float, source: str) -> dict:
    """Convert any source format to {implied_probability, american, decimal}.

    source="polymarket": price is 0-1, use betting.convert_odds(from_format="probability")
    source="kalshi":     price is 0-100 int, divide by 100 then convert
    source="espn":       price is American odds, use betting.convert_odds(from_format="american")
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
    elif source == "espn":
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

        try:
            kalshi_matches = _search_kalshi(search_query, game["sport"])
        except Exception as exc:
            warnings.append(f"Kalshi search failed for '{search_query}': {exc}")

        try:
            poly_matches = _search_polymarket(search_query, game["sport"])
        except Exception as exc:
            warnings.append(f"Polymarket search failed for '{search_query}': {exc}")

        game_entry = {
            **game,
            "kalshi_markets": kalshi_matches,
            "polymarket_markets": poly_matches,
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
    warnings = []

    try:
        kalshi_results = _search_kalshi(query, sport)
    except Exception as exc:
        warnings.append(f"Kalshi search failed: {exc}")

    try:
        poly_results = _search_polymarket(query, sport)
    except Exception as exc:
        warnings.append(f"Polymarket search failed: {exc}")

    total = len(kalshi_results) + len(poly_results)

    return _success_partial(
        {
            "query": query,
            "sport": sport,
            "kalshi": kalshi_results,
            "polymarket": poly_results,
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

    if search_query:
        try:
            kalshi_matches = _search_kalshi(search_query, sport)
        except Exception as exc:
            warnings.append(f"Kalshi search failed: {exc}")

        try:
            poly_matches = _search_polymarket(search_query, sport)
        except Exception as exc:
            warnings.append(f"Polymarket search failed: {exc}")

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

    if len(all_probs) >= 2:
        try:
            from sports_skills.betting._calcs import find_arbitrage
            arb_result = find_arbitrage({
                "params": {
                    "market_probs": all_probs,
                    "labels": all_labels,
                }
            })
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
        source (str): Source platform — "polymarket", "kalshi", or "espn".
    """
    params = request_data.get("params", {})

    try:
        price = float(params.get("price", 0))
    except (TypeError, ValueError) as e:
        return _error(f"Invalid price: {e}")

    source = str(params.get("source", "")).lower()
    if source not in ("polymarket", "kalshi", "espn"):
        return _error(f"Unknown source '{source}'. Use 'polymarket', 'kalshi', or 'espn'.")

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
            market_result = kalshi.get_market(ticker=kalshi_ticker)
            if market_result.get("status"):
                market_data = market_result.get("data", {})
                yes_price = market_data.get("yes_bid", market_data.get("last_price", 0))
                market_prob = float(yes_price) / 100.0 if float(yes_price) > 1 else float(yes_price)
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

    eval_result = evaluate_bet({
        "params": {
            "book_odds": book_odds_str,
            "market_prob": market_prob,
            "book_format": "american",
            "outcome": outcome,
        }
    })

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
