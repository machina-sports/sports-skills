"""Tests for markets.compare_market_url on UEFA Champions League game links.

Fixtures in tests/fixtures/ucl_market_links/ are trimmed (fields removed,
values unchanged) from public responses captured 2026-10-16 — see
provenance.json there:
  polymarket.get_event_details(slug='ucl-psg-fcb-2026-10-20')
  kalshi.get_event(event_ticker='KXUCLGAME-26OCT20PSGBAR', with_nested_markets=True)
  ESPN soccer/uefa.champions scoreboard for 2026-10-20 (raw site API payload)

A soccer game is three binary contracts per venue (home / draw / away), settled
on 90 minutes plus stoppage time. It is compared as one three-way market and
never folded into the two-way compare_odds path.

No network. Seams patched:
  sports_skills.polymarket.get_event_details  source event for a Polymarket link
  sports_skills.polymarket.get_sports_events  Polymarket UCL listing (counterpart of a Kalshi link)
  sports_skills.kalshi.get_event              source event for a Kalshi link
  sports_skills.kalshi.get_events             Kalshi KXUCLGAME listing (counterpart of a Polymarket link)
  sports_skills._espn_base.espn_request       ESPN soccer/uefa.champions scoreboard
  sports_skills.markets._connector.compare_odds  two-way path; never reached for UCL
"""

import copy
import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sports_skills import markets

_FIXTURES = Path(__file__).parent / "fixtures" / "ucl_market_links"


def _load(name):
    with open(_FIXTURES / name, encoding="utf-8") as fh:
        return json.load(fh)


POLY_RESPONSE = _load("polymarket_event.json")
KALSHI_RESPONSE = _load("kalshi_event.json")
ESPN_BOARD = _load("espn_scoreboard_20261020.json")

# The two links the user supplied, verbatim.
POLY_URL = "https://polymarket.com/sports/ucl/ucl-psg-fcb-2026-10-20"
KALSHI_URL = "https://kalshi.com/markets/kxuclgame/uefa-champions-league-game/kxuclgame-26oct20psgbar"

ESPN_EVENT_ID = "401915399"
ESPN_PATH = "soccer/uefa.champions"

POLY_CONTRACTS = {"home": "5409678", "draw": "5409679", "away": "5409680"}
POLY_YES_TOKENS = {
    "home": "26770595787602001462130355491642361938223218040760514066563322814696934151767",
    "draw": "67663514218312333544563894318029407264693493524344306629077712685778694931883",
    "away": "31682511723608770150053064810802010400448330082929879191712653876010261915911",
}
POLY_PRICES = {"home": 0.395, "draw": 0.215, "away": 0.395}
KALSHI_CONTRACTS = {
    "home": "KXUCLGAME-26OCT20PSGBAR-PSG",
    "draw": "KXUCLGAME-26OCT20PSGBAR-TIE",
    "away": "KXUCLGAME-26OCT20PSGBAR-BAR",
}
KALSHI_PRICES = {"home": 0.40, "draw": 0.21, "away": 0.40}
SIDES = ("home", "draw", "away")

# Provider metadata timestamps: none of them is when a price was observed.
_METADATA_TIMESTAMPS = {
    "2026-10-06T00:34:01.062734Z",
    "2026-10-06T00:28:04.995875Z",
    "2026-10-06T00:34:00Z",
    "2026-10-16T18:47:04.984344Z",
    "2026-10-16T18:46:52.63624Z",
    "2026-10-16T18:24:52.578576Z",
}


def _ok(data, message=""):
    return {"status": True, "data": copy.deepcopy(data), "message": message}


def _poly_event():
    return copy.deepcopy(POLY_RESPONSE["data"])


def _kalshi_event():
    return copy.deepcopy(KALSHI_RESPONSE["data"]["event"])


def _poly_child(event, side):
    return next(m for m in event["markets"] if m["id"] == POLY_CONTRACTS[side])


def _kalshi_child(event, side):
    return next(m for m in event["markets"] if m["ticker"] == KALSHI_CONTRACTS[side])


def _espn_events():
    return copy.deepcopy(ESPN_BOARD["events"])


def _espn_game(events):
    return next(e for e in events if e["id"] == ESPN_EVENT_ID)


def _retick(event, event_ticker):
    """Move a Kalshi event and its children to another event ticker."""
    event["event_ticker"] = event_ticker
    for m in event["markets"]:
        m["event_ticker"] = event_ticker
        m["ticker"] = f"{event_ticker}-{m['ticker'].rsplit('-', 1)[1]}"
    return event


def _days(dates: str) -> set:
    """'20261020' or '20261019-20261021' -> the set of YYYYMMDD days it covers."""
    from datetime import date, timedelta

    if "-" not in dates:
        return {dates}
    start, end = (date(int(d[:4]), int(d[4:6]), int(d[6:])) for d in dates.split("-", 1))
    out = set()
    while start <= end:
        out.add(start.strftime("%Y%m%d"))
        start += timedelta(days=1)
    return out


class _EspnUcl:
    """Fake ``_espn_base.espn_request``: UCL scoreboard by day, recording calls."""

    def __init__(self, by_day=None, fail_days=()):
        self.by_day = by_day if by_day is not None else {"20261020": _espn_events()}
        self.fail_days = set(fail_days)
        self.calls = []

    def __call__(self, sport_path, resource="scoreboard", params=None, **_kwargs):
        self.calls.append((sport_path, resource, dict(params or {})))
        if sport_path != ESPN_PATH or resource != "scoreboard":
            return {"error": True, "message": f"unexpected ESPN request {sport_path}/{resource}"}
        days = _days(str((params or {}).get("dates", "")))
        if days & self.fail_days:
            return {"error": True, "status_code": 503, "message": "HTTP 503 from site.api.espn.com"}
        return {"events": [copy.deepcopy(e) for d in sorted(days) for e in self.by_day.get(d, [])]}


