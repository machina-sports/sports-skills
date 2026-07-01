import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

# ============================================================
# Configuration
# ============================================================

GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
CLOB_BASE_URL = "https://clob.polymarket.com"

# Sports tag ID on Polymarket
SPORTS_TAG_ID = 1

# Common sport-related tags for filtering
SPORT_TAGS = {
    "sports": 1,
    "basketball": 28,
    "nba": 28,
}


# ============================================================
# Module-Level Cache (TTL-based)
# ============================================================

_cache = {}
_cache_lock = threading.Lock()


def _cache_get(key):
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        value, expiry = entry
        if time.monotonic() > expiry:
            del _cache[key]
            return None
        return value


def _cache_set(key, value, ttl=300):
    with _cache_lock:
        if len(_cache) > 500:
            now = time.monotonic()
            expired = [k for k, (_, exp) in _cache.items() if now > exp]
            for k in expired:
                del _cache[k]
        _cache[key] = (value, time.monotonic() + ttl)


# ============================================================
# Rate Limiters (Token Bucket)
# ============================================================


class _RateLimiter:
    def __init__(self, max_tokens=10, refill_rate=10.0):
        self.max_tokens = max_tokens
        self.tokens = max_tokens
        self.refill_rate = refill_rate
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self):
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now
            if self.tokens >= 1:
                self.tokens -= 1
                return
        time.sleep(max(0, (1 - self.tokens) / self.refill_rate))
        self.acquire()


# Gamma API: 300 req/10s for /markets, 500 req/10s for /events
_gamma_rate_limiter = _RateLimiter(max_tokens=25, refill_rate=25.0)
# CLOB API: 1500 req/10s for price endpoints
_clob_rate_limiter = _RateLimiter(max_tokens=50, refill_rate=50.0)


# ============================================================
# HTTP Helpers
# ============================================================

_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _gamma_request(endpoint, params=None, ttl=120):
    """Gamma API request (public, no auth). Cached."""
    cache_key = f"gamma:{endpoint}:{json.dumps(params or {}, sort_keys=True)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    _gamma_rate_limiter.acquire()
    url = f"{GAMMA_BASE_URL}{endpoint}"
    if params:
        clean_params = {k: v for k, v in params.items() if v is not None and v != ""}
        if clean_params:
            url += "?" + urllib.parse.urlencode(clean_params, doseq=True)

    req = urllib.request.Request(url)
    req.add_header("User-Agent", _USER_AGENT)
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            _cache_set(cache_key, data, ttl=ttl)
            return data
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"error": True, "status_code": e.code, "message": body}
    except Exception as e:
        return {"error": True, "message": str(e)}


def _clob_request(endpoint, params=None, ttl=30):
    """CLOB API request (public reads, no auth). Cached with shorter TTL."""
    cache_key = f"clob:{endpoint}:{json.dumps(params or {}, sort_keys=True)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    _clob_rate_limiter.acquire()
    url = f"{CLOB_BASE_URL}{endpoint}"
    if params:
        clean_params = {k: v for k, v in params.items() if v is not None and v != ""}
        if clean_params:
            url += "?" + urllib.parse.urlencode(clean_params, doseq=True)

    req = urllib.request.Request(url)
    req.add_header("User-Agent", _USER_AGENT)
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            _cache_set(cache_key, data, ttl=ttl)
            return data
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"error": True, "status_code": e.code, "message": body}
    except Exception as e:
        return {"error": True, "message": str(e)}


# ============================================================
# Response Helpers
# ============================================================


def _success(data, message=""):
    return {"status": True, "data": data, "message": message}


def _error(message, data=None):
    return {"status": False, "data": data, "message": message}


def _check_error(response):
    """Check if a response is an error. Returns error dict or None."""
    if isinstance(response, dict) and response.get("error"):
        code = response.get("status_code", "unknown")
        msg = response.get("message", "Unknown error")
        return _error(f"API error ({code}): {msg}")
    return None


# ============================================================
# Market Normalization
# ============================================================


def _parse_json_field(value):
    """Parse a field that may be a JSON string or already a list."""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    if isinstance(value, list):
        return value
    return []


