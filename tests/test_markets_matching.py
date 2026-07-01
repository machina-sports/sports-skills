"""Tests for cross-venue matching and unified prices (markets module)."""

from unittest.mock import patch

from sports_skills.markets._connector import (
    _parse_at_time,
    _parse_kalshi_game_event,
    _parse_poly_game_slug,
    _titles_match,
    get_market_price,
    get_price_history,
    match_markets,
)

# ============================================================
# Identifier Parsing
# ============================================================


class TestParseKalshiGameEvent:
    def test_with_time_component(self):
        assert _parse_kalshi_game_event("KXMLBGAME-26JUN062210NYMSD") == (
            "2026-06-06",
            "NYMSD",
        )

    def test_without_time_component(self):
        # World Cup game tickers carry no HHMM part.
        assert _parse_kalshi_game_event("KXWCGAME-26JUN27JORARG") == (
            "2026-06-27",
            "JORARG",
        )

    def test_non_game_ticker(self):
        assert _parse_kalshi_game_event("KXMLB-26") is None
        assert _parse_kalshi_game_event("KXMENWORLDCUP-26-FR") is None

    def test_empty(self):
        assert _parse_kalshi_game_event("") is None


class TestParsePolyGameSlug:
    def test_plain_slug(self):
        assert _parse_poly_game_slug("mlb-nym-sd-2026-06-06") == (
            "2026-06-06",
            "nym",
            "sd",
        )

    def test_suffixed_slug(self):
        # Props variants share the game prefix.
        assert _parse_poly_game_slug("fifwc-jor-arg-2026-06-27-exact-score") == (
            "2026-06-27",
            "jor",
            "arg",
        )

    def test_non_game_slug(self):
        assert _parse_poly_game_slug("will-france-win-the-world-cup") is None

    def test_empty(self):
        assert _parse_poly_game_slug("") is None


class TestTitlesMatch:
    def test_straight_orientation(self):
        assert _titles_match("Milwaukee vs Colorado", "Milwaukee Brewers vs. Colorado Rockies")

    def test_crossed_orientation(self):
        # Venues may list home/away in opposite order.
        assert _titles_match("Colorado vs Milwaukee", "Milwaukee Brewers vs. Colorado Rockies")

    def test_different_games(self):
        assert not _titles_match("Jordan vs Argentina", "Colombia vs. Portugal")

    def test_non_matchup_title(self):
        assert not _titles_match("Pro Baseball Champion", "Milwaukee vs. Colorado")


class TestParseAtTime:
    def test_none(self):
        assert _parse_at_time(None) is None

    def test_unix_int(self):
        assert _parse_at_time(1780500000) == 1780500000

    def test_numeric_string(self):
        assert _parse_at_time("1780500000") == 1780500000

    def test_iso_string(self):
        assert _parse_at_time("2026-06-01T00:00:00+00:00") == 1780272000

    def test_naive_iso_treated_as_utc(self):
        assert _parse_at_time("2026-06-01T00:00:00") == 1780272000


# ============================================================
# match_markets (mocked venues)
# ============================================================

_KALSHI_EVENTS = {
    "status": True,
    "data": {
        "events": [
            {
                "event_ticker": "KXMLBGAME-26JUN062210NYMSD",
                "title": "New York M vs San Diego",
                "markets": [
                    {"ticker": "KXMLBGAME-26JUN062210NYMSD-NYM"},
                    {"ticker": "KXMLBGAME-26JUN062210NYMSD-SD"},
                ],
            },
            {
                "event_ticker": "KXMLBGAME-26JUN062110MILCOL",
                "title": "Milwaukee vs Colorado",
                "markets": [{"ticker": "KXMLBGAME-26JUN062110MILCOL-MIL"}],
            },
            # Futures event — must be ignored, not unmatched.
            {"event_ticker": "KXMLB-26", "title": "Pro Baseball Champion"},
        ]
    },
}

