"""Novig exchange — public read-only catalog and order-book endpoints.

Wraps the unauthenticated Novig v3 public API (https://api.novig.com/v3/public).
GET only, no credentials, plain ``requests`` (redirects refused).

Upstream behavior (probed 2026-10-10):
- Lists are ``{"items": [...], "next": "<cursor>"}``; ``next`` is absent on
  the last page and is passed back as ``after``.
- Times are ``startsTs`` epoch milliseconds.
- Catalog markets carry outcomes, fee and void rules but no prices. Prices come
  only from ``/catalog/markets/{id}/book``: per-outcome BIDS, ``price`` a
  probability string, ``qty`` in contracts that each pay $0.01.
"""

import json
import re
import threading
import time
import urllib.parse
from datetime import datetime, timezone

import requests

from sports_skills import _replay, _response

BASE_URL = "https://api.novig.com/v3/public"

CONTRACT_PAYOUT_USD = 0.01
_PAGE_LIMIT = 50
_MAX_LIMIT = 100
_MAX_DEPTH = 20
_DAY_MS = 24 * 3600 * 1000
_MAX_PAGES = 5  # bounded scan for search/today
_MAX_SEARCH_EVENTS = 5

# From /types/leagues (2026-10-10). Static so filters validate without a request.
LEAGUES = [
    "NFL",
    "NBA",
    "MLB",
    "NHL",
    "NCAAF",
    "NCAAB",
    "NCAAWB",
    "NCAABSB",
    "WNBA",
    "UFC",
    "Boxing",
    "CFL",
    "MLS",
    "FIFA Club World Cup",
    "EPL",
    "Bundesliga",
    "Serie A",
    "La Liga",
    "Liga MX",
    "Ligue 1",
    "Champions League",
    "Europa League",
    "WTA",
    "ATP",
    "PGA",
    "TGL",
    "League of Legends",
    "Counter Strike 2",
    "Dota 2",
    "WBC",
    "FIFA World Cup",
    "Olympics Hockey Men",
    "KBO",
    "NPB",
    "UEFA Nations League",
    "ENTERTAINMENT",
]

# Sport codes used across sports-skills -> Novig league names.
LEAGUE_ALIASES = {
    "cfb": "NCAAF",
    "cbb": "NCAAB",
    "ucl": "Champions League",
    "laliga": "La Liga",
    "seriea": "Serie A",
    "ligue1": "Ligue 1",
    "worldcup": "FIFA World Cup",
}

_ID_RE = re.compile(r"^[0-9A-Za-z-]{1,64}$")

# ============================================================
# HTTP (cached, throttled, replay-aware)
# ============================================================

_cache = {}
_throttle_lock = threading.Lock()
_last_request = [0.0]
_MIN_INTERVAL = 0.25


def _get(path, params=None, ttl=15, meta=None):
    """GET a public path. Returns parsed JSON or an ``{"error": True, ...}`` dict.

    ``meta``, when given, receives ``retrieved_at`` — the original retrieval
    time, preserved across cache hits.
    """
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    hit = _cache.get(url)
    if hit and hit[1] > time.monotonic():
        if meta is not None:
            meta["retrieved_at"] = hit[2]
        return hit[0]
    raw, err = _replay.fetch(url, lambda: _live_fetch(url))
    if err is not None:
        return err
    try:
        data = json.loads(raw.decode())
    except (ValueError, UnicodeDecodeError) as exc:
        return {"error": True, "message": f"Malformed JSON from upstream: {exc}"}
    if len(_cache) > 500:
        _cache.clear()
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    _cache[url] = (data, time.monotonic() + ttl, retrieved_at)
    if meta is not None:
        meta["retrieved_at"] = retrieved_at
    return data


def _live_fetch(url):
    with _throttle_lock:
        wait = _last_request[0] + _MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_request[0] = time.monotonic()
    try:
        # A callable auth is truthy, so requests skips ~/.netrc; it adds nothing.
        resp = requests.get(
            url, headers={"Accept": "application/json"}, timeout=20, allow_redirects=False, auth=lambda r: r
        )
    except Exception as e:
        return None, {"error": True, "message": str(e)}
    if 300 <= resp.status_code < 400:
        return None, {"error": True, "status_code": resp.status_code, "message": "Redirect refused"}
    if resp.status_code >= 400:
        return None, {"error": True, "status_code": resp.status_code, "message": str(resp.reason)}
    return resp.content, None


def _fail(err):
    code = err.get("status_code", "n/a")
    return _response.wrap({**err, "message": f"Novig API error ({code}): {err.get('message', '')}"})


# ============================================================
# Validation + normalization
# ============================================================


