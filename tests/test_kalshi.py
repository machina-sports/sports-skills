"""Unit tests for the kalshi module (no network)."""

from unittest.mock import patch

from sports_skills.kalshi._connector import (
    KALSHI_SERIES,
    _price_cents,
    _volume_units,
    get_todays_events,
)


class TestPriceCents:
    def test_legacy_cent_field(self):
        assert _price_cents({"yes_bid": 29}, "yes_bid") == 29

    def test_dollars_fallback(self):
        # Kalshi's API migration: nested /events markets only carry the
        # *_dollars string form.
        assert _price_cents({"yes_bid_dollars": "0.2900"}, "yes_bid") == 29

    def test_legacy_zero_falls_through_to_dollars(self):
        assert _price_cents({"yes_bid": 0, "yes_bid_dollars": "0.1630"}, "yes_bid") == 16

    def test_both_missing(self):
        assert _price_cents({}, "yes_bid") == 0

    def test_malformed_dollars(self):
        assert _price_cents({"last_price_dollars": "n/a"}, "last_price") == 0

    def test_true_zero_price(self):
        assert _price_cents({"yes_bid_dollars": "0.0000"}, "yes_bid") == 0

    def test_dollars_above_one(self):
        assert _price_cents({"last_price_dollars": "1.5000"}, "last_price") == 150


class TestVolumeUnits:
    def test_legacy_volume(self):
        assert _volume_units({"volume": 357}) == 357

    def test_fp_fallback(self):
        assert _volume_units({"volume_fp": "5499371.43"}) == 5499371.43

    def test_missing(self):
        assert _volume_units({}) == 0

    def test_malformed_fp(self):
        assert _volume_units({"volume_fp": "n/a"}) == 0

    def test_true_zero_fp(self):
        assert _volume_units({"volume_fp": "0.00"}) == 0


class TestWorldCupSeries:
    def test_worldcup_series_present(self):
        tickers = KALSHI_SERIES["worldcup"]
        assert "KXMENWORLDCUP" in tickers
        assert "KXWCGAME" in tickers


class TestGetTodaysEventsNormalization:
    @patch("sports_skills.kalshi._connector._request")
    def test_nested_markets_get_cent_fields(self, mock_request):
        # Nested /events markets carry only the *_dollars form post-migration;
        # get_todays_events re-injects the documented 0-100 cent fields.
        mock_request.return_value = {
            "events": [
                {
                    "event_ticker": "KXTEST-1",
                    "title": "Test Event",
                    "markets": [
                        {
                            "ticker": "KXTEST-1-A",
                            "yes_bid_dollars": "0.1630",
                            "no_bid_dollars": "0.8400",
                            "last_price_dollars": "0.1680",
                            "volume_fp": "123.45",
                        }
                    ],
                }
            ]
        }

        result = get_todays_events({"params": {"sport": "mls"}})

        assert result["status"] is True
        m = result["data"]["events"][0]["markets"][0]
        assert m["yes_bid"] == 16
        assert m["no_bid"] == 84
        assert m["last_price"] == 17
        assert m["volume"] == 123.45


class TestGetMarketOrderbook:
    @patch("sports_skills.kalshi._connector._request")
    def test_orderbook_fp_preferred(self, mock_request):
        mock_request.return_value = {
            "orderbook_fp": {
                "yes_dollars": [["0.1600", "42.55"]],
                "no_dollars": [["0.8300", "100.00"]],
            }
        }
        from sports_skills.kalshi._connector import get_market_orderbook

        result = get_market_orderbook({"params": {"ticker": "KXTEST-1-A"}})
        assert result["status"] is True
        assert result["data"]["orderbook"]["yes_dollars"] == [["0.1600", "42.55"]]

    @patch("sports_skills.kalshi._connector._request")
    def test_legacy_orderbook_fallback(self, mock_request):
        mock_request.return_value = {"orderbook": {"yes": [[16, 42]], "no": [[83, 100]]}}
        from sports_skills.kalshi._connector import get_market_orderbook

        result = get_market_orderbook({"params": {"ticker": "KXTEST-1-A"}})
        assert result["data"]["orderbook"]["yes"] == [[16, 42]]

    def test_ticker_required(self):
        from sports_skills.kalshi._connector import get_market_orderbook

        result = get_market_orderbook({"params": {}})
        assert result["status"] is False


