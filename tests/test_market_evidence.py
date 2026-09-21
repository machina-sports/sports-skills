"""Market evidence regressions: executable prices, ESPN odds, identity, sources.

Every fixture here is a minimal, source-faithful slice of a real public payload
(ESPN summary pickcenter, ESPN team news, Kalshi order book, Polymarket game
market). Network boundaries are mocked; nothing here places or prices an order.
"""

from unittest.mock import MagicMock, patch

import pytest

from sports_skills.markets._connector import (
    _executable_ask,
    _game_identity,
    _kalshi_ticker_identity,
    _kalshi_yes_ask,
    _normalized_espn_odds,
    _poly_market_identity,
    _team_nickname,
    compare_odds,
    evaluate_market,
)
from sports_skills.nfl._connector import _normalize_game_summary
from sports_skills.nfl._connector import get_news as _get_news

# ============================================================
# Source-faithful fixtures
# ============================================================

# Trimmed from the public ESPN summary for NYG @ LAR (event 401872947):
# header identity + the single DraftKings pickcenter entry.
RAW_NFL_SUMMARY = {
    "header": {
        "id": "401872947",
        "competitions": [
            {
                "id": "401872947",
                "date": "2026-09-22T00:15Z",
                "competitors": [
                    {
                        "id": "14",
                        "homeAway": "home",
                        "score": "0",
                        "team": {
                            "id": "14",
                            "location": "Los Angeles",
                            "name": "Rams",
                            "abbreviation": "LAR",
                            "displayName": "Los Angeles Rams",
                        },
                    },
                    {
                        "id": "19",
                        "homeAway": "away",
                        "score": "0",
                        "team": {
                            "id": "19",
                            "location": "New York",
                            "name": "Giants",
                            "abbreviation": "NYG",
                            "displayName": "New York Giants",
                        },
                    },
                ],
                "status": {"type": {"name": "STATUS_SCHEDULED", "shortDetail": "9/21 - 8:15 PM EDT"}},
            }
        ],
    },
    "pickcenter": [
        {
            "provider": {"id": "100", "name": "Draft Kings", "priority": 1},
            "details": "LAR -6.5",
            "overUnder": 47.5,
            "spread": -6.5,
            "awayTeamOdds": {"favorite": False, "underdog": True, "moneyLine": 240, "teamId": "19"},
            "homeTeamOdds": {"favorite": True, "underdog": False, "moneyLine": -298, "teamId": "14"},
            "moneyline": {
                "displayName": "Moneyline",
                "home": {"close": {"odds": "-298"}, "open": {"odds": "-375"}},
                "away": {"close": {"odds": "+240"}, "open": {"odds": "+295"}},
            },
        }
    ],
}

NFL_SUMMARY = _normalize_game_summary(RAW_NFL_SUMMARY)

# Real normalized Kalshi book shape: dollar-string [price, size] levels, both
# sides quoted as BIDS. A yes ask of 0.27 is the complement of the 0.73 no bid.
KALSHI_BOOK = {"yes_dollars": [["0.2600", "100"]], "no_dollars": [["0.7300", "100"]]}

KALSHI_AWAY_TICKER = "KXNFLGAME-26SEP21NYGLAR-NYG"
KALSHI_HOME_TICKER = "KXNFLGAME-26SEP21NYGLAR-LAR"

POLY_GAME_MARKET = {
    "source": "polymarket",
    "market_id": "5320",
    "title": "Giants vs. Rams",
    "slug": "nfl-nyg-la-2026-09-22",
    "end_date": "2026-09-22T00:15:00Z",
    "sports_market_type": "moneyline",
    "outcomes": [
        {"token_id": "111", "outcome": "Giants", "price": 0.265},
        {"token_id": "222", "outcome": "Rams", "price": 0.735},
    ],
}


def _kalshi_book_response(ticker=KALSHI_AWAY_TICKER, book=None):
    return {
        "status": True,
        "data": {"ticker": ticker, "orderbook": KALSHI_BOOK if book is None else book},
    }


def _sport_module(summary=None):
    mod = MagicMock()
    mod.get_game_summary.return_value = {"status": True, "data": summary or NFL_SUMMARY}
    return mod


# ============================================================
# Fix 2 — ESPN odds contract
# ============================================================


class TestEspnOddsContract:
    def test_nfl_summary_emits_normalized_moneyline_odds(self):
        odds = NFL_SUMMARY["odds"]
        assert odds["home_odds"] == -298
        assert odds["away_odds"] == 240
        assert odds["provider"] == "Draft Kings"
        assert odds["line"] == "close"
        # ESPN publishes no capture timestamp for pickcenter; never invent one.
        assert odds["captured_at"] is None

    def test_nfl_summary_keeps_existing_fields_and_adds_start_time(self):
        assert set(NFL_SUMMARY) >= {"game_info", "competitors", "boxscore", "scoring_plays", "leaders"}
        assert NFL_SUMMARY["game_info"]["start_time"] == "2026-09-22T00:15Z"
        assert [c["home_away"] for c in NFL_SUMMARY["competitors"]] == ["home", "away"]

    def test_sides_are_never_stitched_across_bookmakers(self):
        from sports_skills._espn_base import normalize_summary_odds

        summary = {
            "pickcenter": [
                {
                    "provider": {"id": "38", "name": "Caesars", "priority": 2},
                    "homeTeamOdds": {"moneyLine": -310},
                    "awayTeamOdds": {},
                },
                {
                    "provider": {"id": "100", "name": "Draft Kings", "priority": 1},
                    "homeTeamOdds": {"moneyLine": -298},
                    "awayTeamOdds": {"moneyLine": 240},
                },
            ]
        }
        odds = normalize_summary_odds(summary)
        assert odds["provider"] == "Draft Kings"
        assert (odds["home_odds"], odds["away_odds"]) == (-298, 240)

    def test_open_lines_only_are_labeled_open(self):
        from sports_skills._espn_base import normalize_summary_odds

        summary = {
            "pickcenter": [
                {
                    "provider": {"id": "100", "name": "Draft Kings", "priority": 1},
                    "moneyline": {"home": {"open": {"odds": "-375"}}, "away": {"open": {"odds": "+295"}}},
                }
            ]
        }
        odds = normalize_summary_odds(summary)
        assert odds["line"] == "open"
        assert (odds["home_odds"], odds["away_odds"]) == (-375, 295)

    def test_missing_or_incomplete_odds_return_none(self):
        from sports_skills._espn_base import normalize_summary_odds

        assert normalize_summary_odds({}) is None
        assert normalize_summary_odds({"pickcenter": []}) is None
        assert (
            normalize_summary_odds(
                {"pickcenter": [{"provider": {"name": "Draft Kings"}, "homeTeamOdds": {"moneyLine": -298}}]}
            )
            is None
        )

    def test_markets_accepts_every_sport_odds_shape(self):
        # NFL summary shape (this patch), scoreboard normalize_odds shape
        # (other sports), and the legacy flat shape callers already pass.
        assert _normalized_espn_odds(NFL_SUMMARY)["home_odds"] == -298
        scoreboard_shape = {"odds": {"provider": "DraftKings", "moneyline": {"home": "-298", "away": "+240"}}}
        normalized = _normalized_espn_odds(scoreboard_shape)
        assert (normalized["home_odds"], normalized["away_odds"]) == (-298, 240)
        flat = _normalized_espn_odds({"odds": {"home_odds": -150, "away_odds": 130}})
        assert (flat["home_odds"], flat["away_odds"]) == (-150, 130)
        assert _normalized_espn_odds({"odds": {}}) is None


