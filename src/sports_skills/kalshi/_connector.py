"""Kalshi prediction market API client — public read-only endpoints.

Wraps the Kalshi Trade API v2 for market data discovery.
No authentication required for public endpoints.
Uses stdlib only (urllib, json, threading).
"""

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

# ============================================================
# Configuration
# ============================================================

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

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
# Rate Limiter (Token Bucket)
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


_rate_limiter = _RateLimiter(max_tokens=10, refill_rate=10.0)


# ============================================================
# HTTP Helpers
# ============================================================

_USER_AGENT = "sports-skills/0.1 (Python; stdlib)"


def _request(endpoint, params=None, ttl=120):
    """Make a GET request to the Kalshi API. Cached."""
    cache_key = f"kalshi:{endpoint}:{json.dumps(params or {}, sort_keys=True)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    _rate_limiter.acquire()
    url = f"{BASE_URL}{endpoint}"
    if params:
        clean = {k: v for k, v in params.items() if v is not None and v != ""}
        if clean:
            url += "?" + urllib.parse.urlencode(clean, doseq=True)

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
    if isinstance(response, dict) and response.get("error"):
        code = response.get("status_code", "unknown")
        msg = response.get("message", "Unknown error")
        return _error(f"API error ({code}): {msg}")
    return None


# ============================================================
# Commands — Public Endpoints
# ============================================================


def get_exchange_status(request_data):
    """Get exchange status (trading active, maintenance windows).

    No params required.
    """
    try:
        response = _request("/exchange/status", ttl=30)
        err = _check_error(response)
        if err:
            return err
        return _success(response, "Exchange status retrieved")
    except Exception as e:
        return _error(f"Error fetching exchange status: {str(e)}")


def get_exchange_schedule(request_data):
    """Get exchange operating schedule.

    No params required.
    """
    try:
        response = _request("/exchange/schedule", ttl=3600)
        err = _check_error(response)
        if err:
            return err
        return _success(response, "Exchange schedule retrieved")
    except Exception as e:
        return _error(f"Error fetching exchange schedule: {str(e)}")


def get_series_list(request_data):
    """Get all available series (leagues, recurring event groups).

    Params:
        category (str): Filter by series category
        tags (str): Filter by tags
    """
    try:
        params = request_data.get("params", {})
        query = {}
        if params.get("category"):
            query["category"] = params["category"]
        if params.get("tags"):
            query["tags"] = params["tags"]

        response = _request("/series", params=query if query else None, ttl=600)
        err = _check_error(response)
        if err:
            return err

        series = response.get("series") or []
        return _success(
            {"series": series, "count": len(series)}, f"Retrieved {len(series)} series"
        )
    except Exception as e:
        return _error(f"Error fetching series list: {str(e)}")


def get_series(request_data):
    """Get details for a specific series.

    Params:
        series_ticker (str): Series ticker (required)
    """
    try:
        params = request_data.get("params", {})
        ticker = params.get("series_ticker", "")
        if not ticker:
            return _error("series_ticker is required")

        response = _request(f"/series/{ticker}", ttl=300)
        err = _check_error(response)
        if err:
            return err

        return _success(response.get("series", response), f"Retrieved series: {ticker}")
    except Exception as e:
        return _error(f"Error fetching series: {str(e)}")


def get_events(request_data):
    """Get events with optional filtering.

    Params:
        limit (int): Max results per page (default: 100, max: 200)
        cursor (str): Pagination cursor
        status (str): Filter by status ('open', 'closed', 'settled')
        series_ticker (str): Filter by series ticker
        with_nested_markets (bool): Include nested markets (default: False)
    """
    try:
        params = request_data.get("params", {})
        query = {
            "limit": min(int(params.get("limit", 100)), 200),
        }
        if params.get("cursor"):
            query["cursor"] = params["cursor"]
        if params.get("status"):
            query["status"] = params["status"]
        if params.get("series_ticker"):
            query["series_ticker"] = params["series_ticker"]
        if params.get("with_nested_markets"):
            query["with_nested_markets"] = "true"

        response = _request("/events", params=query, ttl=60)
        err = _check_error(response)
        if err:
            return err

        events = response.get("events", [])
        return _success(
            {
                "events": events,
                "count": len(events),
                "cursor": response.get("cursor", ""),
            },
            f"Retrieved {len(events)} events",
        )
    except Exception as e:
        return _error(f"Error fetching events: {str(e)}")


