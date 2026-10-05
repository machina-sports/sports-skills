"""WTA API tennis commands: entry lists and player results, keyed by native WTA ids.

No network: every test fakes the HTTP layer. Ids, names, and tournaments are
synthetic; the payload shapes follow the public api.wtatennis.com responses.
"""

from __future__ import annotations

import json
import math

import pytest

from sports_skills import _espn_base, _replay, tennis
from sports_skills.tennis import _wta

PLAYER_ID = "900001"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.delenv(_replay.MODE_ENV, raising=False)
    monkeypatch.delenv(_replay.DIR_ENV, raising=False)
    monkeypatch.setattr(_espn_base, "_cache", {})


class FakeFetch:
    """Stands in for ``_wta._http_fetch``; records every URL requested."""

    def __init__(self, body=None, err=None):
        self.body = body
        self.err = err
        self.urls = []

    def __call__(self, url, **kwargs):
        self.urls.append(url)
        if self.err is not None:
            return None, self.err
        raw = self.body if isinstance(self.body, bytes) else json.dumps(self.body).encode()
        return raw, None


@pytest.fixture
def fetch(monkeypatch):
    def install(body=None, err=None):
        fake = FakeFetch(body, err)
        monkeypatch.setattr(_wta, "_http_fetch", fake)
        return fake

    return install


# ============================================================
# Synthetic payloads
# ============================================================


def person(pid, name, country="SYN"):
    first, _, last = name.partition(" ")
    return {
        "id": pid,
        "firstName": first,
        "lastName": last,
        "fullName": name,
        "countryCode": country,
        "dateOfBirth": None,
        "metadata": None,
    }


def entry(players, seed="", entry_type="", eliminated=False, winner=False, runner_up=False):
    return {
        "players": players,
        "seed": seed,
        "eliminated": eliminated,
        "entryType": entry_type,
        "winner": winner,
        "runnerUp": runner_up,
    }


def entries_payload():
    return {
        "events": [
            {
                "description": "null",
                "eventTypeCode": "LS",
                "eventPlayers": [
                    entry([person(900001, "Synthetic Alpha")], seed="1", runner_up=True),
                    entry([person(900002, "Synthetic Beta", "")], entry_type="Q", eliminated=True),
                ],
            },
            {
                "description": "null",
                "eventTypeCode": "LD",
                "eventPlayers": [
                    entry([person(900003, "Synthetic Gamma"), person(900004, "Synthetic Delta")], seed="1", winner=True),
                ],
            },
        ]
    }


def match(
    start,
    round_name="R32",
    *,
    tournament_id=8001,
    year=None,
    doubles=False,
    winner=1,
    scores="6-1  6-2",
    player_1=PLAYER_ID,
    qpm="M",
):
    year = year if year is not None else int(start[:4])
    return {
        "StartDate": f"{start}T00:00:00+00:00",
        "Surface": "HARD",
        "TournamentLevel": "SYN",
        "TournamentName": f"SYNTHETIC OPEN {tournament_id}",
        "Country": "SYNTHLAND",
        "entry_type_1": None,
        "entry_type_2": "Q",
        "opponent": person(910001, "Synthetic Opponent"),
        "opponent_partner": person(910002, "Synthetic Opponent Partner") if doubles else None,
        "partner": person(920001, "Synthetic Partner") if doubles else None,
        "player_1": player_1,
        "player_2": "910001",
        "qpm_flag": qpm,
        "reason_code": "W",
        "round_name": round_name,
        "s_d_flag": "D" if doubles else "S",
        "scores": scores,
        "seed_1": 3,
        "seed_2": None,
        "tourn_nbr": f" {tournament_id}",
        "tourn_round": "1",
        "tourn_year": str(year),
        "tournament": {
            "tournamentGroup": {"id": tournament_id, "name": f"SYNTHETIC OPEN {tournament_id}", "level": "SYN"},
            "year": year,
            "title": f"Synthetic Open {tournament_id}",
            "startDate": start,
            "endDate": start,
            "surface": "Hard",
            "inOutdoor": "O",
            "city": "",
            "country": "SYNTHLAND",
        },
        "winner": winner,
    }


