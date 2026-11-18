"""Unit tests for the gemini module and its markets aggregation (no network).

Upstream payloads are real unauthenticated Gemini Predictions responses
captured on 2026-10-23 and trimmed (see tests/fixtures/gemini/provenance.json).
Edge cases are deep copies of those events with one field changed; each is
labelled "synthetic" where it is built. Transport is faked at the shared
``_replay.fetch`` hook, or at requests' adapter for transport tests; sockets
and urlopen are denied.
"""

import copy
import importlib
import importlib.util
import json
import socket
import types
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://api.gemini.com/v1/prediction-markets"
PREFIX = "/v1/prediction-markets"

SAMPLE = json.loads((ROOT / "tests" / "fixtures" / "gemini" / "events_sample.json").read_text())
NBA, EPL = SAMPLE["data"]
NBA_ML = "NBA-2610232300-MIN-ORL-M"
NBA_SPREAD = "NBA-2610232300-MIN-ORL-S"
NBA_TOTAL = "NBA-2610232300-MIN-ORL-T"
EPL_ML = "EPL-2610231900-NFO-IPS-M"
ERR_503 = (None, {"error": True, "status_code": 503, "message": "Service Unavailable"})


def _parse(value):
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _synthetic(event, mutate):
    """Synthetic: a deep copy of a real event with one change applied."""
    out = copy.deepcopy(event)
    mutate(out)
    return out


# ============================================================
# RED via existing public callers (no new module needed to fail)
# ============================================================


def test_public_normalize_gemini_price():
    from sports_skills import markets

    result = markets.normalize_price(price=0.51, source="gemini")
    assert result["status"] is True, result["message"]
    assert result["data"]["implied_probability"] == pytest.approx(0.51)


@pytest.mark.parametrize("price", [1.5, -0.1, float("nan")])
def test_public_normalize_gemini_price_rejects_non_probability(price):
    from sports_skills import markets

    result = markets.normalize_price(price=price, source="gemini")
    assert result["status"] is False


def test_gemini_module_is_available():
    assert importlib.util.find_spec("sports_skills.gemini") is not None


def test_cli_registers_gemini_commands_and_schema():
    from sports_skills import cli

    assert "gemini" in cli._REGISTRY, "gemini is not registered in the CLI"
    assert set(cli._REGISTRY["gemini"]) == {"get_events", "get_event", "search_markets", "get_todays_events"}
    assert cli._load_module("gemini") is importlib.import_module("sports_skills.gemini")
    tools = {t["command"]: t for t in cli._generate_schema("gemini")["tools"]}
    assert tools["get_event"]["parameters"]["required"] == ["event_ticker"]
    assert tools["get_events"]["parameters"]["properties"]["limit"]["type"] == "integer"
    assert tools["get_events"]["parameters"]["properties"]["offset"]["type"] == "integer"
    for name, tool in tools.items():
        assert tool["description"] != f"{name} command for gemini", f"{name} has no docstring"


def test_catalog_lists_gemini_as_read_only_medium_risk():
    meta = json.loads((ROOT / "skills" / "catalog.json").read_text())["skills"]["gemini"]
    assert meta["mode"] == "read_only"
    assert meta["money_movement"] is False
    assert meta["secrets_required"] is False
    assert meta["external_network"] is True
    assert meta["untrusted_content"] is True
    assert meta["risk"] == "medium"
    assert meta["skill_path"] == "skills/gemini/SKILL.md"
    assert (ROOT / meta["skill_path"]).exists()
    assert (ROOT / "skills" / "gemini" / "references" / "api-reference.md").exists()


def test_site_and_markets_docs_list_gemini():
    assert '"gemini": "gemini"' in (ROOT / "site" / "build.py").read_text()
    assert "gemini" in (ROOT / "skills" / "markets" / "SKILL.md").read_text().lower()
    assert "gemini" in (ROOT / "skills" / "markets" / "references" / "api-reference.md").read_text().lower()


# ============================================================
# Harness
# ============================================================


@pytest.fixture
def gm():
    """The provider module; skips (not errors) while it does not exist."""
    return pytest.importorskip("sports_skills.gemini")


def _clear_cache():
    try:
        connector = importlib.import_module("sports_skills.gemini._connector")
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
    _clear_cache()
    yield
    _clear_cache()
    assert not attempts, "a test reached the real network"


def _all_events(events):
    for event in events:
        yield event
        yield from event.get("events") or []