@pytest.fixture
def env():
    """Patch every outbound seam; tests tweak return values per case."""
    espn = _EspnUcl()
    poly_event = MagicMock(return_value=_ok(_poly_event(), POLY_RESPONSE["message"]))
    poly_list = MagicMock(return_value=_ok({"events": [_poly_event()], "count": 1, "sport": "ucl"}))
    kalshi_event = MagicMock(return_value=copy.deepcopy(KALSHI_RESPONSE))
    kalshi_list = MagicMock(return_value=_ok({"events": [_kalshi_event()], "cursor": ""}))
    compare = MagicMock(return_value={"status": False, "data": None, "message": "compare_odds must not run for UCL"})
    with ExitStack() as stack:
        stack.enter_context(patch("sports_skills.polymarket.get_event_details", poly_event))
        stack.enter_context(patch("sports_skills.polymarket.get_sports_events", poly_list))
        stack.enter_context(patch("sports_skills.kalshi.get_event", kalshi_event))
        stack.enter_context(patch("sports_skills.kalshi.get_events", kalshi_list))
        stack.enter_context(patch("sports_skills._espn_base.espn_request", espn))
        stack.enter_context(patch("sports_skills.markets._connector.compare_odds", compare))
        yield {
            "espn": espn,
            "poly_event": poly_event,
            "poly_list": poly_list,
            "kalshi_event": kalshi_event,
            "kalshi_list": kalshi_list,
            "compare": compare,
        }


def _set_poly_source(env, event):
    env["poly_event"].return_value = _ok(event)


def _set_kalshi_source(env, event):
    env["kalshi_event"].return_value = _ok({"event": event, "markets": []})


def _set_kalshi_listing(env, events):
    env["kalshi_list"].return_value = _ok({"events": events, "cursor": ""})


def _set_poly_listing(env, events):
    env["poly_list"].return_value = _ok({"events": events, "count": len(events), "sport": "ucl"})


def _no_calls(env):
    for seam in ("poly_event", "poly_list", "kalshi_event", "kalshi_list", "compare"):
        assert not env[seam].called, seam
    assert env["espn"].calls == []


def _quotes(data, side, venue):
    assert data["source_market"]["market_type"] == "three_way_moneyline"
    assert data["source_market"]["settlement_period"] == "regulation"
    assert data["source_market"]["in_downstream_search"] is True
    return [q for q in data["side_prices"][side]["quotes"] if q["venue"] == venue]


def _quote(data, side, venue):
    found = _quotes(data, side, venue)
    assert len(found) == 1, (side, venue, found)
    return found[0]


def _quote_set(data):
    return {
        (side, q["venue"], str(q["contract"]), round(float(q["implied_probability"]), 6))
        for side in SIDES
        for q in data["side_prices"][side]["quotes"]
        if q["venue"] in ("polymarket", "kalshi")
    }


# ============================================================
# The two supplied public links
# ============================================================


