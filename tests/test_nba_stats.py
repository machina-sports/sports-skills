"""Tests for the NBA Stats (stats.nba.com) backend.

No network: `_request` is monkeypatched to serve trimmed real payloads captured
from the live endpoints (tests/fixtures/nba_stats/), so the normalizers are
exercised against the actual response shapes.
"""

import json
import pathlib

import pytest

from sports_skills.nba import _stats

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "nba_stats"


def _fixture(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


@pytest.fixture
def offline(monkeypatch):
    """Serve every endpoint from its captured fixture; record what was asked."""
    calls = []

    def fake_request(endpoint, params, ttl=600):
        calls.append((endpoint, params))
        if params.get("PlayerOrTeam") == "P":
            return _fixture(f"{endpoint}_player")
        return _fixture(endpoint)

    monkeypatch.setattr(_stats, "_request", fake_request)
    return calls


# ── season coercion ─────────────────────────────────────────────


class TestSeasonStr:
    def test_year_int(self):
        assert _stats._season_str(2024) == "2024-25"

    def test_year_str(self):
        assert _stats._season_str("2024") == "2024-25"

    def test_nba_form_passthrough(self):
        assert _stats._season_str("2024-25") == "2024-25"

    def test_century_boundary(self):
        assert _stats._season_str(1999) == "1999-00"

    def test_decade_boundary(self):
        assert _stats._season_str(2009) == "2009-10"

    def test_none_is_current_season(self):
        assert _stats._season_str(None) == _stats._season_str(_stats._current_season_year())

    def test_garbage_is_reported(self):
        with pytest.raises(_stats._NbaStatsError, match="Invalid season"):
            _stats._season_str("next year")


# ── team abbreviation translation ─────────────────────────────────────────────


class TestNormalizeTeam:
    @pytest.mark.parametrize(
        ("espn", "nba"),
        [("GS", "GSW"), ("NO", "NOP"), ("NY", "NYK"), ("SA", "SAS"), ("UTAH", "UTA"), ("WSH", "WAS")],
    )
    def test_translates_espn_spellings(self, espn, nba):
        assert _stats._normalize_team(espn) == nba

    @pytest.mark.parametrize("abbr", ["GSW", "BOS", "LAL", "OKC"])
    def test_shared_spellings_untouched(self, abbr):
        assert _stats._normalize_team(abbr) == abbr

    def test_lowercase_and_whitespace(self):
        assert _stats._normalize_team(" gs ") == "GSW"

    def test_none_passes_through(self):
        assert _stats._normalize_team(None) is None

    def test_alias_maps_are_inverses(self):
        for espn, nba in _stats._ESPN_TO_NBA.items():
            assert _stats._NBA_TO_ESPN[nba] == espn


# ── enum-ish parameter validation ─────────────────────────────────────────────


class TestLookup:
    def test_default_when_none(self):
        assert _stats._lookup(_stats._SEASON_TYPES, None, "regular", "season_type") == "Regular Season"

    def test_tolerates_case_and_separators(self):
        assert _stats._lookup(_stats._MEASURE_TYPES, "Four Factors", "base", "measure") == "Four Factors"
        assert _stats._lookup(_stats._PER_MODES, "PER-GAME", "totals", "per_mode") == "PerGame"

    def test_invalid_lists_valid_values(self):
        with pytest.raises(_stats._NbaStatsError, match="playoffs"):
            _stats._lookup(_stats._SEASON_TYPES, "bogus", "regular", "season_type")


class TestSeasonTypeAliases:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, "Regular Season"),
            ("regular", "Regular Season"),
            ("Regular Season", "Regular Season"),
            ("2", "Regular Season"),
            (2, "Regular Season"),
            ("Playoffs", "Playoffs"),
            ("playoff", "Playoffs"),
            ("postseason", "Playoffs"),
            ("4", "Playoffs"),
            ("PlayIn", "PlayIn"),
            ("Play-In", "PlayIn"),
            ("play in", "PlayIn"),
            ("5", "PlayIn"),
            ("Pre Season", "Pre Season"),
            ("preseason", "Pre Season"),
        ],
    )
    def test_common_forms_are_mapped(self, value, expected):
        assert _stats._season_type(value) == expected

    def test_unknown_still_lists_canonical_values(self):
        with pytest.raises(_stats._NbaStatsError, match="playin, playoffs, preseason, regular"):
            _stats._season_type("3")

    def test_alias_reaches_upstream(self, offline):
        _stats.get_nbastats_game_log({"params": {"season": 2024, "season_type": "Regular Season"}})
        assert offline[-1][1]["SeasonType"] == "Regular Season"