def get_event(request_data):
    """Get details for a specific event.

    Params:
        event_ticker (str): Event ticker (required)
        with_nested_markets (bool): Include nested markets (default: False)
    """
    try:
        params = request_data.get("params", {})
        ticker = params.get("event_ticker", "")
        if not ticker:
            return _error("event_ticker is required")

        query = {}
        if params.get("with_nested_markets"):
            query["with_nested_markets"] = "true"

        response = _request(
            f"/events/{ticker}", params=query if query else None, ttl=60
        )
        err = _check_error(response)
        if err:
            return err

        return _success(
            {
                "event": response.get("event", {}),
                "markets": response.get("markets", []),
            },
            f"Retrieved event: {ticker}",
        )
    except Exception as e:
        return _error(f"Error fetching event: {str(e)}")


def get_markets(request_data):
    """Get markets with optional filtering.

    Params:
        limit (int): Max results (default: 100)
        cursor (str): Pagination cursor
        event_ticker (str): Filter by event
        series_ticker (str): Filter by series
        status (str): Filter by status ('unopened', 'open', 'closed', 'settled')
        tickers (str): Comma-separated market tickers
    """
    try:
        params = request_data.get("params", {})
        query = {
            "limit": min(int(params.get("limit", 100)), 200),
        }
        if params.get("cursor"):
            query["cursor"] = params["cursor"]
        if params.get("event_ticker"):
            query["event_ticker"] = params["event_ticker"]
        if params.get("series_ticker"):
            query["series_ticker"] = params["series_ticker"]
        if params.get("status"):
            query["status"] = params["status"]
        if params.get("tickers"):
            query["tickers"] = params["tickers"]

        response = _request("/markets", params=query, ttl=60)
        err = _check_error(response)
        if err:
            return err

        markets = response.get("markets", [])
        return _success(
            {
                "markets": markets,
                "count": len(markets),
                "cursor": response.get("cursor", ""),
            },
            f"Retrieved {len(markets)} markets",
        )
    except Exception as e:
        return _error(f"Error fetching markets: {str(e)}")


def get_market(request_data):
    """Get details for a specific market.

    Params:
        ticker (str): Market ticker (required)
    """
    try:
        params = request_data.get("params", {})
        ticker = params.get("ticker", "")
        if not ticker:
            return _error("ticker is required")

        response = _request(f"/markets/{ticker}", ttl=60)
        err = _check_error(response)
        if err:
            return err

        return _success(response.get("market", response), f"Retrieved market: {ticker}")
    except Exception as e:
        return _error(f"Error fetching market: {str(e)}")


def get_market_orderbook(request_data):
    """Get the order book (bid depth) for a specific market.

    Kalshi returns yes/no bid levels as dollar-string pairs under
    ``orderbook_fp`` (e.g. ``{"yes_dollars": [["0.1600", "42.55"], ...]}``);
    legacy integer-cent levels appear under ``orderbook`` when present.
    Both forms are returned untouched.

    Params:
        ticker (str): Market ticker (required)
        depth (int): Max price levels per side (optional)
    """
    try:
        params = request_data.get("params", {})
        ticker = params.get("ticker", "")
        if not ticker:
            return _error("ticker is required")

        query = {}
        if params.get("depth"):
            query["depth"] = int(params["depth"])

        response = _request(
            f"/markets/{ticker}/orderbook", params=query or None, ttl=15
        )
        err = _check_error(response)
        if err:
            return err

        orderbook = response.get("orderbook_fp") or response.get("orderbook") or {}
        return _success(
            {"ticker": ticker, "orderbook": orderbook},
            f"Retrieved order book: {ticker}",
        )
    except Exception as e:
        return _error(f"Error fetching order book: {str(e)}")