# ============================================================
# Fix 1 — executable prices, correct side, fee-aware evaluation
# ============================================================


class TestExecutableAsk:
    def test_yes_ask_is_the_complement_of_the_best_no_bid(self):
        ask, reason = _kalshi_yes_ask(KALSHI_BOOK)
        assert reason == ""
        assert ask == {"ask": 0.27, "depth": 100.0}

    def test_legacy_integer_cent_levels_are_read(self):
        ask, reason = _kalshi_yes_ask({"yes": [[26, 100]], "no": [[73, 100]]})
        assert reason == ""
        assert ask["ask"] == 0.27

    def test_deepest_no_bid_is_not_mistaken_for_the_touch(self):
        ask, _ = _kalshi_yes_ask({"no_dollars": [["0.7000", "500"], ["0.7300", "100"]]})
        assert ask["ask"] == 0.27
        assert ask["depth"] == 100.0

    def test_missing_ask_side_fails_closed(self):
        ask, reason = _kalshi_yes_ask({"yes_dollars": [["0.2600", "100"]]})
        assert ask is None
        assert "no ask" in reason.lower() or "no bid" in reason.lower()

    def test_zero_depth_fails_closed(self):
        ask, reason = _kalshi_yes_ask({"no_dollars": [["0.7300", "0"]]})
        assert ask is None
        assert "depth" in reason.lower()

    def test_non_finite_levels_fail_closed(self):
        for bad in ("NaN", "Infinity", "-1"):
            ask, reason = _kalshi_yes_ask({"no_dollars": [[bad, "100"]]})
            assert ask is None, bad
            assert reason

    def test_polymarket_ask_comes_from_the_book_not_the_price_endpoint(self):
        with patch("sports_skills.polymarket") as poly:
            poly.get_order_book.return_value = {
                "status": True,
                "data": {
                    "token_id": "111",
                    "bids": [{"price": 0.26, "size": 900.0}],
                    "asks": [{"price": 0.27, "size": 450.0}],
                    "best_bid": 0.26,
                    "best_ask": 0.27,
                },
            }
            ask, reason = _executable_ask("polymarket", "111")
        assert reason == ""
        assert ask["ask"] == 0.27
        assert ask["depth"] == 450.0
        assert ask["source"] == "orderbook"

    def test_polymarket_empty_book_fails_closed(self):
        with patch("sports_skills.polymarket") as poly:
            poly.get_order_book.return_value = {
                "status": True,
                "data": {"token_id": "111", "bids": [], "asks": [], "best_bid": 0, "best_ask": 0},
            }
            ask, reason = _executable_ask("polymarket", "111")
        assert ask is None
        assert reason


