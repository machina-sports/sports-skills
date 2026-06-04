"""Unit tests for the kalshi module (no network)."""

from sports_skills.kalshi._connector import (
    KALSHI_SERIES,
    _price_cents,
    _volume_units,
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


class TestVolumeUnits:
    def test_legacy_volume(self):
        assert _volume_units({"volume": 357}) == 357

    def test_fp_fallback(self):
        assert _volume_units({"volume_fp": "5499371.43"}) == 5499371.43

    def test_missing(self):
        assert _volume_units({}) == 0


class TestWorldCupSeries:
    def test_worldcup_series_present(self):
        tickers = KALSHI_SERIES["worldcup"]
        assert "KXMENWORLDCUP" in tickers
        assert "KXWCGAME" in tickers