def get_trades(request_data):
    """Get recent trades with optional filtering.

    Params:
        limit (int): Max results (default: 100, max: 1000)
        cursor (str): Pagination cursor
        ticker (str): Filter by market ticker
        min_ts (int): Filter trades after this Unix timestamp
        max_ts (int): Filter trades before this Unix timestamp
    """
    try:
        params = request_data.get("params", {})
        query = {
            "limit": min(int(params.get("limit", 100)), 1000),
        }
        if params.get("cursor"):
            query["cursor"] = params["cursor"]
        if params.get("ticker"):
            query["ticker"] = params["ticker"]
        if params.get("min_ts"):
            query["min_ts"] = int(params["min_ts"])
        if params.get("max_ts"):
            query["max_ts"] = int(params["max_ts"])

        response = _request("/markets/trades", params=query, ttl=30)
        err = _check_error(response)
        if err:
            return err

        trades = response.get("trades", [])
        return _success(
            {
                "trades": trades,
                "count": len(trades),
                "cursor": response.get("cursor", ""),
            },
            f"Retrieved {len(trades)} trades",
        )
    except Exception as e:
        return _error(f"Error fetching trades: {str(e)}")


def get_market_candlesticks(request_data):
    """Get candlestick (OHLC) data for a market.

    Params:
        series_ticker (str): Series ticker (required)
        ticker (str): Market ticker (required)
        start_ts (int): Start Unix timestamp (required)
        end_ts (int): End Unix timestamp (required)
        period_interval (int): Candlestick interval in minutes: 1, 60, or 1440 (required)
    """
    try:
        params = request_data.get("params", {})
        series_ticker = params.get("series_ticker", "")
        ticker = params.get("ticker", "")
        if not series_ticker or not ticker:
            return _error("series_ticker and ticker are required")

        start_ts = params.get("start_ts")
        end_ts = params.get("end_ts")
        period = params.get("period_interval")
        if not all([start_ts, end_ts, period]):
            return _error("start_ts, end_ts, and period_interval are required")

        query = {
            "start_ts": int(start_ts),
            "end_ts": int(end_ts),
            "period_interval": int(period),
        }

        response = _request(
            f"/series/{series_ticker}/markets/{ticker}/candlesticks",
            params=query,
            ttl=60,
        )
        err = _check_error(response)
        if err:
            return err

        candlesticks = response.get("candlesticks", [])
        return _success(
            {
                "ticker": ticker,
                "candlesticks": candlesticks,
                "count": len(candlesticks),
            },
            f"Retrieved {len(candlesticks)} candlesticks",
        )
    except Exception as e:
        return _error(f"Error fetching candlesticks: {str(e)}")


def get_sports_filters(request_data):
    """Get available sports filter categories (leagues, teams, etc.).

    No params required.
    """
    try:
        response = _request("/search/filters_by_sport", ttl=3600)
        err = _check_error(response)
        if err:
            return err
        return _success(response, "Sports filters retrieved")
    except Exception as e:
        return _error(f"Error fetching sports filters: {str(e)}")


# ============================================================
# Sport-aware convenience commands
# ============================================================

