"""Tests for the cricket module — ESPN live backend and Cricsheet historical backend."""

import io
import json
import os
import time
import zipfile

import pytest

from sports_skills.cricket import _cricsheet
from sports_skills.cricket import _espn

# ── get_competitions ────────────────────────────────────────


class TestGetCompetitions:
    def test_returns_known_codes_with_attribution(self):
        result = _cricsheet.get_competitions({})
        codes = {c["code"] for c in result["competitions"]}
        assert "ipl" in codes
        assert "tests" in codes
        assert "wbb" in codes
        assert result["count"] == len(result["competitions"])
        assert "cricsheet.org" in result["attribution"]

    def test_every_competition_has_name(self):
        result = _cricsheet.get_competitions({})
        for c in result["competitions"]:
            assert c["code"]
            assert c["name"]


# ── cache layer ─────────────────────────────────────────────


class TestFetchFile:
    def test_downloads_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_cricsheet, "_cache_dir", lambda: str(tmp_path))
        calls = []

        def fake_download(url, dest):
            calls.append(url)
            with open(dest, "wb") as f:
                f.write(b"payload")

        monkeypatch.setattr(_cricsheet, "_download", fake_download)
        path, stale, err = _cricsheet._fetch_file("http://x/file.zip", "file.zip", ttl=60)
        assert err is None
        assert stale is False
        assert open(path, "rb").read() == b"payload"
        assert calls == ["http://x/file.zip"]

    def test_serves_cached_within_ttl(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_cricsheet, "_cache_dir", lambda: str(tmp_path))
        (tmp_path / "file.zip").write_bytes(b"cached")

        def fail_download(url, dest):
            raise AssertionError("should not download")

        monkeypatch.setattr(_cricsheet, "_download", fail_download)
        path, stale, err = _cricsheet._fetch_file("http://x/file.zip", "file.zip", ttl=3600)
        assert err is None
        assert stale is False
        assert open(path, "rb").read() == b"cached"

    def test_serves_stale_on_download_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_cricsheet, "_cache_dir", lambda: str(tmp_path))
        stale_file = tmp_path / "file.zip"
        stale_file.write_bytes(b"old")
        old = time.time() - 100_000
        os.utime(stale_file, (old, old))

        def fail_download(url, dest):
            raise OSError("network down")

        monkeypatch.setattr(_cricsheet, "_download", fail_download)
        path, stale, err = _cricsheet._fetch_file("http://x/file.zip", "file.zip", ttl=60)
        assert err is None
        assert stale is True
        assert open(path, "rb").read() == b"old"

    def test_error_when_no_cache_and_download_fails(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_cricsheet, "_cache_dir", lambda: str(tmp_path))

        def fail_download(url, dest):
            raise OSError("network down")

        monkeypatch.setattr(_cricsheet, "_download", fail_download)
        path, stale, err = _cricsheet._fetch_file("http://x/file.zip", "file.zip", ttl=60)
        assert path is None
        assert err["error"] is True
        assert "network down" in err["message"]


# ── cricsheet fixture ───────────────────────────────────────