class _Upstream:
    """Fake of the public events API, honoring its documented filters.

    ``search`` matches titles only, as upstream documents, so a team-name
    query must be matched client-side over participants.
    """

    def __init__(self):
        self.events = [NBA, EPL]
        self.routes = {}
        self.urls = []

    def fetch(self, url, live_fetch, recordable=None):
        self.urls.append(url)
        if not url.startswith(BASE + "/"):
            return None, {"error": True, "message": f"unexpected host: {url}"}
        parts = urllib.parse.urlsplit(url)
        path = parts.path[len(PREFIX) :]
        query = {}
        for key, value in urllib.parse.parse_qsl(parts.query):
            query.setdefault(key, []).append(value)
        route = self.routes.get(path)
        if route is not None:
            body = route(query) if callable(route) else route
        elif path == "/events":
            body = self._list(query)
        elif path.startswith("/events/"):
            ticker = urllib.parse.unquote(path[len("/events/") :])
            body = next((e for e in _all_events(self.events) if e["ticker"] == ticker), None)
            if body is None:
                return None, {"error": True, "status_code": 404, "message": "Not Found"}
        else:
            return None, {"error": True, "status_code": 404, "message": "Not Found"}
        if isinstance(body, tuple):
            return body
        if isinstance(body, bytes):
            return body, None
        return json.dumps(body).encode(), None

    def _list(self, query):
        found = list(self.events)
        if "status" in query:
            found = [e for e in found if e.get("status") in query["status"]]
        if "category" in query:
            found = [e for e in found if e.get("category") in query["category"]]
        if "sport" in query:
            found = [e for e in found if (e.get("sportsMarket") or {}).get("sport") in query["sport"]]
        if "search" in query:
            found = [e for e in found if query["search"][0].lower() in e.get("title", "").lower()]
        limit = int(query.get("limit", ["50"])[0])
        offset = int(query.get("offset", ["0"])[0])
        return {
            "data": found[offset : offset + limit],
            "pagination": {"limit": limit, "offset": offset, "total": len(found)},
        }

    def queries(self, path):
        return [
            dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(u).query))
            for u in self.urls
            if urllib.parse.urlsplit(u).path == PREFIX + path
        ]


@pytest.fixture
def upstream():
    fake = _Upstream()
    with patch("sports_skills._replay.fetch", side_effect=fake.fetch):
        yield fake


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

    http = types.SimpleNamespace(sent=sent, reply=lambda request: (200, json.dumps(NBA).encode(), {}))
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    return http


# ============================================================
# Provider: public surface and transport safety
# ============================================================


def test_public_surface_is_read_only(gm):
    for name in ("get_events", "get_event", "search_markets", "get_todays_events"):
        assert callable(getattr(gm, name, None)), name
    for name in (n for n in dir(gm) if not n.startswith("_")):
        assert not any(w in name.lower() for w in ("order", "place", "cancel", "trade", "submit", "position")), name


def test_requests_are_keyless_gets_to_fixed_base(gm, http, monkeypatch, tmp_path):
    netrc = tmp_path / "netrc"
    netrc.write_text("machine api.gemini.com login user password sekret-netrc\n")
    monkeypatch.setenv("NETRC", str(netrc))
    monkeypatch.setenv("GEMINI_API_KEY", "sekret-key")
    monkeypatch.setenv("GEMINI_API_SECRET", "sekret-secret")
    assert gm.get_event(event_ticker=NBA_ML)["status"] is True

    assert http.sent
    for req, kwargs in http.sent:
        assert req.method == "GET"
        assert req.url.startswith(BASE + "/")
        headers = {k.lower(): v for k, v in req.headers.items()}
        assert not {"authorization", "cookie", "x-gemini-apikey", "x-gemini-payload", "x-gemini-signature"} & set(
            headers
        )
        assert "sekret" not in req.url
        assert "sekret" not in " ".join(headers.values())


def test_redirect_is_error_not_followed(gm, http):
    http.reply = lambda request: (302, b"<html>moved</html>", {"Location": "https://evil.example/x"})
    result = gm.get_event(event_ticker=NBA_ML)
    assert result["status"] is False
    assert "302" in result["message"]
    assert "redirect" in result["message"].lower()
    assert len(http.sent) == 1


@pytest.mark.parametrize("status", [403, 429])
def test_http_error_is_reported_once_without_retry(gm, http, status):
    http.reply = lambda request: (status, b"<html>blocked</html>", {})
    result = gm.get_event(event_ticker=NBA_ML)
    assert result["status"] is False
    assert str(status) in result["message"]
    assert len(http.sent) == 1


@pytest.mark.parametrize("exc", [requests.ConnectionError("conn refused"), requests.Timeout("read timed out")])
def test_network_errors_are_wrapped(gm, http, exc):
    http.reply = lambda request: exc
    result = gm.get_event(event_ticker=NBA_ML)
    assert result["status"] is False
    assert str(exc) in result["message"]


def test_malformed_json_is_error_not_crash(gm, upstream):
    upstream.routes["/events"] = b"<html>WAF</html>"
    result = gm.get_events(league="nba")
    assert result["status"] is False
    assert result["message"]