class TestPublicExamples:
    @pytest.mark.parametrize("url", [POLY_URL, KALSHI_URL])
    def test_resolves_to_one_espn_game_as_a_three_way_market(self, env, url):
        result = markets.compare_market_url(url=url)

        assert result["status"] is True, result["message"]
        data = result["data"]
        assert data["sport"] == "ucl"
        assert data["event_id"] == ESPN_EVENT_ID
        assert data["home_team"] == "Paris Saint-Germain"
        assert data["away_team"] == "Barcelona"
        assert data["start_time"] == "2026-10-20T19:00Z"
        assert data["market_type"] == "three_way_moneyline"
        assert data["settlement_period"] == "regulation"
        assert data["source_market"]["espn_event_id"] == ESPN_EVENT_ID
        assert not env["compare"].called

    @pytest.mark.parametrize("url", [POLY_URL, KALSHI_URL])
    def test_prices_all_three_sides_on_both_venues(self, env, url):
        data = markets.compare_market_url(url=url)["data"]

        assert set(data["side_prices"]) == set(SIDES)
        for side in SIDES:
            poly = _quote(data, side, "polymarket")
            assert str(poly["contract"]) == POLY_CONTRACTS[side]
            assert str(poly["token_id"]) == POLY_YES_TOKENS[side]
            assert poly["implied_probability"] == pytest.approx(POLY_PRICES[side])
            kalshi = _quote(data, side, "kalshi")
            assert kalshi["contract"] == KALSHI_CONTRACTS[side]
            assert kalshi["implied_probability"] == pytest.approx(KALSHI_PRICES[side])
        assert data["sources"]["polymarket"]["outcome"] == "ok"
        assert data["sources"]["kalshi"]["outcome"] == "ok"

    def test_both_links_resolve_the_same_fixture(self, env):
        poly = markets.compare_market_url(url=POLY_URL)["data"]
        kalshi = markets.compare_market_url(url=KALSHI_URL)["data"]

        assert poly["event_id"] == kalshi["event_id"] == ESPN_EVENT_ID
        assert (poly["home_team"], poly["away_team"]) == (kalshi["home_team"], kalshi["away_team"])
        assert _quote_set(poly) == _quote_set(kalshi)
        assert len(_quote_set(poly)) == 6

    def test_polymarket_source_metadata(self, env):
        source = markets.compare_market_url(url=POLY_URL)["data"]["source_market"]

        env["poly_event"].assert_called_once_with(slug="ucl-psg-fcb-2026-10-20")
        assert source["venue"] == "polymarket"
        assert source["url"] == POLY_URL
        assert source["sport"] == "ucl"
        assert source["event_id"] == "1149399"
        assert source["event_slug"] == "ucl-psg-fcb-2026-10-20"
        assert {k: str(v) for k, v in source["contracts"].items()} == POLY_CONTRACTS

    def test_polymarket_event_route_is_the_same_ucl_game(self, env):
        event_url = "https://polymarket.com/event/ucl-psg-fcb-2026-10-20"
        result = markets.compare_market_url(url=event_url)

        assert result["status"] is True, result["message"]
        env["poly_event"].assert_called_once_with(slug="ucl-psg-fcb-2026-10-20")
        assert result["data"]["source_market"]["url"] == event_url
        assert result["data"]["market_type"] == "three_way_moneyline"
        assert _quote_set(result["data"]) == _quote_set(markets.compare_market_url(url=POLY_URL)["data"])
        assert not env["compare"].called

    def test_kalshi_source_metadata(self, env):
        source = markets.compare_market_url(url=KALSHI_URL)["data"]["source_market"]

        env["kalshi_event"].assert_called_once_with(event_ticker="KXUCLGAME-26OCT20PSGBAR", with_nested_markets=True)
        assert source["venue"] == "kalshi"
        assert source["url"] == KALSHI_URL
        assert source["sport"] == "ucl"
        assert source["event_id"] == "KXUCLGAME-26OCT20PSGBAR"
        assert source["contracts"] == KALSHI_CONTRACTS

    def test_polymarket_link_discovers_kalshi_in_its_ucl_game_series_only(self, env):
        markets.compare_market_url(url=POLY_URL)
        assert env["kalshi_list"].called
        assert all(c.kwargs.get("series_ticker") == "KXUCLGAME" for c in env["kalshi_list"].call_args_list)
        # The source is kept as fetched, never re-found through a generic search.
        assert not env["poly_list"].called

    def test_kalshi_link_discovers_polymarket_in_its_ucl_listing_only(self, env):
        markets.compare_market_url(url=KALSHI_URL)
        assert env["poly_list"].called
        assert all(c.kwargs.get("sport") == "ucl" for c in env["poly_list"].call_args_list)
        assert not env["kalshi_list"].called

    @pytest.mark.parametrize("url", [POLY_URL, KALSHI_URL])
    def test_espn_lookup_is_the_ucl_scoreboard_around_the_source_date(self, env, url):
        markets.compare_market_url(url=url)
        assert env["espn"].calls
        assert {path for path, _resource, _params in env["espn"].calls} == {ESPN_PATH}
        covered = set().union(*(_days(str(p.get("dates", ""))) for _path, _res, p in env["espn"].calls))
        assert "20261020" in covered

    @pytest.mark.parametrize(
        "url",
        [
            POLY_URL + "?utm_source=x&tid=123",
            "https://www.polymarket.com/sports/ucl/ucl-psg-fcb-2026-10-20",
            POLY_URL + "/",
            "https://polymarket.com/event/ucl-psg-fcb-2026-10-20",
            "https://www.polymarket.com/event/ucl-psg-fcb-2026-10-20?tid=1",
            KALSHI_URL + "?utm_campaign=share",
            "https://www.kalshi.com/markets/KXUCLGAME/uefa-champions-league-game/KXUCLGAME-26OCT20PSGBAR",
        ],
    )
    def test_tracking_query_www_host_and_case_variants_are_accepted(self, env, url):
        result = markets.compare_market_url(url=url)
        assert result["status"] is True, result["message"]
        assert result["data"]["event_id"] == ESPN_EVENT_ID


# ============================================================
# Three-way semantics: draw kept, nothing renormalized or inferred
# ============================================================


class TestThreeWaySemantics:
    def test_draw_is_its_own_side_on_both_venues(self, env):
        data = markets.compare_market_url(url=POLY_URL)["data"]
        assert _quote(data, "draw", "polymarket")["implied_probability"] == pytest.approx(0.215)
        assert _quote(data, "draw", "kalshi")["implied_probability"] == pytest.approx(0.21)

    def test_prices_are_raw_not_renormalized_to_sum_to_one(self, env):
        data = markets.compare_market_url(url=POLY_URL)["data"]
        poly_sum = sum(_quote(data, s, "polymarket")["implied_probability"] for s in SIDES)
        kalshi_sum = sum(_quote(data, s, "kalshi")["implied_probability"] for s in SIDES)
        assert poly_sum == pytest.approx(1.005)
        assert kalshi_sum == pytest.approx(1.01)

    def test_no_two_way_view_or_arbitrage_is_produced(self, env):
        data = markets.compare_market_url(url=POLY_URL)["data"]
        assert data.get("arbitrage_check") is None
        assert set(data["side_prices"]) == set(SIDES)

    def test_every_quote_is_a_reference_price(self, env):
        data = markets.compare_market_url(url=POLY_URL)["data"]
        assert data["price_basis"] == "reference"
        for side in SIDES:
            for quote in data["side_prices"][side]["quotes"]:
                assert quote["price_basis"] == "reference"
                assert quote["execution_guaranteed"] is False

    def test_settlement_caveat_names_cancellation_differences(self, env):
        data = markets.compare_market_url(url=POLY_URL)["data"]
        assert "cancel" in data["settlement_note"].lower()

    def test_quotes_never_present_metadata_timestamps_as_price_times(self, env):
        data = markets.compare_market_url(url=KALSHI_URL)["data"]
        for side in SIDES:
            for quote in data["side_prices"][side]["quotes"]:
                assert not (set(map(str, quote.values())) & _METADATA_TIMESTAMPS), quote

    def test_polymarket_draw_is_the_yes_price_not_one_minus_no(self, env):
        event = _poly_event()
        _poly_child(event, "draw")["outcomes"][1]["price"] = 0.70
        _set_poly_source(env, event)
        data = markets.compare_market_url(url=POLY_URL)["data"]
        assert _quote(data, "draw", "polymarket")["implied_probability"] == pytest.approx(0.215)

    def test_polymarket_missing_yes_price_is_not_inferred_from_no(self, env):
        event = _poly_event()
        _poly_child(event, "draw")["outcomes"][0]["price"] = None
        _set_poly_source(env, event)
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is True, result["message"]
        assert _quotes(result["data"], "draw", "polymarket") == []

    def test_kalshi_reference_is_last_trade_not_inferred_from_no_side(self, env):
        event = _kalshi_event()
        _kalshi_child(event, "draw")["last_price_dollars"] = "0.2300"
        _set_kalshi_source(env, event)
        data = markets.compare_market_url(url=KALSHI_URL)["data"]
        assert _quote(data, "draw", "kalshi")["implied_probability"] == pytest.approx(0.23)