# ── name matching ─────────────────────────────────────────────


class TestFold:
    def test_strips_diacritics(self):
        """The registry stores accented names; ASCII queries must still match."""
        assert _stats._fold("Nikola Jokić") == "nikola jokic"
        assert _stats._fold("Luka Dončić") == "luka doncic"

    def test_lowercases(self):
        assert _stats._fold("Stephen CURRY") == "stephen curry"


class TestResolvePlayer:
    def test_player_id_short_circuits(self, offline):
        pid, _ = _stats._resolve_player("2544", None)
        assert pid == "2544"
        assert offline == [], "no registry fetch when an id is given"

    def test_ascii_query_finds_accented_name(self, offline):
        pid, name = _stats._resolve_player(None, "jokic")
        assert pid == "203999"
        assert "Joki" in name

    def test_ambiguous_name_lists_candidates(self, offline):
        with pytest.raises(_stats._NbaStatsError, match="matched"):
            _stats._resolve_player(None, "james")

    def test_no_match_points_at_find(self, offline):
        with pytest.raises(_stats._NbaStatsError, match="find_nba_player"):
            _stats._resolve_player(None, "zzz-nobody")

    def test_neither_id_nor_name_is_reported(self):
        with pytest.raises(_stats._NbaStatsError, match="player_id or player"):
            _stats._resolve_player(None, None)


# ── records normalization ─────────────────────────────────────────────


class TestRecords:
    def test_lowercases_headers(self):
        data = {"resultSets": [{"name": "X", "headers": ["GAME_ID", "PTS"], "rowSet": [["1", 30]]}]}
        assert _stats._records(data) == [{"game_id": "1", "pts": 30}]

    def test_selects_named_set(self):
        data = {
            "resultSets": [
                {"name": "A", "headers": ["X"], "rowSet": [[1]]},
                {"name": "B", "headers": ["Y"], "rowSet": [[2]]},
            ]
        }
        assert _stats._records(data, "B") == [{"y": 2}]

    def test_missing_named_set_falls_back_to_first(self):
        data = {"resultSets": [{"name": "A", "headers": ["X"], "rowSet": [[1]]}]}
        assert _stats._records(data, "Nope") == [{"x": 1}]

    def test_empty_payload(self):
        assert _stats._records({}) == []


# ── getters against captured payloads ─────────────────────────────────────────────


class TestGameLog:
    def test_returns_rows_with_both_abbreviations(self, offline):
        out = _stats.get_nbastats_game_log({"params": {"season": 2024}})
        assert out["count"] == len(out["games"]) > 0
        row = out["games"][0]
        assert row["team_abbreviation"]
        assert row["team_abbreviation_espn"]

    def test_espn_spelling_filter(self, offline):
        out = _stats.get_nbastats_game_log({"params": {"season": 2024, "team": "GS"}})
        assert all(r["team_abbreviation"] == "GSW" for r in out["games"])

    def test_unmatched_team_warns(self, offline):
        out = _stats.get_nbastats_game_log({"params": {"season": 2024, "team": "ZZZ"}})
        assert out["count"] == 0
        assert out["warnings"] and "matched no rows" in out["warnings"][0]

    def test_season_type_is_sent_upstream(self, offline):
        _stats.get_nbastats_game_log({"params": {"season": 2024, "season_type": "playoffs"}})
        endpoint, params = offline[-1]
        assert endpoint == "leaguegamelog"
        assert params["SeasonType"] == "Playoffs"

    def test_default_request_and_output_unchanged(self, offline):
        """#150: the team log must not change with the new player options."""
        out = _stats.get_nbastats_game_log({"params": {"season": 2024}})
        endpoint, params = offline[-1]
        assert params["PlayerOrTeam"] == "T"
        assert "player_or_team" not in out and "player" not in out
        explicit = _stats.get_nbastats_game_log({"params": {"season": 2024, "player_or_team": "team"}})
        assert explicit == out
        assert offline[-1] == (endpoint, params)