def test_schema_drift_is_error_not_crash(gm, upstream):
    upstream.routes["/events"] = {"items": []}
    assert gm.get_events(league="nba")["status"] is False


@pytest.mark.parametrize(
    "call",
    [
        lambda g: g.get_event(event_ticker="../events"),
        lambda g: g.get_event(event_ticker="https://evil.example/x"),
        lambda g: g.get_event(event_ticker=f"{NBA_ML}/../../x"),
        lambda g: g.get_event(event_ticker="NBA ML"),
        lambda g: g.get_event(event_ticker=""),
        lambda g: g.get_event(event_ticker=NBA_ML + "\n"),
        lambda g: g.get_events(league="quidditch"),
        lambda g: g.get_events(status="bogus"),
        lambda g: g.get_events(limit=0),
        lambda g: g.get_events(limit=-5),
        lambda g: g.get_events(limit="many"),
        lambda g: g.get_events(limit=501),
        lambda g: g.get_events(offset=-1),
        lambda g: g.get_events(offset="x"),
        lambda g: g.get_events(limit=1.9),
        lambda g: g.get_events(limit=True),
        lambda g: g.get_events(limit=float("inf")),
        lambda g: g.get_events(offset=-0.9),
        lambda g: g.get_events(offset=2.9),
        lambda g: g.get_events(offset=True),
        lambda g: g.get_events(offset=float("inf")),
        lambda g: g.search_markets(query="Magic", limit=1.9),
        lambda g: g.get_todays_events(limit=2.9),
        lambda g: g.search_markets(query="Magic", market_type="bogus"),
        lambda g: g.search_markets(query="Magic", league="quidditch"),
        lambda g: g.get_todays_events(league="quidditch"),
    ],
)
def test_invalid_input_fails_cleanly_without_fetching(gm, upstream, call):
    result = call(gm)
    assert result["status"] is False
    assert result["message"]
    assert upstream.urls == []


# ============================================================
# Provider: events, detail, normalization
# ============================================================


def test_events_map_filters_and_report_next_offset(gm, upstream):
    upstream.events = [NBA, _synthetic(NBA, lambda e: e.update(id="366163", ticker="NBA-2610240000-CHI-MIL-M"))]
    result = gm.get_events(league="nba", limit=1, offset=0)
    assert result["status"] is True
    assert upstream.queries("/events") == [
        {"category": "Sports", "status": "active", "sport": "basketball", "limit": "1", "offset": "0"}
    ]
    assert [e["ticker"] for e in result["data"]["events"]] == [NBA_ML]
    assert result["data"]["pagination"] == {"limit": 1, "offset": 0, "total": 2}
    assert result["data"]["next_offset"] == 1


def test_events_league_filter_excludes_same_sport_other_league(gm, upstream):
    wnba = _synthetic(NBA, lambda e: e.update(ticker="WNBA-2610232300-MIN-ORL-M", id="999"))
    upstream.events = [wnba, NBA]
    result = gm.get_events(league="nba")
    assert [e["ticker"] for e in result["data"]["events"]] == [NBA_ML]


# Real (ticker, sportsMarket.sport) pairs, one per prefix, from the full live
# Sports listing captured 2026-10-23 (764 events).
_LEAGUE_SAMPLES = {
    "nfl": ("NFL-2610251330-PIT-NO-M", "american_football"),
    "cfb": ("NCAAF-2610232300-DUK-VIR-M", "american_football"),
    "mlb": ("MLB-2610240000-TB-MIL-M", "baseball"),
    "nhl": ("NHL-2610240000-MTL-CHI-M", "hockey"),
    "wnba": ("WNBA-2610241700-GSV-ATL-M", "basketball"),
    "mls": ("MLS-2610241730-NSH-MTL-REGS", "soccer"),
    "ligamx": ("LIGAMX-2610240100-JUA-NCX-M", "soccer"),
    "ufc": ("UFC-VAG-MAL-20261024", "mixed_martial_arts"),
    "f1": ("F1-UNIGP-POD-20261025", "motorsports"),
    "golf": ("GOLF-BUT-WIN-20261025", "golf"),
}


def _listed(ticker, sport):
    """Synthetic: the NBA event carrying a real ticker and sport from another league."""

    def mutate(e):
        e.update(id=ticker, ticker=ticker, events=[])
        e["sportsMarket"]["sport"] = sport

    return _synthetic(NBA, mutate)