MATCH_1 = {
    "meta": {"data_version": "1.0.0", "created": "2024-05-01", "revision": 1},
    "info": {
        "city": "Mumbai",
        "dates": ["2024-04-01"],
        "event": {"name": "Indian Premier League", "match_number": 1},
        "gender": "male",
        "match_type": "T20",
        "outcome": {"winner": "Team A", "by": {"runs": 10}},
        "players": {"Team A": ["A One", "A Two"], "Team B": ["B One", "B Two"]},
        "registry": {"people": {"A One": "aaa111"}},
        "season": "2024",
        "teams": ["Team A", "Team B"],
        "toss": {"decision": "bat", "winner": "Team A"},
        "venue": "Wankhede Stadium",
    },
    "innings": [
        {
            "team": "Team A",
            "overs": [
                {
                    "over": 0,
                    "deliveries": [
                        # legal ball, boundary four
                        {"batter": "A One", "bowler": "B One", "non_striker": "A Two",
                         "runs": {"batter": 4, "extras": 0, "total": 4}},
                        # wide — not faced by batter, charged to bowler
                        {"batter": "A One", "bowler": "B One", "non_striker": "A Two",
                         "runs": {"batter": 0, "extras": 1, "total": 1},
                         "extras": {"wides": 1}},
                        # six
                        {"batter": "A One", "bowler": "B One", "non_striker": "A Two",
                         "runs": {"batter": 6, "extras": 0, "total": 6}},
                        # leg byes — faced, NOT charged to bowler
                        {"batter": "A One", "bowler": "B One", "non_striker": "A Two",
                         "runs": {"batter": 0, "extras": 1, "total": 1},
                         "extras": {"legbyes": 1}},
                        # bowled — credited to bowler
                        {"batter": "A One", "bowler": "B One", "non_striker": "A Two",
                         "runs": {"batter": 0, "extras": 0, "total": 0},
                         "wickets": [{"kind": "bowled", "player_out": "A One"}]},
                    ],
                }
            ],
        },
        {
            "team": "Team B",
            "overs": [
                {
                    "over": 0,
                    "deliveries": [
                        # run out — NOT credited to bowler
                        {"batter": "B One", "bowler": "A Two", "non_striker": "B Two",
                         "runs": {"batter": 1, "extras": 0, "total": 1},
                         "wickets": [{"kind": "run out", "player_out": "B One"}]},
                    ],
                }
            ],
        },
    ],
}

MATCH_2 = {
    "meta": {"data_version": "1.0.0", "created": "2023-05-01", "revision": 1},
    "info": {
        "city": "Chennai",
        "dates": ["2023-04-05"],
        "event": {"name": "Indian Premier League", "match_number": 7},
        "gender": "male",
        "match_type": "T20",
        "outcome": {"winner": "Team B", "by": {"wickets": 5}},
        "players": {"Team A": ["A One", "A Two"], "Team B": ["B One", "B Two"]},
        "registry": {"people": {}},
        "season": "2023",
        "teams": ["Team A", "Team B"],
        "toss": {"decision": "field", "winner": "Team B"},
        "venue": "Chepauk",
    },
    "innings": [
        {
            "team": "Team A",
            "overs": [
                {
                    "over": 0,
                    "deliveries": [
                        {"batter": "A One", "bowler": "B Two", "non_striker": "A Two",
                         "runs": {"batter": 1, "extras": 0, "total": 1}},
                        # no-ball — faced by batter, not a legal ball for bowler
                        {"batter": "A One", "bowler": "B Two", "non_striker": "A Two",
                         "runs": {"batter": 2, "extras": 1, "total": 3},
                         "extras": {"noballs": 1}},
                    ],
                }
            ],
        }
    ],
}


@pytest.fixture
def fixture_zip(tmp_path, monkeypatch):
    """Build an in-memory ipl_json.zip in a temp cache dir; block real downloads."""
    monkeypatch.setattr(_cricsheet, "_cache_dir", lambda: str(tmp_path))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("1001.json", json.dumps(MATCH_1))
        zf.writestr("1002.json", json.dumps(MATCH_2))
        zf.writestr("README.txt", "not a match")
    (tmp_path / "ipl_json.zip").write_bytes(buf.getvalue())

    def fail_download(url, dest):
        raise AssertionError("tests must not hit the network")

    monkeypatch.setattr(_cricsheet, "_download", fail_download)
    return tmp_path


# ── get_matches ─────────────────────────────────────────────