class TestPlayerGameLog:
    """#150: player rows via leaguegamelog "P", or playergamelog for one player."""

    def test_league_player_rows(self, offline):
        out = _stats.get_nbastats_game_log({"params": {"season": 2024, "player_or_team": "player"}})
        endpoint, params = offline[-1]
        assert (endpoint, params["PlayerOrTeam"]) == ("leaguegamelog", "P")
        assert out["player_or_team"] == "player"
        row = out["games"][0]
        assert row["player_name"] == "Al Horford"
        assert row["matchup"] == "BOS vs. NYK" and row["wl"] == "W" and row["pts"] == 11
        assert row["team_abbreviation_espn"] == "BOS"

    def test_team_filter_on_player_rows(self, offline):
        out = _stats.get_nbastats_game_log(
            {"params": {"season": 2024, "player_or_team": "player", "team": "GS"}}
        )
        assert out["count"] == 4
        assert all(r["team_abbreviation"] == "GSW" for r in out["games"])

    def test_one_player_uses_the_light_endpoint(self, offline):
        out = _stats.get_nbastats_game_log({"params": {"season": 2024, "player": "LeBron James"}})
        endpoint, params = offline[-1]
        assert endpoint == "playergamelog"
        assert params["PlayerID"] == "2544" and params["Season"] == "2024-25"
        assert out["player_id"] == "2544" and out["player"] == "LeBron James"
        assert out["count"] == 5

    def test_one_player_rows_match_league_row_form(self, offline):
        out = _stats.get_nbastats_game_log({"params": {"season": 2024, "player": "2544"}})
        assert all(e != "commonallplayers" for e, _ in offline), "an id needs no registry lookup"
        dates = [r["game_date"] for r in out["games"]]
        assert dates == sorted(dates), "chronological, like leaguegamelog"
        last = out["games"][-1]
        assert last["game_id"] == "0022401185" and last["game_date"] == "2025-04-11"
        assert last["matchup"] == "LAL vs. HOU" and last["wl"] == "W" and last["pts"] == 14
        assert last["team_abbreviation"] == "LAL" and last["team_abbreviation_espn"] == "LAL"

    def test_shaping_keeps_player_identity(self, offline):
        out = _stats.get_nbastats_game_log(
            {"params": {"season": 2024, "player": "2544", "sort_by": "pts", "limit": 1, "fields": "pts"}}
        )
        assert out["total_rows"] == 5 and out["returned_rows"] == 1
        assert set(out["games"][0]) == {
            "game_id", "game_date", "player_id", "team_abbreviation", "matchup", "pts"
        }

    def test_opponent_and_home_away_from_matchup(self, offline):
        league = _stats.get_nbastats_game_log({"params": {"season": 2024, "player_or_team": "player"}})
        home = league["games"][0]  # BOS vs. NYK
        assert (home["matchup"], home["opponent"], home["home_away"]) == ("BOS vs. NYK", "NYK", "home")
        away = next(r for r in league["games"] if " @ " in r["matchup"])
        assert away["home_away"] == "away" and away["opponent"] == away["matchup"].split(" @ ")[1]
        one = _stats.get_nbastats_game_log({"params": {"season": 2024, "player": "2544"}})
        last = one["games"][-1]  # LAL vs. HOU
        assert (last["opponent"], last["home_away"], last["wl"]) == ("HOU", "home", "W")
        assert all(r["home_away"] in ("home", "away") for r in one["games"])

    def test_team_rows_gain_no_matchup_columns(self, offline):
        out = _stats.get_nbastats_game_log({"params": {"season": 2024}})
        assert "opponent" not in out["games"][0] and "home_away" not in out["games"][0]

    @pytest.mark.parametrize(
        "matchup, expected",
        [
            ("LAL vs. HOU", ("HOU", "home")),
            ("LAL @ HOU", ("HOU", "away")),
            ("", (None, None)),
            (None, (None, None)),
            ("LAL - HOU", (None, None)),
        ],
    )
    def test_matchup_parsing(self, matchup, expected):
        assert _stats._matchup_sides(matchup) == expected

    def test_player_with_team_mode_is_reported(self, offline):
        out = _stats.get_nbastats_game_log(
            {"params": {"player_or_team": "team", "player": "LeBron James"}}
        )
        assert out["error"] is True and "player_or_team" in out["message"]
        assert offline == []

    def test_invalid_mode_lists_valid_values(self, offline):
        out = _stats.get_nbastats_game_log({"params": {"player_or_team": "both"}})
        assert out["error"] is True and "player, team" in out["message"]

    def test_ambiguous_player_is_reported(self, offline):
        out = _stats.get_nbastats_game_log({"params": {"player": "Curry"}})
        assert out["error"] is True and "Stephen Curry" in out["message"]

    def test_empty_player_log_warns(self, monkeypatch):
        empty = _fixture("playergamelog")
        empty["resultSets"][0]["rowSet"] = []
        monkeypatch.setattr(_stats, "_request", lambda endpoint, params, ttl=600: empty)
        out = _stats.get_nbastats_game_log({"params": {"season": 2024, "player": "2544"}})
        assert out["count"] == 0 and "no Regular Season games" in out["warnings"][0]


