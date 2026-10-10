"""Unit tests for the novig module and its markets aggregation (no network).

Upstream payloads are the real unauthenticated v3 public responses captured on
2026-10-10 (Commanders @ 49ers full-game MONEY market and its book). Transport
is faked at the shared ``_replay.fetch`` hook, or at requests' adapter for
transport tests; sockets and urlopen are denied.
"""

import copy
import importlib
import importlib.util
import json
import socket
import types
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import requests


def test_public_normalize_novig_price():
    from sports_skills import markets

    result = markets.normalize_price(price=0.4, source="novig")
    assert result["status"] is True
    assert result["data"]["implied_probability"] == pytest.approx(0.4)


BASE = "https://api.novig.com/v3/public"

SF_EVENT_ID = "01a112eb-5439-7743-96e1-9e00db6695ca"
SF_MARKET_ID = "01a112eb-54e7-7963-8beb-344308c4e05b"
SF_OUT = "01a112eb-54e7-7963-8beb-34520e3ef3d5"
WSH_OUT = "01a112eb-54e7-7963-8beb-346d078da983"
SF_START_MS = 1792455300000  # 2026-10-20T00:15:00Z (Oct 19 evening ET)
WEEK_MS = 7 * 24 * 3600 * 1000

SPORTS = ["FOOTBALL", "BASKETBALL", "BASEBALL", "ICE_HOCKEY", "SOCCER", "TENNIS"]
LEAGUES = ["NFL", "NBA", "MLB", "NHL", "NCAAF", "EPL", "Champions League", "WTA"]

SF_EVENT = {
    "eventId": SF_EVENT_ID,
    "description": "Washington Commanders @ San Francisco 49ers",
    "sport": "FOOTBALL",
    "league": "NFL",
    "status": "OPEN_PREGAME",
    "startsTs": SF_START_MS,
}

SF_MONEY = {
    "marketId": SF_MARKET_ID,
    "description": "SF",
    "eventId": SF_EVENT_ID,
    "marketType": "MONEY",
    "strike": "0",
    "status": "OPEN",
    "voids": "FMV",
    "startsTs": SF_START_MS,
    "fee": {"coefficient": "0.03", "makerCredit": "0.5", "charged": "WHEN_LIVE"},
    "outcomes": [
        {"outcomeId": SF_OUT, "name": "SF", "status": "TBD"},
        {"outcomeId": WSH_OUT, "name": "WSH", "status": "TBD"},
    ],
}

SF_BOOK = {
    "marketId": SF_MARKET_ID,
    "seq": 974,
    "orders": {
        SF_OUT: [
            {"orderId": "o1", "price": "0.775", "qty": 50000},
            {"orderId": "o2", "price": "0.775", "qty": 35734},
            {"orderId": "o3", "price": "0.77", "qty": 300000},
        ],
        WSH_OUT: [
            {"orderId": "o4", "price": "0.19", "qty": 300000},
            {"orderId": "o5", "price": "0.18", "qty": 3400},
        ],
    },
}


ERR_503 = (None, {"error": True, "status_code": 503, "message": "Service Unavailable"})


def _variant(market, market_id, market_type, prefix):
    """A sibling market on the same event (spread / period line)."""
    m = copy.deepcopy(market)
    m["marketId"] = market_id
    m["marketType"] = market_type
    for i, outcome in enumerate(m["outcomes"]):
        outcome["outcomeId"] = f"{prefix}-{i}"
    return m


def _book_for(market, prices=("0.6", "0.35")):
    return {
        "marketId": market["marketId"],
        "seq": 1,
        "orders": {
            o["outcomeId"]: [{"orderId": f"x{i}", "price": p, "qty": 1000}]
            for i, (o, p) in enumerate(zip(market["outcomes"], prices))
        },
    }


# ============================================================
# Harness
# ============================================================


def _novig():
    """Import lazily so a missing module fails tests instead of collection."""
    assert importlib.util.find_spec("sports_skills.novig") is not None, "sports_skills.novig is not implemented"
    return importlib.import_module("sports_skills.novig")


def _clear_novig_cache():
    try:
        connector = importlib.import_module("sports_skills.novig._connector")
    except ImportError:
        return
    cache = getattr(connector, "_cache", None)
    if hasattr(cache, "clear"):
        cache.clear()


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    """Deny all real network access and isolate the connector cache."""
    attempts = []

    def deny(*args, **kwargs):
        attempts.append(args)
        raise AssertionError("real network access attempted")

    monkeypatch.delenv("SPORTS_SKILLS_REPLAY", raising=False)
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(urllib.request, "urlopen", deny)
    _clear_novig_cache()
    yield
    _clear_novig_cache()
    assert not attempts, "a test reached the real network"