def results_payload(matches):
    return {"matches": matches, "player": person(int(PLAYER_ID), "Synthetic Alpha")}


def results_url(query):
    return f"https://api.wtatennis.com/tennis/players/{PLAYER_ID}/matches?{query}"


def entry_list(**params):
    return _wta.get_wta_entry_list({"params": {"tournament_id": "8001", "year": 2025, **params}})


def results(**params):
    return _wta.get_wta_player_results({"params": {"player_id": PLAYER_ID, **params}})


# ============================================================
# Input validation — rejected before any request is made
# ============================================================


BAD_IDS = [
    "../8001",
    "8001/../../players",
    "8001?x=1",
    "8001#",
    " 8001",
    "abc",
    "-1",
    "0",
    "000",
    "08001",  # leading zero: rejected, not rewritten to "8001"
    "0001",
    "１２３",  # full-width digits
    "12345678901",
    0,
    -5,
    True,
    8001.0,
    [8001],
]


@pytest.mark.parametrize("bad", BAD_IDS)
def test_invalid_tournament_id_is_rejected_without_a_request(fetch, bad):
    fake = fetch(entries_payload())
    out = entry_list(tournament_id=bad)
    assert out["error"] is True and "tournament_id" in out["message"]
    assert fake.urls == []


@pytest.mark.parametrize("bad", BAD_IDS)
def test_invalid_player_id_is_rejected_without_a_request(fetch, bad):
    fake = fetch(results_payload([]))
    out = results(player_id=bad)
    assert out["error"] is True and "player_id" in out["message"]
    assert fake.urls == []


@pytest.mark.parametrize("missing", [None, ""])
def test_missing_ids_say_which_id_system(fetch, missing):
    fetch(entries_payload())
    assert "not an ESPN id" in entry_list(tournament_id=missing)["message"]
    assert "not an ESPN id" in results(player_id=missing)["message"]


def test_numeric_ids_are_accepted_as_int_or_digit_string(fetch):
    fake = fetch(entries_payload())
    assert "error" not in entry_list(tournament_id=8001)
    assert "error" not in entry_list(tournament_id="8001", year="2024")
    assert fake.urls == [
        "https://api.wtatennis.com/tennis/tournaments/8001/2025/players",
        "https://api.wtatennis.com/tennis/tournaments/8001/2024/players",
    ]


@pytest.mark.parametrize("bad", ["abc", 1900, 3000, 2025.5, True, math.nan, math.inf, "20 25", [2025]])
def test_invalid_year_is_rejected(fetch, bad):
    fake = fetch(entries_payload())
    assert "Invalid year" in entry_list(year=bad)["message"]
    assert "Invalid year" in results(year=bad)["message"]
    assert fake.urls == []


def test_entry_list_requires_year(fetch):
    fake = fetch(entries_payload())
    out = _wta.get_wta_entry_list({"params": {"tournament_id": "8001"}})
    assert out == {"error": True, "message": "year is required (e.g. 2025)."}
    assert fake.urls == []


@pytest.mark.parametrize("bad", [0, -1, 201, 10**9, 1.5, math.nan, math.inf, -math.inf, "x", True, [5]])
def test_invalid_limit_is_rejected(fetch, bad):
    fake = fetch(results_payload([]))
    out = results(limit=bad)
    assert out["error"] is True and "Invalid limit" in out["message"]
    assert fake.urls == []


# ============================================================
# Entry list
# ============================================================


def test_entry_list_normalizes_singles_and_doubles(fetch):
    fetch(entries_payload())
    out = entry_list()
    assert out["tournament_id"] == "8001" and out["year"] == 2025
    assert out["count"] == 2 and out["entry_count"] == 3
    singles, doubles = out["events"]

    assert singles["event_type_code"] == "LS" and singles["format"] == "singles"
    assert singles["description"] is None
    assert singles["entries"][0] == {
        "players": [{"id": "900001", "name": "Synthetic Alpha", "country_code": "SYN"}],
        "seed": 1,
        "entry_type": None,
        "eliminated": False,
        "winner": False,
        "runner_up": True,
    }
    unseeded = singles["entries"][1]
    assert unseeded["seed"] is None and unseeded["entry_type"] == "Q" and unseeded["eliminated"] is True
    assert unseeded["players"][0]["country_code"] is None

    assert doubles["event_type_code"] == "LD" and doubles["format"] == "doubles"
    (team,) = doubles["entries"]
    assert [p["id"] for p in team["players"]] == ["900003", "900004"]
    assert team["winner"] is True and team["seed"] == 1

    assert out["source"]["provider"] == "WTA (api.wtatennis.com)"
    assert out["source"]["url"] == "https://api.wtatennis.com/tennis/tournaments/8001/2025/players"
    assert out["source"]["fetched_at"].endswith("Z")
    assert "not a final draw" in out["note"]
    assert "warnings" not in out