class TestEvaluateMarketPricing:
    def _evaluate(self, params, book=None, ticker=KALSHI_AWAY_TICKER, summary=None):
        with (
            patch("sports_skills.markets._connector._load_sport_module") as load,
            patch("sports_skills.kalshi") as kalshi,
        ):
            load.return_value = _sport_module(summary)
            kalshi.get_market_orderbook.return_value = _kalshi_book_response(ticker, book)
            request = {"sport": "nfl", "event_id": "401872947"}
            request.update(params)
            return evaluate_market({"params": request})

    def test_away_side_prices_the_away_ticker_at_ask_plus_fee(self):
        result = self._evaluate(
            {"kalshi_ticker": KALSHI_AWAY_TICKER, "outcome": 1, "fee_per_contract": 0.005}
        )
        assert result["status"] is True, result["message"]
        assert result["data"]["side"] == "away"
        assert result["data"]["team"] == "New York Giants"
        assert result["data"]["market"]["ask"] == 0.27
        assert result["data"]["effective_cost"] == pytest.approx(0.275)
        assert result["data"]["fee"]["known"] is True
        edge = result["data"]["evaluation"]["edge"]
        assert edge["market_prob"] == pytest.approx(0.275)
        assert edge["fair_prob"] == pytest.approx(0.282030, abs=1e-5)
        assert edge["recommendation"] == "bet"

    def test_home_side_prices_the_home_ticker(self):
        result = self._evaluate(
            {"kalshi_ticker": KALSHI_HOME_TICKER, "outcome": 0, "fee_per_contract": 0.0},
            ticker=KALSHI_HOME_TICKER,
        )
        assert result["status"] is True, result["message"]
        assert result["data"]["side"] == "home"
        assert result["data"]["team"] == "Los Angeles Rams"
        assert result["data"]["evaluation"]["edge"]["fair_prob"] == pytest.approx(0.717970, abs=1e-5)

    def test_reversed_competitor_order_still_maps_home_and_away(self):
        reversed_summary = dict(NFL_SUMMARY, competitors=list(reversed(NFL_SUMMARY["competitors"])))
        result = self._evaluate(
            {"kalshi_ticker": KALSHI_AWAY_TICKER, "outcome": 1, "fee_per_contract": 0.005},
            summary=reversed_summary,
        )
        assert result["status"] is True, result["message"]
        assert result["data"]["team"] == "New York Giants"

    def test_fee_can_flip_a_gross_positive_edge_negative(self):
        gross = self._evaluate(
            {"kalshi_ticker": KALSHI_AWAY_TICKER, "outcome": 1, "fee_per_contract": 0.0}
        )
        net = self._evaluate(
            {"kalshi_ticker": KALSHI_AWAY_TICKER, "outcome": 1, "fee_per_contract": 0.02}
        )
        assert gross["data"]["evaluation"]["edge"]["edge"] > 0
        assert net["data"]["evaluation"]["edge"]["edge"] < 0
        assert net["data"]["evaluation"]["recommendation"] == "no bet"

    def test_unknown_fee_refuses_the_numeric_evaluation(self):
        result = self._evaluate({"kalshi_ticker": KALSHI_AWAY_TICKER, "outcome": 1})
        assert result["status"] is True
        assert result["data"]["evaluation"] is None
        assert result["data"]["fee"]["known"] is False
        assert result["data"]["effective_cost"] is None
        # The executable reference price is still reported, honestly labelled.
        assert result["data"]["market"]["ask"] == 0.27
        assert "fee_per_contract" in result["message"]

    def test_explicit_outcome_zero_is_distinguishable_from_absent(self):
        explicit = self._evaluate(
            {"kalshi_ticker": KALSHI_HOME_TICKER, "outcome": 0, "fee_per_contract": 0.0},
            ticker=KALSHI_HOME_TICKER,
        )
        absent = self._evaluate(
            {"kalshi_ticker": KALSHI_HOME_TICKER, "fee_per_contract": 0.0}, ticker=KALSHI_HOME_TICKER
        )
        assert explicit["data"]["outcome_explicit"] is True
        assert absent["data"]["outcome_explicit"] is False
        assert explicit["data"]["side"] == absent["data"]["side"] == "home"

    def test_missing_ask_refuses_rather_than_falling_back(self):
        result = self._evaluate(
            {"kalshi_ticker": KALSHI_AWAY_TICKER, "outcome": 1, "fee_per_contract": 0.0},
            book={"yes_dollars": [["0.2600", "100"]]},
        )
        assert result["status"] is False
        assert "ask" in result["message"].lower()

    def test_zero_depth_refuses(self):
        result = self._evaluate(
            {"kalshi_ticker": KALSHI_AWAY_TICKER, "outcome": 1, "fee_per_contract": 0.0},
            book={"no_dollars": [["0.7300", "0"]]},
        )
        assert result["status"] is False
        assert "depth" in result["message"].lower()

    def test_fee_pushing_cost_to_or_past_one_refuses(self):
        result = self._evaluate(
            {"kalshi_ticker": KALSHI_AWAY_TICKER, "outcome": 1, "fee_per_contract": 0.8}
        )
        assert result["data"]["evaluation"] is None
        assert "cost" in result["message"].lower()

    def test_missing_espn_odds_still_refuses(self):
        stripped = dict(NFL_SUMMARY, odds=None)
        result = self._evaluate(
            {"kalshi_ticker": KALSHI_AWAY_TICKER, "outcome": 1, "fee_per_contract": 0.0},
            summary=stripped,
        )
        assert result["status"] is False


# ============================================================
# Fix 3 — cross-venue discovery + identity
# ============================================================


class TestIdentity:
    identity = None

    def setup_method(self):
        self.identity = _game_identity(NFL_SUMMARY)

    def test_matchup_query_uses_mascots_both_venues_title_games_by(self):
        assert _team_nickname({"name": "Los Angeles Rams"}) == "Rams"
        assert _team_nickname({"name": "New York Giants"}) == "Giants"

    def test_identity_carries_both_venue_dates(self):
        # Kalshi dates a game by its US venue day, Polymarket by the UTC day.
        assert self.identity["dates"] == {"2026-09-21", "2026-09-22"}
        assert self.identity["home"]["abbreviation"] == "LAR"
        assert self.identity["away"]["abbreviation"] == "NYG"

    def test_kalshi_ticker_for_the_selected_side_validates(self):
        assert _kalshi_ticker_identity(KALSHI_AWAY_TICKER, "nfl", self.identity, "away") == ""
        assert _kalshi_ticker_identity(KALSHI_HOME_TICKER, "nfl", self.identity, "home") == ""

    def test_wrong_team_ticker_is_refused(self):
        reason = _kalshi_ticker_identity(KALSHI_HOME_TICKER, "nfl", self.identity, "away")
        assert "NYG" in reason

    def test_derivative_market_ticker_is_refused(self):
        reason = _kalshi_ticker_identity("KXNFLH1-26SEP21NYGLAR-NYG", "nfl", self.identity, "away")
        assert "full-game" in reason.lower()

    def test_repeat_matchup_on_the_wrong_day_is_refused(self):
        reason = _kalshi_ticker_identity("KXNFLGAME-26SEP28NYGLAR-NYG", "nfl", self.identity, "away")
        assert "2026-09-28" in reason

    def test_unrelated_matchup_is_refused(self):
        reason = _kalshi_ticker_identity("KXNFLGAME-26SEP21NYGLAC-NYG", "nfl", self.identity, "away")
        assert reason

    def test_polymarket_full_game_moneyline_validates(self):
        assert _poly_market_identity(POLY_GAME_MARKET, self.identity, "away") == ""

    def test_polymarket_first_half_is_not_the_full_game(self):
        first_half = dict(POLY_GAME_MARKET, slug="nfl-nyg-la-2026-09-22-1h", title="Giants vs. Rams 1st Half")
        reason = _poly_market_identity(first_half, self.identity, "away")
        assert "full-game" in reason.lower()

    def test_polymarket_spread_and_total_are_refused(self):
        for market_type in ("spreads", "totals"):
            reason = _poly_market_identity(
                dict(POLY_GAME_MARKET, sports_market_type=market_type), self.identity, "away"
            )
            assert "moneyline" in reason.lower()

    def test_polymarket_same_city_other_team_is_refused(self):
        chargers = dict(
            POLY_GAME_MARKET,
            slug="nfl-nyg-lac-2026-09-22",
            title="Giants vs. Chargers",
            outcomes=[
                {"token_id": "331", "outcome": "Giants", "price": 0.46},
                {"token_id": "332", "outcome": "Chargers", "price": 0.54},
            ],
        )
        assert _poly_market_identity(chargers, self.identity, "away") != ""

    def test_polymarket_wrong_day_repeat_matchup_is_refused(self):
        wrong_day = dict(POLY_GAME_MARKET, slug="nfl-nyg-la-2026-12-14")
        reason = _poly_market_identity(wrong_day, self.identity, "away")
        assert "2026-12-14" in reason


