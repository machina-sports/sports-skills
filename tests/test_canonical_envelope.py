"""The public canonical surface: one normalized event in, one full envelope out.

The envelope is not assembled here. ``canonicalize_event`` calls the vendored
serializer, so the graph, the compact view, the provenance block, the crosswalk, the
capability report and the rights block are all the shared runtime's own output rather
than a second code path producing the same shape. A second code path is the thing
that drifts, and these tests are written to notice if one appears.

The byte comparison against machina-templates' checked-in envelope is the whole
cross-repository gate. Everything below it pins a rule that comparison would only
catch by accident on this one fixture.
"""

import ast
import copy
import json
import re
from pathlib import Path

import pytest

from sports_skills import canonical
from tests.test_canonical_reference_fixtures import (
    ENVELOPE_PATH,
    NATIVE_PATH,
    canonical_bytes,
)

OBSERVED_AT = "2026-03-01T22:05:00+00:00"
START_TIME = "2026-03-01T20:00:00+00:00"

PROVIDER_NAMESPACE = "sports-skills/espn"

#: Every provider identifier the synthetic payload states. They are crosswalk
#: evidence and must never appear in a resource identifier.
PROVIDER_IDS = ("9001", "9011", "9012", "9101",
                "synthetic-league-1", "synthetic-league-1-2026")

SURROGATE = re.compile(r"^urn:machina:sports:[a-z-]+:x[0-9a-f]{32}$")

CANONICAL_PACKAGE = (
    Path(__file__).resolve().parents[1] / "src/sports_skills/canonical"
)


def native():
    return json.loads(NATIVE_PATH.read_text(encoding="utf-8"))


def envelope(event=None):
    return canonical.canonicalize_event(
        native() if event is None else event, observed_at=OBSERVED_AT
    )


def block(event=None):
    return envelope(event)["machina_sports_schema"]


def graph_nodes():
    return block()["sport_schema_graph"]["@graph"]


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------

def test_the_expected_envelope_is_reproduced_byte_for_byte():
    assert canonical_bytes(envelope()) == ENVELOPE_PATH.read_text(encoding="utf-8")


def test_two_runs_produce_identical_bytes():
    """Nothing in this path reads the clock, the network or a random source, and the
    checked-in fixtures depend on that staying true."""
    assert canonical_bytes(envelope()) == canonical_bytes(envelope())


def test_the_envelope_carries_every_part_and_both_versions():
    document = block()
    assert sorted(document) == [
        "capabilities", "event_view", "profile", "provenance", "provider_ids",
        "rights", "schema_version", "sport_schema_graph",
    ]
    assert document["schema_version"] == "machina-sports-schema/1"
    assert document["profile"] == "machina-iptc-profile/1.2"


def test_the_graph_is_one_inline_context_and_one_flat_graph():
    graph = block()["sport_schema_graph"]
    assert sorted(graph) == ["@context", "@graph"]
    assert graph["@context"]["sport"] == "https://sportschema.org/ontologies/main/"
    assert isinstance(graph["@graph"], list)
    assert all("@context" not in node for node in graph["@graph"])


# ---------------------------------------------------------------------------
# Identity is a surrogate, and the crosswalk is where provider ids live
# ---------------------------------------------------------------------------

def test_every_resource_identifier_is_a_marked_machina_surrogate():
    for node in graph_nodes():
        assert SURROGATE.match(node["@id"]), node["@id"]


def test_no_provider_identifier_is_used_as_a_resource_identifier():
    for node in graph_nodes():
        for provider_id in PROVIDER_IDS:
            assert provider_id not in node["@id"], (provider_id, node["@id"])


def test_no_provider_namespace_token_reaches_an_identifier_or_a_term():
    """The namespace is ``sports-skills/espn``. Neither half of it may appear in a
    resource identifier or in a property name: an official term under a provider's
    namespace is a term nothing can resolve."""
    graph = block()["sport_schema_graph"]
    for node in graph["@graph"]:
        for token in ("sports-skills", "espn"):
            assert token not in node["@id"], (token, node["@id"])
            for key in node:
                assert token not in key, (token, key)
    for prefix in graph["@context"]:
        assert prefix not in ("sports-skills", "espn")


def test_the_crosswalk_holds_every_identifier_the_payload_stated():
    entries = block()["provider_ids"]
    assert [entry["entity_type"] for entry in entries] == [
        "competition", "season", "site", "event", "team", "team",
    ]
    assert sorted(entry["provider_id"] for entry in entries) == sorted(PROVIDER_IDS)
    for entry in entries:
        assert entry["provider_namespace"] == PROVIDER_NAMESPACE
        assert entry["resolution_method"] == "provider-native"
        assert entry["confidence"] == 1.0


def test_every_crosswalk_entry_names_the_observation_field_it_came_from():
    by_type = {entry["entity_type"]: entry for entry in block()["provider_ids"]}
    assert by_type["event"]["evidence"] == "observation.event.provider_id"
    assert by_type["season"]["evidence"] == "observation.competition.season.provider_id"
    assert by_type["site"]["evidence"] == "observation.site.provider_id"