# ============================================================
# Price validation — a bad price drops that quote, never the game
# ============================================================


class TestPriceValidation:
    @pytest.mark.parametrize("bad", [True, False, None, 0, 1, 1.5, -0.1, float("nan"), float("inf")])
    def test_invalid_polymarket_yes_price_drops_only_that_quote(self, env, bad):
        event = _poly_event()
        _poly_child(event, "draw")["outcomes"][0]["price"] = bad
        _set_poly_source(env, event)

        result = markets.compare_market_url(url=POLY_URL)

        assert result["status"] is True, result["message"]
        data = result["data"]
        assert _quotes(data, "draw", "polymarket") == []
        assert _quote(data, "home", "polymarket")["implied_probability"] == pytest.approx(0.395)
        assert _quote(data, "away", "polymarket")["implied_probability"] == pytest.approx(0.395)
        assert _quote(data, "draw", "kalshi")["implied_probability"] == pytest.approx(0.21)
        assert any(POLY_CONTRACTS["draw"] in w for w in data.get("warnings", []))

    @pytest.mark.parametrize(
        "bad", [True, False, None, "", "abc", "0", "0.0000", "1", "1.0000", "1.5", "-0.01", "nan", "inf", "-inf"]
    )
    def test_invalid_kalshi_dollars_price_drops_only_that_quote(self, env, bad):
        event = _kalshi_event()
        _kalshi_child(event, "draw")["last_price_dollars"] = bad
        _set_kalshi_listing(env, [event])

        result = markets.compare_market_url(url=POLY_URL)

        assert result["status"] is True, result["message"]
        data = result["data"]
        assert _quotes(data, "draw", "kalshi") == []
        assert _quote(data, "home", "kalshi")["implied_probability"] == pytest.approx(0.40)
        assert _quote(data, "away", "kalshi")["implied_probability"] == pytest.approx(0.40)
        assert _quote(data, "draw", "polymarket")["implied_probability"] == pytest.approx(0.215)
        assert any(KALSHI_CONTRACTS["draw"] in w for w in data.get("warnings", []))

    def test_kalshi_source_with_invalid_price_keeps_source_and_other_quotes(self, env):
        event = _kalshi_event()
        _kalshi_child(event, "home")["last_price_dollars"] = True
        _set_kalshi_source(env, event)

        result = markets.compare_market_url(url=KALSHI_URL)

        assert result["status"] is True, result["message"]
        data = result["data"]
        assert _quotes(data, "home", "kalshi") == []
        assert _quote(data, "draw", "kalshi")["implied_probability"] == pytest.approx(0.21)
        assert data["source_market"]["contracts"] == KALSHI_CONTRACTS

    def test_no_usable_price_anywhere_is_an_explicit_failure(self, env):
        poly = _poly_event()
        for m in poly["markets"]:
            m["outcomes"][0]["price"] = None
        kalshi = _kalshi_event()
        for m in kalshi["markets"]:
            m["last_price_dollars"] = ""
        events = _espn_events()
        for e in events:
            for comp in e["competitions"]:
                comp.pop("odds", None)
        env["espn"].by_day = {"20261020": events}
        _set_poly_source(env, poly)
        _set_kalshi_listing(env, [kalshi])

        result = markets.compare_market_url(url=POLY_URL)

        assert result["status"] is False
        assert result["message"]
        assert result["data"]["source_market"]["venue"] == "polymarket"


# ============================================================
# URL validation — nothing is fetched for a rejected URL
# ============================================================