class TestDiscovery:
    def _evaluate(self, params, poly_markets):
        with (
            patch("sports_skills.markets._connector._load_sport_module") as load,
            patch("sports_skills.markets._connector._search_polymarket") as search,
            patch("sports_skills.polymarket") as poly,
        ):
            load.return_value = _sport_module()
            search.return_value = poly_markets
            poly.get_order_book.return_value = {
                "status": True,
                "data": {"asks": [{"price": 0.27, "size": 400.0}], "best_ask": 0.27},
            }
            request = {"sport": "nfl", "event_id": "401872947", "fee_per_contract": 0.0}
            request.update(params)
            result = evaluate_market({"params": request})
            return result, search

    def test_explicit_token_resolves_through_the_validated_market(self):
        result, search = self._evaluate({"token_id": "111", "outcome": 1}, [POLY_GAME_MARKET])
        assert result["status"] is True, result["message"]
        assert result["data"]["market"]["venue"] == "polymarket"
        assert result["data"]["market"]["identifier"] == "111"
        # Discovery is bounded: one mascot-pair query, not one per team.
        assert search.call_count == 1
        assert search.call_args[0][0] == "Giants Rams"

    def test_token_naming_the_other_side_is_refused(self):
        result, _ = self._evaluate({"token_id": "222", "outcome": 1}, [POLY_GAME_MARKET])
        assert result["status"] is False
        assert "222" in result["message"]

    def test_token_absent_from_every_validated_market_is_refused(self):
        result, _ = self._evaluate({"token_id": "999", "outcome": 1}, [POLY_GAME_MARKET])
        assert result["status"] is False

    def test_derivative_candidates_are_never_selected(self):
        first_half = dict(POLY_GAME_MARKET, market_id="5321", slug="nfl-nyg-la-2026-09-22-1h")
        spread = dict(POLY_GAME_MARKET, market_id="5322", sports_market_type="spreads")
        result, _ = self._evaluate({"outcome": 1}, [first_half, spread, POLY_GAME_MARKET])
        assert result["status"] is True, result["message"]
        assert result["data"]["market"]["identifier"] == "111"

    def test_two_ambiguous_full_game_candidates_are_refused(self):
        twin = dict(POLY_GAME_MARKET, market_id="5399")
        result, _ = self._evaluate({"outcome": 1}, [POLY_GAME_MARKET, twin])
        assert result["status"] is False
        assert "ambiguous" in result["message"].lower()

    def test_no_candidate_reports_unmatched_without_inventing_a_price(self):
        result, _ = self._evaluate({"outcome": 1}, [])
        assert result["data"]["evaluation"] is None
        assert result["data"]["sources"]["polymarket"]["outcome"] in ("empty", "unmatched")
        assert result["data"]["market"] is None


# ============================================================
# Fix 5 — NFL team news
# ============================================================

TEAM_CATEGORY_RAMS = {
    "id": 1583,
    "type": "team",
    "uid": "s:20~l:28~t:14",
    "description": "Los Angeles Rams",
    "sportId": 28,
    "teamId": 14,
    "team": {"id": 14, "description": "Los Angeles Rams", "abbreviation": "LAR"},
}
TEAM_CATEGORY_GIANTS = {
    "id": 2884,
    "type": "team",
    "uid": "s:20~l:28~t:19",
    "description": "New York Giants",
    "sportId": 28,
    "teamId": 19,
    "team": {"id": 19, "description": "New York Giants", "abbreviation": "NYG"},
}
# A topic category whose `id` collides with a team ID — never a team match.
TOPIC_CATEGORY = {"id": 14, "type": "topic", "description": "news - nfl", "sportId": 0, "topicId": 121}

NEWS_PAYLOAD = {
    "header": "NFL News",
    "articles": [
        {
            "id": 49995686,
            "headline": "NFL Week 3 betting: Odds, lines and totals for every game",
            "description": "A look at the odds for every NFL game in Week 3.",
            "published": "2026-09-21T16:51:40Z",
            "type": "Story",
            "categories": [TEAM_CATEGORY_RAMS, TEAM_CATEGORY_GIANTS, TOPIC_CATEGORY],
            "links": {"web": {"href": "https://www.espn.com/nfl/story/_/id/49995686"}},
        },
        {
            "id": 49995700,
            "headline": "Giants name their Week 4 starter",
            "description": "",
            "published": "2026-09-21T18:00:00Z",
            "type": "Story",
            "categories": [TEAM_CATEGORY_GIANTS],
            "links": {"web": {"href": "https://www.espn.com/nfl/story/_/id/49995700"}},
        },
        {
            "id": 49995711,
            "headline": "Rams mentioned in a headline about the Rams",
            "description": "",
            "published": "2026-09-21T19:00:00Z",
            "type": "Story",
            "categories": [TOPIC_CATEGORY],
            "links": {"web": {"href": "https://www.espn.com/nfl/story/_/id/49995711"}},
        },
    ],
}