def test_a_provider_identifier_appears_only_on_a_crosswalk_resource():
    """The rule stated positively: wherever a provider identifier is in the graph, it
    is the value of a ``machina:`` property on a ``machina:ProviderIdentifier``,
    which is the sanctioned place for it."""
    for node in graph_nodes():
        carried = [
            value for value in node.values()
            if isinstance(value, str) and value in PROVIDER_IDS
        ]
        if carried:
            assert node["@type"] == "machina:ProviderIdentifier", node


def test_the_two_crosswalk_views_agree():
    """The flat envelope block and the graph resources are two projections of one
    entry list. Two lists that could disagree would make either useless."""
    document = block()
    resources = [
        node for node in document["sport_schema_graph"]["@graph"]
        if node["@type"] == "machina:ProviderIdentifier"
    ]
    assert [
        (node["machina:providerNamespace"], node["machina:providerId"])
        for node in resources
    ] == [
        (entry["provider_namespace"], entry["provider_id"])
        for entry in document["provider_ids"]
    ]


def test_two_events_with_different_identifiers_mint_different_surrogates():
    """A surrogate that ignored part of its identity tuple would silently merge two
    distinct matches into one, which is the hardest class of data bug to notice."""
    other = native()
    other["id"] = "9002"
    first = next(n for n in graph_nodes() if n["@type"] == "sport:Event")
    second = next(
        n for n in block(other)["sport_schema_graph"]["@graph"]
        if n["@type"] == "sport:Event"
    )
    assert first["@id"] != second["@id"]


# ---------------------------------------------------------------------------
# Provenance, rights, capabilities — all from the shared runtime
# ---------------------------------------------------------------------------

def test_the_provenance_block_cites_the_pin_the_adapter_and_the_id_strategy():
    provenance = block()["provenance"]
    assert provenance["provider"]["namespace"] == PROVIDER_NAMESPACE
    assert provenance["adapter"]["name"] == "sports_skills.canonical.adapters.football"
    assert provenance["observed_at"] == OBSERVED_AT
    assert provenance["upstream_pin"]["target_version"] == "1.1"
    assert provenance["determinism"]["id_strategy"] == "provider-scoped-surrogate"


def test_the_rights_block_is_the_observation_rights_carried_through_unchanged():
    """An envelope that could soften the adapter's rights claim would make the claim
    worthless. The gate downstream reads this block, so it has to be the same one."""
    from sports_skills.canonical.adapters import football

    assert block()["rights"] == football.RIGHTS


def test_the_rights_block_grants_no_entitlement_and_claims_no_commercial_use():
    rights = block()["rights"]
    assert rights["prototype_only"] is True
    assert rights["commercial_use"] is False
    for word in ("licensed", "redistributable"):
        assert word not in rights["data_class"], word


def test_the_rights_gate_is_vendored_beside_the_serializer_not_written_here():
    """The deferral this test used to record is closed. machina-templates moved
    ``rights_findings`` out of ``tools/iptc/validate_graph.py`` and into
    ``tools/iptc/canonical/rights.py`` precisely so it could be vendored, and the
    serializer still does not own it: stating a rights block and deciding who may
    consume one are separate jobs, reported separately. The rule itself is exercised in
    ``tests/test_canonical_rights.py``."""
    from sports_skills.canonical._vendored import rights, serialize

    assert callable(rights.rights_findings)
    for name in ("rights_findings", "consumer_tier", "assert_rights"):
        assert not hasattr(serialize, name), name


def test_the_capability_report_claims_only_what_the_payload_supports():
    """A capability report is a promise a consumer plans against. Claiming one this
    payload cannot keep is worse than claiming none."""
    capabilities = block()["capabilities"]
    assert capabilities["tier"] == "core"
    assert capabilities["tiers_satisfied"] == ["core"]
    assert capabilities["present"] == [
        "event.competition", "event.identity", "event.participants", "event.score",
        "event.start_time", "event.status", "provenance",
    ]
    assert capabilities["violations"] == []


def test_the_capability_report_names_the_absences_a_consumer_would_plan_against():
    absent = block()["capabilities"]["absent"]
    for capability in ("event.clock", "event.period", "event.actions", "event.result",
                       "event.start_time.bounded", "participant.player_statistics", "event.lineups"):
        assert capability in absent, capability


def test_exact_observations_keep_the_exact_projection_and_no_graph_refusal():
    document = block()
    assert "sport_schema_graph" in document
    assert "graph_unavailable_reason" not in document["capabilities"]
    assert document["event_view"]["start_time"] == START_TIME
    assert "temporal_evidence" not in document["event_view"]
    assert document["provenance"]["profile"] == "machina-iptc-profile/1.1"


# ---------------------------------------------------------------------------
# Nothing fabricated reaches the output
# ---------------------------------------------------------------------------

def test_no_null_and_no_empty_string_reaches_the_graph():
    blob = json.dumps(block()["sport_schema_graph"])
    assert "null" not in blob
    assert '""' not in blob