class TestPlayerCareer:
    def test_seasons_and_totals(self, offline):
        out = _stats.get_nbastats_player_career({"params": {"player_id": "203999"}})
        assert out["count"] == len(out["seasons"]) > 0
        assert out["career_totals"] is not None
        assert out["seasons"][0]["team_abbreviation_espn"]

    def test_per_mode_is_sent_upstream(self, offline):
        _stats.get_nbastats_player_career({"params": {"player_id": "1", "per_mode": "per_game"}})
        _, params = offline[-1]
        assert params["PerMode"] == "PerGame"


class TestTeamStats:
    def test_rows_gain_abbreviations(self, offline):
        out = _stats.get_nbastats_team_stats({"params": {"season": 2024, "measure": "advanced"}})
        assert out["count"] > 0
        row = out["teams"][0]
        assert row.get("team_abbreviation")
        assert row.get("team_abbreviation_espn")

    def test_team_filter_matches_by_name_table(self, offline):
        got_any = False
        for abbr in ("GSW", "BOS", "OKC", "CLE", "DEN", "NYK", "LAL", "HOU"):
            out = _stats.get_nbastats_team_stats({"params": {"season": 2024, "team": abbr}})
            if out["count"]:
                got_any = True
                assert all(_stats._name_to_abbr(r.get("team_name")) == abbr for r in out["teams"])
        assert got_any, "fixture holds 8 teams; at least one should match"

    def test_per_36_sends_the_value_stats_nba_accepts(self, offline):
        """#160: "Per36Minutes" got HTTP 400 from leaguedashteamstats and
        playercareerstats (checked live 2026-09-29); "Per36" is accepted."""
        _stats.get_nbastats_team_stats({"params": {"season": 2024, "per_mode": "per_36"}})
        _stats.get_nbastats_player_career({"params": {"player_id": "2544", "per_mode": "per_36"}})
        assert [params["PerMode"] for _, params in offline] == ["Per36", "Per36"]

    def test_every_franchise_name_is_mapped(self):
        assert len(_stats._TEAM_NAMES) == 30
        assert len(set(_stats._TEAM_NAMES.values())) == 30


class TestShotChart:
    def test_shot_shape(self, offline):
        out = _stats.get_nbastats_shot_chart({"params": {"player_id": "203999", "season": 2024}})
        shot = out["shots"][0]
        assert {"loc_x", "loc_y", "made", "shot_distance", "period"} <= set(shot)
        assert isinstance(shot["made"], bool)

    def test_game_date_matches_game_log_format(self, offline):
        """#160: shotchartdetail sends GAME_DATE "20241122"; game logs use "2024-10-22"."""
        out = _stats.get_nbastats_shot_chart({"params": {"player_id": "203999", "season": 2024}})
        assert out["shots"][0]["game_date"] == "2024-11-22"
        log = _stats.get_nbastats_game_log({"params": {"season": 2024}})
        assert log["games"][0]["game_date"] == "2024-10-22"

    def test_limit_flags_truncation(self, offline):
        out = _stats.get_nbastats_shot_chart(
            {"params": {"player_id": "203999", "season": 2024, "limit": 3}}
        )
        assert out["count"] == 3
        assert out["truncated"] is True
        assert "truncated" in out["warnings"][0]


class TestPlayByPlay:
    def test_actions_normalized(self, offline):
        out = _stats.get_nbastats_play_by_play({"params": {"game_id": "0022400072"}})
        play = out["plays"][0]
        assert {"action_number", "period", "clock", "description"} <= set(play)

    def test_limit_flags_truncation(self, offline):
        out = _stats.get_nbastats_play_by_play({"params": {"game_id": "0022400072", "limit": 2}})
        assert out["count"] == 2 and out["truncated"] is True

    def test_missing_game_id_mentions_the_id_system(self, offline):
        out = _stats.get_nbastats_play_by_play({"params": {}})
        assert out["error"] is True
        assert "ESPN event id" in out["message"]

    def test_espn_event_id_is_caught_with_join_guidance(self, offline):
        """The natural mistake: both id systems live in this module."""
        out = _stats.get_nbastats_play_by_play({"params": {"game_id": "401704627"}})
        assert out["error"] is True
        assert "looks like an ESPN event id" in out["message"]
        assert "get_nbastats_game_log" in out["message"]

    def test_other_malformed_ids_get_the_format(self, offline):
        out = _stats.get_nbastats_advanced_boxscore({"params": {"game_id": "abc"}})
        assert out["error"] is True
        assert "10-digit" in out["message"]
        assert "looks like an ESPN event id" not in out["message"]

    def test_valid_id_passes_validation(self, offline):
        out = _stats.get_nbastats_advanced_boxscore({"params": {"game_id": "0022400072"}})
        assert "error" not in out