class TestNflTeamNews:
    def _news(self, payload, team_id=None):
        with patch("sports_skills.nfl._connector.espn_request") as request:
            request.return_value = payload
            params = {"team_id": team_id} if team_id is not None else {}
            return _get_news({"params": params}), request

    def test_team_news_uses_the_league_news_endpoint_with_a_team_filter(self):
        _, request = self._news(NEWS_PAYLOAD, team_id=14)
        args, kwargs = request.call_args
        assert args[1] == "news"
        assert (kwargs.get("params") or (args[2] if len(args) > 2 else {})) == {"team": "14"}

    def test_requested_team_is_validated_through_category_tags(self):
        result, _ = self._news(NEWS_PAYLOAD, team_id=14)
        headlines = [a["headline"] for a in result["articles"]]
        assert "NFL Week 3 betting: Odds, lines and totals for every game" in headlines
        # Headline substrings are not tags: this Rams story carries no team tag.
        assert "Rams mentioned in a headline about the Rams" not in headlines
        # A Giants-only story is not Rams news.
        assert "Giants name their Week 4 starter" not in headlines
        assert result["count"] == len(result["articles"]) == 1

    def test_string_and_int_team_ids_agree(self):
        as_int, _ = self._news(NEWS_PAYLOAD, team_id=19)
        as_str, _ = self._news(NEWS_PAYLOAD, team_id="19")
        assert [a["headline"] for a in as_int["articles"]] == [a["headline"] for a in as_str["articles"]]
        assert as_int["count"] == 2

    def test_topic_category_id_is_not_a_team_id(self):
        # Only the topic-tagged article would match if `id` were read as teamId.
        result, _ = self._news({"articles": [NEWS_PAYLOAD["articles"][2]]}, team_id=14)
        assert result["articles"] == []
        assert result["count"] == 0

    def test_malformed_empty_object_is_an_error_not_zero_matches(self):
        result, _ = self._news({}, team_id=14)
        assert result.get("error") is True
        assert "articles" in result["message"]

    def test_non_list_articles_is_an_error(self):
        result, _ = self._news({"articles": {"0": {}}}, team_id=14)
        assert result.get("error") is True

    def test_genuinely_empty_article_list_is_a_success(self):
        result, _ = self._news({"articles": []}, team_id=14)
        assert result.get("error") is not True
        assert result["count"] == 0
        assert result["total_articles"] == 0

    def test_transport_failure_is_surfaced(self):
        result, _ = self._news({"error": True, "status_code": 503, "message": "ESPN unavailable"})
        assert result.get("error") is True
        assert result["status_code"] == 503

    def test_league_news_is_unfiltered(self):
        result, request = self._news(NEWS_PAYLOAD)
        assert result["count"] == 3
        assert request.call_args[0][1] == "news"


# ============================================================
# Fix 6 — partial-source outcomes
# ============================================================


def _compare(summary, kalshi=None, poly=None, prophetx=None):
    with (
        patch("sports_skills.markets._connector._load_sport_module") as load,
        patch("sports_skills.markets._connector._search_kalshi") as k,
        patch("sports_skills.markets._connector._search_polymarket") as p,
        patch("sports_skills.markets._connector._search_prophetx") as px,
    ):
        load.return_value = _sport_module(summary)
        for mock, value in ((k, kalshi), (p, poly), (px, prophetx)):
            if isinstance(value, Exception):
                mock.side_effect = value
            else:
                mock.return_value = value or []
        return compare_odds({"params": {"sport": "nfl", "event_id": "401872947"}})


class TestPartialSources:
    def test_independent_provider_failure_is_reported_as_error_not_empty(self):
        result = _compare(NFL_SUMMARY, kalshi=RuntimeError("kalshi 503"), poly=[POLY_GAME_MARKET])
        sources = result["data"]["sources"]
        assert sources["kalshi"]["outcome"] == "error"
        assert "503" in sources["kalshi"]["detail"]
        assert sources["polymarket"]["outcome"] == "ok"
        assert sources["prophetx"]["outcome"] == "empty"
        assert result["status"] is True

    def test_espn_odds_absent_is_distinct_from_matchup_missing(self):
        result = _compare(dict(NFL_SUMMARY, odds=None), poly=[POLY_GAME_MARKET])
        assert result["data"]["sources"]["espn"]["outcome"] == "empty"
        assert result["data"]["home_team"] == "Los Angeles Rams"

        with_odds = _compare(NFL_SUMMARY, poly=[POLY_GAME_MARKET])
        assert with_odds["data"]["sources"]["espn"]["outcome"] == "ok"

    def test_successful_search_with_rejected_identity_is_unmatched(self):
        unrelated = dict(
            POLY_GAME_MARKET,
            outcomes=[
                {"token_id": "441", "outcome": "Chiefs", "price": 0.5},
                {"token_id": "442", "outcome": "Bills", "price": 0.5},
            ],
        )
        result = _compare(dict(NFL_SUMMARY, odds=None), poly=[unrelated])
        assert result["data"]["sources"]["polymarket"]["outcome"] == "unmatched"

    def test_all_unusable_comparison_fails(self):
        result = _compare(dict(NFL_SUMMARY, odds=None))
        assert result["status"] is False
        assert result["data"]["completeness"]["usable_sources"] == []

    def test_partial_useful_response_still_succeeds(self):
        result = _compare(NFL_SUMMARY, kalshi=RuntimeError("boom"), poly=RuntimeError("boom"))
        assert result["status"] is True
        assert result["data"]["completeness"]["usable_sources"] == ["espn"]
        assert result["data"]["completeness"]["complete"] is False

    def test_reference_prices_are_not_called_executable_arbitrage(self):
        result = _compare(NFL_SUMMARY, poly=[POLY_GAME_MARKET])
        arb = result["data"]["arbitrage_check"]
        assert arb is not None
        assert arb["price_basis"] == "reference"
        assert "executable" in arb["note"].lower()

    def test_no_zero_price_is_invented_for_a_missing_field(self):
        priceless = dict(
            POLY_GAME_MARKET,
            outcomes=[
                {"token_id": "111", "outcome": "Giants"},
                {"token_id": "222", "outcome": "Rams"},
            ],
        )
        result = _compare(dict(NFL_SUMMARY, odds=None), poly=[priceless])
        assert result["data"]["arbitrage_check"] is None
        assert result["status"] is False