def test_entry_list_empty_events_is_flagged_not_silent(fetch):
    fetch({"events": []})
    out = entry_list()
    assert "error" not in out
    assert out["events"] == [] and out["count"] == 0 and out["entry_count"] == 0
    assert "may not be published" in out["note"]


def test_entry_list_skips_malformed_nested_rows_and_says_so(fetch):
    payload = entries_payload()
    payload["events"].append("not an event")
    payload["events"][0]["eventPlayers"].append({"players": [{"id": "../x", "fullName": "Bad"}]})
    payload["events"][0]["eventPlayers"].append({"players": []})
    fetch(payload)
    out = entry_list()
    assert out["count"] == 2 and out["entry_count"] == 3
    assert out["skipped_rows"] == 3
    assert out["warnings"] == ["Skipped 3 malformed entry-list row(s) from the WTA API."]


def test_entry_list_with_only_malformed_rows_is_an_error(fetch):
    fetch({"events": [{"eventTypeCode": "LS", "eventPlayers": [{"players": None}, 7]}, None]})
    out = entry_list()
    assert out["error"] is True and "format may have changed" in out["message"]


def test_mixed_team_sizes_leave_format_unset(fetch):
    fetch({
        "events": [{
            "eventTypeCode": "XX",
            "eventPlayers": [
                entry([person(900001, "Synthetic Alpha")]),
                entry([person(900002, "Synthetic Beta"), person(900003, "Synthetic Gamma")]),
            ],
        }]
    })
    assert entry_list()["events"][0]["format"] is None


# ============================================================
# Provider failures and schema drift
# ============================================================


@pytest.mark.parametrize("body", [b"<html>not json</html>", b"\xff\xfe\x00", b""])
def test_malformed_json_is_an_error(fetch, body):
    fetch(body)
    assert "invalid JSON" in entry_list()["message"]
    assert "invalid JSON" in results()["message"]


@pytest.mark.parametrize("payload", [None, [], "events", {}, {"events": None}, {"events": {}}, {"matches": "x"}])
def test_unexpected_top_level_shape_is_an_error(fetch, payload):
    fetch(payload)
    for out in (entry_list(), results()):
        assert out["error"] is True and "unexpected response shape" in out["message"]


def test_http_failure_is_a_structured_error(fetch):
    fetch(err={"error": True, "status_code": 404, "message": "HTTP 404 from api.wtatennis.com"})
    out = entry_list()
    assert out["error"] is True and out["status_code"] == 404
    assert "HTTP 404" in out["message"] and "tournaments/8001/2025/players" in out["message"]


def test_failures_are_not_cached(fetch):
    fake = fetch(err={"error": True, "message": "timed out"})
    entry_list()
    entry_list()
    assert len(fake.urls) == 2