class TestAdvancedBoxscore:
    def test_both_sides_normalized(self, offline):
        out = _stats.get_nbastats_advanced_boxscore({"params": {"game_id": "0022400072"}})
        for side in ("home", "away"):
            team = out[side]
            assert team["team"] and team["team_name"]
            assert team["players"], side
            player = team["players"][0]
            assert player["player_id"] and player["name"]
            assert isinstance(player["stats"], dict) and player["stats"]

    def test_espn_abbreviation_present(self, offline):
        out = _stats.get_nbastats_advanced_boxscore({"params": {"game_id": "0022400072"}})
        assert out["home"]["team_abbreviation_espn"]


class TestFindPlayer:
    def test_ascii_finds_accented(self, offline):
        out = _stats.find_nba_player({"params": {"name": "doncic"}})
        assert out["count"] >= 1
        assert any("Don" in p["name"] for p in out["players"])

    def test_missing_name_is_reported(self, offline):
        out = _stats.find_nba_player({"params": {}})
        assert out["error"] is True


# ── failure behaviour ─────────────────────────────────────────────


class TestGuard:
    def test_unexpected_error_is_reported(self, monkeypatch):
        def boom(endpoint, params, ttl=600):
            raise RuntimeError("upstream exploded")

        monkeypatch.setattr(_stats, "_request", boom)
        out = _stats.get_nbastats_game_log({"params": {"season": 2024}})
        assert out["error"] is True
        assert "RuntimeError" in out["message"]

    def test_throttle_carries_the_premium_marker(self, monkeypatch):
        from sports_skills._premium import UPGRADE_MARKER
        from sports_skills._response import wrap

        def tarpitted(endpoint, params, ttl=600):
            raise _stats._NbaStatsThrottled("stats.nba.com did not answer.")

        monkeypatch.setattr(_stats, "_request", tarpitted)
        raw = _stats.get_nbastats_game_log({"params": {"season": 2024}})
        assert raw[UPGRADE_MARKER] == "rate_limited"
        wrapped = wrap(raw)
        assert wrapped["status"] is False
        assert wrapped["upgrade"]["trigger"] == "rate_limited"
        assert UPGRADE_MARKER not in wrapped

    def test_timeout_becomes_throttle_guidance(self, monkeypatch):
        def fake_fetch(url, **kw):
            return None, {"error": True, "message": "The read operation timed out"}

        monkeypatch.setattr(_stats, "_http_fetch", fake_fetch)
        monkeypatch.setattr(_stats, "_cache_get", lambda k: None)
        with pytest.raises(_stats._NbaStatsThrottled, match="tarpitted"):
            _stats._request("leaguegamelog", {})

    def test_non_timeout_error_is_plain(self, monkeypatch):
        def fake_fetch(url, **kw):
            return None, {"error": True, "message": "HTTP 400 from stats.nba.com: bad param"}

        monkeypatch.setattr(_stats, "_http_fetch", fake_fetch)
        monkeypatch.setattr(_stats, "_cache_get", lambda k: None)
        with pytest.raises(_stats._NbaStatsError) as exc:
            _stats._request("leaguegamelog", {})
        assert not isinstance(exc.value, _stats._NbaStatsThrottled)

    def test_stats_requests_never_retry(self, monkeypatch):
        """Retrying a tarpitted request extends the penalty — pin max_retries=0."""
        seen = {}

        def fake_fetch(url, **kw):
            seen.update(kw)
            return b"{}", None

        monkeypatch.setattr(_stats, "_http_fetch", fake_fetch)
        monkeypatch.setattr(_stats, "_cache_get", lambda k: None)
        monkeypatch.setattr(_stats, "_cache_set", lambda *a, **k: None)
        _stats._request("leaguegamelog", {})
        assert seen.get("max_retries") == 0


