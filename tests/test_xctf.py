"""Tests for TFRRS roster parsing — readable names and explained empties."""

from pathlib import Path

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


FIXTURES = Path(__file__).parent / "fixtures" / "tfrrs"


def _fixture(name):
    return (FIXTURES / name).read_text()


def _event(events, prefix):
    return next(e for e in events if e["event"].startswith(prefix))


class TestCompiledResults:
    """Recorded compiled pages (#164): decoy columns, wind, relays, DNF rows."""

    @pytest.fixture(scope="class")
    def first_rounds(self):
        return _connector._parse_compiled_results(
            _fixture("96716_m_east_first_rounds.html"), "men"
        )

    @pytest.fixture(scope="class")
    def championships(self):
        return _connector._parse_compiled_results(_fixture("96875_m_ncaa_outdoor.html"), "men")

    def test_hidden_decoy_columns_are_dropped(self, first_rounds):
        row = _event(first_rounds, "Men's 100 Meters")["results"][0]
        assert row["name"] == "Kanyinsola Ajayi"
        # Five hidden decoy TIME columns precede the real one.
        assert row["marks"] == ["9.84"]

    def test_wind_is_not_the_score(self, first_rounds):
        row = _event(first_rounds, "Men's 100 Meters")["results"][0]
        assert row["wind"] == "0.7"
        assert row["score"] is None  # no SC column at a qualifying meet

    def test_dnf_row_keeps_its_columns(self, first_rounds):
        rows = _event(first_rounds, "Men's 10,000")["results"]
        dnf = next(r for r in rows if r["name"] == "Mohammed Jouhari")
        assert dnf["place"] is None
        assert dnf["year"] == "SR-4"
        assert dnf["team"] == "Eastern Kentucky"
        assert dnf["marks"] == ["DNF"]

    def test_relay_row_maps_team_and_athletes(self, first_rounds):
        row = _event(first_rounds, "Men's 4 x 100")["results"][0]
        assert row["team"] == "Auburn"
        assert row["name"] is None
        assert row["athletes"] == [
            "Azeem Fahmi",
            "Kanyinsola Ajayi",
            "Austin Kresley",
            "Tyler Davis",
        ]
        assert row["marks"] == ["38.20"]

    def test_field_event_mark_conversion_and_wind(self, first_rounds):
        rows = _event(first_rounds, "Men's Long Jump")["results"]
        assert rows[0]["marks"] == ["8.05m"]
        assert rows[0]["conversion"] == "26' 5\""
        assert rows[0]["wind"] == "0.5"
        foul = next(r for r in rows if r["name"] == "Jake Wall")
        assert foul["team"] == "Michigan"
        assert foul["marks"] == ["FOUL"]

    def test_scored_meet_reads_sc_column(self, championships):
        row = _event(championships, "Men 100 M Finals")["results"][0]
        assert row["marks"] == ["9.72"]
        assert row["score"] == "10"
        relay = _event(championships, "Men's 4 x 400")["results"][0]
        assert relay["team"] == "Georgia"
        assert relay["marks"] == ["2:57.93"]
        assert relay["score"] == "10"

    def test_multi_event_points_are_the_mark(self, championships):
        row = _event(championships, "Men's Decathlon")["results"][0]
        assert row["marks"] == ["8169"]
        assert row["score"] == "10"


class TestMeetResultsSport:
    def test_xc_meet_uses_xc_path_and_parses_races(self, monkeypatch):
        seen = []

        def fake(url):
            seen.append(url)
            return _fixture("xc_28714_gans_creek.html")

        monkeypatch.setattr(_connector, "_fetch", fake)
        out = _connector.get_meet_results(meet_id="28714", slug="Gans_Creek_Classic", sport="xc")
        assert seen == ["https://www.tfrrs.org/results/xc/28714/Gans_Creek_Classic"]
        assert out["meet"] == "Gans Creek Classic"
        assert out["date"] == "September 25, 2026"
        assert out["team_scores"]["Women's Gold Invite 6k"][0] == {
            "rank": "1",
            "team": "Missouri",
            "score": "56",
        }
        race = _event(out["events"], "Women's Gold Invite 6k")
        assert race["gender"] == "women"
        assert race["results"][0]["name"] == "Isca Chelangat"
        assert race["results"][0]["marks"] == ["18:58.4"]
        assert race["results"][0]["score"] == "1"
        assert "warnings" not in out

    def test_xc_id_on_track_path_warns(self, monkeypatch):
        # What tfrrs.org/results/28714/Gans_Creek_Classic actually serves.
        page = '<h3 class="panel-title">2013 Greyhound Relays</h3>'

        def fake(url):
            if "/m/" in url or "/f/" in url:
                return {"error": True, "message": "HTTP 404"}
            return page

        monkeypatch.setattr(_connector, "_fetch", fake)
        out = _connector.get_meet_results(meet_id="28714", slug="Gans_Creek_Classic")
        assert out["meet"] == "2013 Greyhound Relays"
        assert "sport='xc'" in out["warnings"][0]

    def test_invalid_sport_is_an_error(self):
        out = _connector.get_meet_results(meet_id="1", slug="x", sport="swim")
        assert out["error"] is True
        assert "'tf' or 'xc'" in out["message"]


class TestAthleteProfileMeets:
    def test_padded_date_range_meet_is_kept(self):
        profile = _connector._parse_athlete_profile(_fixture("athlete_9230145_hedengren.html"))
        stanford = next(m for m in profile["meets"] if m["meet"] == "Stanford Invitational")
        assert stanford["date"] == "Apr 3-4, 2026"  # page shows "Apr  3- 4, 2026"
        assert stanford["results"][0]["mark"] == "30:46.80"

    def test_every_pr_appears_in_results(self):
        profile = _connector._parse_athlete_profile(_fixture("athlete_9230145_hedengren.html"))
        marks = {r["mark"] for m in profile["meets"] for r in m["results"]}
        assert profile["prs"]["10,000"] in marks