class TestEventsPagination:
    """search_markets/get_todays_events must follow the /events cursor —
    a single un-paged call drops the soonest matchdays of large series."""

    @staticmethod
    def _event(i, n_markets=3):
        return {
            "event_ticker": f"KXWCGAME-26JUN{i:02d}AAABBB",
            "title": f"Team A vs Team B {i}",
            "markets": [
                {
                    "ticker": f"KXWCGAME-26JUN{i:02d}AAABBB-{j}",
                    "title": "Winner?",
                    "subtitle": "",
                    "yes_bid": 50,
                    "no_bid": 50,
                    "last_price": 50,
                    "volume": 100,
                    "status": "active",
                }
                for j in range(n_markets)
            ],
        }

    @patch("sports_skills.kalshi._connector._request")
    def test_search_markets_follows_cursor(self, mock_request):
        from sports_skills.kalshi._connector import search_markets

        page1 = {"events": [self._event(i) for i in range(1, 201)], "cursor": "next-page"}
        page2 = {"events": [self._event(i) for i in range(201, 251)], "cursor": ""}
        mock_request.side_effect = [page1, page2]

        result = search_markets({"params": {"series_ticker": "KXWCGAME", "limit": 1000}})
        assert result["status"] is True
        # 250 events x 3 markets — everything past the first page included.
        assert result["data"]["count"] == 750
        assert mock_request.call_count == 2
        # Second call carried the cursor.
        assert (
            mock_request.call_args_list[1].kwargs.get("params", {}).get("cursor") == "next-page"
            or mock_request.call_args_list[1][1].get("params", {}).get("cursor") == "next-page"
        )

    @patch("sports_skills.kalshi._connector._request")
    def test_limit_caps_total_and_stops_paging(self, mock_request):
        from sports_skills.kalshi._connector import search_markets

        page1 = {"events": [self._event(i) for i in range(1, 51)], "cursor": "more"}
        mock_request.side_effect = [page1]

        result = search_markets({"params": {"series_ticker": "KXWCGAME", "limit": 50}})
        assert result["status"] is True
        # 50 events fetched (= limit) -> no second page requested.
        assert mock_request.call_count == 1

    @patch("sports_skills.kalshi._connector._request")
    def test_later_page_failure_returns_partial(self, mock_request):
        from sports_skills.kalshi._connector import search_markets

        page1 = {"events": [self._event(i) for i in range(1, 201)], "cursor": "next"}
        boom = {"error": True, "status_code": 500, "message": "upstream"}
        mock_request.side_effect = [page1, boom]

        result = search_markets({"params": {"series_ticker": "KXWCGAME", "limit": 1000}})
        assert result["status"] is True
        assert result["data"]["count"] == 600  # first page preserved

    @patch("sports_skills.kalshi._connector._request")
    def test_get_todays_events_follows_cursor(self, mock_request):
        page1 = {"events": [self._event(i) for i in range(1, 201)], "cursor": "n2"}
        page2 = {"events": [self._event(i) for i in range(201, 221)], "cursor": ""}
        # get_todays_events iterates every series of the sport; return empty
        # final pages for the remaining worldcup series.
        empty = {"events": [], "cursor": ""}
        mock_request.side_effect = [page1, page2] + [empty] * 20

        result = get_todays_events({"params": {"sport": "worldcup", "limit": 1000}})
        assert result["status"] is True
        assert result["data"]["count"] == 220

    @patch("sports_skills.kalshi._connector._request")
    def test_all_series_failing_returns_error(self, mock_request):
        from sports_skills.kalshi._connector import search_markets

        # Every series' first page fails — must NOT look like "no markets".
        mock_request.return_value = {"error": True, "status_code": 503, "message": "down"}

        result = search_markets({"params": {"sport": "worldcup", "limit": 50}})
        assert result["status"] is False
        assert "503" in result["message"]

        result = get_todays_events({"params": {"sport": "worldcup", "limit": 50}})
        assert result["status"] is False
        assert "503" in result["message"]
