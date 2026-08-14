"""NBA Phase-1A native-to-canonical adapter contract."""

import copy
import inspect
import json
from pathlib import Path

import pytest

from sports_skills import canonical
from sports_skills.canonical._vendored.ids import surrogate_resolver
from sports_skills.canonical._vendored.observation import validate_observation
from sports_skills.canonical._vendored.serialize import (
    GraphUnavailable,
    sport_schema_graph,
)
from sports_skills.nba._connector import _normalize_event, _normalize_plays

FIXTURE = Path(__file__).parent / "fixtures/nba_summary_401859967.json"
OBSERVED_AT = "2026-06-14T03:30:00Z"


def native_inputs():
    summary = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return _normalize_event(summary["header"]), _normalize_plays(summary)


def observation(event=None, plays=None, *, start_time_precision="minute"):
    fixture_event, fixture_plays = native_inputs()
    return canonical.to_nba_observation(
        fixture_event if event is None else event,
        fixture_plays if plays is None else plays,
        observed_at=OBSERVED_AT,
        start_time_precision=start_time_precision,
    )


def envelope(event=None, plays=None, *, start_time_precision="minute"):
    fixture_event, fixture_plays = native_inputs()
    return canonical.canonicalize_nba_event(
        fixture_event if event is None else event,
        fixture_plays if plays is None else plays,
        observed_at=OBSERVED_AT,
        start_time_precision=start_time_precision,
    )


def exact_event(value="2026-06-14T00:30:00Z"):
    event, _plays = native_inputs()
    event["start_time"] = value
    return event