class _Upstream:
    """Path-routed fake for ``_replay.fetch``; records every URL requested."""

    def __init__(self):
        self.routes = {}
        self.urls = []

    def fetch(self, url, live_fetch, recordable=None):
        self.urls.append(url)
        if not url.startswith(BASE + "/"):
            return None, {"error": True, "message": f"unexpected host: {url}"}
        parts = urllib.parse.urlsplit(url)
        path = parts.path[len("/v3/public") :]
        query = dict(urllib.parse.parse_qsl(parts.query))
        route = self.routes.get(path)
        if route is None:
            return None, {"error": True, "status_code": 404, "message": "Not Found"}
        body = route(query) if callable(route) else route
        if isinstance(body, tuple):
            return body
        if isinstance(body, bytes):
            return body, None
        return json.dumps(body).encode(), None

    def queries(self, path):
        found = []
        for url in self.urls:
            parts = urllib.parse.urlsplit(url)
            if parts.path == "/v3/public" + path:
                found.append(dict(urllib.parse.parse_qsl(parts.query)))
        return found


@pytest.fixture
def upstream():
    fake = _Upstream()
    with patch("sports_skills._replay.fetch", side_effect=fake.fetch):
        yield fake


def _serve_game(upstream, event=SF_EVENT, markets=(SF_MONEY,), books=None):
    """Route one event, its markets, and per-market books."""
    books = books if books is not None else {SF_MARKET_ID: SF_BOOK}
    upstream.routes["/types/sports"] = SPORTS
    upstream.routes["/types/leagues"] = LEAGUES
    upstream.routes["/catalog/events"] = {"items": [event]}
    upstream.routes[f"/catalog/events/{event['eventId']}"] = event
    upstream.routes["/catalog/markets"] = {"items": list(markets)}
    for market in markets:
        mid = market["marketId"]
        upstream.routes[f"/catalog/markets/{mid}"] = market
        upstream.routes[f"/catalog/markets/{mid}/book"] = books.get(mid, {"marketId": mid, "seq": 1, "orders": {}})


def _ms(dt):
    return int(dt.timestamp() * 1000)