class TestGetMatches:
    def test_lists_matches_newest_first(self, fixture_zip):
        result = _cricsheet.get_matches({"params": {"competition": "ipl"}})
        assert result["count"] == 2
        assert [m["match_id"] for m in result["matches"]] == ["1001", "1002"]
        m = result["matches"][0]
        assert m["teams"] == ["Team A", "Team B"]
        assert m["winner"] == "Team A"
        assert m["venue"] == "Wankhede Stadium"
        assert result["attribution"] == _cricsheet._ATTRIBUTION

    def test_season_filter(self, fixture_zip):
        result = _cricsheet.get_matches({"params": {"competition": "ipl", "season": 2023}})
        assert result["count"] == 1
        assert result["matches"][0]["match_id"] == "1002"

    def test_unknown_competition_errors(self):
        result = _cricsheet.get_matches({"params": {"competition": "nope"}})
        assert result["error"] is True
        assert "nope" in result["message"]

    def test_missing_competition_errors(self):
        result = _cricsheet.get_matches({"params": {}})
        assert result["error"] is True


# ── get_match_deliveries ────────────────────────────────────


class TestGetMatchDeliveries:
    def test_returns_all_innings(self, fixture_zip):
        result = _cricsheet.get_match_deliveries(
            {"params": {"competition": "ipl", "match_id": "1001"}}
        )
        assert result["match"]["match_id"] == "1001"
        assert len(result["innings"]) == 2
        first = result["innings"][0]
        assert first["innings"] == 1
        assert first["team"] == "Team A"
        assert first["count"] == 5
        d0 = first["deliveries"][0]
        assert d0 == {
            "over": 0, "ball": 1, "batter": "A One", "bowler": "B One",
            "non_striker": "A Two", "runs": {"batter": 4, "extras": 0, "total": 4},
        }
        # wide carries its extras dict; wicket ball carries its wickets list
        assert first["deliveries"][1]["extras"] == {"wides": 1}
        assert first["deliveries"][4]["wickets"][0]["kind"] == "bowled"
        assert result["attribution"] == _cricsheet._ATTRIBUTION

    def test_innings_filter(self, fixture_zip):
        result = _cricsheet.get_match_deliveries(
            {"params": {"competition": "ipl", "match_id": "1001", "innings": 2}}
        )
        assert len(result["innings"]) == 1
        assert result["innings"][0]["team"] == "Team B"

    def test_match_not_found(self, fixture_zip):
        result = _cricsheet.get_match_deliveries(
            {"params": {"competition": "ipl", "match_id": "9999"}}
        )
        assert result["error"] is True
        assert "9999" in result["message"]

    def test_missing_match_id(self, fixture_zip):
        result = _cricsheet.get_match_deliveries({"params": {"competition": "ipl"}})
        assert result["error"] is True


# ── get_player_stats ────────────────────────────────────────


class TestGetPlayerStats:
    def test_batting_aggregation(self, fixture_zip):
        result = _cricsheet.get_player_stats(
            {"params": {"competition": "ipl", "player": "A One"}}
        )
        bat = result["batting"]
        assert result["player"] == "A One"
        assert result["matches"] == 2
        assert bat["runs"] == 13        # 4+6 in match 1, 1+2 in match 2
        assert bat["balls"] == 6        # wide not faced, no-ball faced
        assert bat["fours"] == 1
        assert bat["sixes"] == 1
        assert bat["dismissals"] == 1   # bowled in match 1
        assert bat["strike_rate"] == round(13 / 6 * 100, 2)
        assert result["attribution"] == _cricsheet._ATTRIBUTION

    def test_bowling_aggregation(self, fixture_zip):
        result = _cricsheet.get_player_stats(
            {"params": {"competition": "ipl", "player": "B One"}}
        )
        bowl = result["bowling"]
        assert bowl["balls"] == 4           # wide doesn't count as a ball bowled
        assert bowl["runs_conceded"] == 11  # 4+6+wide(1); leg-bye not charged
        assert bowl["wickets"] == 1         # bowled credited
        assert bowl["economy"] == round(11 / (4 / 6), 2)

    def test_run_out_not_credited_to_bowler(self, fixture_zip):
        result = _cricsheet.get_player_stats(
            {"params": {"competition": "ipl", "player": "A Two"}}
        )
        assert result["bowling"]["wickets"] == 0

    def test_season_filter(self, fixture_zip):
        result = _cricsheet.get_player_stats(
            {"params": {"competition": "ipl", "player": "A One", "season": 2023}}
        )
        assert result["matches"] == 1
        assert result["batting"]["runs"] == 3

    def test_no_ball_not_a_legal_ball_but_charged(self, fixture_zip):
        result = _cricsheet.get_player_stats(
            {"params": {"competition": "ipl", "player": "B Two"}}
        )
        bowl = result["bowling"]
        assert bowl["balls"] == 1           # no-ball not a legal delivery
        assert bowl["runs_conceded"] == 4   # 1 + batter 2 + no-ball 1
        assert bowl["wickets"] == 0

    def test_unknown_player_errors(self, fixture_zip):
        result = _cricsheet.get_player_stats(
            {"params": {"competition": "ipl", "player": "Nobody"}}
        )
        assert result["error"] is True