@pytest.mark.parametrize("league", sorted(_LEAGUE_SAMPLES))
def test_events_league_filter_uses_verified_sport_and_exact_prefix(gm, upstream, league):
    # Same-sport neighbors (NFL/NCAAF, WNBA/NBA, MLS/LIGAMX/EPL) must not leak.
    upstream.events = [NBA, EPL] + [_listed(*sample) for sample in _LEAGUE_SAMPLES.values()]
    ticker, sport = _LEAGUE_SAMPLES[league]
    result = gm.get_events(league=league)
    assert result["status"] is True, result["message"]
    assert [q["sport"] for q in upstream.queries("/events")] == [sport]
    assert [e["ticker"] for e in result["data"]["events"]] == [ticker]


def test_events_without_league_include_futures_lacking_sport_metadata(gm, upstream):
    future = _synthetic(NBA, lambda e: (e.update(id="1", ticker="NFLMVP2026", events=[]), e.pop("sportsMarket")))
    upstream.events = [NBA, future]
    result = gm.get_events()
    assert "sport" not in upstream.queries("/events")[0]
    assert [e["ticker"] for e in result["data"]["events"]] == [NBA_ML, "NFLMVP2026"]


def _one_then_empty(query):
    """Synthetic paging: one event at offset 0, then an empty page, total 3."""
    offset = int(query.get("offset", ["0"])[0])
    return {"data": [] if offset else [NBA], "pagination": {"limit": 100, "offset": offset, "total": 3}}


def test_events_empty_page_before_total_is_not_exhaustion(gm, upstream):
    upstream.routes["/events"] = _one_then_empty
    result = gm.get_events(league="nba", offset=1)
    assert result["status"] is False or result["data"].get("warnings"), result


def test_event_detail_normalizes_real_snapshot(gm, upstream):
    result = gm.get_event(event_ticker=NBA_ML)
    assert result["status"] is True
    event = result["data"]
    assert event["id"] == "366162"
    assert event["ticker"] == NBA_ML
    assert event["name"] == "Minnesota vs Orlando"
    assert event["league"] == "NBA"
    assert event["sport"] == "basketball"
    assert event["status"] == "active"
    assert (event["market_type"], event["market_subject"], event["market_scope"]) == (
        "moneyline",
        "contest",
        "full_contest",
    )
    # startTime is kickoff; effectiveDate (listing) and expiryDate (settlement) are not.
    assert _parse(event["start_time"]) == datetime(2026, 10, 23, 23, tzinfo=timezone.utc)
    assert {(p["abbreviation"], p["side"]) for p in event["participants"]} == {("ORL", "home"), ("MIN", "away")}
    assert event["_raw"] == NBA
    assert event["execution_guaranteed"] is False
    assert _parse(event["retrieved_at"])

    orl = next(c for c in event["contracts"] if c["ticker"] == "ORL")
    assert orl["id"] == "366162-858592"
    assert orl["label"] == "Orlando"
    assert orl["side"] == "home"
    assert orl["status"] == "active"
    assert orl["market_state"] == "open"
    assert orl["is_combo"] is False
    assert orl["instrument_symbol"] == "GEMI-NBA-2610232300-MIN-ORL-M-ORL"
    assert orl["best_bid"] == pytest.approx(0.49)
    assert orl["best_ask"] == pytest.approx(0.51)
    assert orl["buy_yes"] == pytest.approx(0.51)
    assert orl["last_trade_price"] == pytest.approx(0.43)

    children = {c["ticker"]: c for c in event["child_events"]}
    assert set(children) == {NBA_SPREAD, NBA_TOTAL}
    assert children[NBA_SPREAD]["market_type"] == "spread"
    one_sided = next(c for c in children[NBA_SPREAD]["contracts"] if c["ticker"] == "ORL26")
    assert one_sided["best_bid"] is None  # missing stays missing, never 0
    assert one_sided["best_ask"] == pytest.approx(0.06)


def test_missing_start_time_is_none_not_expiry(gm, upstream):
    upstream.events = [_synthetic(NBA, lambda e: e.pop("startTime"))]
    assert gm.get_event(event_ticker=NBA_ML)["data"]["start_time"] is None


@pytest.mark.parametrize("bad", ["abc", "NaN", "Infinity", "1.5", "-0.1", None, True])
def test_invalid_prices_are_none_not_coerced(gm, upstream, bad):
    def mutate(e):
        e["contracts"][0]["prices"] = {
            "buy": {"yes": bad, "no": bad},
            "sell": {"yes": bad},
            "bestBid": bad,
            "bestAsk": bad,
        }

    upstream.events = [_synthetic(NBA, mutate)]
    contract = gm.get_event(event_ticker=NBA_ML)["data"]["contracts"][0]
    for key in ("best_bid", "best_ask", "buy_yes", "buy_no", "sell_yes", "last_trade_price"):
        assert contract[key] is None, key


