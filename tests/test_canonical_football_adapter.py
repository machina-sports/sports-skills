"""The native -> canonical reading for ``sports-skills/espn``.

The adapter's whole acceptance test is the checked-in observation: it must reproduce
those bytes from the checked-in native payload, using the vendored runtime and
nothing else. Everything below that is a rule the byte comparison would only catch
by accident on this one fixture, and would stop catching the day a second fixture
lands — the status map, the fail-closed behaviour, the placeholder drops, the
absence of a live call.

The adapter reads the shape ``_normalize_espn_event`` **returns**, not raw ESPN
transport JSON. Reading transport JSON here would put a second ESPN parser in the
package, and the two would disagree the first time either was fixed.
"""

import ast
import json
from pathlib import Path

import pytest

from sports_skills.canonical._vendored.observation import validate_observation
from sports_skills.canonical._vendored.vocab import EVENT_STATUS
from tests.test_canonical_reference_fixtures import (
    NATIVE_PATH,
    NATIVE_PLACEHOLDERS,
    OBSERVATION_PATH,
    canonical_bytes,
)

OBSERVED_AT = "2026-03-01T22:05:00+00:00"
START_TIME = "2026-03-01T20:00:00+00:00"

ADAPTER_PATH = (
    Path(__file__).resolve().parents[1]
    / "src/sports_skills/canonical/adapters/football.py"
)


def native():
    return json.loads(NATIVE_PATH.read_text(encoding="utf-8"))


def observation(event=None, **kwargs):
    from sports_skills.canonical.adapters import football

    kwargs.setdefault("observed_at", OBSERVED_AT)
    return football.to_observation(native() if event is None else event, **kwargs)


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------

def test_the_expected_observation_is_reproduced_byte_for_byte():
    """The cross-repository gate. If this fails, this repository and
    machina-templates disagree about one provider reading, and the diff says which
    field."""
    assert canonical_bytes(observation()) == OBSERVATION_PATH.read_text(encoding="utf-8")


def test_the_produced_observation_validates_clean():
    """Byte equality against a fixture proves agreement with that fixture. This
    proves the document is valid on its own terms, which is what a second fixture
    would still need."""
    assert validate_observation(observation()) == []


def test_the_provider_is_recorded_as_open_data_under_its_own_namespace():
    document = observation()["observation"]
    assert document["provider"] == {"namespace": "sports-skills/espn", "family": "open-data"}


def test_the_adapter_names_and_versions_itself():
    """An anonymous claim is unfixable: when a fact turns out to be wrong there has
    to be something naming the code that produced it."""
    adapter = observation()["observation"]["adapter"]
    assert adapter["name"] == "sports_skills.canonical.adapters.football"
    assert adapter["version"] == "1"


def test_the_source_ref_is_an_endpoint_class_and_not_a_request():
    refs = observation()["observation"]["adapter"]["source_refs"]
    assert [ref["kind"] for ref in refs] == ["endpoint-class"]
    for ref in refs:
        for marker in ("://", "?", "&", "key=", "token=", "secret", "Authorization"):
            assert marker not in ref["value"], marker


# ---------------------------------------------------------------------------
# Status: explicit, and closed against everything else
# ---------------------------------------------------------------------------

def test_every_status_the_normalizer_can_emit_is_mapped_explicitly():
    """Checked against the live ``ESPN_STATUS_MAP`` rather than a copy, so the day
    the normalizer gains a status this fails here instead of raising in front of a
    user. ``not_started`` is included because it is the normalizer's fallback."""
    from sports_skills.canonical.adapters import football
    from sports_skills.football._connector import ESPN_STATUS_MAP

    reachable = set(ESPN_STATUS_MAP.values()) | {"not_started"}
    assert reachable <= set(football.STATUS)


def test_every_mapped_status_is_a_key_the_pinned_vocabulary_admits():
    """A status the vocabulary has no NewsCode for would reach the graph as a value
    nothing can resolve, and layer 4 fails closed on it."""
    from sports_skills.canonical.adapters import football

    for native_status, canonical_status in sorted(football.STATUS.items()):
        assert canonical_status in EVENT_STATUS, (native_status, canonical_status)


def test_the_three_native_statuses_that_are_not_canonical_are_translated():
    """``live``, ``1st_half`` and ``2nd_half`` are this repository's own vocabulary
    and are absent from ``vocab.EVENT_STATUS``. Passing one through would put an
    unresolvable value on the graph."""
    from sports_skills.canonical.adapters import football

    for native_status in ("live", "1st_half", "2nd_half"):
        assert native_status not in EVENT_STATUS
        assert football.STATUS[native_status] == "in_progress"


def test_an_unknown_status_fails_closed():
    event = native()
    event["status"] = "STATUS_INVENTED_BY_ESPN_TOMORROW"
    with pytest.raises(ValueError) as excinfo:
        observation(event)
    assert "STATUS_INVENTED_BY_ESPN_TOMORROW" in str(excinfo.value)