def _normalize_market(market):
    """Normalize a Gamma API market response to a consistent format."""
    # Extract CLOB token IDs for price lookups — fields may be JSON strings
    clob_token_ids = _parse_json_field(market.get("clobTokenIds", []))
    outcomes = _parse_json_field(market.get("outcomes", []))
    outcome_prices = _parse_json_field(market.get("outcomePrices", []))

    # Parse outcome prices to floats
    parsed_prices = []
    if outcome_prices:
        for p in outcome_prices:
            try:
                parsed_prices.append(float(p) if isinstance(p, str) else p)
            except (ValueError, TypeError):
                parsed_prices.append(None)

    # Build outcomes list
    normalized_outcomes = []
    for i, outcome in enumerate(outcomes):
        entry = {"name": outcome}
        if i < len(parsed_prices) and parsed_prices[i] is not None:
            entry["price"] = round(parsed_prices[i], 4)
        if i < len(clob_token_ids):
            entry["clob_token_id"] = clob_token_ids[i]
        normalized_outcomes.append(entry)

    return {
        "id": market.get("id", ""),
        "question": market.get("question", ""),
        "description": market.get("description", ""),
        "slug": market.get("slug", ""),
        "status": "active"
        if market.get("active") and not market.get("closed")
        else "closed"
        if market.get("closed")
        else "inactive",
        "outcomes": normalized_outcomes,
        "volume": _safe_float(market.get("volume")),
        "volume_24h": _safe_float(market.get("volume24hr")),
        "liquidity": _safe_float(market.get("liquidity")),
        "competitive": market.get("competitive", 0),
        "spread": _safe_float(market.get("spread")),
        "start_date": market.get("startDate", ""),
        "end_date": market.get("endDate", ""),
        "created_at": market.get("createdAt", ""),
        "updated_at": market.get("updatedAt", ""),
        "event_id": market.get("events", [{}])[0].get("id", "")
        if market.get("events")
        else "",
        "sports_market_type": market.get("sportsMarketType", ""),
        "game_id": market.get("gameId", ""),
        "clob_token_ids": clob_token_ids,
        "tags": [
            t.get("label", "") if isinstance(t, dict) else t
            for t in market.get("tags", [])
        ],
    }


def _normalize_event(event):
    """Normalize a Gamma API event response."""
    markets = event.get("markets", [])

    return {
        "id": event.get("id", ""),
        "title": event.get("title", ""),
        "description": event.get("description", ""),
        "slug": event.get("slug", ""),
        "status": "active"
        if event.get("active") and not event.get("closed")
        else "closed"
        if event.get("closed")
        else "inactive",
        "start_date": event.get("startDate", ""),
        "end_date": event.get("endDate", ""),
        "created_at": event.get("createdAt", ""),
        "updated_at": event.get("updatedAt", ""),
        "volume": _safe_float(event.get("volume")),
        "liquidity": _safe_float(event.get("liquidity")),
        "competitive": event.get("competitive", 0),
        "market_count": len(markets),
        "markets": [_normalize_market(m) for m in markets] if markets else [],
        "tags": [
            t.get("label", "") if isinstance(t, dict) else t
            for t in event.get("tags", [])
        ],
        "series_id": event.get("seriesId", ""),
    }