# ============================================================
# Review blockers — cross-venue admission, date identity, null shapes
# ============================================================

# The same matchup, a different meeting of it: NYG @ LAR again in December.
POLY_WRONG_DATE_MARKET = dict(
    POLY_GAME_MARKET,
    market_id="5911",
    slug="nfl-nyg-la-2026-12-22",
    outcomes=[
        {"token_id": "911", "outcome": "Giants", "price": 0.1},
        {"token_id": "922", "outcome": "Rams", "price": 0.9},
    ],
)

# Real ProphetX shape: one event carries the full-game Moneyline alongside
# period derivatives that share the "moneyline" type.
PROPHETX_FULL_GAME_MARKET = {
    "market_key": "1700008786:219",
    "title": "Moneyline",
    "type": "moneyline",
    "total_stake": 234043.45,
    "selections_available": True,
    "outcomes": [
        {"outcome": "Los Angeles Rams -275", "odds_american": -275, "implied_probability": 0.7333},
        {"outcome": "New York Giants +270", "odds_american": 270, "implied_probability": 0.2703},
    ],
}
PROPHETX_FIRST_HALF_MARKET = {
    "market_key": "1700008786:64",
    "title": "First Half Moneyline",
    "type": "moneyline",
    "total_stake": 15646.79,
    "selections_available": True,
    "outcomes": [
        {"outcome": "Los Angeles Rams -205", "odds_american": -205, "implied_probability": 0.6721},
        {"outcome": "New York Giants +190", "odds_american": 190, "implied_probability": 0.3448},
    ],
}


def _prophetx_event(markets, scheduled="2026-09-22T00:15:00Z"):
    event = {
        "source": "prophetx",
        "event_id": 1700008786,
        "title": "New York Giants at Los Angeles Rams",
        "tournament": "NFL",
        "markets": list(markets),
    }
    if scheduled is not None:
        event["scheduled"] = scheduled
    return event


# Real Kalshi shape: one dated event, one market per team, prices in cents.
def _kalshi_event(event_ticker="KXNFLGAME-26SEP21NYGLAR", markets=None):
    return {
        "source": "kalshi",
        "event_ticker": event_ticker,
        "title": "NY Giants vs LA Rams",
        "status": "active",
        "markets": [
            {"ticker": f"{event_ticker}-LAR", "title": "Los Angeles R wins", "yes_price": 73, "no_price": 26},
            {"ticker": f"{event_ticker}-NYG", "title": "New York G wins", "yes_price": 26, "no_price": 73},
        ]
        if markets is None
        else markets,
    }


def _labels(result):
    arb = result["data"]["arbitrage_check"]
    return [allocation.get("label", "") for allocation in (arb or {}).get("allocations", [])]


def _dateless_summary(start_time=""):
    return dict(NFL_SUMMARY, game_info=dict(NFL_SUMMARY["game_info"], start_time=start_time))


class TestPolymarketDateAdmission:
    """A December meeting of this matchup is not this September game."""

    def test_wrong_date_moneyline_never_prices_this_game(self):
        result = _compare(NFL_SUMMARY, poly=[POLY_WRONG_DATE_MARKET])
        assert result["data"]["sources"]["polymarket"]["outcome"] == "unmatched"
        assert "polymarket" not in result["data"]["completeness"]["usable_sources"]
        assert not any(label.startswith("poly_") for label in _labels(result))
        # 0.1 for the Giants in December is not an arbitrage against September.
        assert result["data"]["arbitrage_check"]["arbitrage_found"] is False

    def test_wrong_date_moneyline_is_still_reported_as_raw_discovery(self):
        result = _compare(NFL_SUMMARY, poly=[POLY_WRONG_DATE_MARKET])
        assert result["data"]["polymarket_markets"] == [POLY_WRONG_DATE_MARKET]

    def test_derivative_polymarket_markets_never_price_this_game(self):
        spread = dict(POLY_GAME_MARKET, market_id="5322", sports_market_type="spreads")
        first_half = dict(POLY_GAME_MARKET, market_id="5321", slug="nfl-nyg-la-2026-09-22-1h")
        result = _compare(dict(NFL_SUMMARY, odds=None), poly=[spread, first_half])
        assert result["data"]["sources"]["polymarket"]["outcome"] == "unmatched"
        assert result["data"]["arbitrage_check"] is None

    def test_the_validated_moneyline_still_prices_this_game(self):
        result = _compare(NFL_SUMMARY, poly=[POLY_GAME_MARKET])
        assert result["data"]["sources"]["polymarket"]["outcome"] == "ok"
        assert any(label.startswith("poly_") for label in _labels(result))

    def test_a_dateless_espn_summary_admits_no_market(self):
        result = _compare(_dateless_summary(), poly=[POLY_GAME_MARKET])
        assert result["data"]["sources"]["polymarket"]["outcome"] == "unmatched"
        assert "start time" in result["data"]["sources"]["polymarket"]["detail"].lower()