@pytest.mark.parametrize(
    "url",
    [
        # scheme / host / credentials / port
        "http://polymarket.com/sports/ucl/ucl-psg-fcb-2026-10-20",
        "https://polymarket.com.evil.com/sports/ucl/ucl-psg-fcb-2026-10-20",
        "https://evil.com/sports/ucl/ucl-psg-fcb-2026-10-20",
        "https://user:pw@polymarket.com/sports/ucl/ucl-psg-fcb-2026-10-20",
        "https://polymarket.com:443/sports/ucl/ucl-psg-fcb-2026-10-20",
        "https://kalshi.com:8443/markets/kxuclgame/uefa-champions-league-game/kxuclgame-26oct20psgbar",
        "https://user@kalshi.com/markets/kxuclgame/uefa-champions-league-game/kxuclgame-26oct20psgbar",
        "https://gamma-api.polymarket.com/sports/ucl/ucl-psg-fcb-2026-10-20",
        # query / fragment / control characters / traversal
        "https://polymarket.com/sports/ucl/ucl-psg-fcb-2026-10-20?outcome=draw",
        "https://polymarket.com/sports/ucl/ucl-psg-fcb-2026-10-20?slug=ucl-rma-liv-2026-10-20",
        "https://kalshi.com/markets/kxuclgame/uefa-champions-league-game/kxuclgame-26oct20psgbar?ticker=KXUCLGAME-26OCT20PSGBAR-TIE",
        "https://polymarket.com/sports/ucl/ucl-psg-fcb-2026-10-20#draw",
        "https://polymarket.com/sports/ucl/ucl-psg-fcb-\n2026-10-20",
        "https://polymarket.com/sports/ucl/%2e%2e/ucl-psg-fcb-2026-10-20",
        "https://polymarket.com/sports/ucl/../ucl-psg-fcb-2026-10-20",
        "https://polymarket.com/sports/ucl//ucl-psg-fcb-2026-10-20",
        "https://polymarket.com/sports/ucl/ucl-psg-fcb-2026-10-20%2F..%2Fx",
        # malformed /sports route
        "https://polymarket.com/sports/ucl",
        "https://polymarket.com/sports/ucl/",
        "https://polymarket.com/sports/ucl/ucl-psg-fcb-2026-10-20/extra",
        "https://polymarket.com/sports/ucl/ucl-psg-fcb-2026-10-20-more-markets",
        "https://polymarket.com/sports/ucl/ucl-psg-fcb",
        # /event route: the game only, never one of its three contracts or a variant event
        "https://polymarket.com/event/ucl-psg-fcb-2026-10-20/ucl-psg-fcb-2026-10-20-psg",
        "https://polymarket.com/event/ucl-psg-fcb-2026-10-20-more-markets",
        "https://polymarket.com/event/ucl-psg-fcb-2026-02-30",
        # league mismatch between route and slug
        "https://polymarket.com/sports/epl/ucl-psg-fcb-2026-10-20",
        "https://polymarket.com/sports/ucl/epl-ars-che-2026-10-20",
        "https://polymarket.com/sports/ucl/nfl-sf-sea-2026-10-11",
        "https://polymarket.com/sports/nfl/ucl-psg-fcb-2026-10-20",
        # only UCL gains soccer support; US sports keep the /event route only
        "https://polymarket.com/sports/epl/epl-ars-che-2026-10-20",
        "https://polymarket.com/sports/lal/lal-rma-fcb-2026-10-20",
        "https://polymarket.com/sports/fifwc/fifwc-bra-arg-2026-07-01",
        "https://polymarket.com/sports/nfl/nfl-sf-sea-2026-10-11",
        "https://polymarket.com/event/epl-ars-che-2026-10-11",
        "https://kalshi.com/markets/kxeplgame/ars-che/kxeplgame-26oct11arsche",
        "https://kalshi.com/markets/kxlaligagame/rma-fcb/kxlaligagame-26oct20rmafcb",
        "https://kalshi.com/markets/kxucl/uefa-champions-league/kxucl-27",
        # invalid dates
        "https://polymarket.com/sports/ucl/ucl-psg-fcb-2026-02-30",
        "https://polymarket.com/sports/ucl/ucl-psg-fcb-2026-13-01",
        "https://polymarket.com/sports/ucl/ucl-psg-fcb-9999-12-31",
        "https://kalshi.com/markets/kxuclgame/uefa-champions-league-game/kxuclgame-26feb30psgbar",
        # Kalshi structure
        "https://kalshi.com/markets/kxuclgame/uefa-champions-league-game",
        "https://kalshi.com/markets/kxuclgame/uefa-champions-league-game/kxuclgame-26oct20psgbar/extra",
        "https://kalshi.com/markets/kxuclgame/uefa-champions-league-game/kxnflgame-26oct20psgbar",
        "https://kalshi.com/markets/kxnflgame/uefa-champions-league-game/kxuclgame-26oct20psgbar",
        "https://kalshi.com/markets/kxuclgame/uefa-champions-league-game/kxuclgame-psgbar",
    ],
)
def test_rejected_url_makes_no_calls(env, url):
    result = markets.compare_market_url(url=url)
    assert result["status"] is False
    assert result["message"]
    _no_calls(env)


# ============================================================
# Polymarket source: explicit children, else an explicit refusal
# ============================================================


def _drop_side(event, side):
    event["markets"] = [m for m in event["markets"] if m["id"] != POLY_CONTRACTS[side]]


def _duplicate_home(event):
    extra = copy.deepcopy(_poly_child(event, "home"))
    extra.update(id="5409999", slug="ucl-psg-fcb-2026-10-20-psg2")
    event["markets"].append(extra)


def _set(side, **fields):
    return lambda event: _poly_child(event, side).update(**fields)


def _rules(event, side, old, new):
    child = _poly_child(event, side)
    assert old in child["description"]
    child["description"] = child["description"].replace(old, new)