def test_retrieved_at_survives_cache_hit(gm, upstream, monkeypatch):
    connector = importlib.import_module("sports_skills.gemini._connector")
    first = gm.get_event(event_ticker=NBA_ML)

    class _Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2030, 1, 1, tzinfo=timezone.utc)

    monkeypatch.setattr(connector, "datetime", _Later)
    second = gm.get_event(event_ticker=NBA_ML)
    assert second["data"]["retrieved_at"] == first["data"]["retrieved_at"]
    assert len(upstream.urls) == 1


def _spread_strike(event):
    return next(c for c in event["child_events"] if c["ticker"] == NBA_SPREAD)["contracts"][0]["strike"]


def test_mutating_a_result_does_not_corrupt_the_cache(gm, upstream):
    first = gm.get_event(event_ticker=NBA_ML)["data"]
    original_strike = copy.deepcopy(_spread_strike(first))
    first["_raw"]["contracts"][0]["prices"]["buy"]["yes"] = "0.99"
    _spread_strike(first)["value"] = "99"

    second = gm.get_event(event_ticker=NBA_ML)["data"]
    assert second["_raw"] == NBA
    assert second["contracts"][0]["buy_yes"] == pytest.approx(float(NBA["contracts"][0]["prices"]["buy"]["yes"]))
    assert _spread_strike(second) == original_strike
    assert second["retrieved_at"] == first["retrieved_at"]
    assert len(upstream.urls) == 1


def test_warm_cache_does_not_bypass_replay(gm, http, monkeypatch, tmp_path):
    assert gm.get_event(event_ticker=NBA_ML)["status"] is True  # replay off: live, cached
    monkeypatch.setenv("SPORTS_SKILLS_REPLAY_DIR", str(tmp_path))
    monkeypatch.setenv("SPORTS_SKILLS_REPLAY", "replay")
    result = gm.get_event(event_ticker=NBA_ML)
    assert result["status"] is False
    assert "replay miss" in result["message"].lower()
    assert len(http.sent) == 1


def test_cache_does_not_cross_replay_corpora(gm, http, monkeypatch, tmp_path):
    other = _synthetic(NBA, lambda e: e["contracts"][0]["prices"]["buy"].update(yes="0.77"))
    monkeypatch.setenv("SPORTS_SKILLS_REPLAY", "record")
    for name, event in (("a", NBA), ("b", other)):
        monkeypatch.setenv("SPORTS_SKILLS_REPLAY_DIR", str(tmp_path / name))
        http.reply = lambda request, event=event: (200, json.dumps(event).encode(), {})
        assert gm.get_event(event_ticker=NBA_ML)["status"] is True
        _clear_cache()

    monkeypatch.setenv("SPORTS_SKILLS_REPLAY", "replay")
    prices = []
    for name in ("a", "b"):
        monkeypatch.setenv("SPORTS_SKILLS_REPLAY_DIR", str(tmp_path / name))
        prices.append(gm.get_event(event_ticker=NBA_ML)["data"]["contracts"][0]["buy_yes"])
    assert prices == [pytest.approx(float(NBA["contracts"][0]["prices"]["buy"]["yes"])), pytest.approx(0.77)]
    assert len(http.sent) == 2


def test_record_then_replay_serves_without_network(gm, http, monkeypatch, tmp_path):
    monkeypatch.setenv("SPORTS_SKILLS_REPLAY_DIR", str(tmp_path))
    monkeypatch.setenv("SPORTS_SKILLS_REPLAY", "record")
    recorded = gm.get_event(event_ticker=NBA_ML)
    assert recorded["status"] is True
    _clear_cache()
    monkeypatch.setenv("SPORTS_SKILLS_REPLAY", "replay")
    replayed = gm.get_event(event_ticker=NBA_ML)
    assert replayed["status"] is True
    assert replayed["data"]["_raw"] == recorded["data"]["_raw"]
    assert len(http.sent) == 1


def test_replay_miss_is_error(gm, http, monkeypatch, tmp_path):
    monkeypatch.setenv("SPORTS_SKILLS_REPLAY_DIR", str(tmp_path))
    monkeypatch.setenv("SPORTS_SKILLS_REPLAY", "replay")
    result = gm.get_event(event_ticker=NBA_ML)
    assert result["status"] is False
    assert "replay miss" in result["message"].lower()
    assert http.sent == []


# ============================================================
# Provider: search and today
# ============================================================


def test_search_matches_participants_and_flattens_child_markets_once(gm, upstream):
    # Synthetic duplicate: upstream also lists child events top-level.
    upstream.events = [NBA, copy.deepcopy(NBA["events"][0]), EPL]
    result = gm.search_markets(query="Timberwolves Magic", league="nba")
    assert result["status"] is True
    tickers = [m["ticker"] for m in result["data"]["markets"]]
    assert sorted(tickers) == sorted([NBA_ML, NBA_SPREAD, NBA_TOTAL])
    assert result["data"]["truncated"] is False