def test_a_missing_status_fails_closed():
    event = native()
    del event["status"]
    with pytest.raises(ValueError):
        observation(event)


def test_an_empty_status_fails_closed_rather_than_defaulting():
    """Defaulting to ``not_started`` would place a finished match at the top of a
    consumer's upcoming-fixtures list, which is worse than refusing."""
    event = native()
    event["status"] = ""
    with pytest.raises(ValueError):
        observation(event)


# ---------------------------------------------------------------------------
# Omission over fabrication
# ---------------------------------------------------------------------------

def test_no_native_placeholder_reaches_any_section_but_raw():
    document = observation()["observation"]
    sections = {key: value for key, value in document.items() if key != "raw"}
    blob = json.dumps(sections)
    assert "null" not in blob
    assert '""' not in blob


def test_the_placeholder_fields_are_still_readable_in_raw():
    """The mirror. The absences above are not lost — they are where a reviewer can
    see exactly what the native payload said."""
    raw = observation()["observation"]["raw"]
    for key, value in sorted(NATIVE_PLACEHOLDERS.items()):
        assert raw[key] == value


def test_no_phase_is_derived_from_the_round_fields():
    """``round`` and ``matchday`` are empty, and ``round_name`` is a display string
    with no identifier the provider addresses by. Recording it as a provider
    identifier would invent provider-native evidence."""
    assert "phase" not in observation()["observation"]


def test_a_round_name_alone_still_produces_no_phase():
    """The normalizer fills ``round_name`` from ESPN's week text for competitions
    that have one, while ``round`` and ``matchday`` stay empty. A display label is
    not an identifier."""
    event = native()
    event["round_name"] = "Matchweek 27"
    document = observation(event)["observation"]
    assert "phase" not in document
    assert "Matchweek 27" not in json.dumps({k: v for k, v in document.items() if k != "raw"})


def test_an_empty_venue_drops_the_site_rather_than_naming_it_unknown():
    event = native()
    event["venue"] = {"id": "", "name": "", "city": "", "country": ""}
    document = observation(event)
    assert "site" not in document["observation"]
    assert validate_observation(document) == []


def test_a_venue_with_only_a_name_carries_only_the_name():
    event = native()
    event["venue"] = {"id": "", "name": "Synthetic Home Ground", "city": "", "country": ""}
    site = observation(event)["observation"]["site"]
    assert site == {"name": "Synthetic Home Ground"}


def test_an_absent_season_drops_the_season_rather_than_faking_one():
    event = native()
    event["season"] = {"id": "", "name": "", "year": ""}
    competition = observation(event)["observation"]["competition"]
    assert "season" not in competition


def test_a_missing_competition_identifier_fails_closed():
    """``competition.provider_id`` is required by the observation contract, so an
    adapter that omits it produces a document the serializer refuses. Raising here
    names the native field instead."""
    event = native()
    event["competition"] = {"id": "", "name": ""}
    with pytest.raises(ValueError):
        observation(event)


def test_no_odds_or_referee_fact_is_claimed():
    document = observation()["observation"]
    for key in ("odds", "referees"):
        assert key not in document


def test_no_outcome_is_derived_from_the_scoreline():
    """The native shape carries no winner flag. ``2-1`` plus ``closed`` makes a win
    obvious to a reader and is still an inference, and ``sport:eventOutcome`` is
    exactly the wrong place for one."""
    document = observation()["observation"]
    assert "outcome_type" not in document["event"]
    for participant in document["participants"]:
        assert "outcome" not in participant


def test_nothing_absent_from_the_payload_is_invented():
    document = observation()["observation"]
    for key in ("clock", "attendance", "end_time"):
        assert key not in document["event"]
    for key in ("actions", "memberships"):
        assert key not in document
    assert "type" not in document["competition"]
    for participant in document["participants"]:
        assert "statistics" not in participant


# ---------------------------------------------------------------------------
# Participants
# ---------------------------------------------------------------------------

def test_home_comes_first_and_both_teams_carry_alignment_and_a_string_score():
    """Ordering is part of the contract: the cross-provider equivalence test
    compares ``[home, away]`` positionally across providers."""
    participants = observation()["observation"]["participants"]
    assert [
        (p["kind"], p["provider_id"], p["name"], p["alignment"], p["score"])
        for p in participants
    ] == [
        ("team", "9011", "Synthetic Home United", "home", "2"),
        ("team", "9012", "Synthetic Away Town", "away", "1"),
    ]
    for participant in participants:
        assert isinstance(participant["score"], str)


def test_home_comes_first_even_when_the_native_order_is_reversed():
    """The native list happens to be home-first, so positional passthrough would
    pass the fixture. Alignment is read, not assumed from position."""
    event = native()
    event["competitors"] = list(reversed(event["competitors"]))
    participants = observation(event)["observation"]["participants"]
    assert [p["alignment"] for p in participants] == ["home", "away"]
    assert [p["provider_id"] for p in participants] == ["9011", "9012"]


