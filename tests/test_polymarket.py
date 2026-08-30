"""Unit tests for the polymarket module (no network)."""

from sports_skills.polymarket._connector import (
    _normalize_market,
    _text_match,
    _text_match_market,
)


class TestTextMatch:
    """Cross-venue callers (markets.compare_odds) build "<away> <home>"
    queries whose tokens are never contiguous in Polymarket titles."""

    def test_normalize_market_tolerates_null_tags(self):
        market = _normalize_market(
            {
                "id": "m1",
                "question": "Will the Orioles beat the Rays?",
                "tags": None,
                "events": None,
            }
        )
        assert market["tags"] == []
        assert market["event_id"] == ""

    def test_contiguous_match_still_works(self):
        event = {"title": "Baltimore Orioles vs. Tampa Bay Rays", "description": "", "slug": ""}
        assert _text_match("Tampa Bay Rays", event) is True

    def test_two_token_query_matches_non_contiguous_title(self):
        event = {"title": "Baltimore Orioles vs. Tampa Bay Rays", "description": "", "slug": ""}
        assert _text_match("Orioles Rays", event) is True

    def test_two_token_query_requires_all_tokens(self):
        event = {"title": "Baltimore Orioles vs. Tampa Bay Rays", "description": "", "slug": ""}
        assert _text_match("Orioles Yankees", event) is False

    def test_tokens_must_match_one_semantic_field(self):
        event = {"title": "Orioles moneyline", "description": "Rays futures", "slug": "mlb"}
        assert _text_match("Orioles Rays", event) is False

    def test_token_matching_uses_word_boundaries(self):
        event = {"title": "Programs featuring Eagles", "description": "", "slug": ""}
        assert _text_match("Rams Eagles", event) is False

    def test_null_provider_fields_are_tolerated(self):
        event = {"title": "Baltimore Orioles vs. Tampa Bay Rays", "description": None, "slug": None}
        assert _text_match("Orioles Rays", event) is True

    def test_single_token_stays_contiguous_only(self):
        event = {"title": "Baltimore Orioles vs. Tampa Bay Rays", "description": "", "slug": ""}
        assert _text_match("Cardinals", event) is False


class TestTextMatchMarket:
    def test_two_token_query_matches_market_question(self):
        market = {"question": "Will the Orioles beat the Rays?", "slug": "", "events": []}
        assert _text_match_market("Orioles Rays", market) is True

    def test_two_token_query_matches_parent_event_title(self):
        market = {
            "question": "Moneyline",
            "slug": "",
            "events": [{"title": "Baltimore Orioles vs. Tampa Bay Rays", "slug": ""}],
        }
        assert _text_match_market("Orioles Rays", market) is True

    def test_tokens_must_not_span_multiple_parent_events(self):
        market = {
            "question": "Moneyline",
            "slug": "",
            "events": [
                {"title": "Baltimore Orioles", "slug": "orioles"},
                {"title": "Tampa Bay Rays", "slug": "rays"},
            ],
        }
        assert _text_match_market("Orioles Rays", market) is False

    def test_null_events_are_tolerated(self):
        market = {"question": "Will the Orioles beat the Rays?", "slug": None, "events": None}
        assert _text_match_market("Orioles Rays", market) is True

    def test_no_match_returns_false(self):
        market = {"question": "Moneyline", "slug": "", "events": [{"title": "Cubs vs. Cards", "slug": ""}]}
        assert _text_match_market("Orioles Rays", market) is False