class TestPolymarketSource:
    @pytest.mark.parametrize(
        "mutate",
        [
            pytest.param(lambda e: _drop_side(e, "draw"), id="missing-draw"),
            pytest.param(lambda e: _drop_side(e, "away"), id="missing-away"),
            pytest.param(_duplicate_home, id="duplicate-home"),
            pytest.param(_set("draw", status="closed"), id="closed-draw"),
            pytest.param(lambda e: e.update(status="closed"), id="closed-event"),
            pytest.param(_set("home", question="Will Paris Saint-Germain FC win on 2026-10-21?"), id="child-date"),
            pytest.param(_set("home", slug="ucl-psg-fcb-2026-10-21-psg"), id="child-of-other-event"),
            pytest.param(_set("home", slug="epl-psg-fcb-2026-10-20-psg"), id="child-other-league"),
            pytest.param(_set("home", question="Will Paris FC win on 2026-10-20?"), id="no-fuzzy-team"),
            pytest.param(_set("away", question="Will Liverpool FC win on 2026-10-20?"), id="other-team"),
            pytest.param(_set("home", sports_market_type="spreads"), id="home-not-moneyline"),
            pytest.param(
                _set("home", outcomes=[{"name": "PSG", "price": 0.4}, {"name": "Barcelona", "price": 0.6}]),
                id="not-yes-no",
            ),
            pytest.param(
                _set("draw", description="If the game ends in a draw after extra time and penalties, Yes."),
                id="not-regulation",
            ),
            pytest.param(lambda e: _rules(e, "home", "October 20, 2026", "October 21, 2026"), id="rules-date"),
            pytest.param(
                lambda e: _rules(e, "home", "If Paris Saint-Germain FC wins", "If Liverpool FC wins"), id="rules-team"
            ),
            pytest.param(lambda e: e.update(tags=["Sports", "Games", "Soccer", "EPL"]), id="not-ucl-tagged"),
        ],
    )
    def test_invalid_source_structure_is_refused(self, env, mutate):
        event = _poly_event()
        mutate(event)
        _set_poly_source(env, event)

        result = markets.compare_market_url(url=POLY_URL)

        assert result["status"] is False
        assert result["message"]
        assert not env["compare"].called

    def test_unrelated_extra_market_is_ignored(self, env):
        event = _poly_event()
        extra = copy.deepcopy(_poly_child(event, "home"))
        extra.update(id="5409700", slug="ucl-psg-fcb-2026-10-20-total-2pt5", sports_market_type="totals")
        extra["question"] = "Paris Saint-Germain FC vs. FC Barcelona: O/U 2.5"
        event["markets"].append(extra)
        _set_poly_source(env, event)

        result = markets.compare_market_url(url=POLY_URL)

        assert result["status"] is True, result["message"]
        assert _quote(result["data"], "home", "polymarket")["contract"] == POLY_CONTRACTS["home"]

    def test_returned_slug_mismatch_is_refused_before_espn(self, env):
        event = _poly_event()
        event["slug"] = "ucl-psg-fcb-2026-12-09"
        _set_poly_source(env, event)
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert "ucl-psg-fcb-2026-12-09" in result["message"]
        assert env["espn"].calls == []

    def test_closed_event_is_refused_before_espn(self, env):
        event = _poly_event()
        event["status"] = "closed"
        _set_poly_source(env, event)
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert "closed" in result["message"]
        assert env["espn"].calls == []

    def test_provider_error_is_preserved(self, env):
        env["poly_event"].return_value = {"status": False, "data": None, "message": "Event not found: x"}
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert "Event not found" in result["message"]
        assert env["espn"].calls == []

    def test_provider_exception_fails_gracefully(self, env):
        env["poly_event"].side_effect = RuntimeError("socket closed")
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert "socket closed" in result["message"]


# ============================================================
# Kalshi source: explicit children, else an explicit refusal
# ============================================================


def _k_set(side, **fields):
    return lambda event: _kalshi_child(event, side).update(**fields)


def _k_drop(side):
    return lambda event: event.update(markets=[m for m in event["markets"] if m["ticker"] != KALSHI_CONTRACTS[side]])


def _k_rules(side, old, new):
    def mutate(event):
        child = _kalshi_child(event, side)
        assert old in child["rules_primary"]
        child["rules_primary"] = child["rules_primary"].replace(old, new)

    return mutate


def _k_duplicate_tie(event):
    extra = copy.deepcopy(_kalshi_child(event, "draw"))
    extra["ticker"] = "KXUCLGAME-26OCT20PSGBAR-TIE2"
    event["markets"].append(extra)


class TestKalshiSource:
    @pytest.mark.parametrize(
        "mutate",
        [
            pytest.param(_k_drop("draw"), id="missing-tie"),
            pytest.param(_k_drop("home"), id="missing-home"),
            pytest.param(_k_duplicate_tie, id="duplicate-tie"),
            pytest.param(_k_set("home", ticker="KXUCLGAME-26OCT21PSGBAR-PSG"), id="child-of-other-event"),
            pytest.param(_k_set("home", event_ticker="KXUCLGAME-26OCT21PSGBAR"), id="child-declares-other-event"),
            pytest.param(lambda e: e.update(series_ticker="KXEPLGAME"), id="series-mismatch"),
            pytest.param(
                lambda e: e.update(product_metadata={"competition": "Premier League", "competition_scope": "Game"}),
                id="competition-mismatch",
            ),
            pytest.param(lambda e: e.update(mutually_exclusive=False), id="not-mutually-exclusive"),
            pytest.param(_k_set("draw", status="finalized"), id="closed-child"),
            pytest.param(_k_set("away", yes_sub_title="Barca"), id="no-fuzzy-team"),
            pytest.param(_k_set("away", yes_sub_title="Liverpool"), id="other-team"),
            pytest.param(
                _k_set("home", rules_primary="If PSG advances after extra time or penalties, Yes."),
                id="not-regulation",
            ),
            pytest.param(_k_rules("home", "Champions League", "Premier League"), id="rules-competition"),
            pytest.param(_k_rules("draw", "Oct 20, 2026", "Oct 21, 2026"), id="rules-date"),
            pytest.param(_k_rules("home", "If PSG wins", "If Barcelona wins"), id="rules-team"),
        ],
    )
    def test_invalid_source_structure_is_refused(self, env, mutate):
        event = _kalshi_event()
        mutate(event)
        _set_kalshi_source(env, event)

        result = markets.compare_market_url(url=KALSHI_URL)

        assert result["status"] is False
        assert result["message"]
        assert not env["compare"].called

    def test_returned_event_ticker_mismatch_is_refused_before_espn(self, env):
        _set_kalshi_source(env, _retick(_kalshi_event(), "KXUCLGAME-26OCT21PSGBAR"))
        result = markets.compare_market_url(url=KALSHI_URL)
        assert result["status"] is False
        assert "KXUCLGAME-26OCT21PSGBAR" in result["message"]
        assert env["espn"].calls == []

    def test_provider_error_is_preserved(self, env):
        env["kalshi_event"].return_value = {"status": False, "data": None, "message": "API error (404): not found"}
        result = markets.compare_market_url(url=KALSHI_URL)
        assert result["status"] is False
        assert "API error (404): not found" in result["message"]
        assert env["espn"].calls == []

    def test_provider_exception_fails_gracefully(self, env):
        env["kalshi_event"].side_effect = TimeoutError("read timed out")
        result = markets.compare_market_url(url=KALSHI_URL)
        assert result["status"] is False
        assert "read timed out" in result["message"]


