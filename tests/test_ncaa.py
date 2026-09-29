"""Tests for the shared NCAA backend and its cfb/cbb wrappers.

No network: `_fetch_json` is monkeypatched to serve trimmed real payloads
captured from the live endpoints (tests/fixtures/ncaa/), so the normalizers are
exercised against the actual response shapes of both upstreams (ncaa.com JSON
and the sdataprod persisted queries).
"""

import json
import pathlib
import re
import urllib.parse

import pytest

from sports_skills import _ncaa

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "ncaa"


def _key_for(url):
    if "sdataprod" in url:
        h = re.search(r"sha256Hash%22%3A%20%22([a-f0-9]{12})", url)
        hid = h.group(1)[:12] if h else "gql"
        var = re.search(r"variables=([^&]+)", url)
        v = json.loads(urllib.parse.unquote(var.group(1))) if var else {}
        tail = v.get("contestId") or v.get("id") or v.get("sportUrl") or v.get("sportCode") or ""
        if v.get("year"):
            tail = f"{tail}_{v['year']}"
        return f"gql_{hid}_{tail}"
    path = url.split("casablanca/")[-1] if "casablanca" in url else url.rsplit("/", 2)[-1]
    return re.sub(r"[^A-Za-z0-9]+", "_", path.replace(".json", "")).strip("_")


@pytest.fixture
def offline(monkeypatch):
    calls = []

    def fake_fetch(url, ttl=300):
        calls.append(url)
        return json.loads((FIXTURES / f"{_key_for(url)}.json").read_text())

    monkeypatch.setattr(_ncaa, "_fetch_json", fake_fetch)
    return calls


# ── sport / division validation ─────────────────────────────────────────────


class TestSportConfig:
    def test_known_sports(self):
        for sport in ("football", "basketball-men", "basketball-women"):
            assert _ncaa.sport_config(sport)["code"]

    def test_unknown_sport_lists_valid(self):
        with pytest.raises(_ncaa._NcaaError, match="basketball-men"):
            _ncaa.sport_config("hockey")

    def test_division_codes(self):
        assert _ncaa.resolve_division("football", "fbs") == ("fbs", 11)
        assert _ncaa.resolve_division("football", "fcs") == ("fcs", 12)
        assert _ncaa.resolve_division("basketball-men", "d3") == ("d3", 3)

    def test_default_division(self):
        assert _ncaa.resolve_division("football", None)[0] == "fbs"
        assert _ncaa.resolve_division("basketball-men", None)[0] == "d1"

    def test_wrong_division_for_sport(self):
        """Football splits FBS/FCS; d1-d3 belong to other sports."""
        with pytest.raises(_ncaa._NcaaError, match="fbs, fcs"):
            _ncaa.resolve_division("football", "d3")


# ── game id validation ─────────────────────────────────────────────


class TestRequireGameId:
    def test_valid_id_passes(self):
        assert _ncaa.require_game_id(6306261) == "6306261"

    def test_espn_event_id_gets_join_guidance(self):
        with pytest.raises(_ncaa._NcaaError, match="looks like an ESPN event id"):
            _ncaa.require_game_id("401628455")

    def test_missing_is_reported(self):
        with pytest.raises(_ncaa._NcaaError, match="game_id is required"):
            _ncaa.require_game_id(None)

    def test_garbage_gets_the_format(self):
        with pytest.raises(_ncaa._NcaaError, match="Invalid NCAA game id"):
            _ncaa.require_game_id("abc")


# ── scoreboard / schedule (sdataprod) ─────────────────────────────


def _variables(url):
    return json.loads(urllib.parse.unquote(re.search(r"variables=([^&]+)", url).group(1)))