def _parse(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


# ============================================================
# Module availability / public surface
# ============================================================


def test_novig_module_is_available():
    assert importlib.util.find_spec("sports_skills.novig") is not None


def test_public_surface_is_read_only():
    nv = _novig()
    for name in (
        "get_sports_config",
        "get_events",
        "get_event",
        "get_markets",
        "get_market",
        "get_order_book",
        "search_markets",
        "get_todays_events",
    ):
        assert callable(getattr(nv, name, None)), name
    public = [n for n in dir(nv) if not n.startswith("_")]
    for name in public:
        assert not any(w in name.lower() for w in ("place", "create", "cancel", "wager", "submit", "trade")), name


# ============================================================
# Transport safety: keyless GET, fixed base URL, path-param validation
# ============================================================


@pytest.fixture
def http(monkeypatch):
    """Fake requests' transport adapter; ``http.reply`` builds each response."""
    sent = []

    def send(adapter, request, **kwargs):
        sent.append((request, kwargs))
        result = http.reply(request)
        if isinstance(result, Exception):
            raise result
        status, body, headers = result
        resp = requests.Response()
        resp.status_code, resp._content, resp.reason = status, body, "Reason"
        resp.headers.update(headers)
        resp.url, resp.request = request.url, request
        return resp

    http = types.SimpleNamespace(sent=sent, reply=lambda request: (200, json.dumps(SPORTS).encode(), {}))
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    return http


def test_requests_are_keyless_gets_to_fixed_base(http, monkeypatch, tmp_path):
    netrc = tmp_path / "netrc"
    netrc.write_text("machine api.novig.com login user password sekret-netrc\n")
    monkeypatch.setenv("NETRC", str(netrc))
    monkeypatch.setenv("NOVIG_API_KEY", "sekret-token")
    _novig().get_sports_config()

    assert http.sent
    for req, kwargs in http.sent:
        assert req.method == "GET"
        assert req.url.startswith(BASE + "/")
        assert kwargs["timeout"] == 20
        headers = {k.lower(): v for k, v in req.headers.items()}
        assert not {"authorization", "cookie", "x-api-key"} & set(headers)
        assert "sekret" not in req.url
        assert "sekret" not in " ".join(headers.values())


def test_redirect_is_error_not_followed(http):
    http.reply = lambda request: (302, b"<html>moved</html>", {"Location": "https://evil.example/x"})
    result = _novig().get_event(event_id=SF_EVENT_ID)
    assert result["status"] is False
    assert "302" in result["message"]
    assert "redirect" in result["message"].lower()
    assert len(http.sent) == 1


@pytest.mark.parametrize("status", [403, 429])
def test_http_error_is_reported_once_without_retry(http, status):
    http.reply = lambda request: (status, b"<html>blocked</html>", {})
    result = _novig().get_event(event_id=SF_EVENT_ID)
    assert result["status"] is False
    assert str(status) in result["message"]
    assert len(http.sent) == 1


@pytest.mark.parametrize("exc", [requests.ConnectionError("conn refused"), requests.Timeout("read timed out")])
def test_network_errors_are_wrapped(http, exc):
    http.reply = lambda request: exc
    result = _novig().get_event(event_id=SF_EVENT_ID)
    assert result["status"] is False
    assert str(exc) in result["message"]


@pytest.mark.parametrize(
    "call",
    [
        lambda nv: nv.get_event(event_id="../types/sports"),
        lambda nv: nv.get_market(market_id="https://evil.example/x"),
        lambda nv: nv.get_order_book(market_id=f"{SF_MARKET_ID}/../../x"),
        lambda nv: nv.get_markets(event_id="x&league=NFL"),
    ],
)
def test_invalid_ids_fail_cleanly_without_fetching(upstream, call):
    result = call(_novig())
    assert result["status"] is False
    assert result["message"]
    assert upstream.urls == []


# ============================================================
# Response shapes (real probe payloads)
# ============================================================


def test_sports_config_lists_sports_and_leagues(upstream):
    _serve_game(upstream)
    result = _novig().get_sports_config()
    assert result["status"] is True
    assert "FOOTBALL" in result["data"]["sports"]
    assert "NFL" in result["data"]["leagues"]


def test_event_shape_keeps_context_and_raw(upstream):
    _serve_game(upstream)
    result = _novig().get_event(event_id=SF_EVENT_ID)
    assert result["status"] is True
    event = result["data"]
    assert event["id"] == SF_EVENT_ID
    assert event["name"] == "Washington Commanders @ San Francisco 49ers"
    assert event["league"] == "NFL"
    assert event["sport"] == "FOOTBALL"
    assert event["status"] == "OPEN_PREGAME"
    assert _parse(event["start_time"]) == datetime(2026, 10, 20, 0, 15, tzinfo=timezone.utc)
    assert event["_raw"] == SF_EVENT


def test_catalog_market_keeps_rules_fees_and_never_prices(upstream):
    _serve_game(upstream)
    result = _novig().get_market(market_id=SF_MARKET_ID)
    assert result["status"] is True
    market = result["data"]
    assert market["id"] == SF_MARKET_ID
    assert market["event_id"] == SF_EVENT_ID
    assert market["type"] == "MONEY"
    assert market["status"] == "OPEN"
    assert market["voids"] == "FMV"
    assert market["fee"] == SF_MONEY["fee"]
    assert market["_raw"] == SF_MONEY
    assert [(o["id"], o["name"]) for o in market["outcomes"]] == [(SF_OUT, "SF"), (WSH_OUT, "WSH")]
    for outcome in market["outcomes"]:
        assert outcome.get("price") is None
        assert outcome.get("implied_probability") is None
    assert not any(u.endswith("/book") or "/book?" in u for u in upstream.urls)


# ============================================================
# Pagination and filter mapping
# ============================================================


def test_events_map_league_limit_and_preserve_cursor(upstream):
    upstream.routes["/catalog/events"] = {"items": [SF_EVENT], "next": "cursor-2"}
    result = _novig().get_events(league="nfl", limit=2, after="cursor-1")
    assert result["status"] is True
    assert upstream.queries("/catalog/events") == [{"league": "NFL", "limit": "2", "after": "cursor-1"}]
    assert result["data"]["count"] == 1
    assert result["data"]["events"][0]["id"] == SF_EVENT_ID
    assert result["data"]["next"] == "cursor-2"


def test_markets_map_event_and_market_type(upstream):
    upstream.routes["/catalog/markets"] = {"items": [SF_MONEY]}
    result = _novig().get_markets(event_id=SF_EVENT_ID, market_type="MONEY", limit=2)
    assert result["status"] is True
    assert upstream.queries("/catalog/markets") == [{"event": SF_EVENT_ID, "marketType": "MONEY", "limit": "2"}]
    assert result["data"]["markets"][0]["id"] == SF_MARKET_ID
    assert not result["data"].get("next")


def test_unknown_league_fails_without_fetching_events(upstream):
    upstream.routes["/types/leagues"] = LEAGUES
    result = _novig().get_events(league="quidditch")
    assert result["status"] is False
    assert "quidditch" in result["message"]
    assert upstream.queries("/catalog/events") == []


@pytest.mark.parametrize("limit", [0, -5, "many"])
def test_invalid_limit_fails_without_fetching(upstream, limit):
    result = _novig().get_events(league="NFL", limit=limit)
    assert result["status"] is False
    assert upstream.queries("/catalog/events") == []


def test_search_is_bounded_and_honest_about_truncation(upstream):
    upstream.routes["/types/leagues"] = LEAGUES

    def endless(query):
        n = len(upstream.urls)
        other = dict(SF_EVENT, eventId=f"01a112eb-0000-7000-8000-{n:012d}", description="Bears @ Lions")
        return {"items": [other], "next": f"c{n}"}

    upstream.routes["/catalog/events"] = endless
    result = _novig().search_markets(query="zebras", league="NFL")
    assert result["status"] is True
    assert result["data"]["markets"] == []
    assert result["data"]["truncated"] is True
    assert len(upstream.urls) <= 25


def test_search_matches_tokens_and_keeps_event_context(upstream):
    _serve_game(upstream)
    result = _novig().search_markets(query="Commanders 49ers", league="NFL", market_type="MONEY")
    assert result["status"] is True
    assert result["data"]["truncated"] is False
    market = next(m for m in result["data"]["markets"] if m["id"] == SF_MARKET_ID)
    assert market["event_name"] == "Washington Commanders @ San Francisco 49ers"
    assert market["league"] == "NFL"
    assert _parse(market["start_time"]) == datetime(2026, 10, 20, 0, 15, tzinfo=timezone.utc)


def test_search_marks_truncated_when_event_markets_have_next_page(upstream):
    _serve_game(upstream)
    upstream.routes["/catalog/markets"] = {"items": [SF_MONEY], "next": "m2"}
    result = _novig().search_markets(query="Commanders 49ers", league="NFL")
    assert result["status"] is True
    assert result["data"]["truncated"] is True


def test_search_marks_truncated_when_limit_drops_markets(upstream):
    spread = _variant(SF_MONEY, "01a112eb-2222-7000-8000-000000000001", "SPREAD", "sp")
    _serve_game(upstream, markets=(SF_MONEY, spread))
    result = _novig().search_markets(query="Commanders 49ers", league="NFL", limit=1)
    assert result["data"]["count"] == 1
    assert result["data"]["truncated"] is True


def test_search_warns_when_later_event_page_fails(upstream):
    _serve_game(upstream)
    upstream.routes["/catalog/events"] = lambda q: ERR_503 if q.get("after") else {"items": [SF_EVENT], "next": "c2"}
    result = _novig().search_markets(query="Commanders 49ers", league="NFL")
    assert result["status"] is True
    assert result["data"]["truncated"] is True
    assert [m["id"] for m in result["data"]["markets"]] == [SF_MARKET_ID]
    assert "503" in str(result["data"]["warnings"])


def test_search_fails_when_every_market_fetch_fails(upstream):
    _serve_game(upstream)
    upstream.routes["/catalog/markets"] = ERR_503
    result = _novig().search_markets(query="Commanders 49ers", league="NFL")
    assert result["status"] is False
    assert "503" in result["message"]


def test_search_warns_on_partial_market_fetch_failure(upstream):
    other = dict(SF_EVENT, eventId="01a112eb-5555-7000-8000-000000000001")
    _serve_game(upstream)
    upstream.routes["/catalog/events"] = {"items": [SF_EVENT, other]}
    upstream.routes["/catalog/markets"] = lambda q: (
        ERR_503 if q.get("event") == other["eventId"] else {"items": [SF_MONEY]}
    )
    result = _novig().search_markets(query="Commanders 49ers", league="NFL")
    assert result["status"] is True
    assert [m["id"] for m in result["data"]["markets"]] == [SF_MARKET_ID]
    assert len(result["data"]["warnings"]) == 1
    assert other["eventId"] in str(result["data"]["warnings"])


# ============================================================
# Empty / error data
# ============================================================


def test_empty_events_page_is_empty_success(upstream):
    upstream.routes["/catalog/events"] = {"items": []}
    result = _novig().get_events(league="NFL")
    assert result["status"] is True
    assert result["data"]["events"] == []
    assert result["data"]["count"] == 0
    assert not result["data"].get("next")


def test_upstream_http_error_is_informative(upstream):
    result = _novig().get_event(event_id=SF_EVENT_ID)  # no route -> 404
    assert result["status"] is False
    assert "404" in result["message"]


def test_malformed_json_is_error_not_crash(upstream):
    upstream.routes["/catalog/events"] = b"<html>WAF</html>"
    result = _novig().get_events(league="NFL")
    assert result["status"] is False
    assert result["message"]


# ============================================================
# UTC today
# ============================================================


def test_todays_events_filter_by_utc_date(upstream):
    upstream.routes["/types/leagues"] = LEAGUES
    now = datetime.now(timezone.utc)
    today = dict(
        SF_EVENT,
        eventId="01a112eb-1111-7000-8000-000000000001",
        startsTs=_ms(now.replace(hour=12, minute=0, second=0, microsecond=0)),
    )
    old = dict(
        SF_EVENT,
        eventId="01a112eb-1111-7000-8000-000000000002",
        startsTs=_ms(datetime(2020, 1, 1, 12, tzinfo=timezone.utc)),
    )
    upstream.routes["/catalog/events"] = {"items": [today, old]}

    result = _novig().get_todays_events(league="NFL")
    assert result["status"] is True
    assert result["data"]["date"] == now.date().isoformat()
    assert [e["id"] for e in result["data"]["events"]] == [today["eventId"]]


def test_todays_events_requests_native_utc_day_bounds(upstream):
    upstream.routes["/catalog/events"] = {"items": []}
    _novig().get_todays_events(league="NFL")
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    query = upstream.queries("/catalog/events")[0]
    assert query["startsAfter"] == str(_ms(start) - 1)
    assert query["startsBefore"] == str(_ms(start + timedelta(days=1)))


def test_todays_events_marks_limit_truncation(upstream):
    noon = _ms(datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0))
    first = dict(SF_EVENT, eventId="01a112eb-1111-7000-8000-000000000001", startsTs=noon)
    second = dict(SF_EVENT, eventId="01a112eb-1111-7000-8000-000000000002", startsTs=noon + 60000)
    upstream.routes["/catalog/events"] = {"items": [first, second]}
    result = _novig().get_todays_events(league="NFL", limit=1)
    assert result["data"]["count"] == 1
    assert result["data"]["truncated"] is True