# ============================================================
# ESPN game identity: competition, date and both teams
# ============================================================


class TestEspnIdentity:
    def test_scoreboard_failure_is_not_reported_as_no_game(self, env):
        env["espn"].fail_days = {"20261019"}
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert "503" in result["message"]
        assert "no espn" not in result["message"].lower()

    def test_no_matching_game_keeps_source_metadata(self, env):
        env["espn"].by_day = {"20261020": [e for e in _espn_events() if e["id"] != ESPN_EVENT_ID]}
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert result["data"]["source_market"]["venue"] == "polymarket"
        assert result["data"]["source_market"]["event_id"] == "1149399"

    def test_other_team_in_the_espn_game_is_not_matched(self, env):
        events = _espn_events()
        away = _espn_game(events)["competitions"][0]["competitors"][1]["team"]
        away.update(abbreviation="BAY", displayName="Bayern Munich", shortDisplayName="Bayern", name="Bayern Munich")
        away["location"] = "Bayern Munich"
        env["espn"].by_day = {"20261020": events}
        assert markets.compare_market_url(url=POLY_URL)["status"] is False
        assert markets.compare_market_url(url=KALSHI_URL)["status"] is False

    def test_kalshi_event_dated_another_day_is_not_this_game(self, env):
        _set_kalshi_source(env, _retick(_kalshi_event(), "KXUCLGAME-26OCT21PSGBAR"))
        result = markets.compare_market_url(
            url="https://kalshi.com/markets/kxuclgame/uefa-champions-league-game/kxuclgame-26oct21psgbar"
        )
        assert result["status"] is False
        assert not env["compare"].called

    def test_two_matching_espn_games_are_ambiguous(self, env):
        events = _espn_events()
        twin = copy.deepcopy(_espn_game(events))
        twin["id"] = twin["competitions"][0]["id"] = "401999999"
        twin["date"] = twin["competitions"][0]["date"] = "2026-10-20T21:00Z"
        events.append(twin)
        env["espn"].by_day = {"20261020": events}
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is False
        assert ESPN_EVENT_ID in result["message"] and "401999999" in result["message"]

    def test_same_game_listed_on_adjacent_days_is_deduplicated(self, env):
        env["espn"].by_day = {"20261020": _espn_events(), "20261021": [_espn_game(_espn_events())]}
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is True, result["message"]
        assert result["data"]["event_id"] == ESPN_EVENT_ID


# ============================================================
# Counterpart venue: partial coverage is kept, never guessed
# ============================================================