def test_a_goalless_draw_keeps_both_zeroes_as_facts():
    """``0`` is a score, not an absence. A truthiness test here would silently drop
    every clean sheet in the package."""
    event = native()
    for competitor in event["competitors"]:
        competitor["score"] = 0
    event["scores"] = {"home": 0, "away": 0}
    participants = observation(event)["observation"]["participants"]
    assert [p["score"] for p in participants] == ["0", "0"]


def test_an_unplayed_match_carries_no_score_rather_than_a_zero():
    """``_parse_espn_score`` returns ``None`` for a match with no scoreline. A zero
    there would report a 0-0 draw for a fixture that has not kicked off."""
    event = native()
    event["status"] = "not_started"
    for competitor in event["competitors"]:
        competitor["score"] = None
    event["scores"] = {"home": None, "away": None}
    document = observation(event)
    for participant in document["observation"]["participants"]:
        assert "score" not in participant
    assert validate_observation(document) == []


def test_a_payload_with_no_identified_teams_fails_closed():
    event = native()
    for competitor in event["competitors"]:
        competitor["team"] = {"id": "", "name": "", "short_name": "", "abbreviation": ""}
    with pytest.raises(ValueError):
        observation(event)


# ---------------------------------------------------------------------------
# Rights
# ---------------------------------------------------------------------------

def test_the_rights_block_is_explicit_prototype_only_open_data():
    """This package is public and non-commercial and can never emit anything else,
    so the flags are constants rather than inputs. Stated explicitly because a
    consumer with no rights block picks its own licence default."""
    rights = observation()["observation"]["rights"]
    assert rights == {
        "data_class": "mapping-contract-synthetic-open-prototype",
        "prototype_only": True,
        "commercial_use": False,
    }


def test_the_rights_block_names_no_entitlement_it_does_not_have():
    rights = observation()["observation"]["rights"]
    for word in ("licensed", "redistributable", "commercial"):
        assert word not in rights["data_class"], word


def test_there_is_no_way_to_ask_the_adapter_for_a_better_rights_tier():
    """The refusal has to be un-upgradable at the seam, not merely absent from the
    happy path. An adapter with a rights argument is an adapter whose licence claim
    is set by its caller."""
    import inspect

    from sports_skills.canonical.adapters import football

    parameters = inspect.signature(football.to_observation).parameters
    assert sorted(parameters) == ["event", "observed_at"]
    assert parameters["observed_at"].kind is inspect.Parameter.KEYWORD_ONLY


# ---------------------------------------------------------------------------
# raw, determinism, and the absence of a live call
# ---------------------------------------------------------------------------

def test_raw_is_the_native_payload_unaltered():
    """``raw`` is the only place the native payload survives, and it survives whole:
    that is what makes "we omitted it" checkable rather than asserted."""
    assert observation()["observation"]["raw"] == native()


def test_the_adapter_does_not_mutate_the_event_it_was_given():
    """A caller's native payload is the value it is about to return to its own
    caller. An adapter that edits it in place corrupts the default output path."""
    event = native()
    before = json.dumps(event, sort_keys=True)
    to_observation_result = observation(event)
    assert json.dumps(event, sort_keys=True) == before
    assert to_observation_result["observation"]["raw"] == event


def test_raw_is_a_copy_so_editing_the_observation_cannot_reach_back():
    event = native()
    document = observation(event)
    document["observation"]["raw"]["status"] = "tampered"
    assert event["status"] == "closed"


def test_two_runs_produce_identical_bytes():
    assert canonical_bytes(observation()) == canonical_bytes(observation())


def test_the_adapter_reaches_for_no_clock_network_or_credential():
    """``observed_at`` is an input, which is what makes the checked-in bytes
    reproducible. A module that could read the clock, the network or the
    environment could not promise that."""
    tree = ast.parse(ADAPTER_PATH.read_text(encoding="utf-8"))
    forbidden = {
        "os", "time", "datetime", "socket", "http", "urllib", "requests",
        "feedparser", "random", "subprocess",
    }
    for node in ast.walk(tree):
        module = None
        if isinstance(node, ast.Import):
            module = node.names[0].name
        elif isinstance(node, ast.ImportFrom):
            module = node.module
        if module:
            assert module.split(".")[0] not in forbidden, module


def test_the_adapter_does_not_import_the_connector_it_mirrors():
    """Importing ``_connector`` for its status table would drag the whole ESPN
    transport layer, its cache and its third-party dependency into the canonical
    path. The table is restated here and a test cross-checks the two."""
    tree = ast.parse(ADAPTER_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        module = node.module if isinstance(node, ast.ImportFrom) else None
        if isinstance(node, ast.Import):
            module = node.names[0].name
        if module:
            assert "_connector" not in module, module


def test_the_adapter_parses_as_python_39():
    ast.parse(ADAPTER_PATH.read_text(encoding="utf-8"), feature_version=(3, 9))
