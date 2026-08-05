"""Tests for the shared ESPN transport: User-Agent, error reporting, host fallback.

No network — the shared helpers are driven directly and `_http_fetch` is
substituted where a request would otherwise be made.
"""

import sys
import urllib.error

import pytest

from sports_skills._espn_base import (
    _HOST_FALLBACK_CODES,
    _SITE_API_HOSTS,
    _default_user_agent,
    _is_retryable,
    _summarize_http_error,
    _unwrap_json_error,
    fetch_season,
)


def _espn_base_module():
    from sports_skills import _espn_base

    return _espn_base


# ── User-Agent ─────────────────────────────────────────────


class TestUserAgent:
    """The outbound UA must stay a recognized client and never misreport."""

    def test_starts_with_a_client_token(self):
        assert _default_user_agent().startswith("Python-urllib/")

    def test_reports_the_running_interpreter(self):
        expected = f"Python-urllib/{sys.version_info.major}.{sys.version_info.minor}"
        assert _default_user_agent().startswith(expected)

    def test_identifies_the_project(self):
        assert "sports-skills/" in _default_user_agent()

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setenv("SPORTS_SKILLS_USER_AGENT", "curl/8.7.1 (+deploy)")
        assert _default_user_agent() == "curl/8.7.1 (+deploy)"

    def test_blank_override_is_ignored(self, monkeypatch):
        monkeypatch.setenv("SPORTS_SKILLS_USER_AGENT", "")
        assert _default_user_agent().startswith("Python-urllib/")

    def test_football_shares_the_shared_value(self):
        """This module used to carry its own copy, which drifted."""
        import sports_skills.football._connector as fbc

        assert fbc._USER_AGENT == _espn_base_module()._USER_AGENT

    def test_polymarket_keeps_its_own(self):
        """Polymarket's edge rejects what ESPN's requires — do not unify."""
        import sports_skills.polymarket._connector as pmc

        assert pmc._USER_AGENT != _espn_base_module()._USER_AGENT


# ── HTTP error summarization ─────────────────────────────────────────────

_BLOCK_PAGE = """<HTML><HEAD>
<TITLE>Access Denied</TITLE>
</HEAD><BODY>
<H1>Access Denied</H1>
You don&#39;t have permission to access this server.<P>
Reference&#32;&#35;18&#46;53b06c9&#46;1785874538&#46;b92b78a6
</BODY></HTML>"""


class TestSummarizeHttpError:
    """An upstream error page must never reach the caller as `message`."""

    def test_html_body_is_collapsed(self):
        msg = _summarize_http_error(403, "https://site.api.espn.com/x", _BLOCK_PAGE)
        assert "<HTML>" not in msg and "<TITLE>" not in msg

    def test_keeps_status_host_and_title(self):
        msg = _summarize_http_error(403, "https://site.api.espn.com/x", _BLOCK_PAGE)
        assert "403" in msg
        assert "site.api.espn.com" in msg
        assert "Access Denied" in msg

    def test_extracts_reference_id(self):
        msg = _summarize_http_error(403, "https://site.api.espn.com/x", _BLOCK_PAGE)
        assert "18.53b06c9.1785874538.b92b78a6" in msg

    def test_empty_body_still_informative(self):
        assert _summarize_http_error(404, "https://site.api.espn.com/x", "") == (
            "HTTP 404 from site.api.espn.com"
        )

    def test_plain_text_body_is_preserved(self):
        assert _summarize_http_error(500, "https://x/y", "boom") == "boom"

    def test_long_html_is_bounded(self):
        msg = _summarize_http_error(403, "https://x/y", "<html>" + "z" * 10000 + "</html>")
        assert len(msg) < 300


class TestUnwrapJsonError:
    """A JSON error envelope must not reach the caller verbatim."""

    def test_nested_error_message(self):
        assert _unwrap_json_error('{"error":{"message":"No stats found.","code":404}}') == (
            "No stats found."
        )

    def test_top_level_message(self):
        assert _unwrap_json_error('{"message":"not found"}') == "not found"

    def test_detail_key(self):
        assert _unwrap_json_error('{"detail":"bad request"}') == "bad request"

    def test_list_payload(self):
        assert _unwrap_json_error('[{"message":"first"}]') == "first"

    def test_non_json_returns_none(self):
        assert _unwrap_json_error("plain text") is None

    def test_json_without_message_returns_none(self):
        assert _unwrap_json_error('{"code":404}') is None

    def test_malformed_json_returns_none(self):
        assert _unwrap_json_error('{"error":') is None

    def test_summarizer_uses_it(self):
        msg = _summarize_http_error(
            404,
            "https://sports.core.api.espn.com/x",
            '{"error":{"message":"No stats found."}}',
        )
        assert msg == "HTTP 404 from sports.core.api.espn.com: No stats found."
        assert "{" not in msg


# ── Host fallback ─────────────────────────────────────────────