# ============================================================
# Order book: probability units, $0.01 contracts, bid sides
# ============================================================


def _book_outcomes(result):
    return {o["name"]: o for o in result["data"]["outcomes"]}


def test_order_book_units_and_derived_complement_ask(upstream):
    _serve_game(upstream)
    result = _novig().get_order_book(market_id=SF_MARKET_ID, depth=2)
    assert result["status"] is True
    assert upstream.queries(f"/catalog/markets/{SF_MARKET_ID}/book") == [{"depth": "2"}]
    data = result["data"]
    assert data["market_id"] == SF_MARKET_ID
    assert data["seq"] == 974
    assert data["contract_payout_usd"] == 0.01
    assert data["price_basis"] == "cached_snapshot"
    assert data["execution_guaranteed"] is False
    assert data["_raw"] == SF_BOOK

    sf, wsh = _book_outcomes(result)["SF"], _book_outcomes(result)["WSH"]
    assert sf["id"] == SF_OUT
    assert sf["best_bid"] == pytest.approx(0.775)  # probability, not a string
    assert sf["best_bid_qty"] == 85734  # summed at the best price level
    assert sf["best_bid_payout_usd"] == pytest.approx(857.34)  # qty x $0.01, not x $1
    assert wsh["best_bid"] == pytest.approx(0.19)
    # Books are bids by outcome: buying SF means matching the best WSH bid.
    assert sf["derived_ask"] == pytest.approx(0.81)
    assert wsh["derived_ask"] == pytest.approx(0.225)


