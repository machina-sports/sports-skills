"""Tests for the prospects (MPI) module — embedded data, no network."""

from sports_skills import prospects
from sports_skills.prospects._cohort_2015 import PLAYERS


def test_list_cohorts():
    res = prospects.list_cohorts()
    assert res["status"] is True
    cohorts = res["data"]["cohorts"]
    assert any(c["cohort_id"] == "fifa-u17-wc-2015" for c in cohorts)
    assert cohorts[0]["player_count"] == len(PLAYERS)


def test_methodology_has_formula_and_calibration():
    res = prospects.get_methodology()
    assert res["status"] is True
    assert res["data"]["formula"] == "MPI = 7500 + FACT + PROJECTION"
    cal = res["data"]["projection_component"]["calibration"]
    assert cal["baseline"]["p_reach"] == 0.11
    assert cal["scored_not_market_aware"]["p_reach"] == 0.25


def test_cohort_index_ranked_and_filterable():
    res = prospects.get_cohort_index(limit=10)
    assert res["status"] is True
    players = res["data"]["players"]
    assert len(players) == 10
    scores = [p["mpi"] for p in players]
    assert scores == sorted(scores, reverse=True)
    assert res["data"]["basket_mpi"] and res["data"]["basket_mpi"] > 7500

    fw = prospects.get_cohort_index(position="FW", limit=5)
    assert all(p["position"] == "FW" for p in fw["data"]["players"])


def test_score_arithmetic_holds_for_every_player():
    for p in PLAYERS:
        assert p["mpi"] == 7500 + p["fact_points"] + p["projection_points"]
        assert p["projection_points"] == round(p["p_reach"] * 2000)


def test_player_lookup_accent_insensitive_and_decomposed():
    res = prospects.get_player_index(query="christian pulisic")
    assert res["status"] is True
    player = res["data"]["player"]
    assert player["name"] == "Christian Pulisic"
    dec = player["decomposition"]
    assert dec["base"] + dec["fact_points"] + dec["projection_points"] == player["mpi"]


def test_graceful_errors():
    assert prospects.get_cohort_index(cohort_id="nope")["status"] is False
    assert prospects.get_player_index(query="")["status"] is False
    assert prospects.get_player_index(query="zz-no-such-player")["status"] is False