_POLY_EVENTS = {
    "status": True,
    "data": {
        "events": [
            {
                "id": "100",
                "slug": "mlb-nym-sd-2026-06-06",
                "title": "New York Mets vs. San Diego Padres",
                "markets": [
                    {
                        "question": "Mets vs. Padres",
                        "sports_market_type": "moneyline",
                        "clob_token_ids": ["t1", "t2"],
                        "outcomes": [{"name": "New York Mets"}, {"name": "San Diego Padres"}],
                    }
                ],
            },
            {
                # Different team codes than Kalshi's MILCOL would produce
                # via code join — forces the title fallback.
                "id": "200",
                "slug": "mlb-brew-rock-2026-06-06",
                "title": "Milwaukee Brewers vs. Colorado Rockies",
                "markets": [
                    {
                        "question": "Brewers vs. Rockies",
                        "sports_market_type": "moneyline",
                        "clob_token_ids": ["t3", "t4"],
                        "outcomes": [{"name": "Milwaukee Brewers"}, {"name": "Colorado Rockies"}],
                    }
                ],
            },
            {
                "id": "300",
                "slug": "mlb-atl-cws-2026-06-06",
                "title": "Atlanta Braves vs. Chicago White Sox",
                "markets": [],
            },
        ]
    },
}


class TestMatchMarkets:
    @patch("sports_skills.polymarket")
    @patch("sports_skills.kalshi")
    def test_code_and_title_matching(self, mock_kalshi, mock_poly):
        mock_kalshi.get_todays_events.return_value = _KALSHI_EVENTS
        mock_poly.get_todays_events.return_value = _POLY_EVENTS

        result = match_markets({"params": {"sport": "mlb"}})

        assert result["status"] is True
        data = result["data"]
        assert data["match_count"] == 2

        by_ticker = {m["kalshi"]["event_ticker"]: m for m in data["matches"]}
        code_match = by_ticker["KXMLBGAME-26JUN062210NYMSD"]
        assert code_match["match_method"] == "code"
        assert code_match["polymarket"]["slug"] == "mlb-nym-sd-2026-06-06"
        assert code_match["polymarket"]["markets"][0]["token_ids"] == ["t1", "t2"]

        title_match = by_ticker["KXMLBGAME-26JUN062110MILCOL"]
        assert title_match["match_method"] == "title"
        assert title_match["polymarket"]["slug"] == "mlb-brew-rock-2026-06-06"

        # Futures event ignored entirely; the unmatched poly game listed.
        assert data["unmatched"]["kalshi"] == []
        assert data["unmatched"]["polymarket"] == ["mlb-atl-cws-2026-06-06"]

    @patch("sports_skills.polymarket")
    @patch("sports_skills.kalshi")
    def test_date_filter(self, mock_kalshi, mock_poly):
        mock_kalshi.get_todays_events.return_value = _KALSHI_EVENTS
        mock_poly.get_todays_events.return_value = _POLY_EVENTS

        result = match_markets({"params": {"sport": "mlb", "date": "2030-01-01"}})

        assert result["status"] is True
        assert result["data"]["match_count"] == 0

    @patch("sports_skills.polymarket")
    @patch("sports_skills.kalshi")
    def test_canonical_event_upgrade(self, mock_kalshi, mock_poly):
        # The listed poly event is a props variant without moneylines;
        # match_markets must fetch the canonical slug for token ids.
        mock_kalshi.get_todays_events.return_value = {
            "status": True,
            "data": {
                "events": [
                    {
                        "event_ticker": "KXWCGAME-26JUN27JORARG",
                        "title": "Jordan vs Argentina",
                        "markets": [{"ticker": "KXWCGAME-26JUN27JORARG-JOR"}],
                    }
                ]
            },
        }
        mock_poly.get_todays_events.return_value = {
            "status": True,
            "data": {
                "events": [
                    {
                        "id": "401",
                        "slug": "fifwc-jor-arg-2026-06-27-exact-score",
                        "title": "Jordan vs. Argentina - Exact Score",
                        "markets": [
                            {"sports_market_type": "soccer_exact_score"}
                        ],
                    }
                ]
            },
        }
        mock_poly.get_event_details.return_value = {
            "status": True,
            "data": {
                "id": "400",
                "slug": "fifwc-jor-arg-2026-06-27",
                "title": "Jordan vs. Argentina",
                "markets": [
                    {
                        "question": "Will Jordan vs. Argentina end in a draw?",
                        "sports_market_type": "moneyline",
                        "clob_token_ids": ["d1", "d2"],
                        "outcomes": [{"name": "Yes"}, {"name": "No"}],
                    }
                ],
            },
        }

        result = match_markets({"params": {"sport": "worldcup"}})

        assert result["status"] is True
        match = result["data"]["matches"][0]
        assert match["polymarket"]["slug"] == "fifwc-jor-arg-2026-06-27"
        assert match["polymarket"]["markets"][0]["token_ids"] == ["d1", "d2"]
        mock_poly.get_event_details.assert_called_once_with(
            slug="fifwc-jor-arg-2026-06-27"
        )

    def test_unsupported_sport(self):
        result = match_markets({"params": {"sport": "cricket"}})
        assert result["status"] is False
        assert "not available on both venues" in result["message"]

    def test_missing_sport(self):
        result = match_markets({"params": {}})
        assert result["status"] is False