class TestCounterpartCoverage:
    def test_kalshi_listing_error_keeps_polymarket_source(self, env):
        env["kalshi_list"].return_value = {"status": False, "data": None, "message": "API error (503): unavailable"}
        result = markets.compare_market_url(url=POLY_URL)

        assert result["status"] is True, result["message"]
        data = result["data"]
        assert data["sources"]["kalshi"]["outcome"] == "error"
        assert "503" in data["sources"]["kalshi"]["detail"]
        for side in SIDES:
            assert _quote(data, side, "polymarket")["implied_probability"] == pytest.approx(POLY_PRICES[side])
            assert _quotes(data, side, "kalshi") == []

    def test_kalshi_listing_exception_keeps_polymarket_source(self, env):
        env["kalshi_list"].side_effect = ConnectionError("connection reset")
        result = markets.compare_market_url(url=POLY_URL)
        assert result["status"] is True, result["message"]
        assert result["data"]["sources"]["kalshi"]["outcome"] == "error"
        assert len(result["data"]["side_prices"]["draw"]["quotes"]) >= 1

    def test_polymarket_listing_error_keeps_kalshi_source(self, env):
        env["poly_list"].return_value = {"status": False, "data": None, "message": "HTTP 502 from gamma-api"}
        result = markets.compare_market_url(url=KALSHI_URL)

        assert result["status"] is True, result["message"]
        data = result["data"]
        assert data["sources"]["polymarket"]["outcome"] == "error"
        for side in SIDES:
            assert _quote(data, side, "kalshi")["implied_probability"] == pytest.approx(KALSHI_PRICES[side])
            assert _quotes(data, side, "polymarket") == []

    @pytest.mark.parametrize(
        "events",
        [
            pytest.param([], id="empty"),
            pytest.param([_retick(_kalshi_event(), "KXUCLGAME-26OCT21PSGBAR")], id="other-date"),
            pytest.param([_retick(_kalshi_event(), "KXUCLGAME-26OCT20LIVVIL")], id="other-teams-ticker"),
        ],
    )
    def test_no_matching_kalshi_counterpart(self, env, events):
        _set_kalshi_listing(env, events)
        result = markets.compare_market_url(url=POLY_URL)

        assert result["status"] is True, result["message"]
        data = result["data"]
        assert data["sources"]["kalshi"]["outcome"] != "ok"
        assert all(_quotes(data, side, "kalshi") == [] for side in SIDES)
        assert all(len(_quotes(data, side, "polymarket")) == 1 for side in SIDES)

    def test_ambiguous_kalshi_counterpart_is_not_guessed(self, env):
        twin = _retick(_kalshi_event(), "KXUCLGAME-26OCT20PSGBARG2")
        _set_kalshi_listing(env, [_kalshi_event(), twin])
        result = markets.compare_market_url(url=POLY_URL)

        data = result["data"]
        assert data["sources"]["kalshi"]["outcome"] != "ok"
        assert "ambiguous" in data["sources"]["kalshi"]["detail"].lower()
        assert all(_quotes(data, side, "kalshi") == [] for side in SIDES)

    def test_incomplete_kalshi_counterpart_is_not_used(self, env):
        event = _kalshi_event()
        _k_drop("draw")(event)
        _set_kalshi_listing(env, [event])
        result = markets.compare_market_url(url=POLY_URL)

        data = result["data"]
        assert data["sources"]["kalshi"]["outcome"] != "ok"
        assert all(_quotes(data, side, "kalshi") == [] for side in SIDES)

    def test_kalshi_counterpart_with_fuzzy_team_label_is_not_used(self, env):
        event = _kalshi_event()
        _kalshi_child(event, "home")["yes_sub_title"] = "Paris"
        _set_kalshi_listing(env, [event])
        data = markets.compare_market_url(url=POLY_URL)["data"]
        assert all(_quotes(data, side, "kalshi") == [] for side in SIDES)

    def test_closed_polymarket_counterpart_is_not_used(self, env):
        event = _poly_event()
        _poly_child(event, "draw")["status"] = "closed"
        _set_poly_listing(env, [event])
        result = markets.compare_market_url(url=KALSHI_URL)

        data = result["data"]
        assert data["sources"]["polymarket"]["outcome"] != "ok"
        assert all(_quotes(data, side, "polymarket") == [] for side in SIDES)

    def test_decoy_games_in_the_listing_are_ignored(self, env):
        decoy = _retick(_kalshi_event(), "KXUCLGAME-26OCT20FENSLP")
        for m, sub in zip(decoy["markets"], ("Fenerbahce", "Slavia Prague", "Tie")):
            m["yes_sub_title"] = sub
        _set_kalshi_listing(env, [decoy, _kalshi_event()])
        data = markets.compare_market_url(url=POLY_URL)["data"]
        assert _quote(data, "home", "kalshi")["contract"] == KALSHI_CONTRACTS["home"]


# ============================================================
# Regression: the two-way US-sports path is untouched
# ============================================================


class _NflBoard:
    def __init__(self):
        self.calls = []

    def get_scoreboard(self, date=None):
        self.calls.append(date)
        events = []
        if date == "2026-10-11":
            events = [
                {
                    "id": "401772",
                    "start_time": "2026-10-11T20:25Z",
                    "competitors": [
                        {"team": {"id": "26", "name": "Seattle Seahawks", "abbreviation": "SEA"}, "home_away": "home"},
                        {"team": {"id": "25", "name": "San Francisco 49ers", "abbreviation": "SF"}, "home_away": "away"},
                    ],
                }
            ]
        return {"status": True, "data": {"events": events}, "message": ""}


_NFL_EVENT = {
    "id": "941347",
    "title": "49ers vs. Seahawks",
    "slug": "nfl-sf-sea-2026-10-11",
    "status": "active",
    "markets": [
        {
            "id": "4024680",
            "question": "49ers vs. Seahawks",
            "slug": "nfl-sf-sea-2026-10-11",
            "status": "active",
            "outcomes": [
                {"name": "49ers", "price": 0.385, "clob_token_id": "tok-0"},
                {"name": "Seahawks", "price": 0.615, "clob_token_id": "tok-1"},
            ],
            "sports_market_type": "moneyline",
        }
    ],
}


def test_nfl_event_link_still_routes_through_two_way_compare_odds(env):
    env["poly_event"].return_value = _ok(_NFL_EVENT)
    env["compare"].return_value = {
        "status": True,
        "data": {"sport": "nfl", "event_id": "401772", "polymarket_markets": [{"market_id": "4024680"}]},
        "message": "Odds comparison for San Francisco 49ers @ Seattle Seahawks.",
    }
    with patch("sports_skills.markets._connector._load_sport_module", return_value=_NflBoard()):
        result = markets.compare_market_url(url="https://polymarket.com/event/nfl-sf-sea-2026-10-11")

    assert result["status"] is True, result["message"]
    env["compare"].assert_called_once_with({"params": {"sport": "nfl", "event_id": "401772"}})
    assert env["espn"].calls == []
    assert "market_type" not in result["data"]


def test_two_way_compare_odds_still_refuses_ucl(env):
    result = markets.compare_odds(sport="ucl", event_id=ESPN_EVENT_ID)
    assert result["status"] is False