def _safe_float(value, default=0.0):
    """Safely convert a value to float."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


# ============================================================
# Commands
# ============================================================


def get_sports_markets(request_data):
    """Get active sports prediction markets with optional filtering.

    Params:
        limit (int): Max results per page (default: 50, max: 100)
        offset (int): Pagination offset (default: 0)
        sports_market_types (str): Filter by type (e.g. 'moneyline', 'spreads', 'totals')
        game_id (str): Filter by specific game
        active (bool): Only active markets (default: True)
        closed (bool): Include closed markets (default: False)
        order (str): Sort field (default: 'volume')
        ascending (bool): Sort ascending (default: False)
    """
    try:
        params = request_data.get("params", {})

        query = {
            "tag_id": params.get("tag_id", SPORTS_TAG_ID),
            "limit": min(int(params.get("limit", 50)), 100),
            "offset": int(params.get("offset", 0)),
            "active": str(params.get("active", True)).lower(),
            "closed": str(params.get("closed", False)).lower(),
            "order": params.get("order", "volume"),
            "ascending": str(params.get("ascending", False)).lower(),
        }

        # Optional filters
        if params.get("sports_market_types"):
            query["sports_market_types"] = params["sports_market_types"]
        if params.get("game_id"):
            query["game_id"] = params["game_id"]

        response = _gamma_request("/markets", params=query)
        err = _check_error(response)
        if err:
            return err

        # Response is a list of markets
        markets = (
            response
            if isinstance(response, list)
            else response.get("markets", response)
        )
        if not isinstance(markets, list):
            markets = []

        normalized = [_normalize_market(m) for m in markets]

        return _success(
            {
                "markets": normalized,
                "count": len(normalized),
                "offset": query["offset"],
            },
            f"Retrieved {len(normalized)} sports markets",
        )

    except Exception as e:
        return _error(f"Error fetching sports markets: {str(e)}")


def get_sports_events(request_data):
    """Get sports events (each event groups related markets).

    Params:
        limit (int): Max results (default: 50, max: 100)
        offset (int): Pagination offset (default: 0)
        active (bool): Only active events (default: True)
        closed (bool): Include closed events (default: False)
        order (str): Sort field (default: 'volume')
        ascending (bool): Sort ascending (default: False)
        series_id (str): Filter by series (league) ID
    """
    try:
        params = request_data.get("params", {})

        query = {
            "tag_id": params.get("tag_id", SPORTS_TAG_ID),
            "limit": min(int(params.get("limit", 50)), 100),
            "offset": int(params.get("offset", 0)),
            "active": str(params.get("active", True)).lower(),
            "closed": str(params.get("closed", False)).lower(),
            "order": params.get("order", "volume"),
            "ascending": str(params.get("ascending", False)).lower(),
        }

        if params.get("series_id"):
            query["series_id"] = params["series_id"]

        response = _gamma_request("/events", params=query)
        err = _check_error(response)
        if err:
            return err

        events = (
            response if isinstance(response, list) else response.get("events", response)
        )
        if not isinstance(events, list):
            events = []

        normalized = [_normalize_event(e) for e in events]

        return _success(
            {"events": normalized, "count": len(normalized), "offset": query["offset"]},
            f"Retrieved {len(normalized)} sports events",
        )

    except Exception as e:
        return _error(f"Error fetching sports events: {str(e)}")


def get_series(request_data):
    """Get all series (leagues, recurring event groups).

    Params:
        limit (int): Max results (default: 100)
        offset (int): Pagination offset (default: 0)
    """
    try:
        params = request_data.get("params", {})

        query = {
            "limit": min(int(params.get("limit", 100)), 200),
            "offset": int(params.get("offset", 0)),
        }

        response = _gamma_request("/series", params=query, ttl=600)
        err = _check_error(response)
        if err:
            return err

        series_list = (
            response if isinstance(response, list) else response.get("series", response)
        )
        if not isinstance(series_list, list):
            series_list = []

        normalized = []
        for s in series_list:
            normalized.append(
                {
                    "id": s.get("id", ""),
                    "title": s.get("title", ""),
                    "slug": s.get("slug", ""),
                    "description": s.get("description", ""),
                    "image": s.get("image", ""),
                    "created_at": s.get("createdAt", ""),
                    "updated_at": s.get("updatedAt", ""),
                }
            )

        return _success(
            {"series": normalized, "count": len(normalized)},
            f"Retrieved {len(normalized)} series",
        )

    except Exception as e:
        return _error(f"Error fetching series: {str(e)}")


def get_market_details(request_data):
    """Get detailed information for a specific market.

    Params:
        market_id (str): Market ID (numeric)
        slug (str): Market slug (alternative to ID)
    """
    try:
        params = request_data.get("params", {})
        market_id = params.get("market_id", "")
        slug = params.get("slug", "")

        if not market_id and not slug:
            return _error("Either market_id or slug is required")

        endpoint = f"/markets/{slug}" if slug else f"/markets/{market_id}"
        response = _gamma_request(endpoint, ttl=60)
        err = _check_error(response)
        if err:
            return err

        if not response or (isinstance(response, dict) and not response.get("id")):
            return _error(f"Market not found: {market_id or slug}")

        normalized = _normalize_market(response)

        return _success(
            normalized, f"Retrieved market: {normalized.get('question', '')}"
        )

    except Exception as e:
        return _error(f"Error fetching market details: {str(e)}")


def get_event_details(request_data):
    """Get detailed information for a specific event (includes nested markets).

    Params:
        event_id (str): Event ID (numeric)
        slug (str): Event slug (alternative to ID)
    """
    try:
        params = request_data.get("params", {})
        event_id = params.get("event_id", "")
        slug = params.get("slug", "")

        if not event_id and not slug:
            return _error("Either event_id or slug is required")

        if slug:
            # Gamma resolves slugs via query param, not path (the path
            # segment must be a numeric id).
            response = _gamma_request("/events", params={"slug": slug}, ttl=60)
            if isinstance(response, list):
                response = response[0] if response else {}
        else:
            response = _gamma_request(f"/events/{event_id}", ttl=60)
        err = _check_error(response)
        if err:
            return err

        if not response or (isinstance(response, dict) and not response.get("id")):
            return _error(f"Event not found: {event_id or slug}")

        normalized = _normalize_event(response)

        return _success(normalized, f"Retrieved event: {normalized.get('title', '')}")

    except Exception as e:
        return _error(f"Error fetching event details: {str(e)}")


def get_market_prices(request_data):
    """Get current prices for one or more markets from the CLOB API.

    Params:
        token_id (str): Single CLOB token ID
        token_ids (list): Multiple CLOB token IDs (batch)
    """
    try:
        params = request_data.get("params", {})
        token_id = params.get("token_id", "")
        token_ids = params.get("token_ids", [])

        if not token_id and not token_ids:
            return _error("Either token_id or token_ids is required")

        if token_id and not token_ids:
            # Single price lookup
            midpoint = _clob_request("/midpoint", params={"token_id": token_id})
            err = _check_error(midpoint)
            if err:
                return err

            buy_price = _clob_request(
                "/price", params={"token_id": token_id, "side": "BUY"}
            )
            sell_price = _clob_request(
                "/price", params={"token_id": token_id, "side": "SELL"}
            )

            price_data = {
                "token_id": token_id,
                "midpoint": _safe_float(midpoint.get("mid")),
                "buy_price": _safe_float(buy_price.get("price"))
                if not _check_error(buy_price)
                else None,
                "sell_price": _safe_float(sell_price.get("price"))
                if not _check_error(sell_price)
                else None,
            }

            return _success(price_data, "Price data retrieved")

        else:
            # Batch price lookup
            prices = []
            for tid in token_ids[:20]:  # Cap at 20 to avoid rate limits
                midpoint = _clob_request("/midpoint", params={"token_id": tid})
                if not _check_error(midpoint):
                    prices.append(
                        {
                            "token_id": tid,
                            "midpoint": _safe_float(midpoint.get("mid")),
                        }
                    )

            return _success(
                {"prices": prices, "count": len(prices)},
                f"Retrieved prices for {len(prices)} tokens",
            )

    except Exception as e:
        return _error(f"Error fetching market prices: {str(e)}")


def get_order_book(request_data):
    """Get the full order book for a market from the CLOB API.

    Params:
        token_id (str): CLOB token ID (required)
    """
    try:
        params = request_data.get("params", {})
        token_id = params.get("token_id", "")

        if not token_id:
            return _error("token_id is required")

        response = _clob_request("/book", params={"token_id": token_id})
        err = _check_error(response)
        if err:
            return err

        bids = response.get("bids", [])
        asks = response.get("asks", [])

        # The CLOB returns price levels with the BEST price at the END of
        # each array (bids ascending, asks descending). Never assume order:
        # best bid is the highest bid, best ask is the lowest ask. Returned
        # arrays are sorted best-first so consumers reading [0] get the touch.
        norm_bids = sorted(
            (
                {"price": _safe_float(b.get("price")), "size": _safe_float(b.get("size"))}
                for b in bids
            ),
            key=lambda level: level["price"],
            reverse=True,
        )
        norm_asks = sorted(
            (
                {"price": _safe_float(a.get("price")), "size": _safe_float(a.get("size"))}
                for a in asks
            ),
            key=lambda level: level["price"],
        )
        best_bid = norm_bids[0]["price"] if norm_bids else 0
        best_ask = norm_asks[0]["price"] if norm_asks else 0
        spread = round(best_ask - best_bid, 4) if best_bid and best_ask else None

        book = {
            "token_id": token_id,
            "bids": norm_bids,
            "asks": norm_asks,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "bid_depth": len(bids),
            "ask_depth": len(asks),
        }

        return _success(
            book, f"Order book retrieved ({len(bids)} bids, {len(asks)} asks)"
        )

    except Exception as e:
        return _error(f"Error fetching order book: {str(e)}")


def get_sports_market_types(request_data):
    """Get all valid sports market types (moneyline, spreads, totals, props, etc.).

    No params required.
    """
    try:
        response = _gamma_request("/sports/market-types", ttl=3600)
        err = _check_error(response)
        if err:
            return err

        return _success(response, "Sports market types retrieved")

    except Exception as e:
        return _error(f"Error fetching sports market types: {str(e)}")


def search_markets(request_data):
    """Find sports markets by keyword, sport, or market type.

    Searches the /markets endpoint directly (returns single-game markets)
    and optionally filters by sport (league series) via the /sports config.

    Params:
        query (str): Keyword to match in market questions/slugs or event titles
        sport (str): Sport code to filter by league (e.g. 'nba', 'epl', 'nfl',
            'nhl', 'mlb', 'bun', 'fl1', 'sea', 'ucl', 'mls', 'atp', 'wta').
            Resolves to the correct series_id automatically.
        sports_market_types (str): Filter by type (e.g. 'moneyline', 'spreads', 'totals')
        tag_id (int): Tag ID (default: 1 = Sports)
        limit (int): Max results (default: 20, max: 100)
    """
    try:
        params = request_data.get("params", {})
        query = str(params.get("query") or "").lower()
        sport = str(params.get("sport") or "").lower()
        limit = min(int(params.get("limit", 20)), 100)
        smt = params.get("sports_market_types", "")

        # If sport is specified, resolve to series_id and search via events
        series_id = params.get("series_id")
        if sport and not series_id:
            config = _get_sports_config()
            series_id = config.get(sport, {}).get("series")

        all_markets = []

        # Strategy 1: If we have a series_id (from sport param), query events for that league.
        # Order by VOLUME, not startDate: many Polymarket events carry placeholder
        # start dates (e.g. World Cup moneyline events show an April date for a June
        # game), so startDate-desc sorting buries the liquid 1X2 winner markets past
        # the 100-event limit, leaving only props. Volume-desc surfaces the tradeable
        # markets first.
        if series_id:
            event_params = {
                "series_id": series_id,
                "limit": 100,
                "active": "true",
                "closed": "false",
                "order": "volume",
                "ascending": "false",
            }
            response = _gamma_request("/events", params=event_params, ttl=60)
            if not _check_error(response):
                events = response if isinstance(response, list) else response.get("events", response)
                if isinstance(events, list):
                    for e in events:
                        if query and not _text_match(query, e):
                            continue
                        markets = e.get("markets", [])
                        if smt:
                            markets = [m for m in markets if m.get("sportsMarketType", "") == smt]
                        all_markets.extend([_normalize_market(m) for m in markets])

        # Strategy 2: Query /markets directly (returns single-game markets by volume)
        if len(all_markets) < limit:
            market_params = {
                "tag_id": params.get("tag_id", SPORTS_TAG_ID),
                "limit": 100,
                "active": "true",
                "closed": "false",
                "order": "volume",
                "ascending": "false",
            }
            if smt:
                market_params["sports_market_types"] = smt

            response = _gamma_request("/markets", params=market_params, ttl=60)
            if not _check_error(response):
                markets = response if isinstance(response, list) else response.get("markets", response)
                if isinstance(markets, list):
                    seen_ids = {m["id"] for m in all_markets}
                    for m in markets:
                        if m.get("id", "") in seen_ids:
                            continue
                        if query and not _text_match_market(query, m):
                            continue
                        all_markets.append(_normalize_market(m))

        # Strategy 3: If query provided but no sport, also search /events by volume
        # to find single-game events by name (volume-desc, not startDate — placeholder
        # start dates otherwise bury liquid winner markets; see Strategy 1).
        if query and not series_id and len(all_markets) < limit:
            event_params = {
                "tag_id": params.get("tag_id", SPORTS_TAG_ID),
                "limit": 100,
                "active": "true",
                "closed": "false",
                "order": "volume",
                "ascending": "false",
            }
            response = _gamma_request("/events", params=event_params, ttl=60)
            if not _check_error(response):
                events = response if isinstance(response, list) else response.get("events", response)
                if isinstance(events, list):
                    seen_ids = {m["id"] for m in all_markets}
                    for e in events:
                        if not _text_match(query, e):
                            continue
                        markets = e.get("markets", [])
                        if smt:
                            markets = [m for m in markets if m.get("sportsMarketType", "") == smt]
                        for m in markets:
                            if m.get("id", "") not in seen_ids:
                                all_markets.append(_normalize_market(m))
                                seen_ids.add(m.get("id", ""))

        return _success(
            {
                "markets": all_markets[:limit],
                "count": len(all_markets[:limit]),
                "query": query or "(all sports)",
                "sport": sport or None,
            },
            f"Found {len(all_markets[:limit])} markets",
        )

    except Exception as e:
        return _error(f"Error searching markets: {str(e)}")


def _text_match(query, event):
    """Check if query matches event title, description, or slug."""
    q = query.lower()
    return (
        q in event.get("title", "").lower()
        or q in event.get("description", "").lower()
        or q in event.get("slug", "").lower()
    )


def _text_match_market(query, market):
    """Check if query matches market question, slug, or parent event title."""
    q = query.lower()
    if q in market.get("question", "").lower() or q in market.get("slug", "").lower():
        return True
    return any(
        q in e.get("title", "").lower() or q in e.get("slug", "").lower()
        for e in market.get("events", [])
    )


def get_sports_config(request_data):
    """Get available sports and their series IDs for filtering.

    Returns a mapping of sport codes to their metadata (series_id, tags).
    Use the sport code with search_markets(sport='nba') or get_todays_events(sport='epl').

    No params required.
    """
    try:
        config = _get_sports_config()
        if not config:
            return _error("Failed to fetch sports configuration")

        sports = []
        for code, info in sorted(config.items()):
            sports.append({
                "sport": code,
                "series_id": info.get("series", ""),
                "tags": info.get("tags", ""),
            })

        return _success(
            {"sports": sports, "count": len(sports)},
            f"Retrieved {len(sports)} sport configurations",
        )

    except Exception as e:
        return _error(f"Error fetching sports config: {str(e)}")


def _get_sports_config():
    """Fetch and cache the /sports endpoint mapping sport→series."""
    cache_key = "sports_config"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    response = _gamma_request("/sports", ttl=3600)
    if isinstance(response, list):
        config = {}
        for s in response:
            code = s.get("sport", "")
            if code:
                config[code] = {
                    "series": s.get("series", ""),
                    "tags": s.get("tags", ""),
                    "ordering": s.get("ordering", ""),
                }
        _cache_set(cache_key, config, ttl=3600)
        return config
    return {}


def get_todays_events(request_data):
    """Get today's events (single-game markets) for a specific sport.

    Returns events sorted by volume (most liquid first) for the given
    sport/league. Each event includes its nested markets with prices.

    Params:
        sport (str): Sport code (required) — e.g. 'nba', 'epl', 'nfl', 'nhl',
            'mlb', 'bun', 'fl1', 'sea', 'ucl', 'mls', 'atp', 'wta', 'lal'.
        limit (int): Max events (default: 50, max: 100). Increase to 100 for
            leagues with many concurrent matches.
    """
    try:
        params = request_data.get("params", {})
        sport = str(params.get("sport") or "").lower()
        limit = min(int(params.get("limit", 50)), 100)

        if not sport:
            return _error(
                "sport is required. Use get_sports_config() to see available sport codes "
                "(e.g. 'nba', 'epl', 'nfl', 'nhl', 'mlb', 'bun', 'fl1', 'ucl', 'mls')."
            )

        config = _get_sports_config()
        series_id = config.get(sport, {}).get("series")
        if not series_id:
            available = ", ".join(sorted(config.keys()))
            return _error(
                f"Unknown sport '{sport}'. Available: {available}"
            )

        # Order by VOLUME, not startDate: Polymarket events often carry placeholder
        # start dates (a World Cup 1X2 event for a June game shows an April date), so
        # startDate-desc sorting buries the liquid winner markets past the limit and
        # returns only prop events. Volume-desc surfaces the real tradeable games.
        event_params = {
            "series_id": series_id,
            "limit": limit,
            "active": "true",
            "closed": "false",
            "order": "volume",
            "ascending": "false",
        }

        response = _gamma_request("/events", params=event_params, ttl=60)
        err = _check_error(response)
        if err:
            return err

        events = response if isinstance(response, list) else response.get("events", response)
        if not isinstance(events, list):
            events = []

        normalized = [_normalize_event(e) for e in events]

        return _success(
            {"events": normalized, "count": len(normalized), "sport": sport},
            f"Retrieved {len(normalized)} {sport.upper()} events",
        )

    except Exception as e:
        return _error(f"Error fetching today's events: {str(e)}")


def get_price_history(request_data):
    """Get historical price data for a market over time via CLOB API.

    Params:
        token_id (str): CLOB token ID (required)
        interval (str): Time range - "1d", "1w", "1m", "max" (default: "max")
        fidelity (int): Resolution of data points in minutes (default: 120)
    """
    try:
        params = request_data.get("params", {})
        token_id = params.get("token_id", "")

        if not token_id:
            return _error("token_id is required")

        query = {
            "market": token_id,
            "interval": params.get("interval", "max"),
            "fidelity": int(params.get("fidelity", 120)),
        }

        response = _clob_request("/prices-history", params=query, ttl=60)
        err = _check_error(response)
        if err:
            return err

        history = (
            response.get("history", []) if isinstance(response, dict) else response
        )
        if not isinstance(history, list):
            history = []

        return _success(
            {"history": history, "count": len(history), "token_id": token_id},
            f"Retrieved {len(history)} price data points",
        )

    except Exception as e:
        return _error(f"Error fetching price history: {str(e)}")


def get_last_trade_price(request_data):
    """Get the most recent trade price for a market via CLOB API.

    Params:
        token_id (str): CLOB token ID (required)
    """
    try:
        params = request_data.get("params", {})
        token_id = params.get("token_id", "")

        if not token_id:
            return _error("token_id is required")

        response = _clob_request(
            "/last-trade-price", params={"token_id": token_id}, ttl=15
        )
        err = _check_error(response)
        if err:
            return err

        return _success(
            {
                "token_id": token_id,
                "price": _safe_float(response.get("price")),
                "side": response.get("side", ""),
            },
            f"Last trade price: {response.get('price', 'N/A')}",
        )

    except Exception as e:
        return _error(f"Error fetching last trade price: {str(e)}")


def get_esports_events(request_data):
    """Esports prediction markets on Polymarket (implied probabilities via outcome prices).

    Params:
        query (str): Optional keyword filter (e.g. 'LoL', 'CS2', team name).
        limit (int): Max events (default 30, max 100).
        closed (bool): Include closed events (default False).
    """
    try:
        params = request_data.get("params", {})
        query = str(params.get("query") or "").lower()
        q = {
            "tag_slug": "esports",
            "closed": str(params.get("closed", False)).lower(),
            "limit": min(int(params.get("limit", 30)), 100),
            "order": "volume",
            "ascending": "false",
        }
        response = _gamma_request("/events", params=q, ttl=60)
        err = _check_error(response)
        if err:
            return err
        events = (
            response if isinstance(response, list) else response.get("events", response)
        )
        if not isinstance(events, list):
            events = []
        normalized = [_normalize_event(e) for e in events]
        if query:
            normalized = [
                e
                for e in normalized
                if query in e.get("title", "").lower()
                or query in e.get("slug", "").lower()
            ]
        return _success(
            {"events": normalized, "count": len(normalized)},
            f"Retrieved {len(normalized)} esports events",
        )
    except Exception as e:
        return _error(f"Error fetching esports events: {str(e)}")