# Maps common sport codes to Kalshi series tickers.
# Each sport maps to a list of series tickers to query.
# Football leagues have multiple series per league (game, total, btts, spread, goal).
KALSHI_SERIES = {
    # US sports — single series per sport
    "nfl": ["KXNFL", "KXNFLGAME", "KXNFLSPREAD", "KXNFLTOTAL", "KXNFLTEAMTOTAL", "KXNFLANYTD", "KXNFL1HWINNER", "KXNFL2HWINNER"],
    "nba": ["KXNBA", "KXNBAGAME", "KXNBASPREAD", "KXNBATOTAL", "KXNBATEAMTOTAL", "KXNBAPTS", "KXNBAPRA", "KXNBAREB", "KXNBAAST", "KXNBA3PT"],
    "mlb": ["KXMLB", "KXMLBGAME", "KXMLBSPREAD", "KXMLBTOTAL", "KXMLBTEAMTOTAL", "KXMLBHR", "KXMLB1H"],
    "nhl": ["KXNHL", "KXNHLGAME", "KXNHLSPREAD", "KXNHLTOTAL", "KXNHLTEAMTOTAL", "KXNHLPTS", "KXNHLGOAL"],
    "wnba": ["KXWNBA", "KXWNBAGAME", "KXWNBASPREAD", "KXWNBATOTAL", "KXWNBAPTS"],
    "cfb": ["KXCFB", "KXCFBGAME", "KXCFBSPREAD", "KXCFBTOTAL"],
    "cbb": ["KXCBB", "KXCBBSPREAD", "KXCBBCGAME", "KXCBBTOTAL"],
    # Football — multiple series per league (game, total, btts, spread, goal)
    "epl": ["KXEPLGAME", "KXEPLTOTAL", "KXEPLBTTS", "KXEPLSPREAD", "KXEPLGOAL"],
    "ucl": ["KXUCL", "KXUEFAGAME"],
    "laliga": ["KXLALIGA"],
    "bundesliga": ["KXBUNDESLIGA"],
    "seriea": ["KXSERIEA"],
    "ligue1": ["KXLIGUE1"],
    "mls": ["KXMLSGAME"],
    # FIFA World Cup 2026 — winner, match, group, and futures series. These
    # markets are NOT reachable via the no-sport /events page scan (that
    # returns one page of all Kalshi events); series tickers are the only path.
    "worldcup": [
        "KXMENWORLDCUP",      # tournament winner
        "KXWCGAME",           # match winners
        "KXWCGROUPQUAL",      # group qualification
        "KXWCGROUPORDER",     # group exact order
        "KXWCSTAGE",          # furthest stage advanced
        "KXWCHOSTSTAGE",      # furthest stage by a host nation
        "KXWCBESTHOST",       # best performing host nation
        "KXWCNOEURSA",        # winner outside Europe/South America
        "KXWCREGIONKO",       # region teams reaching knockout stage
        "KXWCEVERYTEAMGOAL",  # every team to score a goal
    ],
}


def get_sports_config(request_data):
    """Get available sport codes and their Kalshi series tickers.

    Returns the mapping you can use with search_markets(sport=...) and
    get_todays_events(sport=...).

    No params required.
    """
    sports = [
        {"sport": code, "series_tickers": tickers}
        for code, tickers in sorted(KALSHI_SERIES.items())
    ]
    return _success(
        {"sports": sports, "count": len(sports)},
        f"Retrieved {len(sports)} sport configurations",
    )