def test_search_filters_market_type(gm, upstream):
    result = gm.search_markets(query="Timberwolves Magic", league="nba", market_type="moneyline")
    assert [m["ticker"] for m in result["data"]["markets"]] == [NBA_ML]


@pytest.mark.parametrize(
    "title",
    [
        pytest.param(None, id="null"),
        pytest.param(7, id="int"),
        pytest.param(1.5, id="float"),
        pytest.param(["Minnesota vs Orlando"], id="list"),
        pytest.param({"en": "Minnesota vs Orlando"}, id="dict"),
    ],
)
def test_search_survives_non_string_title(gm, upstream, title):
    # Synthetic: the NBA moneyline with a non-string title; EPL is untouched.
    upstream.events = [_synthetic(NBA, lambda e: e.update(title=title)), EPL]
    other = gm.search_markets(query="Nottingham Ipswich")
    assert other["status"] is True, other["message"]
    assert EPL_ML in [m["ticker"] for m in other["data"]["markets"]]
    own = gm.search_markets(query="Timberwolves Magic", league="nba")
    assert own["status"] is True, own["message"]
    assert NBA_ML in [m["ticker"] for m in own["data"]["markets"]]


def test_search_is_bounded_and_honest_about_truncation(gm, upstream):
    upstream.routes["/events"] = lambda q: {
        "data": [_synthetic(NBA, lambda e: e.update(ticker=f"NBA-X-{len(upstream.urls)}", title="Bulls vs Bucks"))],
        "pagination": {"limit": 1, "offset": int(q.get("offset", ["0"])[0]), "total": 10**6},
    }
    result = gm.search_markets(query="zebras", league="nba")
    assert result["status"] is True
    assert result["data"]["markets"] == []
    assert result["data"]["truncated"] is True
    assert len(upstream.urls) <= 10


def test_search_warns_when_later_page_fails(gm, upstream):
    upstream.routes["/events"] = lambda q: (
        ERR_503
        if int(q.get("offset", ["0"])[0]) > 0
        else {"data": [NBA], "pagination": {"limit": 1, "offset": 0, "total": 5}}
    )
    result = gm.search_markets(query="Timberwolves Magic", league="nba")
    assert result["status"] is True
    assert result["data"]["truncated"] is True
    assert "503" in str(result["data"]["warnings"])


def test_search_reports_partial_when_page_empties_before_total(gm, upstream):
    upstream.routes["/events"] = _one_then_empty
    result = gm.search_markets(query="Timberwolves Magic", league="nba")
    assert result["status"] is False or (result["data"]["truncated"] is True and result["data"].get("warnings")), result
    assert len(upstream.urls) == 2  # still stops at the empty page


def test_search_fails_when_first_page_fails(gm, upstream):
    upstream.routes["/events"] = ERR_503
    result = gm.search_markets(query="Timberwolves Magic", league="nba")
    assert result["status"] is False
    assert "503" in result["message"]


def test_todays_events_filter_by_utc_start_date(gm, upstream):
    now = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    today = _synthetic(NBA, lambda e: e.update(ticker="NBA-TODAY-M", startTime=now.isoformat().replace("+00:00", "Z")))
    upstream.events = [today, NBA]  # NBA starts 2026-10-23, not today (unless run that day)
    result = gm.get_todays_events(league="nba")
    assert result["status"] is True
    assert result["data"]["date"] == now.date().isoformat()
    tickers = [e["ticker"] for e in result["data"]["events"]]
    assert "NBA-TODAY-M" in tickers
    assert all(_parse(e["start_time"]).date() == now.date() for e in result["data"]["events"])


# ============================================================
# Markets aggregation (public markets callers; RED without the provider)
# ============================================================


def _summary(start="2026-10-23T23:00:00Z"):
    return {
        "status": True,
        "data": {
            "competitors": [
                {"home_away": "home", "team": {"name": "Orlando Magic", "abbreviation": "ORL"}},
                {"home_away": "away", "team": {"name": "Minnesota Timberwolves", "abbreviation": "MIN"}},
            ],
            "game_info": {"start_time": start},
        },
    }


@pytest.fixture
def peers_silent():
    """Other venues return nothing; ESPN is a canned module."""
    from sports_skills.markets import _connector as mc

    espn = types.SimpleNamespace(get_game_summary=lambda event_id: _summary())
    with (
        patch.object(mc, "_search_kalshi", return_value=[]),
        patch.object(mc, "_search_polymarket", return_value=[]),
        patch.object(mc, "_search_prophetx", return_value=[]),
        patch.object(mc, "_search_novig", return_value=[]),
        patch.object(mc, "_load_sport_module", return_value=espn),
    ):
        yield mc


def _compare(mc):
    return mc.compare_odds({"params": {"sport": "nba", "event_id": "401"}})["data"]