class TestProphetXDerivativeAdmission:
    """Only the exact full-game Moneyline of a date-compatible event."""

    def test_first_half_moneyline_is_never_the_game_moneyline(self):
        event = _prophetx_event([PROPHETX_FIRST_HALF_MARKET])
        result = _compare(dict(NFL_SUMMARY, odds=None), prophetx=[event])
        assert result["data"]["sources"]["prophetx"]["outcome"] == "unmatched"
        assert result["data"]["arbitrage_check"] is None

    def test_the_full_game_moneyline_is_not_shadowed_by_a_derivative(self):
        event = _prophetx_event([PROPHETX_FIRST_HALF_MARKET, PROPHETX_FULL_GAME_MARKET])
        result = _compare(dict(NFL_SUMMARY, odds=None), prophetx=[event])
        assert result["data"]["sources"]["prophetx"]["outcome"] == "ok"
        labels = _labels(result)
        assert labels == ["prophetx_Los Angeles Rams -275", "prophetx_New York Giants +270"]

    def test_a_december_prophetx_event_is_not_this_game(self):
        event = _prophetx_event([PROPHETX_FULL_GAME_MARKET], scheduled="2026-12-22T01:15:00Z")
        result = _compare(dict(NFL_SUMMARY, odds=None), prophetx=[event])
        assert result["data"]["sources"]["prophetx"]["outcome"] == "unmatched"
        assert result["data"]["arbitrage_check"] is None

    @pytest.mark.parametrize("scheduled", [None, "", "not-a-timestamp"])
    def test_an_undated_prophetx_event_cannot_be_matched(self, scheduled):
        event = _prophetx_event([PROPHETX_FULL_GAME_MARKET], scheduled=scheduled)
        result = _compare(dict(NFL_SUMMARY, odds=None), prophetx=[event])
        assert result["data"]["sources"]["prophetx"]["outcome"] == "unmatched"
        assert result["data"]["arbitrage_check"] is None


class TestKalshiReferenceLegs:
    """Kalshi's validated pair is a reference price, and it does get compared."""

    def test_both_validated_sides_join_the_comparison(self):
        result = _compare(NFL_SUMMARY, kalshi=[_kalshi_event()])
        assert result["data"]["sources"]["kalshi"]["outcome"] == "ok"
        assert "kalshi" in result["data"]["completeness"]["usable_sources"]
        assert _labels(result) == ["kalshi_Los Angeles Rams", "kalshi_New York Giants"]

    def test_cent_prices_are_normalized_to_probabilities(self):
        result = _compare(dict(NFL_SUMMARY, odds=None), kalshi=[_kalshi_event()])
        arb = result["data"]["arbitrage_check"]
        probs = {a["label"]: a["market_prob"] for a in arb["allocations"]}
        assert probs["kalshi_Los Angeles Rams"] == pytest.approx(0.73)
        assert probs["kalshi_New York Giants"] == pytest.approx(0.26)

    def test_dollar_shaped_prices_are_read_as_probabilities_too(self):
        dollars = _kalshi_event(
            markets=[
                {"ticker": "KXNFLGAME-26SEP21NYGLAR-LAR", "yes_price": 0.73},
                {"ticker": "KXNFLGAME-26SEP21NYGLAR-NYG", "yes_price": 0.26},
            ]
        )
        result = _compare(dict(NFL_SUMMARY, odds=None), kalshi=[dollars])
        arb = result["data"]["arbitrage_check"]
        probs = {a["label"]: a["market_prob"] for a in arb["allocations"]}
        assert probs["kalshi_Los Angeles Rams"] == pytest.approx(0.73)

    def test_kalshi_only_is_a_usable_complete_comparison(self):
        result = _compare(dict(NFL_SUMMARY, odds=None), kalshi=[_kalshi_event()])
        assert result["status"] is True
        assert result["data"]["completeness"]["usable_sources"] == ["kalshi"]

    def test_all_venues_together_stay_usable(self):
        result = _compare(
            NFL_SUMMARY,
            kalshi=[_kalshi_event()],
            poly=[POLY_GAME_MARKET],
            prophetx=[_prophetx_event([PROPHETX_FULL_GAME_MARKET])],
        )
        assert result["data"]["completeness"]["complete"] is True
        assert sorted(result["data"]["completeness"]["usable_sources"]) == [
            "espn",
            "kalshi",
            "polymarket",
            "prophetx",
        ]

    def test_a_december_kalshi_event_is_not_this_game(self):
        result = _compare(dict(NFL_SUMMARY, odds=None), kalshi=[_kalshi_event("KXNFLGAME-26DEC21NYGLAR")])
        assert result["data"]["sources"]["kalshi"]["outcome"] == "unmatched"
        assert result["data"]["arbitrage_check"] is None

    def test_one_validated_side_is_not_half_a_market(self):
        one_side = _kalshi_event(
            markets=[{"ticker": "KXNFLGAME-26SEP21NYGLAR-LAR", "yes_price": 73}]
        )
        result = _compare(dict(NFL_SUMMARY, odds=None), kalshi=[one_side])
        assert result["data"]["sources"]["kalshi"]["outcome"] == "unmatched"
        assert result["data"]["arbitrage_check"] is None

    @pytest.mark.parametrize("price", [0, 100, None, "73", -5])
    def test_unusable_cent_prices_are_skipped(self, price):
        broken = _kalshi_event(
            markets=[
                {"ticker": "KXNFLGAME-26SEP21NYGLAR-LAR", "yes_price": price},
                {"ticker": "KXNFLGAME-26SEP21NYGLAR-NYG", "yes_price": 26},
            ]
        )
        result = _compare(dict(NFL_SUMMARY, odds=None), kalshi=[broken])
        assert result["data"]["sources"]["kalshi"]["outcome"] == "unmatched"
        assert result["data"]["arbitrage_check"] is None

    def test_every_compared_price_is_labelled_a_reference(self):
        result = _compare(NFL_SUMMARY, kalshi=[_kalshi_event()], poly=[POLY_GAME_MARKET])
        assert result["data"]["price_basis"] == "reference"
        assert "executable" in result["data"]["price_basis_note"].lower()
        assert result["data"]["arbitrage_check"]["price_basis"] == "reference"