class TestScoreboard:
    """#165: casablanca froze on 2025-08-29 (every later game stuck at `pre`,
    2026 and newer dates NoSuchKey), so scoreboards come from the GraphQL
    scoreboard query instead."""

    def test_football_week_query(self, offline):
        out = _ncaa.fetch_scoreboard("football", "fbs", year=2025, week=16)
        assert out["count"] == 2
        g = out["games"][0]
        assert {"game_id", "home_team", "away_team", "status"} <= set(g)
        assert re.fullmatch(r"\d+", g["game_id"])
        assert "sdataprod" in offline[-1]
        assert _variables(offline[-1]) == {"sportCode": "MFB", "division": 11, "seasonYear": 2025, "week": 16}

    def test_finished_games_are_final_with_scores(self, offline):
        """Army-Navy 2025: casablanca still lists it as `pre` under the stale id
        6455327, which the game endpoint no longer knows."""
        out = _ncaa.fetch_scoreboard("football", "fbs", year=2025, week=16)
        army_navy = next(g for g in out["games"] if "Navy" in (g["home_team"], g["away_team"]))
        assert army_navy["game_id"] == "6458979"
        assert army_navy["status"] == "final"
        assert army_navy["home_score"] is not None and army_navy["away_score"] is not None

    def test_basketball_date_query(self, offline):
        out = _ncaa.fetch_scoreboard("basketball-men", "d1", date="2026-03-20")
        assert out["count"] > 0
        assert out["games"][0]["status"] == "final"
        # A March date belongs to the season that started the previous fall.
        assert _variables(offline[-1]) == {
            "sportCode": "MBB",
            "division": 1,
            "seasonYear": 2025,
            "contestDate": "03/20/2026",
        }

    def test_football_requires_week(self, offline):
        with pytest.raises(_ncaa._NcaaError, match="week is required"):
            _ncaa.fetch_scoreboard("football", "fbs", year=2024)

    def test_basketball_requires_date(self, offline):
        with pytest.raises(_ncaa._NcaaError, match="date is required"):
            _ncaa.fetch_scoreboard("basketball-men", "d1")

    def test_bad_date_is_reported(self, offline):
        with pytest.raises(_ncaa._NcaaError, match="YYYY-MM-DD"):
            _ncaa.fetch_scoreboard("basketball-men", "d1", date="Feb 28")


class TestSchedule:
    def test_football_schedule_numbers_weeks(self, offline):
        out = _ncaa.fetch_schedule("football", "fbs", year=2025)
        weeks = out["schedule"]
        assert [w["week"] for w in weeks] == list(range(1, 22))
        assert weeks[15] == {"week": 16, "start_date": "2025-12-13", "end_date": "2025-12-13", "games": 2}
        assert out["count"] == 21

    def test_football_schedule_drops_postseason_rollup(self, offline):
        """The source appends one overlapping entry totalling the postseason
        weeks; it is not a week of its own."""
        out = _ncaa.fetch_schedule("football", "fbs", year=2025)
        assert all(w["games"] != 47 for w in out["schedule"])

    def test_basketball_schedule_filters_month(self, offline):
        out = _ncaa.fetch_schedule("basketball-men", "d1", year=2025, month=3)
        assert out["count"] > 0
        assert all(d["date"].startswith("2026-03-") for d in out["schedule"])
        assert _variables(offline[-1]) == {"sportCode": "MBB", "division": 1, "seasonYear": 2025}

    def test_basketball_needs_month(self, offline):
        with pytest.raises(_ncaa._NcaaError, match="month is required"):
            _ncaa.fetch_schedule("basketball-men", "d1", year=2024)


# ── sdataprod layer ─────────────────────────────────────────────