def _gemini_quotes(data):
    return [q for side in ("home", "away") for q in data["side_prices"][side]["quotes"] if q["venue"] == "gemini"]


def test_search_entity_includes_gemini(upstream, peers_silent):
    result = peers_silent.search_entity({"params": {"query": "Timberwolves Magic", "sport": "nba"}})
    assert result["status"] is True
    entries = result["data"]["gemini"]
    assert entries, "gemini results missing from search_entity"
    assert all(e["source"] == "gemini" for e in entries)
    assert result["data"]["total_results"] >= len(entries)
    markets = [m for e in entries for m in e["markets"]]
    assert [m["ticker"] for m in markets].count(NBA_ML) == 1
    ml = next(m for m in markets if m["ticker"] == NBA_ML)
    assert ml["execution_guaranteed"] is False
    assert _parse(ml["retrieved_at"])


def test_search_entity_keeps_soccer_three_way_without_fabricated_prices(upstream, peers_silent):
    result = peers_silent.search_entity({"params": {"query": "Nottingham Ipswich", "sport": "epl"}})
    markets = [m for e in result["data"]["gemini"] for m in e["markets"]]
    ml = next(m for m in markets if m["ticker"] == EPL_ML)
    assert {o["side"] for o in ml["outcomes"]} == {"home", "away", "tie"}
    assert sorted(o["best_ask"] for o in ml["outcomes"]) == pytest.approx([0.28, 0.31, 0.43])


def test_todays_markets_includes_gemini(upstream, peers_silent):
    game = {
        "sport": "nba",
        "event_id": "401",
        "name": "Minnesota Timberwolves at Orlando Magic",
        "start_time": "2026-10-23T23:00:00Z",
        "home": {"name": "Orlando Magic", "abbreviation": "ORL"},
        "away": {"name": "Minnesota Timberwolves", "abbreviation": "MIN"},
    }
    with patch.object(peers_silent, "_fetch_all_schedules", return_value=([game], [])):
        result = peers_silent.get_todays_markets({"params": {"sport": "nba"}})
    assert result["data"]["games"][0]["gemini_markets"]


@pytest.mark.parametrize("sport", ["nfl", "cfb", "mlb", "nhl", "wnba", "cbb"])
def test_compare_gemini_requires_verified_settlement_sport(peers_silent, sport):
    with patch.object(peers_silent, "_search_gemini", return_value=[]) as search:
        result = peers_silent.compare_odds({"params": {"sport": sport, "event_id": "401"}})
    assert result["data"]["sport"] == sport
    search.assert_not_called()
    assert "gemini" not in result["data"]["sources"]


def test_compare_odds_admits_full_game_moneyline_buy_prices(upstream, peers_silent):
    data = _compare(peers_silent)
    assert data["sources"]["gemini"]["outcome"] == "ok"
    assert "gemini" in data["completeness"]["usable_sources"]
    assert "gemini_markets" in data
    home = [q for q in data["side_prices"]["home"]["quotes"] if q["venue"] == "gemini"]
    away = [q for q in data["side_prices"]["away"]["quotes"] if q["venue"] == "gemini"]
    assert [q["implied_probability"] for q in home] == [pytest.approx(0.51)]  # ORL buy yes
    assert [q["implied_probability"] for q in away] == [pytest.approx(0.5)]  # MIN buy yes
    assert all(q["execution_guaranteed"] is False for q in home + away)
    assert "gemini" in data["price_basis_note"].lower()


def test_compare_odds_dedupes_same_ticker_listed_twice(upstream, peers_silent):
    upstream.events = [NBA, copy.deepcopy(NBA), copy.deepcopy(NBA["events"][0])]  # synthetic repeats
    data = _compare(peers_silent)
    assert data["sources"]["gemini"]["outcome"] == "ok"
    assert len(_gemini_quotes(data)) == 2


def _set_both(price):
    def mutate(e):
        e["contracts"][0]["prices"]["buy"]["yes"] = price
        e["contracts"][0]["prices"]["bestAsk"] = price

    return mutate


def _three_way(e):
    e["contracts"].append(dict(copy.deepcopy(EPL["contracts"][2]), id="366162-1", instrumentSymbol="GEMI-X-D"))


def _swap_sides(e):
    e["contracts"][0]["sportsSide"], e["contracts"][1]["sportsSide"] = "away", "home"