class TestHostFallback:
    """A denied request should be retried against the mirror host."""

    @staticmethod
    def _patch(monkeypatch, behavior):
        seen = []

        def fake_fetch(url, headers=None, rate_limiter=None, **kw):
            seen.append(url)
            return behavior(url)

        base = _espn_base_module()
        monkeypatch.setattr(base, "_http_fetch", fake_fetch)
        monkeypatch.setattr(base, "_cache_get", lambda k: None)
        monkeypatch.setattr(base, "_cache_set", lambda *a, **k: None)
        return seen

    def test_primary_host_used_first(self, monkeypatch):
        seen = self._patch(monkeypatch, lambda url: (b'{"ok":1}', None))
        assert _espn_base_module().espn_request("football/nfl", "teams") == {"ok": 1}
        assert _SITE_API_HOSTS[0] in seen[0]
        assert len(seen) == 1

    @pytest.mark.parametrize("code", sorted(_HOST_FALLBACK_CODES))
    def test_denial_falls_back_to_mirror(self, monkeypatch, code):
        def behavior(url):
            if _SITE_API_HOSTS[0] in url:
                return None, {"error": True, "status_code": code, "message": "denied"}
            return b'{"ok":2}', None

        seen = self._patch(monkeypatch, behavior)
        assert _espn_base_module().espn_request("football/nfl", "teams") == {"ok": 2}
        assert len(seen) == 2
        assert _SITE_API_HOSTS[1] in seen[1]

    def test_404_does_not_fall_back(self, monkeypatch):
        """A missing resource is missing on every host — don't double the traffic."""
        seen = self._patch(
            monkeypatch,
            lambda url: (None, {"error": True, "status_code": 404, "message": "nope"}),
        )
        result = _espn_base_module().espn_request("football/nfl", "bogus")
        assert result["status_code"] == 404
        assert len(seen) == 1

    def test_all_hosts_denied_returns_the_error(self, monkeypatch):
        seen = self._patch(
            monkeypatch,
            lambda url: (None, {"error": True, "status_code": 403, "message": "denied"}),
        )
        result = _espn_base_module().espn_request("football/nfl", "teams")
        assert result["error"] is True
        assert len(seen) == len(_SITE_API_HOSTS)

    def test_query_params_survive_the_fallback(self, monkeypatch):
        def behavior(url):
            if _SITE_API_HOSTS[0] in url:
                return None, {"error": True, "status_code": 403, "message": "denied"}
            return b'{"ok":3}', None

        seen = self._patch(monkeypatch, behavior)
        _espn_base_module().espn_request("football/nfl", "scoreboard", {"dates": "20240908"})
        assert "dates=20240908" in seen[1]

    def test_mirror_host_differs_from_primary(self):
        assert len(set(_SITE_API_HOSTS)) == len(_SITE_API_HOSTS) >= 2


class TestDenialIsNotRetried:
    """A 403 is not transient — retrying it only burns the rate limit."""

    def test_403_not_retryable(self):
        exc = urllib.error.HTTPError("http://x", 403, "Forbidden", {}, None)
        assert _is_retryable(exc) is False

    def test_429_is_retryable(self):
        exc = urllib.error.HTTPError("http://x", 429, "Too Many", {}, None)
        assert _is_retryable(exc) is True


# ── Season resolution ─────────────────────────────────────────────


class TestFetchSeason:
    """An implied season may step back a year; an explicit one may not."""

    @staticmethod
    def _loader(good_year):
        calls = []

        def loader(year):
            calls.append(year)
            if year == good_year:
                return {"ok": True, "year": year}
            return {"error": True, "message": "no stats"}

        loader.calls = calls
        return loader

    def test_current_season_succeeds_untouched(self):
        loader = self._loader(2026)
        data, season, note = fetch_season(loader, 2026, explicit=False)
        assert data["ok"] and season == 2026 and note is None
        assert loader.calls == [2026]

    def test_implied_season_steps_back(self):
        loader = self._loader(2025)
        data, season, note = fetch_season(loader, 2026, explicit=False)
        assert data["ok"] and season == 2025
        assert note and "2026" in note and "2025" in note
        assert loader.calls == [2026, 2025]

    def test_explicit_season_is_never_substituted(self):
        loader = self._loader(2025)
        data, season, note = fetch_season(loader, 2026, explicit=True)
        assert data.get("error") and season == 2026 and note is None
        assert loader.calls == [2026], "must not try another year"

    def test_both_years_failing_returns_original_error(self):
        loader = self._loader(1900)
        data, season, note = fetch_season(loader, 2026, explicit=False)
        assert data.get("error") and season == 2026 and note is None

    def test_non_dict_response_passes_through(self):
        data, season, note = fetch_season(lambda y: ["a"], 2026, explicit=False)
        assert data == ["a"] and season == 2026 and note is None


class TestEchoSeason:
    """The reported season must describe the events actually returned."""

    SPORTS = ["nfl", "nba", "wnba", "nhl", "mlb", "cfb", "cbb"]

    @staticmethod
    def _mod(sport):
        return __import__(f"sports_skills.{sport}._connector", fromlist=["_echo_season"])

    @pytest.mark.parametrize("sport", SPORTS)
    def test_requested_season_wins(self, sport):
        envelope = {"season": {"year": 2026}}
        mod = self._mod(sport)
        assert mod._echo_season(2024, envelope) == 2024
        assert mod._echo_season("2024", envelope) == 2024

    @pytest.mark.parametrize("sport", SPORTS)
    def test_falls_back_to_envelope(self, sport):
        mod = self._mod(sport)
        assert mod._echo_season(None, {"season": {"year": 2026}}) == 2026
        assert mod._echo_season("", {"season": {"year": 2026}}) == 2026

    def test_non_numeric_requested_survives(self):
        assert self._mod("nfl")._echo_season("2024-25", {}) == "2024-25"

    def test_missing_envelope_season_is_empty(self):
        assert self._mod("nfl")._echo_season(None, {}) == ""