def test_no_null_and_no_empty_string_reaches_the_view_outside_raw():
    """``provider.raw`` is excluded deliberately: it is the native payload's own
    bytes, it genuinely carries two nulls and two empty strings, and rewriting it
    would destroy the one field whose whole value is being an unaltered record."""
    view = copy.deepcopy(block()["event_view"])
    view.get("provider", {}).pop("raw", None)
    blob = json.dumps(view)
    assert "null" not in blob
    assert '""' not in blob


def test_the_native_payload_survives_only_in_the_view():
    document = block()
    assert document["event_view"]["provider"]["raw"] == native()
    assert "raw" not in json.dumps(document["sport_schema_graph"])
    assert "raw" not in document["provenance"]


def test_no_stub_resource_is_emitted():
    """A resource carrying only an ``@id`` and a ``@type`` reads as a described
    entity to every consumer and describes nothing."""
    for node in graph_nodes():
        assert len(node) > 2, node


def test_no_official_resource_carries_a_machina_property():
    """The pinned shapes are ``sh:closed``, so one ``machina:`` key on a ``sport:``
    resource fails validation for the whole document."""
    for node in graph_nodes():
        if str(node["@type"]).startswith("sport:"):
            assert [key for key in node if key.startswith("machina:")] == []


def test_no_phase_resource_is_emitted_for_a_payload_with_no_round():
    types = [node["@type"] for node in graph_nodes()]
    assert "sport:CompetitionPhase" not in types


def test_the_event_carries_its_status_start_time_and_both_participations():
    event = next(node for node in graph_nodes() if node["@type"] == "sport:Event")
    assert event["sport:eventStatus"] == {"@id": "speventstatus:post-event"}
    assert event["sport:startDateTime"] == {"@value": START_TIME, "@type": "xsd:dateTime"}
    assert len(event["sport:participation"]) == 2


# ---------------------------------------------------------------------------
# Failing closed
# ---------------------------------------------------------------------------

def test_an_unmappable_event_never_reaches_the_serializer():
    event = native()
    event["status"] = "STATUS_INVENTED_BY_ESPN_TOMORROW"
    with pytest.raises(ValueError):
        envelope(event)


def test_an_invalid_observation_is_refused_by_the_vendored_serializer():
    """The gate that matters when a future adapter has a bug: an envelope built from
    an unvalidated observation is a conformance claim, citing a profile and a pin,
    about a document nobody checked."""
    document = json.loads(NATIVE_PATH.read_text(encoding="utf-8"))
    observation = canonical.to_observation(document, observed_at=OBSERVED_AT)
    observation["observation"].pop("rights")
    with pytest.raises(ValueError) as excinfo:
        canonical.to_envelope(observation)
    assert "observation.rights" in str(excinfo.value)


def test_the_refusal_reports_every_error_rather_than_the_first():
    observation = canonical.to_observation(native(), observed_at=OBSERVED_AT)
    observation["observation"].pop("rights")
    observation["observation"].pop("adapter")
    with pytest.raises(ValueError) as excinfo:
        canonical.to_envelope(observation)
    message = str(excinfo.value)
    assert "observation.rights" in message
    assert "observation.adapter" in message


# ---------------------------------------------------------------------------
# The surface itself
# ---------------------------------------------------------------------------

def test_the_public_surface_is_small_and_explicit():
    assert sorted(canonical.__all__) == [
        "CONSUMER_TIERS",
        "LONGITUDINAL_SCHEMA_VERSION",
        "MACHINA_SCHEMA_VERSION",
        "PROFILE_VERSION",
        "SCHEMA_VERSION",
        "SUCCESSOR_MACHINA_SCHEMA_VERSION",
        "SUCCESSOR_PROFILE_VERSION",
        "SUCCESSOR_SCHEMA_VERSION",
        "canonicalize_event",
        "canonicalize_nba_event",
        "rights_findings",
        "to_envelope",
        "to_longitudinal_envelope",
        "to_nba_observation",
        "to_observation",
        "to_successor_envelope",
    ]
    for name in canonical.__all__:
        assert hasattr(canonical, name), name


def test_the_surface_re_exports_the_versions_from_the_vendored_pin():
    from sports_skills.canonical import _vendored

    assert canonical.PROFILE_VERSION == _vendored.PROFILE_VERSION
    assert canonical.SCHEMA_VERSION == _vendored.SCHEMA_VERSION
    assert canonical.MACHINA_SCHEMA_VERSION == _vendored.MACHINA_SCHEMA_VERSION


def test_canonicalize_event_is_the_two_steps_composed_and_not_a_third_path():
    """Stated as a test because a convenience wrapper that rebuilt the envelope its
    own way is exactly how two shapes start to disagree."""
    observation = canonical.to_observation(native(), observed_at=OBSERVED_AT)
    assert canonical.to_envelope(observation) == envelope()


def test_the_surface_does_not_mutate_the_event_it_was_given():
    event = native()
    before = json.dumps(event, sort_keys=True)
    envelope(event)
    assert json.dumps(event, sort_keys=True) == before


def test_the_canonical_package_parses_as_python_39():
    for path in sorted(CANONICAL_PACKAGE.rglob("*.py")):
        ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 9))