def get_todays_events(request_data):
    """Get today's events (single-game markets) for a specific sport.

    Returns open events filtered by series ticker, with nested markets.

    Params:
        sport (str): Sport code (required) — 'nba', 'nfl', 'nhl', 'mlb',
            'wnba', 'cfb', 'cbb', 'epl', 'ucl', 'laliga', 'bundesliga',
            'seriea', 'ligue1', 'mls', 'worldcup'.
        limit (int): Max events (default: 50, max: 200).
    """
    try:
        params = request_data.get("params", {})
        sport = str(params.get("sport") or "").lower()
        limit = min(int(params.get("limit", 50)), 200)

        if not sport:
            available = ", ".join(sorted(KALSHI_SERIES.keys()))
            return _error(
                f"sport is required. Available: {available}"
            )

        series_tickers = KALSHI_SERIES.get(sport)
        if not series_tickers:
            available = ", ".join(sorted(KALSHI_SERIES.keys()))
            return _error(f"Unknown sport '{sport}'. Available: {available}")

        # Query all series tickers for this sport and merge results
        all_events = []
        seen_tickers = set()
        for series_ticker in series_tickers:
            query = {
                "limit": limit,
                "series_ticker": series_ticker,
                "status": "open",
                "with_nested_markets": "true",
            }

            response = _request("/events", params=query, ttl=60)
            err = _check_error(response)
            if err:
                continue

            for event in response.get("events", []):
                event_ticker = event.get("event_ticker", "")
                if event_ticker not in seen_tickers:
                    seen_tickers.add(event_ticker)
                    # Kalshi's dollars migration dropped the legacy cent
                    # fields from nested markets; re-inject them so the
                    # documented 0-100 price fields stay readable.
                    for m in event.get("markets", []) or []:
                        m["yes_bid"] = _price_cents(m, "yes_bid")
                        m["no_bid"] = _price_cents(m, "no_bid")
                        m["last_price"] = _price_cents(m, "last_price")
                        m["volume"] = _volume_units(m)
                    all_events.append(event)

        return _success(
            {"events": all_events[:limit], "count": len(all_events[:limit]), "sport": sport},
            f"Retrieved {len(all_events[:limit])} {sport.upper()} events",
        )

    except Exception as e:
        return _error(f"Error fetching today's events: {str(e)}")


def _price_cents(market, key):
    """Read a market price in cents, tolerating Kalshi's dollars migration.

    Kalshi's API moved from integer-cent fields (``yes_bid: 29``) to
    dollar-string fields (``yes_bid_dollars: "0.2900"``); nested market
    objects on /events now carry only the dollar form. Prefer the legacy
    cent field when present and non-zero, fall back to converting the
    dollar string back to cents so the compact record keeps its
    documented 0-100 unit.
    """
    value = market.get(key)
    if value not in (None, "", 0, "0"):
        return value
    raw = market.get(f"{key}_dollars")
    if raw not in (None, ""):
        try:
            return round(float(raw) * 100)
        except (TypeError, ValueError):
            pass
    return 0


def _volume_units(market):
    """Read market volume, tolerating the *_fp string-field migration."""
    value = market.get("volume")
    if value not in (None, "", 0, "0"):
        return value
    raw = market.get("volume_fp")
    if raw not in (None, ""):
        try:
            return float(raw)
        except (TypeError, ValueError):
            pass
    return 0