def keys_below(value):
    keys = set()
    if isinstance(value, dict):
        keys.update(value)
        for child in value.values():
            keys.update(keys_below(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(keys_below(child))
    return keys


def test_fixture_normalizers_round_trip_into_a_valid_bounded_observation():
    document = observation()
    body = document["observation"]

    assert validate_observation(document) == []
    assert document["schema_version"] == "canonical-observation/1.1"
    assert body["provider"] == {"namespace": "sports-skills/espn", "family": "open-data"}
    assert body["sport"] == {"medtop": "20000851", "key": "basketball"}
    assert body["competition"] == {
        "provider_id": "nba",
        "name": "NBA",
        "resolution_method": "declared",
    }
    assert body["event"]["provider_id"] == "401859967"
    assert body["event"]["status"] == "closed"
    assert [(team["alignment"], team["provider_id"], team["score"]) for team in body["participants"]] == [
        ("home", "24", "90"),
        ("away", "18", "94"),
    ]
    assert len(body["actions"]) == 536


def test_minute_precision_emits_verbatim_temporal_evidence_and_no_exact_start():
    event = observation()["observation"]["event"]
    evidence = event["temporal_evidence"]

    assert "start_time" not in event
    assert evidence == {
        "kind": "start",
        "source_value": "2026-06-14T00:30Z",
        "precision": "minute",
        "lower_inclusive": "2026-06-14T00:30:00Z",
        "upper_exclusive": "2026-06-14T00:31:00Z",
        "provenance": {
            "normalizer": "sports_skills.nba._connector._normalize_event",
            "adapter": "sports_skills.canonical.adapters.nba@1",
            "canonical_version": "0.2.0",
            "derivation": "declared_precision_interval",
        },
    }


@pytest.mark.parametrize(
    "precision,value",
    [
        ("second", "2026-06-14T00:30:00Z"),
        ("fractional_second", "2026-06-14T00:30:00.125+00:00"),
    ],
)
def test_exact_precision_preserves_the_source_value_without_temporal_evidence(precision, value):
    event = observation(exact_event(value), start_time_precision=precision)["observation"]["event"]
    assert event["start_time"] == value
    assert "temporal_evidence" not in event


def test_start_time_precision_is_a_required_keyword_argument():
    event, plays = native_inputs()
    parameters = inspect.signature(canonical.to_nba_observation).parameters
    assert parameters["start_time_precision"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["start_time_precision"].default is inspect.Parameter.empty
    with pytest.raises(TypeError):
        canonical.to_nba_observation(event, plays, observed_at=OBSERVED_AT)


@pytest.mark.parametrize(
    "precision,value",
    [
        ("minute", "2026-06-14T00:30:00Z"),
        ("second", "2026-06-14T00:30Z"),
        ("second", "2026-06-14T00:30:00.1Z"),
        ("fractional_second", "2026-06-14T00:30:00Z"),
        ("millisecond", "2026-06-14T00:30:00.125Z"),
    ],
)
def test_unknown_or_lexically_mismatched_precision_is_refused(precision, value):
    event, plays = native_inputs()
    event["start_time"] = value
    with pytest.raises(ValueError):
        observation(event, plays, start_time_precision=precision)


def test_missing_start_time_is_refused():
    event, plays = native_inputs()
    event.pop("start_time")
    with pytest.raises(ValueError):
        observation(event, plays, start_time_precision="minute")


def test_minute_bounds_are_exactly_sixty_seconds_and_capability_is_bounded():
    block = envelope()["machina_sports_schema"]
    capabilities = block["capabilities"]

    assert "sport_schema_graph" not in block
    assert "event.start_time.bounded" in capabilities["present"]
    assert "event.start_time" in capabilities["absent"]
    assert capabilities["graph_unavailable_reason"] == "exact-event-start-time-required"
    evidence = block["event_view"]["temporal_evidence"]
    assert evidence["lower_inclusive"] == "2026-06-14T00:30:00Z"
    assert evidence["upper_exclusive"] == "2026-06-14T00:31:00Z"


def test_reduced_precision_graph_refusal_is_typed_and_deterministic():
    document = observation()
    resolver = surrogate_resolver("sports-skills/espn")
    reasons = []
    for _ in range(2):
        with pytest.raises(GraphUnavailable) as excinfo:
            sport_schema_graph(document, id_resolver=resolver)
        reasons.append(excinfo.value.reason)
    assert reasons == ["exact-event-start-time-required"] * 2


def test_closed_explicit_winner_result_actions_and_team_links_reach_the_exact_graph():
    document = observation(exact_event(), start_time_precision="second")["observation"]
    participants = document["participants"]
    assert [(team["provider_id"], team["outcome"]) for team in participants] == [
        ("24", "loss"),
        ("18", "win"),
    ]

    block = envelope(exact_event(), start_time_precision="second")["machina_sports_schema"]
    assert "event.result" in block["capabilities"]["present"]
    assert "event.actions" in block["capabilities"]["present"]
    graph = block["sport_schema_graph"]["@graph"]
    team_participations = {node["@id"] for node in graph if node["@type"] == "sport:TeamParticipation"}
    actions = [node for node in graph if node["@type"] == "sport:Action"]
    assert len(actions) == 536
    linked = [node["sport:participation"]["@id"] for node in actions if "sport:participation" in node]
    assert linked
    assert set(linked) == team_participations


def test_winner_outcomes_require_closed_status_and_exactly_one_explicit_winner():
    event, plays = native_inputs()
    event["status"] = "live"
    assert all("outcome" not in team for team in observation(event, plays)["observation"]["participants"])

    event, plays = native_inputs()
    for competitor in event["competitors"]:
        competitor["winner"] = True
    assert all("outcome" not in team for team in observation(event, plays)["observation"]["participants"])


def test_coordinates_shots_players_career_completeness_odds_and_leaders_are_excluded():
    body = observation()["observation"]
    projected = {key: value for key, value in body.items() if key != "raw"}
    forbidden = {"coordinate", "coordinates", "shots", "players", "career", "completeness", "odds", "leaders"}
    assert keys_below(projected).isdisjoint(forbidden)
    assert "coordinate" in keys_below(body["raw"])


def test_only_valid_team_ids_are_linked_from_actions():
    event, plays = native_inputs()
    plays = copy.deepcopy(plays)
    plays["plays"][0]["team_id"] = "not-a-competitor"
    actions = observation(event, plays, start_time_precision="minute")["observation"]["actions"]
    assert "participant_provider_id" not in actions[0]
    assert any(action.get("participant_provider_id") in {"18", "24"} for action in actions[1:])


def test_rights_are_fixed_open_public_prototype_only_and_noncommercial():
    assert observation()["observation"]["rights"] == {
        "data_class": "open-public",
        "prototype_only": True,
        "commercial_use": False,
    }


def test_native_inputs_keep_byte_identity_and_raw_is_a_deep_copy():
    event, plays = native_inputs()
    event_before = json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode()
    plays_before = json.dumps(plays, separators=(",", ":"), ensure_ascii=False).encode()

    document = observation(event, plays)

    assert json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode() == event_before
    assert json.dumps(plays, separators=(",", ":"), ensure_ascii=False).encode() == plays_before
    assert document["observation"]["raw"] == {"event": event, "plays": plays}
    document["observation"]["raw"]["event"]["status"] = "tampered"
    document["observation"]["raw"]["plays"]["plays"][0]["text"] = "tampered"
    assert event["status"] == "closed"
    assert plays["plays"][0]["text"] != "tampered"


def test_public_nba_apis_are_additive_and_football_apis_are_preserved():
    assert canonical.to_observation
    assert canonical.canonicalize_event
    assert canonical.to_nba_observation
    assert canonical.canonicalize_nba_event
    assert {"to_nba_observation", "canonicalize_nba_event"} <= set(canonical.__all__)