def test_no_derived_ask_without_exactly_two_outcomes(upstream):
    three_way = copy.deepcopy(SF_MONEY)
    three_way["marketType"] = "1X2"
    three_way["outcomes"].append({"outcomeId": "draw-out", "name": "Draw", "status": "TBD"})
    _serve_game(upstream, markets=(three_way,), books={SF_MARKET_ID: _book_for(three_way, ("0.4", "0.3", "0.25"))})
    result = _novig().get_order_book(market_id=SF_MARKET_ID)
    assert result["status"] is True
    outcomes = _book_outcomes(result)
    assert outcomes["Draw"]["best_bid"] == pytest.approx(0.25)
    assert all(o["derived_ask"] is None for o in outcomes.values())


@pytest.mark.parametrize(
    "orders",
    [
        {},
        {SF_OUT: [], WSH_OUT: []},
        {
            SF_OUT: [{"orderId": "bad", "price": "abc", "qty": 10}],
            WSH_OUT: [{"orderId": "neg", "price": "0.2", "qty": -1}],
        },
        {
            SF_OUT: [{"orderId": "nan", "price": "NaN", "qty": 10}],
            WSH_OUT: [{"orderId": "inf", "price": "0.2", "qty": "Infinity"}],
        },
        {SF_OUT: [{"orderId": "noqty", "price": "0.5"}], WSH_OUT: [{"orderId": "noprice", "qty": 10}]},
    ],
)
def test_empty_or_malformed_book_never_implies_zero_odds(upstream, orders):
    _serve_game(upstream, books={SF_MARKET_ID: {"marketId": SF_MARKET_ID, "seq": 5, "orders": orders}})
    result = _novig().get_order_book(market_id=SF_MARKET_ID)
    assert result["status"] is True
    for outcome in result["data"]["outcomes"]:
        assert outcome["best_bid"] is None
        assert outcome["derived_ask"] is None


@pytest.mark.parametrize("depth", [0, 21, "deep"])
def test_invalid_depth_fails_before_fetching(upstream, depth):
    result = _novig().get_order_book(market_id=SF_MARKET_ID, depth=depth)
    assert result["status"] is False
    assert upstream.urls == []


def test_order_book_retrieved_at_survives_cache_hit(upstream, monkeypatch):
    _serve_game(upstream)
    nv = _novig()
    connector = importlib.import_module("sports_skills.novig._connector")
    first = nv.get_order_book(market_id=SF_MARKET_ID)
    retrieved = _parse(first["data"]["retrieved_at"])
    assert abs((datetime.now(timezone.utc) - retrieved).total_seconds()) < 60

    class _Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2030, 1, 1, tzinfo=timezone.utc)

    monkeypatch.setattr(connector, "datetime", _Later)
    second = nv.get_order_book(market_id=SF_MARKET_ID)
    assert second["data"]["retrieved_at"] == first["data"]["retrieved_at"]
    assert len(upstream.queries(f"/catalog/markets/{SF_MARKET_ID}/book")) == 1


# ============================================================
# CLI registration / generated schema
# ============================================================


def test_cli_registers_novig_commands_and_schema():
    from sports_skills import cli

    assert "novig" in cli._REGISTRY, "novig is not registered in the CLI"
    commands = cli._REGISTRY["novig"]
    assert set(commands) == {
        "get_sports_config",
        "get_events",
        "get_event",
        "get_markets",
        "get_market",
        "get_order_book",
        "search_markets",
        "get_todays_events",
    }
    assert cli._load_module("novig") is _novig()

    schema = cli._generate_schema("novig")
    tools = {t["command"]: t for t in schema["tools"]}
    assert tools["get_event"]["parameters"]["required"] == ["event_id"]
    assert tools["get_market"]["parameters"]["required"] == ["market_id"]
    assert tools["get_order_book"]["parameters"]["required"] == ["market_id"]
    assert tools["get_order_book"]["parameters"]["properties"]["depth"]["type"] == "integer"
    assert tools["get_events"]["parameters"]["properties"]["limit"]["type"] == "integer"
    for name, tool in tools.items():
        assert tool["description"] != f"{name} command for novig", f"{name} has no docstring"