class TestGameDetail:
    def test_game_info(self, offline):
        out = _ncaa.fetch_game_info("6306261")
        assert out["game"]

    def test_football_pbp_nested_shape(self, offline):
        out = _ncaa.fetch_play_by_play("football", "6306261")
        assert out["count"] > 0
        play = out["plays"][0]
        assert {"period", "description", "home_score", "away_score"} <= set(play)
        assert play["team"], "football blocks resolve team names"

    def test_basketball_pbp_flat_shape(self, offline):
        """Basketball blocks ARE the plays — different shape, same output."""
        out = _ncaa.fetch_play_by_play("basketball-men", "6351148")
        assert out["count"] > 0
        assert all(p["description"] for p in out["plays"])

    def test_pbp_limit_flags_truncation(self, offline):
        out = _ncaa.fetch_play_by_play("football", "6306261", limit=2)
        assert out["count"] == 2 and out["truncated"] is True

    def test_boxscore_normalizes_teams(self, offline):
        out = _ncaa.fetch_boxscore("football", "6306261")
        assert len(out["teams"]) == 2
        assert all(t["name"] and t["team_id"] for t in out["teams"])
        assert out["team_stats"], "sport-specific stat tables pass through"

    def test_scoring_summary(self, offline):
        out = _ncaa.fetch_scoring_summary("6306261")
        assert out["scoring_summary"]

    def test_scoring_summary_field_goals_carry_distance(self, offline):
        """#165: the summary text is "Smith,Garrison Field Goal is good." with
        no distance; the play-by-play attempt text carries it."""
        out = _ncaa.fetch_scoring_summary("6306261")
        fgs = [
            s
            for p in out["scoring_summary"]["periods"]
            for s in p["summary"]
            if s["scoreType"] == "FG"
        ]
        assert [s["distance_yards"] for s in fgs] == [43, 40, 26, 27]

    def test_missing_game_hints_at_reissued_ids(self, monkeypatch):
        monkeypatch.setattr(_ncaa, "_fetch_json", lambda url, ttl=300: {"data": {"contests": []}})
        with pytest.raises(_ncaa._NcaaError, match="get_ncaa_scoreboard"):
            _ncaa.fetch_game_info("6455327")

    def test_bracket_march_madness(self, offline):
        out = _ncaa.fetch_bracket("basketball-men", "d1", 2025)
        assert out["rounds"] and out["regions"]
        assert out["games"], "bracket carries games with live scores in season"

    def test_bracket_without_a_field_is_an_error(self, offline):
        """#165: 2020 returns 67 TBA placeholder games (tournament cancelled)."""
        with pytest.raises(_ncaa._NcaaError, match="cancelled"):
            _ncaa.fetch_bracket("basketball-men", "d1", 2020)


class TestHashRotation:
    """When ncaa.com redeploys, the pinned hashes stop matching."""

    def test_400_becomes_rotation_message(self, monkeypatch):
        def fake(url, ttl=300):
            raise _ncaa._NcaaError("HTTP 400 from sdataprod.ncaa.com")

        monkeypatch.setattr(_ncaa, "_fetch_json", fake)
        with pytest.raises(_ncaa._NcaaError, match="rotated its persisted-query hashes"):
            _ncaa._graphql("deadbeef", {})

    def test_persisted_query_error_becomes_rotation_message(self, monkeypatch):
        def fake(url, ttl=300):
            return {"errors": [{"message": "PersistedQueryNotFound"}], "data": None}

        monkeypatch.setattr(_ncaa, "_fetch_json", fake)
        with pytest.raises(_ncaa._NcaaError, match="rotated its persisted-query hashes"):
            _ncaa._graphql("deadbeef", {})

    def test_rotation_message_names_the_working_layer(self):
        assert "get_ncaa_schools" in _ncaa._ROTATION_MESSAGE
        assert "henrygd/ncaa-api" in _ncaa._ROTATION_MESSAGE

    def test_hash_tables_are_wellformed(self):
        for table in (_ncaa.GAME_HASHES, _ncaa.PBP_HASHES, _ncaa.BOXSCORE_HASHES):
            for name, value in table.items():
                assert re.fullmatch(r"[a-f0-9]{64}", value), name


# ── schools ─────────────────────────────────────────────


class TestSchools:
    def test_query_filters(self, offline):
        out = _ncaa.fetch_schools("michigan")
        assert out["count"] >= 1
        assert all("michigan" in _ncaa.fold(s["name"]) or "michigan" in _ncaa.fold(s["slug"]) for s in out["schools"])