def test_unexpected_exception_becomes_an_error(monkeypatch):
    def boom(url, **kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(_wta, "_http_fetch", boom)
    out = results()
    assert out == {"error": True, "message": "WTA backend error (RuntimeError): synthetic failure"}


def test_wrapper_returns_standard_envelope(fetch):
    fetch(entries_payload())
    ok = tennis.get_wta_entry_list(tournament_id="8001", year=2025)
    assert ok["status"] is True and ok["data"]["entry_count"] == 3
    bad = tennis.get_wta_player_results(player_id="../1")
    assert bad["status"] is False and "player_id" in bad["message"]


# ============================================================
# Player results
# ============================================================


def test_results_normalize_singles_and_doubles(fetch):
    fetch(results_payload([
        match("2024-03-04", "R16", doubles=True, winner=2, scores="6-1  6-1"),
        match("2024-03-04", "QF", winner=1, scores=" 7-6(5)  6-4 "),
    ]))
    out = results()
    assert out["player"] == {"id": PLAYER_ID, "name": "Synthetic Alpha", "country_code": "SYN"}
    doubles, singles = out["matches"]

    assert doubles["format"] == "doubles" and doubles["match_type_code"] == "D"
    assert doubles["partner"] == {"id": "920001", "name": "Synthetic Partner", "country_code": "SYN"}
    assert [p["id"] for p in doubles["opponents"]] == ["910001", "910002"]
    assert doubles["winner_code"] == 2
    assert doubles["score"] == "6-1 6-1"

    assert singles["format"] == "singles" and singles["partner"] is None
    assert [p["id"] for p in singles["opponents"]] == ["910001"]
    assert singles["winner_code"] == 1
    assert singles["score"] == "7-6(5) 6-4"
    assert singles["round"] == "QF" and singles["draw_code"] == "M"
    assert singles["player_seed"] == 3 and singles["opponent_seed"] is None
    assert singles["opponent_entry_type"] == "Q" and singles["reason_code"] == "W"
    assert singles["tournament_start_date"] == "2024-03-04"
    assert singles["tournament"] == {
        "id": "8001",
        "name": "SYNTHETIC OPEN 8001",
        "title": "Synthetic Open 8001",
        "level": "SYN",
        "year": 2024,
        "end_date": "2024-03-04",
        "surface": "Hard",
        "in_outdoor": "O",
        "city": None,
        "country": "SYNTHLAND",
    }


def test_results_never_label_a_tournament_date_as_a_match_date(fetch):
    fetch(results_payload([match("2024-03-04")]))
    out = results()
    (row,) = out["matches"]
    assert not {"date", "played_at", "match_date"} & set(row)
    assert "not the date a match was played" in out["note"]
    assert "not guaranteed" in out["ordering"]


def test_winner_code_stays_raw_and_no_result_is_derived(fetch):
    fetch(results_payload([
        match("2024-03-07", winner=1, player_1="999999"),
        match("2024-03-06", winner=0),
        match("2024-03-05", winner=None),
        match("2024-03-04", winner="2"),
        match("2024-03-03", winner=True),
    ]))
    rows = results()["matches"]
    assert [m["winner_code"] for m in rows] == [1, 0, None, "2", None]
    assert not any("player_won" in m for m in rows)


def test_unknown_codes_stay_raw(fetch):
    row = match("2024-03-04", qpm="P")
    row["s_d_flag"] = "X"
    fetch(results_payload([row]))
    (out,) = results()["matches"]
    assert out["draw_code"] == "P" and out["match_type_code"] == "X"
    assert not {"draw", "match_type"} & set(out)
    assert out["format"] == "singles"


def test_format_comes_from_participant_count_not_codes(fetch):
    coded_doubles = match("2024-03-06")
    coded_doubles["s_d_flag"] = "D"
    lopsided = match("2024-03-05", doubles=True)
    lopsided["opponent_partner"] = None
    no_opponent = match("2024-03-04")
    no_opponent["opponent"] = None
    fetch(results_payload([coded_doubles, lopsided, no_opponent]))
    assert [m["format"] for m in results()["matches"]] == ["singles", None, None]


def test_results_request_the_newest_page_with_a_sentinel_row(fetch):
    fake = fetch(results_payload([]))
    results()
    results(limit=5)
    results(year=2025, limit=3)
    assert fake.urls == [
        results_url("page=0&pageSize=21&sort=desc"),
        results_url("page=0&pageSize=6&sort=desc"),
        results_url("year=2025&page=0&pageSize=4&sort=desc"),
    ]


def test_results_source_url_is_the_bounded_query(fetch):
    fetch(results_payload([match("2025-11-01", year=2025)]))
    out = results(year=2025, limit=3)
    assert out["source"]["url"] == results_url("year=2025&page=0&pageSize=4&sort=desc")


def test_results_keep_provider_order_without_resorting(fetch):
    # Deliberately not date-sorted: the connector must not reorder what the provider sent.
    fetch(results_payload([
        match("2023-05-01", "R16", tournament_id=8002),
        match("2024-08-26", "Q1", tournament_id=8003, qpm="Q"),
        match("2023-05-01", "R32", tournament_id=8002),
        match("2022-01-03", "R32", tournament_id=8001),
    ]))
    out = results()
    assert [(m["tournament_start_date"], m["round"]) for m in out["matches"]] == [
        ("2023-05-01", "R16"),
        ("2024-08-26", "Q1"),
        ("2023-05-01", "R32"),
        ("2022-01-03", "R32"),
    ]


def test_sentinel_row_sets_has_more_and_is_not_returned(fetch):
    rows = [match(f"2024-0{m}-01", tournament_id=8000 + m) for m in (4, 3, 2, 1)]
    fetch(results_payload(rows))
    out = results(limit=3)
    assert out["count"] == 3 and out["has_more"] is True and out["history_complete"] is False
    assert [m["tournament"]["id"] for m in out["matches"]] == ["8004", "8003", "8002"]


@pytest.mark.parametrize("sent", [3, 2, 0])
def test_no_sentinel_row_means_no_more(fetch, sent):
    fetch(results_payload([match(f"2024-0{m}-01") for m in range(1, sent + 1)]))
    out = results(limit=3)
    assert out["count"] == sent and out["has_more"] is False and out["history_complete"] is False


def test_provider_ignoring_page_size_is_still_bounded(fetch):
    fetch(results_payload([match(f"2024-01-{d:02d}") for d in range(10, 0, -1)]))
    out = results(limit=2)
    assert out["count"] == 2 and out["has_more"] is True
    assert [m["tournament_start_date"] for m in out["matches"]] == ["2024-01-10", "2024-01-09"]


def test_results_claim_no_total_count(fetch):
    fetch(results_payload([match("2024-01-01")]))
    out = results()
    assert not {"total", "total_matching", "truncated"} & set(out)
    assert "not the full career history" in out["note"] and "no total count" in out["note"]


def test_requested_year_rows_are_returned(fetch):
    # A season-opening event can start in late December of the previous calendar year.
    fetch(results_payload([match("2025-11-01", "F", year=2025), match("2024-12-29", year=2025)]))
    out = results(year=2025)
    assert out["year"] == 2025
    assert [m["tournament_start_date"] for m in out["matches"]] == ["2025-11-01", "2024-12-29"]


def test_provider_ignoring_year_is_inconclusive_not_a_result(fetch):
    fetch(results_payload([match("2026-08-30"), match("2025-11-01")]))
    out = results(year=2025)
    assert out["error"] is True
    assert "outside year 2025" in out["message"] and "inconclusive" in out["message"]
    assert "year=2025" in out["message"]


def test_year_with_no_matches_is_an_honest_zero(fetch):
    fake = fetch(results_payload([]))
    out = results(year=2020)
    assert "error" not in out
    assert out["matches"] == [] and out["count"] == 0 and out["has_more"] is False
    assert fake.urls == [results_url("year=2020&page=0&pageSize=21&sort=desc")]


def test_default_limit_is_twenty(fetch):
    fake = fetch(results_payload([match(f"2020-01-{d:02d}") for d in range(25, 4, -1)]))
    out = results()
    assert fake.urls == [results_url("page=0&pageSize=21&sort=desc")]
    assert out["limit"] == 20 and out["count"] == 20 and out["has_more"] is True
    assert out["matches"][0]["tournament_start_date"] == "2020-01-25"


def test_limit_accepts_whole_numbers_in_any_form(fetch):
    fake = fetch(results_payload([match(f"2020-01-{d:02d}") for d in range(5, 0, -1)]))
    assert results(limit="3")["count"] == 3
    assert results(limit=2.0)["count"] == 2
    out = results(limit=200)
    assert out["count"] == 5 and out["has_more"] is False
    assert [u.split("?")[1] for u in fake.urls] == [
        "page=0&pageSize=4&sort=desc",
        "page=0&pageSize=3&sort=desc",
        "page=0&pageSize=201&sort=desc",
    ]


def test_empty_history_is_success_with_zero(fetch):
    fetch({"matches": []})
    out = results()
    assert out["matches"] == [] and out["count"] == 0 and out["has_more"] is False
    assert out["player"] == {"id": PLAYER_ID, "name": None, "country_code": None}


def test_results_skip_malformed_rows_and_say_so(fetch):
    undated = match("2024-03-04")
    undated["tournament"]["startDate"] = "soon"
    undated["StartDate"] = None
    fetch(results_payload([match("2024-03-04"), undated, "junk", None]))
    out = results()
    assert out["count"] == 1 and out["skipped_rows"] == 3
    assert out["warnings"] == ["Skipped 3 malformed match row(s) from the WTA API."]


def test_malformed_sentinel_row_only_signals_has_more(fetch):
    fetch(results_payload([match("2024-03-04"), "junk"]))
    out = results(limit=1)
    assert out["count"] == 1 and out["has_more"] is True
    assert "skipped_rows" not in out and "warnings" not in out


def test_partial_row_keeps_unknown_fields_null(fetch):
    row = match("2024-03-04")
    for key in ("opponent", "scores", "winner", "round_name", "seed_1", "s_d_flag", "qpm_flag"):
        row[key] = None
    fetch(results_payload([row]))
    (out,) = results()["matches"]
    assert out["opponents"] == [] and out["format"] is None
    assert out["score"] is None and out["winner_code"] is None and out["round"] is None
    assert out["player_seed"] is None and out["match_type_code"] is None and out["draw_code"] is None


def test_results_with_only_malformed_rows_is_an_error(fetch):
    fetch({"matches": [1, "x", {"tournament": "nope"}]})
    out = results()
    assert out["error"] is True and "format may have changed" in out["message"]


def test_results_fall_back_to_flat_fields(fetch):
    row = match("2024-03-04")
    del row["tournament"]
    fetch(results_payload([row]))
    (out,) = results()["matches"]
    assert out["tournament_start_date"] == "2024-03-04"
    assert out["tournament"]["id"] == "8001" and out["tournament"]["name"] == "SYNTHETIC OPEN 8001"
    assert out["tournament"]["year"] == 2024 and out["tournament"]["surface"] == "HARD"


# ============================================================
# Cache and record/replay
# ============================================================


def test_responses_are_cached_per_query(fetch):
    fake = fetch(results_payload([match("2024-01-01"), match("2023-01-01")]))
    first = results()
    second = results()
    assert len(fake.urls) == 1
    assert first["source"]["fetched_at"] == second["source"]["fetched_at"]
    results(limit=1)
    assert len(fake.urls) == 2


def test_cache_is_keyed_per_tournament_and_year(fetch):
    fake = fetch(entries_payload())
    entry_list()
    entry_list()
    entry_list(year=2024)
    assert len(fake.urls) == 2


def test_cache_ttl_is_ten_minutes(fetch, monkeypatch):
    ttls = []
    real_set = _wta._cache_set
    monkeypatch.setattr(_wta, "_cache_set", lambda key, value, ttl: (ttls.append(ttl), real_set(key, value, ttl)))
    fetch(entries_payload())
    entry_list()
    assert ttls == [600]


@pytest.mark.parametrize("mode", ["replay", "record", "fill"])
def test_record_and_replay_bypass_the_cache(fetch, monkeypatch, tmp_path, mode):
    monkeypatch.setenv(_replay.MODE_ENV, mode)
    monkeypatch.setenv(_replay.DIR_ENV, str(tmp_path))
    fake = fetch(entries_payload())
    entry_list()
    entry_list()
    assert len(fake.urls) == 2
    assert _espn_base._cache == {}


def test_record_then_replay_round_trip_without_network(monkeypatch, tmp_path):
    live_calls = []

    def live(url, **kwargs):
        live_calls.append(url)
        return json.dumps(results_payload([match("2024-03-04")])).encode(), None

    monkeypatch.setattr(_espn_base, "_live_http_fetch", live)
    monkeypatch.setenv(_replay.DIR_ENV, str(tmp_path))
    monkeypatch.setenv(_replay.MODE_ENV, "record")
    recorded = results()
    assert len(live_calls) == 1 and len(list(tmp_path.rglob("*.json"))) == 1
    assert recorded["source"]["replay_mode"] == "record" and recorded["source"]["fetched_at"].endswith("Z")

    def no_network(url, **kwargs):
        raise AssertionError("replay must not reach the network")

    monkeypatch.setattr(_espn_base, "_live_http_fetch", no_network)
    monkeypatch.setenv(_replay.MODE_ENV, "replay")
    replayed = results()
    assert replayed["matches"] == recorded["matches"]
    # A replayed response does not carry the recorded fetch time as if it were live.
    assert replayed["source"]["replay_mode"] == "replay"
    assert replayed["source"]["fetched_at"] is None and replayed["source"]["served_at"].endswith("Z")

    miss = _wta.get_wta_player_results({"params": {"player_id": "900099"}})
    assert miss["error"] is True and miss["replay_miss"] is True
    assert tennis.get_wta_player_results(player_id="900099")["replay_miss"] is True


def _wrapper_sources(fetch):
    fetch(entries_payload())
    entries = tennis.get_wta_entry_list(tournament_id="8001", year=2025)
    fetch(results_payload([match("2024-03-04")]))
    player = tennis.get_wta_player_results(player_id=PLAYER_ID)
    assert entries["status"] is True and player["status"] is True
    return entries["data"]["source"], player["data"]["source"]


@pytest.mark.parametrize("mode", ["off", "record"])
def test_live_modes_report_fetched_at(fetch, monkeypatch, tmp_path, mode):
    monkeypatch.setenv(_replay.MODE_ENV, mode)
    monkeypatch.setenv(_replay.DIR_ENV, str(tmp_path))
    for source in _wrapper_sources(fetch):
        assert source["replay_mode"] == mode
        assert source["fetched_at"].endswith("Z") and source["served_at"].endswith("Z")
        assert "Neither says when the WTA last updated the data" in source["note"]


@pytest.mark.parametrize("mode", ["replay", "fill"])
def test_replay_and_fill_report_served_at_not_fetched_at(fetch, monkeypatch, tmp_path, mode):
    monkeypatch.setenv(_replay.MODE_ENV, mode)
    monkeypatch.setenv(_replay.DIR_ENV, str(tmp_path))
    for source in _wrapper_sources(fetch):
        assert source["replay_mode"] == mode
        assert source["fetched_at"] is None and source["served_at"].endswith("Z")
        assert f"SPORTS_SKILLS_REPLAY={mode}" in source["note"]
        assert "not the freshness of the data or of any event" in source["note"]


# ============================================================
# CLI registry and schema
# ============================================================


def test_cli_registry_exposes_wta_commands():
    from sports_skills.cli import _REGISTRY, _load_module

    cmds = _REGISTRY["tennis"]
    assert cmds["get_wta_entry_list"] == {"required": ["tournament_id", "year"]}
    assert cmds["get_wta_player_results"] == {"required": ["player_id"], "optional": ["year", "limit"]}
    # The ESPN-backed commands are unchanged.
    assert {"get_scoreboard", "get_calendar", "get_rankings", "get_player_info", "get_news"} <= set(cmds)
    module = _load_module("tennis")
    assert callable(module.get_wta_entry_list) and callable(module.get_wta_player_results)


def test_cli_schema_documents_wta_params():
    from sports_skills.cli import _generate_schema

    tools = {t["command"]: t for t in _generate_schema("tennis")["tools"]}
    entries = tools["get_wta_entry_list"]["parameters"]
    assert entries["required"] == ["tournament_id", "year"]
    assert entries["properties"]["tournament_id"]["type"] == "string"
    assert entries["properties"]["year"]["type"] == "integer"
    assert "ESPN" in entries["properties"]["tournament_id"]["description"]

    res = tools["get_wta_player_results"]["parameters"]
    assert res["required"] == ["player_id"]
    assert res["properties"]["limit"]["type"] == "integer"
    assert all(p.get("description") for p in res["properties"].values())


def test_cli_parses_wta_args():
    from sports_skills.cli import _parse_cli_kwargs

    assert _parse_cli_kwargs(["--player_id=900001", "--year=2024", "--limit", "5"]) == {
        "player_id": "900001",
        "year": 2024,
        "limit": 5,
    }