# ============================================================
# Markets aggregation: inclusion with identity gates
# ============================================================


def _summary(start="2026-10-20T00:15:00Z"):
    return {
        "status": True,
        "data": {
            "competitors": [
                {"home_away": "home", "team": {"name": "San Francisco 49ers", "abbreviation": "SF"}},
                {"home_away": "away", "team": {"name": "Washington Commanders", "abbreviation": "WSH"}},
            ],
            "game_info": {"start_time": start},
        },
    }


@pytest.fixture
def peers_silent():
    """Kalshi/Polymarket/ProphetX return nothing; ESPN is a canned module."""
    from sports_skills.markets import _connector as mc

    espn = types.SimpleNamespace(get_game_summary=lambda event_id: _summary())
    with (
        patch.object(mc, "_search_kalshi", return_value=[]),
        patch.object(mc, "_search_polymarket", return_value=[]),
        patch.object(mc, "_search_prophetx", return_value=[]),
        patch.object(mc, "_load_sport_module", return_value=espn),
    ):
        yield mc


def _compare(mc):
    return mc.compare_odds({"params": {"sport": "nfl", "event_id": "401"}})


def test_search_entity_includes_novig(upstream, peers_silent):
    _serve_game(upstream)
    result = peers_silent.search_entity({"params": {"query": "Commanders 49ers", "sport": "nfl"}})
    assert result["status"] is True
    assert result["data"]["novig"], "novig results missing from search_entity"
    assert result["data"]["total_results"] >= len(result["data"]["novig"])
    assert all(entry["source"] == "novig" for entry in result["data"]["novig"])


def test_todays_markets_includes_novig(upstream, peers_silent):
    _serve_game(upstream)
    game = {
        "sport": "nfl",
        "event_id": "401",
        "name": "Washington Commanders at San Francisco 49ers",
        "start_time": "2026-10-20T00:15:00Z",
        "home": {"name": "San Francisco 49ers", "abbreviation": "SF"},
        "away": {"name": "Washington Commanders", "abbreviation": "WSH"},
    }
    with patch.object(peers_silent, "_fetch_all_schedules", return_value=([game], [])):
        result = peers_silent.get_todays_markets({"params": {"sport": "nfl"}})
    assert result["status"] is True
    assert result["data"]["games"][0]["novig_markets"]


def test_compare_odds_admits_priced_full_game_moneyline(upstream, peers_silent):
    _serve_game(upstream)
    result = _compare(peers_silent)
    assert result["status"] is True, result["message"]
    data = result["data"]
    assert "novig_markets" in data
    assert data["sources"]["novig"]["outcome"] == "ok"
    assert "novig" in data["completeness"]["usable_sources"]
    assert "novig" in data["completeness"]["attempted_sources"]


def test_compare_odds_excludes_wrong_date_event(upstream, peers_silent):
    later = dict(SF_EVENT, startsTs=SF_START_MS + WEEK_MS)
    market = dict(copy.deepcopy(SF_MONEY), startsTs=SF_START_MS + WEEK_MS)
    _serve_game(upstream, event=later, markets=(market,))
    result = _compare(peers_silent)
    novig = result["data"]["sources"]["novig"]
    assert novig["outcome"] == "unmatched"
    assert novig["detail"]
    assert "novig" not in result["data"]["completeness"]["usable_sources"]


def test_compare_odds_does_not_pool_spread_or_period_markets(upstream, peers_silent):
    spread = _variant(SF_MONEY, "01a112eb-2222-7000-8000-000000000001", "SPREAD", "sp")
    first_half = _variant(SF_MONEY, "01a112eb-2222-7000-8000-000000000002", "MONEY_1H", "h1")
    _serve_game(
        upstream,
        markets=(spread, first_half),
        books={spread["marketId"]: _book_for(spread), first_half["marketId"]: _book_for(first_half)},
    )
    result = _compare(peers_silent)
    assert result["data"]["sources"]["novig"]["outcome"] != "ok"
    assert "novig" not in result["data"]["completeness"]["usable_sources"]


def test_compare_odds_catalog_only_market_is_not_usable_pricing(upstream, peers_silent):
    _serve_game(upstream, books={SF_MARKET_ID: {"marketId": SF_MARKET_ID, "seq": 2, "orders": {}}})
    result = _compare(peers_silent)
    assert result["data"]["sources"]["novig"]["outcome"] != "ok"
    assert "novig" not in result["data"]["completeness"]["usable_sources"]