# ── TLS trust anchors ─────────────────────────────────────────────


class TestTlsContext:
    """NCAA hosts serve leaf-only chains, and some platform root bundles
    predate GlobalSign Root R46 — both certs ship here, verification stays on."""

    def test_context_builds(self):
        ctx = _ncaa._ssl_context()
        import ssl

        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert ctx.check_hostname is True

    def test_intermediate_chains_to_the_shipped_root(self):
        import ssl

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.load_verify_locations(cadata=_ncaa._GLOBALSIGN_ROOT_R46)
        # loading the intermediate alongside must not raise — and both parse
        ctx.load_verify_locations(cadata=_ncaa._GLOBALSIGN_INTERMEDIATE)
        assert len(ctx.get_ca_certs()) == 2

    def test_certs_are_the_documented_ones(self):
        import hashlib
        import ssl

        root_der = ssl.PEM_cert_to_DER_cert(_ncaa._GLOBALSIGN_ROOT_R46)
        assert hashlib.sha256(root_der).hexdigest() == (
            "4fa3126d8d3a11d1c4855a4f807cbad6cf919d3a5a88b03bea2c6372d93c40c9"
        )
        inter_der = ssl.PEM_cert_to_DER_cert(_ncaa._GLOBALSIGN_INTERMEDIATE)
        assert hashlib.sha256(inter_der).hexdigest() == (
            "d160e2de4e56cb10b66c1cb0adcb79cf93c78dcd9db30c2018220262c04063f9"
        )


# ── wrappers ─────────────────────────────────────────────


class TestWrappers:
    def test_cfb_scoreboard_pins_football(self, offline):
        from sports_skills import cfb

        out = cfb.get_ncaa_scoreboard(week=16, season=2025)
        assert out["status"] is True
        assert (out["data"] or {})["sport"] == "football"

    def test_cbb_scoreboard_pins_basketball(self, offline):
        from sports_skills import cbb

        out = cbb.get_ncaa_scoreboard(date="2026-03-20")
        assert out["status"] is True
        assert (out["data"] or {})["sport"] == "basketball-men"

    def test_cfb_rejects_basketball_divisions(self, offline):
        from sports_skills import cfb

        out = cfb.get_ncaa_scoreboard(week=16, division="d3")
        assert out["status"] is False
        assert "fbs, fcs" in out["message"]

    def test_errors_come_back_as_envelopes_not_raises(self, offline):
        from sports_skills import cbb

        out = cbb.get_ncaa_play_by_play(game_id="401628455")
        assert out["status"] is False
        assert "ESPN event id" in out["message"]


class TestEspnDefaultGrouping:
    """The ESPN-backed cbb scoreboard/schedule un-grouped default is Top-25
    games only (1 vs ~24 on an ordinary day) — the connector now defaults to
    group 50, all of Division I."""

    @staticmethod
    def _capture(monkeypatch):
        from sports_skills.cbb import _connector as cc

        calls = []

        def fake(sport_path, resource="scoreboard", params=None, max_retries=2):
            calls.append(params or {})
            return {"events": [], "season": {}, "day": {}, "leagues": []}

        monkeypatch.setattr(cc, "espn_request", fake)
        return cc, calls

    def test_scoreboard_defaults_to_full_d1(self, monkeypatch):
        cc, calls = self._capture(monkeypatch)
        cc.get_scoreboard({"params": {"date": "2025-02-28"}})
        assert calls[-1].get("groups") == 50

    def test_schedule_defaults_to_full_d1(self, monkeypatch):
        cc, calls = self._capture(monkeypatch)
        cc.get_schedule({"params": {"date": "2025-02-28"}})
        assert calls[-1].get("groups") == 50

    def test_explicit_group_still_wins(self, monkeypatch):
        cc, calls = self._capture(monkeypatch)
        cc.get_scoreboard({"params": {"date": "2025-02-28", "group": 100}})
        assert calls[-1].get("groups") == 100
