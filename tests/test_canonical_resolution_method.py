"""``resolution_method`` is the observation's statement, not the serializer's constant.

The crosswalk publishes, for every provider identifier, how that identifier came to be
attached to a Machina identity. RFC 002 §5 defines exactly three answers:
``provider-native`` (the provider stated it), ``ordinal-derived`` (no stable provider
identifier exists and the value is positional) and ``declared`` (the caller supplied
it). The serializer used to write the first one onto every entry unconditionally,
which made the field decoration — and made it a false claim for any adapter whose
payload does not carry the entity at all.

This repository owns one adapter, and every identifier it reads is genuinely
provider-native, so its own envelope does not move. What these tests pin is that the
vendored runtime it ships can still tell the truth for a caller who states otherwise —
because a consumer reading ``provider_ids`` off a sports-skills envelope is reading a
field whose meaning is defined by this behaviour, not by ESPN.

The rule lives upstream in the vendored runtime and is re-vendored, never edited here.
"""

import copy
import json

import pytest

from sports_skills import canonical
from sports_skills.canonical._vendored.observation import (
    RESOLUTION_DEFAULT,
    RESOLUTION_METHODS,
    validate_observation,
)
from tests.test_canonical_reference_fixtures import NATIVE_PATH

OBSERVED_AT = "2026-03-01T22:05:00+00:00"

#: Every identity-bearing section, as (path into the observation, crosswalk entity
#: type). Written out rather than derived from the crosswalk: deriving it from the
#: thing under test would let a section that stopped being read agree with itself.
IDENTITY_SECTIONS = (
    (("competition",), "competition"),
    (("competition", "season"), "season"),
    (("site",), "site"),
    (("event",), "event"),
    (("participants", 0), "team"),
    (("participants", 1), "team"),
)


def native():
    return json.loads(NATIVE_PATH.read_text(encoding="utf-8"))


def observation():
    return canonical.to_observation(native(), observed_at=OBSERVED_AT)


def stating(path, method):
    """The reference observation, with one section stating ``method``."""
    document = observation()
    node = document["observation"]
    for key in path:
        node = node[key]
    node["resolution_method"] = method
    return document


def crosswalk(document):
    block = canonical.to_envelope(document)["machina_sports_schema"]
    return block["provider_ids"], block["sport_schema_graph"]


def methods_by_entity_type(entries):
    return {entry["entity_type"]: entry["resolution_method"] for entry in entries}


def graph_methods(graph):
    return {
        node["machina:providerId"]: node["machina:resolutionMethod"]
        for node in graph["@graph"]
        if "machina:resolutionMethod" in node
    }


def test_the_three_rfc_002_methods_are_the_whole_set():
    assert RESOLUTION_METHODS == ("provider-native", "ordinal-derived", "declared")
    assert RESOLUTION_DEFAULT == "provider-native"


def test_an_observation_that_states_nothing_is_provider_native_everywhere():
    """The default, and the reason this repository's own envelope does not move: an
    adapter that read a provider field and did not annotate it did read one."""
    entries, graph = crosswalk(observation())

    assert entries
    assert {entry["resolution_method"] for entry in entries} == {"provider-native"}
    assert set(graph_methods(graph).values()) == {"provider-native"}


@pytest.mark.parametrize("method", ["ordinal-derived", "declared"])
@pytest.mark.parametrize("path,entity_type", IDENTITY_SECTIONS,
                         ids=[".".join(str(key) for key in path) for path, _ in IDENTITY_SECTIONS])
def test_a_stated_method_reaches_the_crosswalk_for_every_identity_section(
        path, entity_type, method):
    entries, graph = crosswalk(stating(path, method))

    stated = [entry for entry in entries if entry["resolution_method"] == method]
    assert len(stated) == 1, entries
    assert stated[0]["entity_type"] == entity_type
    assert graph_methods(graph)[stated[0]["provider_id"]] == method


@pytest.mark.parametrize("method", ["ordinal-derived", "declared"])
def test_only_the_section_that_states_it_moves(method):
    entries, _ = crosswalk(stating(("competition",), method))

    assert methods_by_entity_type(entries)["competition"] == method
    assert {entry["entity_type"] for entry in entries
            if entry["resolution_method"] == "provider-native"} == {
        "season", "site", "event", "team"}


@pytest.mark.parametrize("method", RESOLUTION_METHODS)
def test_confidence_stays_one_for_all_three_methods(method):
    """All three are exact statements about where a string came from; none of them is
    a fuzzy match that could have been a near-miss. A spread of invented confidences
    would be the false precision the profile exists to keep out."""
    entries, _ = crosswalk(stating(("competition",), method))

    assert {entry["confidence"] for entry in entries} == {1.0}


@pytest.mark.parametrize("path,entity_type", IDENTITY_SECTIONS,
                         ids=[".".join(str(key) for key in path) for path, _ in IDENTITY_SECTIONS])
def test_a_method_outside_the_set_is_refused_naming_the_section(path, entity_type):
    """A fourth value is not a weaker claim than ``provider-native`` — it is an
    unreadable one, and a consumer deciding whether to trust an identifier cannot act
    on it."""
    document = stating(path, "guessed")
    errors = validate_observation(document)

    assert errors
    assert all("resolution_method" in error for error in errors), errors
    assert any("'guessed' is not one of" in error for error in errors), errors

    with pytest.raises(ValueError) as raised:
        canonical.to_envelope(document)
    assert "resolution_method" in str(raised.value)


def test_a_stated_method_cannot_reach_the_minted_identifier():
    """Identifiers are minted from the provider namespace and the provider id. If a
    resolution method reached the digest, annotating an adapter would re-mint every
    identity it had ever published."""
    baseline, _ = crosswalk(observation())
    for method in ("ordinal-derived", "declared"):
        entries, _ = crosswalk(stating(("competition",), method))
        assert [entry["machina_id"] for entry in entries] == [
            entry["machina_id"] for entry in baseline
        ]


def test_stating_a_method_leaves_the_rest_of_the_envelope_alone():
    """Everything except the crosswalk views is byte-identical, so the field is
    additive rather than a second axis the whole serializer reads."""
    before = canonical.to_envelope(observation())["machina_sports_schema"]
    after = canonical.to_envelope(
        stating(("competition",), "declared"))["machina_sports_schema"]

    for key in ("capabilities", "event_view", "profile", "rights", "schema_version"):
        assert before[key] == after[key], key

    graph = copy.deepcopy(after["sport_schema_graph"])
    for node in graph["@graph"]:
        if node.get("machina:resolutionMethod") == "declared":
            node["machina:resolutionMethod"] = "provider-native"
    assert graph == before["sport_schema_graph"]
