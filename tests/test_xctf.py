"""Tests for TFRRS roster parsing — readable names and explained empties."""

import pytest

from sports_skills.xctf import _connector

_TEAM_PAGE = """
<html><body>
<a href="/athletes/8391234/CA_college_m_Stanford/Amaya_Bharadwaj.html">x</a>
<a href="/athletes/8391235/CA_college_m_Stanford/Silan__Ayyildiz.html">y</a>
<a href="/athletes/8391236/CA_college_m_Stanford/Maya_de_Brouwer">z</a>
<a href="/athletes/8391234/CA_college_m_Stanford/Amaya_Bharadwaj.html">dupe</a>
</body></html>
"""


class TestReadableName:
    """The roster used to emit URL slugs, which its own search could not match."""

    def test_underscores_become_spaces(self):
        assert _connector._readable_name("Amaya_Bharadwaj") == "Amaya Bharadwaj"

    def test_doubled_underscores_collapse(self):
        assert _connector._readable_name("Silan__Ayyildiz") == "Silan Ayyildiz"

    def test_multi_word_surname(self):
        assert _connector._readable_name("Maya_de_Brouwer") == "Maya de Brouwer"

    def test_single_token_unchanged(self):
        assert _connector._readable_name("Prefontaine") == "Prefontaine"


class TestParseTeamRoster:
    def test_extracts_athletes(self):
        athletes = _connector._parse_team_roster(_TEAM_PAGE)
        assert len(athletes) == 3, "duplicate links must collapse"

    def test_keeps_slug_and_adds_display_name(self):
        first = _connector._parse_team_roster(_TEAM_PAGE)[0]
        assert first["name"] == "Amaya_Bharadwaj"
        assert first["display_name"] == "Amaya Bharadwaj"

    def test_captures_ids_and_school(self):
        first = _connector._parse_team_roster(_TEAM_PAGE)[0]
        assert first["athlete_id"] == "8391234"
        assert first["school"] == "CA_college_m_Stanford"

    def test_handles_links_without_html_suffix(self):
        names = [a["name"] for a in _connector._parse_team_roster(_TEAM_PAGE)]
        assert "Maya_de_Brouwer" in names


class TestRosterErrorReporting:
    """A bad slug must not look like a team with no athletes."""

    def test_all_pages_missing_is_an_error(self, monkeypatch):
        monkeypatch.setattr(
            _connector, "_fetch", lambda url: {"error": True, "message": "HTTP 404"}
        )
        result = _connector.get_team_roster(school="NOT_A_REAL_SLUG")
        assert result.get("error") is True
        assert "NOT_A_REAL_SLUG" in result["message"]
        assert "team slug" in result["message"]

    def test_successful_fetch_returns_roster(self, monkeypatch):
        monkeypatch.setattr(_connector, "_fetch", lambda url: _TEAM_PAGE)
        result = _connector.get_team_roster(school="CA_college_m_Stanford", sport="xc")
        assert not result.get("error")
        assert result["count"] == len(result["athletes"]) > 0
        assert result["athletes"][0]["display_name"] == "Amaya Bharadwaj"

    def test_partial_failure_warns_but_returns_data(self, monkeypatch):
        calls = {"n": 0}

        def flaky(url):
            calls["n"] += 1
            if calls["n"] == 1:
                return _TEAM_PAGE
            return {"error": True, "message": "HTTP 500"}

        monkeypatch.setattr(_connector, "_fetch", flaky)
        result = _connector.get_team_roster(school="CA_college_m_Stanford", sport="both")
        assert not result.get("error")
        assert result["count"] > 0
        assert result.get("warnings"), "a dropped page should be reported"

    @pytest.mark.parametrize("sport", ["xc", "tf"])
    def test_single_sport_is_respected(self, monkeypatch, sport):
        seen = []

        def record(url):
            seen.append(url)
            return _TEAM_PAGE

        monkeypatch.setattr(_connector, "_fetch", record)
        _connector.get_team_roster(school="CA_college_m_Stanford", sport=sport)
        assert all(f"/teams/{sport}/" in u for u in seen)