def _mlb_doubleheader(upstream, asks, gap_ms=5 * 3600 * 1000):
    """Red Sox @ Yankees Novig events ``gap_ms`` apart, one MONEY book each."""
    start = 1792515900000  # 2026-10-20T17:05:00Z
    events, markets = [], []
    for n, (nyy_bid, bos_bid) in enumerate(asks):
        event_id = f"01a112eb-3333-7000-8000-00000000000{n}"
        market_id = f"01a112eb-4444-7000-8000-00000000000{n}"
        starts = start + n * gap_ms
        events.append(
            {
                "eventId": event_id,
                "description": "Boston Red Sox @ New York Yankees",
                "sport": "BASEBALL",
                "league": "MLB",
                "status": "OPEN_PREGAME",
                "startsTs": starts,
            }
        )
        market = {
            "marketId": market_id,
            "description": "NYY",
            "eventId": event_id,
            "marketType": "MONEY",
            "status": "OPEN",
            "startsTs": starts,
            "outcomes": [
                {"outcomeId": f"nyy-{n}", "name": "NYY", "status": "TBD"},
                {"outcomeId": f"bos-{n}", "name": "BOS", "status": "TBD"},
            ],
        }
        markets.append(market)
        upstream.routes[f"/catalog/markets/{market_id}"] = market
        upstream.routes[f"/catalog/markets/{market_id}/book"] = _book_for(market, (nyy_bid, bos_bid))
    upstream.routes["/catalog/events"] = {"items": events}
    upstream.routes["/catalog/markets"] = lambda q: {"items": [m for m in markets if m["eventId"] == q.get("event")]}
    return {
        "status": True,
        "data": {
            "competitors": [
                {"home_away": "home", "team": {"name": "New York Yankees", "abbreviation": "NYY"}},
                {"home_away": "away", "team": {"name": "Boston Red Sox", "abbreviation": "BOS"}},
            ],
            "game_info": {"start_time": "2026-10-20T17:05:00Z"},
        },
    }


def test_compare_odds_refuses_to_pool_same_day_doubleheader(upstream, peers_silent):
    # Two distinct markets both at ESPN's exact start: nothing tells them
    # apart, so neither is chosen. Best legs from different games would be
    # NYY ask 0.45 (game 2) + BOS ask 0.40 (game 1).
    summary = _mlb_doubleheader(upstream, (("0.6", "0.3"), ("0.35", "0.55")), gap_ms=0)
    espn = types.SimpleNamespace(get_game_summary=lambda event_id: summary)
    with patch.object(peers_silent, "_load_sport_module", return_value=espn):
        result = peers_silent.compare_odds({"params": {"sport": "mlb", "event_id": "401"}})
    data = result["data"]
    assert data["sources"]["novig"]["outcome"] != "ok"
    assert "ambiguous" in data["sources"]["novig"]["detail"]
    assert data["arbitrage_check"] is None
    assert _novig_quotes(data) == []


@pytest.mark.parametrize(
    "espn_start, expected",
    [("2026-10-20T17:05:00Z", [0.4, 0.7]), ("2026-10-20T22:05:00Z", [0.45, 0.65])],
    ids=["game-1", "game-2"],
)
def test_compare_odds_doubleheader_selects_exact_start_game(upstream, peers_silent, espn_start, expected):
    # Game 1 asks NYY 0.70 / BOS 0.40; game 2 asks NYY 0.45 / BOS 0.65. Only
    # the game starting at ESPN's exact instant may price; the other is
    # another game, not an ambiguity.
    summary = _mlb_doubleheader(upstream, (("0.6", "0.3"), ("0.35", "0.55")))
    summary["data"]["game_info"]["start_time"] = espn_start
    espn = types.SimpleNamespace(get_game_summary=lambda event_id: summary)
    with patch.object(peers_silent, "_load_sport_module", return_value=espn):
        data = peers_silent.compare_odds({"params": {"sport": "mlb", "event_id": "401"}})["data"]
    assert data["sources"]["novig"]["outcome"] == "ok"
    assert sorted(round(q["implied_probability"], 4) for q in _novig_quotes(data)) == expected


def test_search_entity_keeps_novig_book_provenance(upstream, peers_silent):
    _serve_game(upstream)
    result = peers_silent.search_entity({"params": {"query": "Commanders 49ers", "sport": "nfl"}})
    market = result["data"]["novig"][0]["markets"][0]
    assert market["voids"] == "FMV"
    assert market["fee"] == SF_MONEY["fee"]
    assert market["seq"] == 974
    assert market["price_basis"] == "cached_snapshot"
    assert market["execution_guaranteed"] is False
    assert _parse(market["retrieved_at"])
    assert "complement" in market["note"].lower()
    assert {o["id"] for o in market["outcomes"]} == {SF_OUT, WSH_OUT}


def test_search_entity_distinguishes_book_error_empty_and_budget_skip(upstream, peers_silent):
    markets = [SF_MONEY] + [
        _variant(SF_MONEY, f"01a112eb-6666-7000-8000-00000000000{i}", "MONEY", f"m{i}") for i in range(3)
    ]
    _serve_game(upstream, markets=markets)
    upstream.routes[f"/catalog/markets/{markets[1]['marketId']}/book"] = ERR_503
    result = peers_silent.search_entity({"params": {"query": "Commanders 49ers", "sport": "nfl"}})
    entries = result["data"]["novig"][0]["markets"]
    assert [m["book_status"] for m in entries] == ["ok", "error", "empty", "skipped_budget"]
    assert "503" in str(result["data"]["warnings"])