# ============================================================
# get_market_price (mocked venues)
# ============================================================


class TestGetMarketPrice:
    @patch("sports_skills.kalshi")
    def test_kalshi_current_dollars_payload(self, mock_kalshi):
        mock_kalshi.get_market.return_value = {
            "status": True,
            "data": {"last_price_dollars": "0.1700", "yes_bid_dollars": "0.1600"},
        }

        result = get_market_price(
            {"params": {"venue": "kalshi", "ticker": "KXMENWORLDCUP-26-FR"}}
        )

        assert result["status"] is True
        assert result["data"]["yes"]["price"] == 0.17
        assert result["data"]["no"]["price"] == 0.83
        assert result["data"]["source"] == "last_price"

    @patch("sports_skills.kalshi")
    def test_kalshi_at_time_uses_candlesticks(self, mock_kalshi):
        mock_kalshi.get_market_candlesticks.return_value = {
            "status": True,
            "data": {
                "candlesticks": [
                    {
                        "end_period_ts": 1779900000,
                        "price": {"close_dollars": "0.2000"},
                    },
                    {
                        "end_period_ts": 1779940800,
                        "price": {"close_dollars": "0.1650"},
                    },
                ]
            },
        }

        result = get_market_price(
            {
                "params": {
                    "venue": "kalshi",
                    "ticker": "KXMENWORLDCUP-26-FR",
                    "at_time": 1779950000,
                }
            }
        )

        assert result["status"] is True
        assert result["data"]["yes"]["price"] == 0.165
        assert result["data"]["yes"]["at_time"] == 1779940800
        assert result["data"]["source"] == "candlestick"
        # Series ticker derived from the market ticker prefix.
        call = mock_kalshi.get_market_candlesticks.call_args
        assert call.kwargs["series_ticker"] == "KXMENWORLDCUP"

    @patch("sports_skills.polymarket")
    def test_polymarket_current_midpoint(self, mock_poly):
        mock_poly.get_market_prices.return_value = {
            "status": True,
            "data": {"token_id": "t1", "midpoint": 0.52},
        }

        result = get_market_price(
            {"params": {"venue": "polymarket", "token_id": "t1"}}
        )

        assert result["status"] is True
        assert result["data"]["yes"]["price"] == 0.52
        assert result["data"]["no"]["price"] == 0.48
        assert result["data"]["source"] == "midpoint"

    @patch("sports_skills.polymarket")
    def test_polymarket_at_time_uses_history(self, mock_poly):
        mock_poly.get_price_history.return_value = {
            "status": True,
            "data": {
                "history": [
                    {"t": 1779900000, "p": 0.4},
                    {"t": 1779940800, "p": 0.45},
                    {"t": 1780000000, "p": 0.6},  # after at_time — excluded
                ]
            },
        }

        result = get_market_price(
            {
                "params": {
                    "venue": "polymarket",
                    "token_id": "t1",
                    "at_time": 1779950000,
                }
            }
        )

        assert result["status"] is True
        assert result["data"]["yes"]["price"] == 0.45
        assert result["data"]["yes"]["at_time"] == 1779940800
        assert result["data"]["source"] == "history"

    def test_invalid_venue(self):
        result = get_market_price({"params": {"venue": "espn", "ticker": "X"}})
        assert result["status"] is False

    def test_missing_identifier(self):
        assert get_market_price({"params": {"venue": "kalshi"}})["status"] is False
        assert get_market_price({"params": {"venue": "polymarket"}})["status"] is False

    def test_bad_at_time(self):
        result = get_market_price(
            {"params": {"venue": "kalshi", "ticker": "X", "at_time": "yesterday"}}
        )
        assert result["status"] is False