def search_markets(request_data):
    """Search Kalshi markets by sport and/or keyword.

    Params:
        sport (str): Sport code (e.g. 'nba', 'nfl', 'nhl', 'mlb', 'wnba',
            'cfb', 'cbb', 'epl', 'ucl', 'laliga', 'bundesliga', 'seriea',
            'ligue1', 'mls', 'worldcup'). Resolves to series_ticker(s) automatically.
        query (str): Keyword to match in event/market titles.
        status (str): Market status filter (default: 'open').
        limit (int): Max results (default: 50, max: 200).
    """
    try:
        params = request_data.get("params", {})
        sport = str(params.get("sport") or "").lower()
        query = str(params.get("query") or "").lower()
        status = params.get("status", "open")
        limit = min(int(params.get("limit", 50)), 200)

        # Resolve sport to series_tickers list
        explicit_ticker = params.get("series_ticker")
        if explicit_ticker:
            series_tickers = [explicit_ticker]
        elif sport:
            series_tickers = KALSHI_SERIES.get(sport, [])
        else:
            series_tickers = []

        # Fetch events across all series tickers and merge
        all_events = []
        seen_event_tickers = set()

        if series_tickers:
            for series_ticker in series_tickers:
                event_query = {
                    "limit": limit,
                    "status": status,
                    "with_nested_markets": "true",
                    "series_ticker": series_ticker,
                }
                response = _request("/events", params=event_query, ttl=60)
                if _check_error(response):
                    continue
                for event in response.get("events", []):
                    et = event.get("event_ticker", "")
                    if et not in seen_event_tickers:
                        seen_event_tickers.add(et)
                        all_events.append(event)
        else:
            # No sport filter — single query
            event_query = {
                "limit": limit,
                "status": status,
                "with_nested_markets": "true",
            }
            response = _request("/events", params=event_query, ttl=60)
            err = _check_error(response)
            if err:
                return err
            all_events = response.get("events", [])

        # Filter by query if provided
        all_markets = []
        for event in all_events:
            title = event.get("title", "")

            # Normalization for Kalshi's strict team names
            normalized_query = str(query or "").lower()
            norm_map = {
                "lakers": ["los angeles l", "lakers"],
                "clippers": ["los angeles c", "clippers"],
                "warriors": ["golden state", "warriors"],
                "knicks": ["new york", "knicks"],
                "nets": ["brooklyn", "nets"],
                "timberwolves": ["minnesota", "timberwolves"],
                "spurs": ["san antonio", "spurs"],
                "thunder": ["oklahoma city", "okc", "thunder"],
                "cavaliers": ["cleveland", "cavs", "cavaliers"],
                "mavericks": ["dallas", "mavs", "mavericks"],
                "76ers": ["philadelphia", "sixers", "76ers"],
                "celtics": ["boston", "celtics"],
                "heat": ["miami", "heat"],
                "bucks": ["milwaukee", "bucks"],
                "nuggets": ["denver", "nuggets"],
                "suns": ["phoenix", "suns"],
                "pelicans": ["new orleans", "pelicans"],
                "grizzlies": ["memphis", "grizzlies"],
                "bulls": ["chicago", "bulls"],
                "kings": ["sacramento", "kings"],
                "pacers": ["indiana", "pacers"],
                "magic": ["orlando", "magic"],
                "hawks": ["atlanta", "hawks"],
                "pistons": ["detroit", "pistons"],
                "hornets": ["charlotte", "hornets"],
                "jazz": ["utah", "jazz"],
                "raptors": ["toronto", "raptors"],
                "blazers": ["portland", "trail blazers", "blazers"],
                "rockets": ["houston", "rockets"],
                "wizards": ["washington", "wizards"]
            }

            # Expand query into possible matches
            search_terms = [normalized_query]
            for mascot, kalshi_names in norm_map.items():
                if mascot in normalized_query:
                    search_terms.extend(kalshi_names)

            if query:
                # Check if ANY of our expanded search terms match the title
                title_match = any(term in str(title).lower() for term in search_terms)

                # Also check market titles
                event_match = False
                markets = event.get("markets", [])
                if not title_match:
                    for m in markets:
                        m_title = str(m.get("title", "")).lower()
                        m_sub = str(m.get("subtitle", "")).lower()
                        if any(term in m_title or term in m_sub for term in search_terms):
                            event_match = True
                            break

                if not (title_match or event_match):
                    continue

            markets = event.get("markets", [])
            for m in markets:
                all_markets.append({
                    "ticker": m.get("ticker", ""),
                    "event_ticker": event.get("event_ticker", ""),
                    "title": m.get("title", m.get("subtitle", "")),
                    "subtitle": m.get("subtitle", ""),
                    "event_title": title,
                    "yes_bid": _price_cents(m, "yes_bid"),
                    "no_bid": _price_cents(m, "no_bid"),
                    "last_price": _price_cents(m, "last_price"),
                    "volume": _volume_units(m),
                    "status": m.get("status", ""),
                })

        return _success(
            {
                "markets": all_markets[:limit],
                "count": len(all_markets[:limit]),
                "query": query or None,
                "sport": sport or None,
            },
            f"Found {len(all_markets[:limit])} markets",
        )

    except Exception as e:
        return _error(f"Error searching markets: {str(e)}")