# ── find_player ─────────────────────────────────────────────

PEOPLE_CSV = (
    "identifier,name,unique_name,key_bcci,key_bcci_2,key_bigbash,key_cricbuzz,"
    "key_cricheroes,key_crichq,key_cricinfo,key_cricinfo_2,key_cricinfo_3,"
    "key_cricingif,key_cricketarchive,key_cricketarchive_2,key_cricketworld,"
    "key_nvplay,key_nvplay_2,key_opta,key_opta_2,key_pulse,key_pulse_2\n"
    "ba607b88,V Kohli,V Kohli,,,,,,,253802,,,,,,,,,,,,\n"
    "abc123,RG Sharma,RG Sharma,,,,,,,34102,,,,,,,,,,,,\n"
)


class TestFindPlayer:
    def test_finds_by_substring_case_insensitive(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_cricsheet, "_cache_dir", lambda: str(tmp_path))
        (tmp_path / "people.csv").write_text(PEOPLE_CSV)
        monkeypatch.setattr(
            _cricsheet, "_download",
            lambda url, dest: (_ for _ in ()).throw(AssertionError("no network")),
        )
        result = _cricsheet.find_player({"params": {"name": "kohli"}})
        assert result["count"] == 1
        p = result["players"][0]
        assert p["cricsheet_id"] == "ba607b88"
        assert p["name"] == "V Kohli"
        assert p["cricinfo_id"] == "253802"
        assert result["attribution"] == _cricsheet._ATTRIBUTION

    def test_missing_name_errors(self):
        result = _cricsheet.find_player({"params": {}})
        assert result["error"] is True


# ── ESPN backend fixtures (shapes captured live 2026-06-03) ─

HEADER_PAYLOAD = {
    "sports": [{
        "id": "200", "name": "Cricket", "slug": "cricket",
        "leagues": [
            {"id": "8048", "name": "Indian Premier League", "abbreviation": "IPL",
             "isTournament": False,
             "events": [{"id": "1535465", "date": "2026-05-31T14:00Z",
                         "name": "Royal Challengers Bengaluru v Gujarat Titans",
                         "status": "post", "summary": "RCB won"}]},
            {"id": "24423", "name": "Sri Lanka tour of West Indies 2026",
             "abbreviation": "SL@WI", "isTournament": False, "events": []},
        ],
    }]
}


class TestGetSeries:
    def test_lists_active_series(self, monkeypatch):
        monkeypatch.setattr(_espn, "_header_request", lambda: HEADER_PAYLOAD)
        result = _espn.get_series({})
        assert result["count"] == 2
        s = result["series"][0]
        assert s["series_id"] == "8048"
        assert s["name"] == "Indian Premier League"
        assert s["abbreviation"] == "IPL"
        assert s["event_count"] == 1
        assert s["events"][0]["event_id"] == "1535465"

    def test_propagates_fetch_error(self, monkeypatch):
        monkeypatch.setattr(
            _espn, "_header_request",
            lambda: {"error": True, "message": "HTTP 503"},
        )
        result = _espn.get_series({})
        assert result["error"] is True