# ============================================================
# get_price_history (mocked venues)
# ============================================================


class TestGetPriceHistory:
    @patch("sports_skills.kalshi")
    def test_kalshi_candles_to_points(self, mock_kalshi):
        mock_kalshi.get_market_candlesticks.return_value = {
            "status": True,
            "data": {
                "candlesticks": [
                    {"end_period_ts": 200, "price": {"close_dollars": "0.2000"}},
                    {"end_period_ts": 100, "price": {"close_dollars": "0.1800"}},
                    {"end_period_ts": 300, "price": {}},  # no close — dropped
                ]
            },
        }

        result = get_price_history(
            {
                "params": {
                    "venue": "kalshi",
                    "ticker": "KXMENWORLDCUP-26-FR",
                    "interval": "1d",
                    "start_time": 1,
                    "end_time": 1000,
                }
            }
        )

        assert result["status"] is True
        points = result["data"]["points"]
        assert points == [
            {"timestamp": 100, "price": 0.18},
            {"timestamp": 200, "price": 0.2},
        ]
        call = mock_kalshi.get_market_candlesticks.call_args
        assert call.kwargs["period_interval"] == 1440

    @patch("sports_skills.polymarket")
    def test_polymarket_history_window_filter(self, mock_poly):
        mock_poly.get_price_history.return_value = {
            "status": True,
            "data": {
                "history": [
                    {"t": 50, "p": 0.3},  # before window — dropped
                    {"t": 150, "p": 0.4},
                    {"t": 950, "p": 0.5},
                    {"t": 1500, "p": 0.6},  # after window — dropped
                ]
            },
        }

        result = get_price_history(
            {
                "params": {
                    "venue": "polymarket",
                    "token_id": "t1",
                    "interval": "1h",
                    "start_time": 100,
                    "end_time": 1000,
                }
            }
        )

        assert result["status"] is True
        assert result["data"]["points"] == [
            {"timestamp": 150, "price": 0.4},
            {"timestamp": 950, "price": 0.5},
        ]

    def test_invalid_interval(self):
        result = get_price_history(
            {"params": {"venue": "kalshi", "ticker": "X", "interval": "5m"}}
        )
        assert result["status"] is False

    def test_start_after_end(self):
        result = get_price_history(
            {
                "params": {
                    "venue": "kalshi",
                    "ticker": "X",
                    "start_time": 1000,
                    "end_time": 100,
                }
            }
        )
        assert result["status"] is False


# ============================================================
# polymarket.get_event_details slug lookup
# ============================================================


class TestGetEventDetailsSlug:
    @patch("sports_skills.polymarket._connector._gamma_request")
    def test_slug_resolved_via_query_param(self, mock_gamma):
        # Gamma resolves slugs only via ?slug= (the path segment must be
        # a numeric id); the response is a list.
        mock_gamma.return_value = [
            {
                "id": "400",
                "slug": "fifwc-jor-arg-2026-06-27",
                "title": "Jordan vs. Argentina",
                "markets": [],
            }
        ]
        from sports_skills.polymarket._connector import get_event_details

        result = get_event_details({"params": {"slug": "fifwc-jor-arg-2026-06-27"}})

        assert result["status"] is True
        assert result["data"]["slug"] == "fifwc-jor-arg-2026-06-27"
        call = mock_gamma.call_args
        assert call.args[0] == "/events"
        assert call.kwargs["params"] == {"slug": "fifwc-jor-arg-2026-06-27"}

    @patch("sports_skills.polymarket._connector._gamma_request")
    def test_slug_not_found(self, mock_gamma):
        mock_gamma.return_value = []
        from sports_skills.polymarket._connector import get_event_details

        result = get_event_details({"params": {"slug": "no-such-event"}})

        assert result["status"] is False