_REJECT = [
    pytest.param(lambda e: e.update(startTime="2026-10-24T23:00:00.000Z"), id="next-day"),
    pytest.param(lambda e: e.update(startTime="2026-10-23T19:00:00.000Z"), id="same-day-other-start"),
    pytest.param(lambda e: e.update(ticker="WNBA-2610232300-MIN-ORL-M", events=[]), id="wrong-league"),
    pytest.param(lambda e: e["sportsMarket"].update(scope={"type": "half", "ordinal": 1}), id="first-half"),
    pytest.param(lambda e: e["sportsMarket"].update(type="spread"), id="spread-type"),
    pytest.param(lambda e: e["sportsMarket"].update(subject="player"), id="player-subject"),
    pytest.param(lambda e: e["contracts"][0].update(isCombo=True), id="combo"),
    pytest.param(lambda e: e["contracts"][0].update(marketState="closed"), id="contract-closed"),
    pytest.param(lambda e: e["contracts"][0].update(status="settled"), id="contract-settled"),
    pytest.param(lambda e: e["contracts"][0].update(prices={}), id="missing-price"),
    pytest.param(_set_both("abc"), id="malformed-price"),
    pytest.param(_set_both("1.5"), id="price-above-one"),
    pytest.param(_set_both("NaN"), id="nan-price"),
    pytest.param(_set_both("0"), id="zero-price"),
    pytest.param(_three_way, id="three-outcomes"),
    pytest.param(_swap_sides, id="sides-contradict-espn"),
]


@pytest.mark.parametrize("mutate", _REJECT)
def test_compare_odds_refuses_non_comparable_gemini_market(upstream, peers_silent, mutate):
    upstream.events = [_synthetic(NBA, mutate)]
    data = _compare(peers_silent)
    assert _gemini_quotes(data) == []
    assert data["sources"]["gemini"]["outcome"] != "ok"
    assert "gemini" not in data["completeness"]["usable_sources"]


def test_compare_odds_refuses_duplicate_candidates(upstream, peers_silent):
    twin = _synthetic(NBA, lambda e: e.update(id="366999", ticker="NBA-2610232300-MIN-ORL-M2", events=[]))
    upstream.events = [NBA, twin]
    data = _compare(peers_silent)
    assert _gemini_quotes(data) == []
    assert data["sources"]["gemini"]["outcome"] != "ok"
    assert "ambiguous" in data["sources"]["gemini"]["detail"].lower()


def test_compare_odds_abstains_without_espn_start(upstream, peers_silent):
    espn = types.SimpleNamespace(get_game_summary=lambda event_id: _summary(""))
    with patch.object(peers_silent, "_load_sport_module", return_value=espn):
        data = _compare(peers_silent)
    assert _gemini_quotes(data) == []
    assert data["sources"]["gemini"]["outcome"] == "unmatched"
    assert data["sources"]["gemini"]["detail"]


def test_compare_odds_reports_provider_failure_as_error(upstream, peers_silent):
    upstream.routes["/events"] = ERR_503
    data = _compare(peers_silent)
    assert data["sources"]["gemini"]["outcome"] == "error"
    assert "503" in data["sources"]["gemini"]["detail"]


def test_compare_odds_reports_partial_pagination(upstream, peers_silent):
    upstream.routes["/events"] = lambda q: (
        ERR_503
        if int(q.get("offset", ["0"])[0]) > 0
        else {"data": [NBA], "pagination": {"limit": 1, "offset": 0, "total": 5}}
    )
    data = _compare(peers_silent)
    assert data["sources"]["gemini"]["outcome"] == "ok"
    assert "503" in str(data["sources"]["gemini"].get("warnings")) + str(data.get("warnings"))


@pytest.mark.parametrize("label,team", [("Los Angeles C", "LA Clippers"), ("Los Angeles L", "Los Angeles Lakers")])
def test_la_contract_labels_match_only_correct_team(peers_silent, label, team):
    market = {
        "ticker": "test",
        "league": "NBA",
        "market_type": "moneyline",
        "market_subject": "contest",
        "market_scope": "full_contest",
        "status": "active",
        "start_time": "2026-10-23T23:00:00Z",
        "outcomes": [
            {
                "label": label,
                "side": "home",
                "status": "active",
                "market_state": "open",
                "is_combo": False,
                "buy_yes": 0.6,
            },
            {
                "label": "Minnesota",
                "side": "away",
                "status": "active",
                "market_state": "open",
                "is_combo": False,
                "buy_yes": 0.4,
            },
        ],
    }
    summary = _summary()
    summary["data"]["competitors"][0]["team"]["name"] = team
    espn = types.SimpleNamespace(get_game_summary=lambda event_id: summary)
    with (
        patch.object(peers_silent, "_search_gemini", return_value=[{"markets": [market]}]),
        patch.object(peers_silent, "_load_sport_module", return_value=espn),
    ):
        assert _compare(peers_silent)["sources"]["gemini"]["outcome"] == "ok"
        summary["data"]["competitors"][0]["team"]["name"] = (
            "Los Angeles Lakers" if label.endswith("C") else "LA Clippers"
        )
        assert _compare(peers_silent)["sources"]["gemini"]["outcome"] == "unmatched"
