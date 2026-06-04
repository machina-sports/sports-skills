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