class TestEvaluateMarketRequiresADate:
    """No ESPN start time means no proof a dated ticker is this game."""

    def _evaluate(self, params, summary):
        with (
            patch("sports_skills.markets._connector._load_sport_module") as load,
            patch("sports_skills.markets._connector._search_polymarket") as search,
            patch("sports_skills.kalshi") as kalshi,
        ):
            load.return_value = _sport_module(summary)
            search.return_value = [POLY_GAME_MARKET]
            kalshi.get_market_orderbook.return_value = _kalshi_book_response()
            request = {"sport": "nfl", "event_id": "401872947", "fee_per_contract": 0.0}
            request.update(params)
            return evaluate_market({"params": request}), kalshi

    @pytest.mark.parametrize("start_time", ["", "not-a-timestamp"])
    def test_an_undated_event_refuses_a_december_ticker(self, start_time):
        result, kalshi = self._evaluate(
            {"kalshi_ticker": "KXNFLGAME-26DEC21NYGLAR-NYG", "outcome": 1},
            _dateless_summary(start_time),
        )
        assert result["status"] is False
        assert "start time" in result["message"].lower()
        # A refusal, not a priced bet with a warning stapled to it.
        assert result["data"] is None
        kalshi.get_market_orderbook.assert_not_called()

    def test_an_undated_event_refuses_the_matching_ticker_too(self):
        # Fail closed: without a date nothing distinguishes this ticker from
        # the December one above.
        result, _ = self._evaluate(
            {"kalshi_ticker": KALSHI_AWAY_TICKER, "outcome": 1}, _dateless_summary()
        )
        assert result["status"] is False
        assert "start time" in result["message"].lower()

    def test_an_undated_event_refuses_polymarket_discovery(self):
        result, _ = self._evaluate({"outcome": 1}, _dateless_summary())
        assert result["status"] is False
        assert "start time" in result["message"].lower()

    def test_a_december_ticker_is_refused_on_a_dated_event(self):
        result, _ = self._evaluate(
            {"kalshi_ticker": "KXNFLGAME-26DEC21NYGLAR-NYG", "outcome": 1}, NFL_SUMMARY
        )
        assert result["status"] is False
        assert "2026-12-21" in result["message"]

    @pytest.mark.parametrize("ticker", ["KXNFLGAME-26SEP21NYGLAR-NYG", "KXNFLGAME-26SEP22NYGLAR-NYG"])
    def test_either_venue_calendar_day_remains_valid(self, ticker):
        # 00:15 UTC kickoff: Kalshi dates it by the US venue day, Polymarket by
        # the UTC day, and both name the same game.
        result, _ = self._evaluate({"kalshi_ticker": ticker, "outcome": 1}, NFL_SUMMARY)
        assert result["status"] is True, result["message"]
        assert result["data"]["market"]["ask"] == 0.27


class TestPickcenterNullShapes:
    """Optional ESPN containers arrive null or wrong-shaped; none may raise."""

    @pytest.mark.parametrize(
        "entries",
        [
            [{"moneyline": None}],
            [{"moneyline": {"home": None}}],
            [{"moneyline": {"home": {"close": None}, "away": {"close": {"odds": "+240"}}}}],
            [{"homeTeamOdds": None, "awayTeamOdds": None}],
            [{"provider": "unexpected", "moneyline": {}}],
            [{"provider": None, "homeTeamOdds": {"moneyLine": None}, "awayTeamOdds": None}],
            ["not-a-dict"],
        ],
    )
    def test_incomplete_or_wrong_shaped_entries_return_none(self, entries):
        from sports_skills._espn_base import normalize_summary_odds

        assert normalize_summary_odds({"pickcenter": entries}) is None

    def test_a_wrong_shaped_entry_does_not_hide_the_next_valid_provider(self):
        from sports_skills._espn_base import normalize_summary_odds

        summary = {
            "pickcenter": [
                {"provider": "unexpected", "moneyline": None},
                {"provider": {"id": "100", "name": "Draft Kings", "priority": 1},
                 "homeTeamOdds": {"moneyLine": -298},
                 "awayTeamOdds": {"moneyLine": 240}},
            ]
        }
        odds = normalize_summary_odds(summary)
        assert odds["provider"] == "Draft Kings"
        assert (odds["home_odds"], odds["away_odds"]) == (-298, 240)

    def test_sides_are_never_stitched_across_a_broken_entry(self):
        from sports_skills._espn_base import normalize_summary_odds

        summary = {
            "pickcenter": [
                {"provider": {"id": "38", "name": "Caesars", "priority": 1},
                 "moneyline": None,
                 "homeTeamOdds": {"moneyLine": -310},
                 "awayTeamOdds": None},
                {"provider": {"id": "100", "name": "Draft Kings", "priority": 2},
                 "homeTeamOdds": {"moneyLine": -298},
                 "awayTeamOdds": {"moneyLine": 240}},
            ]
        }
        odds = normalize_summary_odds(summary)
        assert odds["provider"] == "Draft Kings"
        assert odds["home_odds"] == -298

    def test_close_is_preferred_over_current_within_one_entry(self):
        from sports_skills._espn_base import normalize_summary_odds

        summary = {
            "pickcenter": [
                {"provider": {"id": "100", "name": "Draft Kings", "priority": 1},
                 "moneyline": {"home": {"close": {"odds": "-298"}}, "away": {"close": {"odds": "+240"}}},
                 "homeTeamOdds": {"moneyLine": -375},
                 "awayTeamOdds": {"moneyLine": 295}},
            ]
        }
        odds = normalize_summary_odds(summary)
        assert odds["line"] == "close"
        assert (odds["home_odds"], odds["away_odds"]) == (-298, 240)