class TestHeaders:
    def test_client_hints_accompany_the_chrome_ua(self):
        """Absent Sec-Ch-Ua alongside a Chrome UA gets silently tarpitted."""
        assert "Chrome" in _stats._STATS_HEADERS["User-Agent"]
        assert "Sec-Ch-Ua" in _stats._STATS_HEADERS
        assert "Sec-Ch-Ua-Mobile" in _stats._STATS_HEADERS
        assert "Sec-Fetch-Dest" in _stats._STATS_HEADERS

    def test_ua_version_matches_client_hint_version(self):
        version = _stats._STATS_HEADERS["User-Agent"].split("Chrome/")[1].split(".")[0]
        assert f'v="{version}"' in _stats._STATS_HEADERS["Sec-Ch-Ua"]

    def test_no_brotli_advertised(self):
        """The stdlib can only decode gzip."""
        assert "br" not in _stats._STATS_HEADERS["Accept-Encoding"].split(", ")


# ── live box score: ESPN fallback when cdn.nba.com refuses ─────────────


class TestLiveFallbackMapsToEspnEventId:
    """#160: on a cdn.nba.com 403 the ESPN fallback was called with the NBA game
    id, which ESPN cannot resolve. ATL @ BOS 2024-11-12: NBA 0022400001 is ESPN
    401703370 (stats.nba.com boxscoresummaryv3 and ESPN scoreboard, trimmed)."""

    CDN_403 = {"error": True, "status_code": 403, "message": "HTTP 403 from cdn.nba.com — Access Denied"}

    @pytest.fixture
    def fallback(self, monkeypatch):
        import sports_skills.nba as nba
        from sports_skills.nba import _connector

        board = json.loads((FIXTURES.parent / "nba_espn_scoreboard_20241112.json").read_text())
        espn_calls, summaries = [], []

        def fake_espn(sport, resource, params=None):
            espn_calls.append((resource, params))
            return board if resource == "scoreboard" else {"error": True, "message": "unexpected"}

        def record(result):
            return lambda rd: summaries.append(rd["params"]) or result

        monkeypatch.setattr(nba, "_get_live_boxscore", lambda rd: dict(self.CDN_403))
        monkeypatch.setattr(nba, "_get_live_playbyplay", lambda rd: dict(self.CDN_403))
        monkeypatch.setattr(_stats, "_request", lambda endpoint, params, ttl=600: _fixture(endpoint))
        monkeypatch.setattr(_connector, "espn_request", fake_espn)
        monkeypatch.setattr(nba, "_get_game_summary", record({"game_info": {}}))
        monkeypatch.setattr(nba, "_get_play_by_play", record({"plays": []}))
        return nba, espn_calls, summaries

    def test_boxscore_fallback_uses_the_espn_event_id(self, fallback):
        nba, espn_calls, summaries = fallback
        out = nba.get_live_boxscore(game_id="0022400001")
        assert out["status"] is True
        assert espn_calls == [("scoreboard", {"dates": "20241112"})]
        assert summaries == [{"event_id": "401703370"}]

    def test_playbyplay_fallback_uses_the_espn_event_id(self, fallback):
        nba, _, summaries = fallback
        nba.get_live_playbyplay(game_id="0022400001")
        assert summaries == [{"event_id": "401703370"}]

    def test_espn_event_id_passes_straight_through(self, fallback):
        nba, espn_calls, summaries = fallback
        nba.get_live_boxscore(game_id="401703370")
        assert espn_calls == [] and summaries == [{"event_id": "401703370"}]

    def test_unmapped_game_is_a_clear_error(self, fallback, monkeypatch):
        nba, _, summaries = fallback
        monkeypatch.setattr(_stats, "_request", lambda endpoint, params, ttl=600: {"boxScoreSummary": {}})
        out = nba.get_live_boxscore(game_id="0022400001")
        assert out["status"] is False and summaries == []
        assert "HTTP 403" in out["message"]
        assert "could not be mapped to an ESPN event id" in out["message"]
        assert "get_game_summary(event_id=" in out["message"]

    def test_no_matching_espn_event_is_a_clear_error(self, fallback, monkeypatch):
        nba, _, summaries = fallback
        summary = _fixture("boxscoresummaryv3")
        summary["boxScoreSummary"]["awayTeam"]["teamTricode"] = "LAL"
        monkeypatch.setattr(_stats, "_request", lambda endpoint, params, ttl=600: summary)
        out = nba.get_live_boxscore(game_id="0022400001")
        assert out["status"] is False and summaries == []
        assert "no ESPN event for LAL @ BOS on 2024-11-12" in out["message"]