def _resolve_league(league):
    """Novig league name for a code/alias/name, or None when unknown."""
    wanted = str(league).strip()
    wanted = LEAGUE_ALIASES.get(wanted.lower(), wanted)
    return next((name for name in LEAGUES if name.lower() == wanted.lower()), None)


def _limit(value, default=_PAGE_LIMIT):
    """Validated limit (capped at _MAX_LIMIT), or None when invalid."""
    try:
        limit = int(default if value is None else value)
    except (TypeError, ValueError):
        return None
    return min(limit, _MAX_LIMIT) if limit > 0 else None


def _valid_id(value):
    return isinstance(value, str) and bool(_ID_RE.match(value))


def _iso(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _normalize_event(event):
    return {
        "id": event.get("eventId"),
        "name": event.get("description", ""),
        "sport": event.get("sport", ""),
        "league": event.get("league", ""),
        "status": event.get("status", ""),
        "start_time": _iso(event.get("startsTs")),
        "_raw": event,
    }


def _normalize_market(market):
    return {
        "id": market.get("marketId"),
        "event_id": market.get("eventId"),
        "name": market.get("description", ""),
        "type": market.get("marketType", ""),
        "strike": market.get("strike"),
        "status": market.get("status", ""),
        "voids": market.get("voids"),
        "fee": market.get("fee"),
        "start_time": _iso(market.get("startsTs")),
        "outcomes": [
            {"id": o.get("outcomeId"), "name": o.get("name", ""), "status": o.get("status", "")}
            for o in market.get("outcomes") or []
            if isinstance(o, dict)
        ],
        "_raw": market,
    }


def _page(response):
    """(items, next) from a list envelope; items is None on schema drift."""
    if not isinstance(response, dict) or not isinstance(response.get("items"), list):
        return None, None
    return response["items"], response.get("next")


def _best_bid(levels):
    """(price, qty) at the best bid; (None, None) for empty or any junk level."""
    if not isinstance(levels, list) or not levels:
        return None, None
    parsed = []
    for level in levels:
        try:
            price, qty = float(level["price"]), float(level["qty"])
        except (TypeError, ValueError, KeyError):
            return None, None
        # Written so NaN fails both checks; inf fails the qty bound.
        if not (0 < price < 1 and 0 < qty < float("inf")):
            return None, None
        parsed.append((price, qty))
    best = max(price for price, _ in parsed)
    return best, sum(qty for price, qty in parsed if price == best)


# ============================================================
# Commands
# ============================================================


def get_sports_config(request_data):
    """Sports and leagues Novig lists, plus accepted league aliases."""
    try:
        sports = _get("/types/sports", ttl=3600)
        if isinstance(sports, dict) and sports.get("error"):
            return _fail(sports)
        leagues = _get("/types/leagues", ttl=3600)
        if isinstance(leagues, dict) and leagues.get("error"):
            return _fail(leagues)
        return _response.success(
            {"sports": sports, "leagues": leagues, "aliases": LEAGUE_ALIASES},
            f"Retrieved {len(sports)} sports and {len(leagues)} leagues",
        )
    except Exception as e:
        return _response.error(f"Error fetching Novig sports config: {e}")


def _list_params(params):
    """Shared league/limit/after validation -> (query, error)."""
    query = {}
    league = params.get("league")
    if league:
        resolved = _resolve_league(league)
        if resolved is None:
            return None, _response.error(f"Unknown league '{league}'. Valid: {', '.join(LEAGUES)}")
        query["league"] = resolved
    limit = _limit(params.get("limit"))
    if limit is None:
        return None, _response.error(f"limit must be a positive integer, got '{params.get('limit')}'")
    query["limit"] = limit
    if params.get("after"):
        query["after"] = params["after"]
    return query, None


def get_events(request_data):
    try:
        query, err = _list_params(request_data.get("params", {}))
        if err:
            return err
        response = _get("/catalog/events", query)
        if isinstance(response, dict) and response.get("error"):
            return _fail(response)
        items, cursor = _page(response)
        if items is None:
            return _response.error("Unexpected Novig events payload shape (schema drift)")
        events = [_normalize_event(e) for e in items if isinstance(e, dict)]
        data = {"events": events, "count": len(events)}
        if cursor:
            data["next"] = cursor
        return _response.success(data, f"Retrieved {len(events)} events")
    except Exception as e:
        return _response.error(f"Error fetching Novig events: {e}")


def _get_one(path, normalize, what):
    response = _get(path)
    if isinstance(response, dict) and response.get("error"):
        return _fail(response)
    if not isinstance(response, dict):
        return _response.error(f"Unexpected Novig {what} payload shape (schema drift)")
    return _response.success(normalize(response), f"Retrieved {what}")


def get_event(request_data):
    try:
        event_id = request_data.get("params", {}).get("event_id")
        if not _valid_id(event_id):
            return _response.error(f"event_id must be a Novig event id, got '{event_id}'")
        return _get_one(f"/catalog/events/{event_id}", _normalize_event, "event")
    except Exception as e:
        return _response.error(f"Error fetching Novig event: {e}")


def get_markets(request_data):
    try:
        params = request_data.get("params", {})
        query, err = _list_params(params)
        if err:
            return err
        event_id = params.get("event_id")
        if event_id is not None:
            if not _valid_id(event_id):
                return _response.error(f"event_id must be a Novig event id, got '{event_id}'")
            query["event"] = event_id
        if params.get("market_type"):
            query["marketType"] = str(params["market_type"]).upper()
        response = _get("/catalog/markets", query, ttl=10)
        if isinstance(response, dict) and response.get("error"):
            return _fail(response)
        items, cursor = _page(response)
        if items is None:
            return _response.error("Unexpected Novig markets payload shape (schema drift)")
        markets = [_normalize_market(m) for m in items if isinstance(m, dict)]
        data = {"markets": markets, "count": len(markets)}
        if cursor:
            data["next"] = cursor
        return _response.success(data, f"Retrieved {len(markets)} markets (catalog only, no prices)")
    except Exception as e:
        return _response.error(f"Error fetching Novig markets: {e}")


def get_market(request_data):
    try:
        market_id = request_data.get("params", {}).get("market_id")
        if not _valid_id(market_id):
            return _response.error(f"market_id must be a Novig market id, got '{market_id}'")
        return _get_one(f"/catalog/markets/{market_id}", _normalize_market, "market")
    except Exception as e:
        return _response.error(f"Error fetching Novig market: {e}")


def get_order_book(request_data):
    """Book bids per outcome, with a complement ask only for two-way markets."""
    try:
        params = request_data.get("params", {})
        market_id = params.get("market_id")
        if not _valid_id(market_id):
            return _response.error(f"market_id must be a Novig market id, got '{market_id}'")
        query = None
        if params.get("depth") is not None:
            try:
                depth = int(params["depth"])
            except (TypeError, ValueError):
                depth = None
            if depth is None or not 1 <= depth <= _MAX_DEPTH:
                return _response.error(f"depth must be an integer from 1 to {_MAX_DEPTH}, got '{params['depth']}'")
            query = {"depth": depth}

        market = get_market({"params": {"market_id": market_id}})
        if not market["status"]:
            return market
        meta = {}
        book = _get(f"/catalog/markets/{market_id}/book", query, ttl=5, meta=meta)
        if isinstance(book, dict) and book.get("error"):
            return _fail(book)
        orders = book.get("orders") if isinstance(book, dict) else None
        if not isinstance(orders, dict):
            return _response.error("Unexpected Novig book payload shape (schema drift)")

        outcomes = []
        for outcome in market["data"]["outcomes"]:
            price, qty = _best_bid(orders.get(outcome["id"]))
            outcomes.append(
                {
                    "id": outcome["id"],
                    "name": outcome["name"],
                    "best_bid": price,
                    "best_bid_qty": int(qty) if qty is not None else None,
                    "best_bid_payout_usd": round(qty * CONTRACT_PAYOUT_USD, 2) if qty is not None else None,
                    "derived_ask": None,
                }
            )
        # Buying one side of a two-way market matches the best bid on the other.
        if len(outcomes) == 2:
            for mine, other in ((outcomes[0], outcomes[1]), (outcomes[1], outcomes[0])):
                if other["best_bid"] is not None:
                    mine["derived_ask"] = round(1 - other["best_bid"], 4)

        return _response.success(
            {
                "market_id": market_id,
                "event_id": market["data"]["event_id"],
                "market_type": market["data"]["type"],
                "seq": book.get("seq"),
                "outcomes": outcomes,
                "contract_payout_usd": CONTRACT_PAYOUT_USD,
                "price_basis": "cached_snapshot",
                "execution_guaranteed": False,
                "retrieved_at": meta.get("retrieved_at"),
                "note": (
                    "Prices are probabilities; each contract pays $0.01. derived_ask is the complement "
                    "of the best opposite bid (1 - bid; two-way markets only). Cached snapshot as of "
                    "retrieved_at (retrieval time, not exchange time), not a fill guarantee."
                ),
                "_raw": book,
            },
            f"Retrieved book for market {market_id}",
        )
    except Exception as e:
        return _response.error(f"Error fetching Novig order book: {e}")


def _scan_events(scan_query):
    """Up to _MAX_PAGES event pages -> (events, truncated, error, warnings)."""
    events, cursor = [], None
    for _ in range(_MAX_PAGES):
        query = dict(scan_query, limit=_PAGE_LIMIT)
        if cursor:
            query["after"] = cursor
        response = _get("/catalog/events", query)
        if isinstance(response, dict) and response.get("error"):
            if events and not (response.get("replay_miss") or response.get("replay_error")):
                warning = {"stage": "events_page", "after": cursor, "message": _fail(response)["message"]}
                return events, True, None, [warning]
            return [], False, _fail(response), []
        items, cursor = _page(response)
        if items is None:
            return [], False, _response.error("Unexpected Novig events payload shape (schema drift)"), []
        events.extend(_normalize_event(e) for e in items if isinstance(e, dict))
        if not cursor or not items:
            return events, False, None, []
    return events, True, None, []


def _league_query(params):
    league = params.get("league")
    if not league:
        return {}, None
    resolved = _resolve_league(league)
    if resolved is None:
        return None, _response.error(f"Unknown league '{league}'. Valid: {', '.join(LEAGUES)}")
    return {"league": resolved}, None


def search_markets(request_data):
    """Token-AND keyword search over a bounded event scan, then catalog markets."""
    try:
        params = request_data.get("params", {})
        league_query, err = _league_query(params)
        if err:
            return err
        limit = _limit(params.get("limit"))
        if limit is None:
            return _response.error(f"limit must be a positive integer, got '{params.get('limit')}'")
        tokens = str(params.get("query") or "").lower().split()

        events, truncated, err, warnings = _scan_events(league_query)
        if err:
            return err
        matched = [e for e in events if all(t in f"{e['name']} {e['league']}".lower() for t in tokens)]
        matched.sort(key=lambda e: e["start_time"] or "9999")
        if len(matched) > _MAX_SEARCH_EVENTS:
            truncated = True

        markets, failures = [], []
        for event in matched[:_MAX_SEARCH_EVENTS]:
            market_params = {"event_id": event["id"], "limit": limit}
            if params.get("market_type"):
                market_params["market_type"] = params["market_type"]
            result = get_markets({"params": market_params})
            if not result["status"]:
                if result.get("replay_miss") or result.get("replay_error"):
                    return result
                failures.append({"stage": "event_markets", "event_id": event["id"], "message": result["message"]})
                continue
            if result["data"].get("next"):
                truncated = True
            for market in result["data"]["markets"]:
                market.update(
                    event_name=event["name"],
                    league=event["league"],
                    sport=event["sport"],
                    event_status=event["status"],
                    event_start_time=event["start_time"],
                )
                markets.append(market)
        if failures and len(failures) == len(matched[:_MAX_SEARCH_EVENTS]):
            return _response.error(
                "Every Novig market fetch failed: " + "; ".join(f"{f['event_id']}: {f['message']}" for f in failures)
            )
        warnings += failures
        if len(markets) > limit:
            truncated = True
        markets = markets[:limit]
        data = {"markets": markets, "count": len(markets), "events_scanned": len(events), "truncated": truncated}
        if warnings:
            data["warnings"] = warnings
        return _response.success(
            data,
            f"Retrieved {len(markets)} markets"
            + (" (scan truncated)" if truncated else "")
            + (f" ({len(warnings)} partial-coverage warnings)" if warnings else ""),
        )
    except Exception as e:
        return _response.error(f"Error searching Novig markets: {e}")


def get_todays_events(request_data):
    """Events starting on today's UTC date, from a bounded scan."""
    try:
        params = request_data.get("params", {})
        league_query, err = _league_query(params)
        if err:
            return err
        limit = _limit(params.get("limit"))
        if limit is None:
            return _response.error(f"limit must be a positive integer, got '{params.get('limit')}'")
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        start_ms = int(start.timestamp() * 1000)
        # Native bounds are exclusive: (start-of-day - 1ms, next start-of-day).
        bounds = {"startsAfter": start_ms - 1, "startsBefore": start_ms + _DAY_MS}
        events, truncated, err, warnings = _scan_events(dict(league_query, **bounds))
        if err:
            return err
        today = start.date().isoformat()
        todays = sorted(
            (e for e in events if (e["start_time"] or "").startswith(today)),
            key=lambda e: e["start_time"],
        )
        if len(todays) > limit:
            truncated = True
        todays = todays[:limit]
        data = {"events": todays, "count": len(todays), "date": today, "truncated": truncated}
        if warnings:
            data["warnings"] = warnings
        return _response.success(data, f"Retrieved {len(todays)} events for {today}")
    except Exception as e:
        return _response.error(f"Error fetching today's Novig events: {e}")