def test_compare_odds_reports_novig_book_error(upstream, peers_silent):
    _serve_game(upstream)
    upstream.routes[f"/catalog/markets/{SF_MARKET_ID}/book"] = ERR_503
    result = _compare(peers_silent)
    novig = result["data"]["sources"]["novig"]
    assert novig["outcome"] != "ok"
    assert "503" in str(novig["warnings"])


def test_compare_odds_reports_novig_search_truncation(upstream, peers_silent):
    _serve_game(upstream)
    upstream.routes["/catalog/markets"] = {"items": [SF_MONEY], "next": "m2"}
    result = _compare(peers_silent)
    novig = result["data"]["sources"]["novig"]
    assert novig["outcome"] == "ok"
    assert "truncated" in str(novig["warnings"])


def test_compare_note_acknowledges_novig_complement_ask(upstream, peers_silent):
    _serve_game(upstream)
    note = _compare(peers_silent)["data"]["price_basis_note"].lower()
    assert "novig" in note
    assert "complement" in note


# ESPN kicks off 2026-10-10T01:00Z (Oct 9 evening ET). UTC and ET day sets of
# a game exactly one day away still share a calendar day, so day intersection
# alone admits the same teams' adjacent game.
_OVERNIGHT_MS = 1791594000000  # 2026-10-10T01:00:00Z
_DAY_MS = 24 * 3600 * 1000


def _compare_at(upstream, mc, espn_start, novig_ms):
    """compare_odds with one priced Novig MONEY book (SF ask 0.55, WSH ask 0.48)."""
    event = dict(SF_EVENT, startsTs=novig_ms)
    market = dict(copy.deepcopy(SF_MONEY), startsTs=novig_ms)
    _serve_game(upstream, event=event, markets=(market,), books={SF_MARKET_ID: _book_for(market, ("0.52", "0.45"))})
    espn = types.SimpleNamespace(get_game_summary=lambda event_id: _summary(espn_start))
    with patch.object(mc, "_load_sport_module", return_value=espn):
        return _compare(mc)


def _novig_quotes(data):
    return [q for side in ("home", "away") for q in data["side_prices"][side]["quotes"] if q["venue"] == "novig"]


@pytest.mark.parametrize(
    "novig_ms",
    [_OVERNIGHT_MS + _DAY_MS, _OVERNIGHT_MS - _DAY_MS],
    ids=["next-day", "previous-day"],
)
def test_compare_odds_excludes_adjacent_day_same_teams(upstream, peers_silent, novig_ms):
    data = _compare_at(upstream, peers_silent, "2026-10-10T01:00:00Z", novig_ms)["data"]
    assert _novig_quotes(data) == []
    for side in ("home", "away"):
        lowest = data["side_prices"][side]["lowest_reference"]
        assert lowest is None or lowest["venue"] != "novig"
    novig = data["sources"]["novig"]
    assert novig["outcome"] == "unmatched"
    assert "Novig event" in novig["detail"]
    assert "novig" not in data["completeness"]["usable_sources"]


@pytest.mark.parametrize(
    "espn_start",
    ["2026-10-10T01:00:00Z", "2026-10-09T21:00:00-04:00"],
    ids=["same-instant-utc", "same-instant-other-offset"],
)
def test_compare_odds_admits_same_instant_overnight_game(upstream, peers_silent, espn_start):
    data = _compare_at(upstream, peers_silent, espn_start, _OVERNIGHT_MS)["data"]
    assert data["sources"]["novig"]["outcome"] == "ok"
    assert sorted(round(q["implied_probability"], 4) for q in _novig_quotes(data)) == [0.48, 0.55]


# Same teams, same or adjacent day, different start instant: a different game.
_WRONG_START = [
    pytest.param("2026-10-20T17:05:00Z", "2026-10-20T22:05:00Z", id="doubleheader-other-game-only"),
    pytest.param("2026-10-20T03:00:00Z", "2026-10-20T14:00:00Z", id="same-utc-day-11h"),
    pytest.param("2026-10-20T16:00:00Z", "2026-10-21T04:00:00Z", id="next-utc-day-12h"),
]


@pytest.mark.parametrize("espn_start, novig_start", _WRONG_START)
def test_compare_odds_excludes_same_teams_at_other_start(upstream, peers_silent, espn_start, novig_start):
    data = _compare_at(upstream, peers_silent, espn_start, _ms(_parse(novig_start)))["data"]
    assert _novig_quotes(data) == []
    for side in ("home", "away"):
        lowest = data["side_prices"][side]["lowest_reference"]
        assert lowest is None or lowest["venue"] != "novig"
    assert data["sources"]["novig"]["outcome"] == "unmatched"
    assert "Novig event" in data["sources"]["novig"]["detail"]


def test_compare_odds_novig_abstains_without_espn_start(upstream, peers_silent):
    data = _compare_at(upstream, peers_silent, "", _OVERNIGHT_MS)["data"]
    assert _novig_quotes(data) == []
    assert data["sources"]["novig"]["outcome"] == "unmatched"
    assert data["sources"]["novig"]["detail"]
