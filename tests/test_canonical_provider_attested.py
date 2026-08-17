"""Design 034 provider-attested operation conformance for sports-skills 0.33.0."""

import ast
import hashlib
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OPERATIONS_ROOT = ROOT / "src/sports_skills/canonical/_operations"
VENDORED = ROOT / "src/sports_skills/canonical/_vendored"
REQUEST = b'{"requires":[],"optional":[]}'

OPERATIONS = {
    "arena_soccer_event": (
        "event",
        (
            "soccer-exact-authoritative",
            "soccer-exact-provider-scoped",
            "soccer-reduced-provider-scoped",
        ),
    ),
    "arena_nfl_event": (
        "event",
        (
            "nfl-exact-authoritative",
            "nfl-exact-provider-scoped",
        ),
    ),
    "arena_nba_event": (
        "event",
        (
            "nba-exact-authoritative",
            "nba-exact-provider-scoped",
        ),
    ),
    "arena_soccer_longitudinal": (
        "longitudinal",
        (
            "soccer-date-range-string",
            "soccer-season-number",
        ),
    ),
    "arena_nfl_longitudinal": (
        "longitudinal",
        (
            "nfl-rolling-anchor-number",
            "nfl-season-string",
        ),
    ),
    "arena_nba_longitudinal": ("longitudinal", ("nba-career-string",)),
    "arena_soccer_refusal_event": (
        "event",
        (
            "provider-scoped-graph",
            "reduced-graph",
            "source-representation-mismatch",
        ),
    ),
    "arena_nfl_refusal_event": (
        "event",
        (
            "rights-ineligible",
            "unsupported-capability",
        ),
    ),
    "arena_nba_refusal_event": (
        "event",
        (
            "ambiguous-identity",
            "unpromised-managed-collection",
            "unresolved-identity",
        ),
    ),
}

SUCCESS_CASES = (
    ("arena_soccer_event", "soccer-exact-authoritative", "with_iptc_graph"),
    ("arena_nfl_event", "nfl-exact-authoritative", "with_iptc_graph"),
    ("arena_nba_event", "nba-exact-authoritative", "with_iptc_graph"),
    ("arena_soccer_event", "soccer-exact-provider-scoped", "operational_only"),
    ("arena_nfl_event", "nfl-exact-provider-scoped", "operational_only"),
    ("arena_nba_event", "nba-exact-provider-scoped", "operational_only"),
    ("arena_soccer_event", "soccer-reduced-provider-scoped", "operational_only"),
    ("arena_soccer_longitudinal", "soccer-date-range-string", "operational_only"),
    ("arena_soccer_longitudinal", "soccer-season-number", "operational_only"),
    ("arena_nfl_longitudinal", "nfl-rolling-anchor-number", "operational_only"),
    ("arena_nfl_longitudinal", "nfl-season-string", "operational_only"),
    ("arena_nba_longitudinal", "nba-career-string", "operational_only"),
)

REFUSAL_CASES = (
    (
        "arena_soccer_refusal_event",
        b'{"fixture_id":"provider-scoped-graph"}',
        "with_iptc_graph",
        "prototype",
        REQUEST,
        "canonical-identity-required-for-graph",
    ),
    (
        "arena_soccer_refusal_event",
        b'{"fixture_id":"reduced-graph"}',
        "with_iptc_graph",
        "prototype",
        REQUEST,
        "exact-event-start-time-required",
    ),
    (
        "arena_soccer_refusal_event",
        b'{"fixture_id":"source-representation-mismatch"}',
        "operational_only",
        "prototype",
        REQUEST,
        "source-representation-mismatch",
    ),
    (
        "arena_nfl_refusal_event",
        b'{"fixture_id":"rights-ineligible"}',
        "operational_only",
        "production",
        REQUEST,
        "consumer-tier-not-allowed",
    ),
    (
        "arena_nfl_refusal_event",
        b'{"fixture_id":"unsupported-capability"}',
        "operational_only",
        "prototype",
        b'{"requires":["adapter.can_supply.event.action.spatial_evidence"],"optional":[]}',
        "required-adapter-capability-missing",
    ),
    (
        "arena_nba_refusal_event",
        b'{"fixture_id":"ambiguous-identity"}',
        "with_iptc_graph",
        "prototype",
        REQUEST,
        "canonical-identity-required-for-graph",
    ),
    (
        "arena_nba_refusal_event",
        b'{"fixture_id":"unpromised-managed-collection"}',
        "operational_only",
        "prototype",
        REQUEST,
        "unpromised-managed-collection-present",
    ),
    (
        "arena_nba_refusal_event",
        b'{"fixture_id":"unresolved-identity"}',
        "with_iptc_graph",
        "prototype",
        REQUEST,
        "canonical-identity-required-for-graph",
    ),
    (
        "arena_nfl_refusal_event",
        b'{"event_id":"1","event_id":"2"}',
        "operational_only",
        "prototype",
        REQUEST,
        "duplicate-json-key",
    ),
    (
        "arena_nfl_refusal_event",
        b'{"api_key":"synthetic-not-a-secret"}',
        "operational_only",
        "prototype",
        REQUEST,
        "secret-operation-argument-forbidden",
    ),
    (
        "arena_nfl_refusal_event",
        b'{"undeclared_selector":"synthetic"}',
        "operational_only",
        "prototype",
        REQUEST,
        "unknown-operation-argument",
    ),
)


def _canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def _record_digest(value):
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _arguments(fixture_id):
    return f'{{"fixture_id":"{fixture_id}"}}'.encode()


def _execute(operation, fixture_id, mode):
    from sports_skills import canonical

    kind = OPERATIONS[operation][0]
    if kind == "longitudinal":
        return canonical.to_longitudinal_envelope(
            operation=operation,
            request_bytes=REQUEST,
            operation_arguments_bytes=_arguments(fixture_id),
            consumer_tier="prototype",
        )
    return canonical.to_successor_envelope(
        operation=operation,
        request_bytes=REQUEST,
        operation_arguments_bytes=_arguments(fixture_id),
        output_mode=mode,
        consumer_tier="prototype",
    )


def test_owner_041_runtime_registry_and_all_27_records_are_byte_exact():
    vendored_receipt = json.loads((VENDORED / "VENDORED.json").read_bytes())
    runtime = json.loads((VENDORED / "data/trusted_loader_manifest_v1.json").read_bytes())
    assert vendored_receipt["source_commit"] == "bf96c8d84b308e2e23d7dd7ec8942e2da82f6c14"
    assert vendored_receipt["owner_distribution"] == {
        "name": "machina-sports-canonical",
        "version": "0.4.1",
        "wheel_sha256": "cd454eb8411b5639af7313c713276bfa4a0dc72aab037b66ba451bc3e0f090bd",
        "aggregate_runtime_digest": "sha256:96d1817fc0ba4357029860b73b5a2dddcc3738a80240a73cd443c7a30bf25e5b",
    }
    assert runtime["owner_package"]["version"] == "0.4.1"
    assert hashlib.sha256((VENDORED / "data/source_shape_registry_v2.json").read_bytes()).hexdigest() == (
        "442213f819bf8f1fd5ea9a940695f9a182dbb914d04203d311427c14bdbd1437"
    )

    registry = json.loads((VENDORED / "data/source_shape_registry_v2.json").read_bytes())
    groups = {
        "source-shapes": registry["shapes"],
        "operation-contracts": registry["operation_contracts"],
        "output-collection-contracts": registry["output_collection_contracts"],
    }
    assert {name: len(records) for name, records in groups.items()} == {
        "source-shapes": 9,
        "operation-contracts": 9,
        "output-collection-contracts": 9,
    }
    for directory, records in groups.items():
        for record in records:
            operation = record["operation"]
            payload = (OPERATIONS_ROOT / "owner-records" / directory / f"{operation}.json").read_bytes()
            assert payload == _canonical_bytes(record)
            assert "sha256:" + hashlib.sha256(payload).hexdigest() == _record_digest(record)


def test_nine_independent_sports_skills_artifact_sets_are_closed_and_digest_bound():
    package = json.loads((OPERATIONS_ROOT / "package.json").read_bytes())
    assert package["schema_version"] == "sports-skills-arena-step10-operations/1"
    assert package["provider_namespace"] == "sports-skills/espn"
    assert package["package_name"] == "sports-skills"
    assert package["approved_distribution_version"] == "0.33.0"
    assert package["release_id"] == "canonical-evidence-step10-operations"
    assert [item["operation"] for item in package["operations"]] == sorted(OPERATIONS)
    assert len(package["operations"]) == 9

    linked = set()
    for registration in package["operations"]:
        operation = registration["operation"]
        resources = {}
        for name in ("package_link", "descriptor", "rights_profile", "argument_schema", "fixture_manifest"):
            path = OPERATIONS_ROOT / registration[f"{name}_path"]
            resources[name] = json.loads(path.read_bytes())
            assert package["resource_digests"][registration[f"{name}_path"]] == _record_digest(resources[name])
        link = resources["package_link"]
        assert link["operation"] == operation
        assert link["approved_distribution_version"] == "0.33.0"
        assert link["descriptor_digest"] == _record_digest(resources["descriptor"])
        assert link["rights_profile_digest"] == _record_digest(resources["rights_profile"])
        assert link["operation_argument_schema_digest"] == _record_digest(resources["argument_schema"])
        assert link["fixture_manifest_digest"] == _record_digest(resources["fixture_manifest"])
        assert resources["argument_schema"]["fields"][0]["allowed_values"] == list(OPERATIONS[operation][1])
        assert resources["fixture_manifest"]["fixture_ids"] == list(OPERATIONS[operation][1])
        linked.update(registration.values())

    inventory = {path.relative_to(OPERATIONS_ROOT).as_posix() for path in OPERATIONS_ROOT.rglob("*.json")}
    assert set(package["resource_digests"]) == inventory - {"package.json"}


def test_every_fixture_is_immutable_synthetic_provider_data_free_and_manifested_once():
    package = json.loads((OPERATIONS_ROOT / "package.json").read_bytes())
    fixture_paths = []
    for registration in package["operations"]:
        manifest = json.loads((OPERATIONS_ROOT / registration["fixture_manifest_path"]).read_bytes())
        for fixture in manifest["fixtures"]:
            path = OPERATIONS_ROOT / fixture["path"]
            fixture_paths.append(fixture["path"])
            payload = path.read_bytes()
            document = json.loads(payload)
            assert payload == _canonical_bytes(document)
            assert document["fixture_id"] == fixture["fixture_id"]
            assert document["synthetic"] is True
            assert document["contains_provider_data"] is False
            assert fixture["synthetic"] is True
            assert fixture["contains_provider_data"] is False
            assert fixture["original_bytes_digest"] == "sha256:" + hashlib.sha256(payload).hexdigest()
            assert "espn.com" not in payload.decode().casefold()
    assert len(fixture_paths) == 20
    assert len(fixture_paths) == len(set(fixture_paths))


@pytest.mark.parametrize(("operation", "fixture_id", "mode"), SUCCESS_CASES)
def test_all_12_success_paths_are_deterministic_and_contract_complete(operation, fixture_id, mode):
    first = _execute(operation, fixture_id, mode)
    second = _execute(operation, fixture_id, mode)
    assert first == second
    assert first == _canonical_bytes(json.loads(first))
    envelope = json.loads(first)
    kind = OPERATIONS[operation][0]
    root_key = "machina_sports_schema" if kind == "event" else "machina_longitudinal_schema"
    root = envelope[root_key]
    assert root["rights"]["provider_namespace"] == "sports-skills/espn"
    assert root["rights"]["operation"] == operation
    assert root["rights"]["data_class"] == "synthetic-provider-data-free-replay"
    assert root["rights"]["prototype_only"] is True
    assert root["rights"]["commercial_use"] is False
    assert root["rights"]["allowed_consumer_tiers"] == ["prototype"]
    assert root["provenance"]["canonical_package"]["version"] == "0.4.1"
    assert root["provenance"]["adapter"]["operation"] == operation
    assert len(root["provenance"]["source_artifact_digests"]) == 1
    assert not set(root["provenance"]).intersection(
        {"rights", "rights_profile", "rights_profile_digest", "consumer_tier"}
    )
    assert ("sport_schema_graph" in root) is (mode == "with_iptc_graph")


def test_success_outputs_preserve_number_string_spatial_and_period_representations():
    soccer = json.loads(_execute("arena_soccer_event", "soccer-exact-authoritative", "with_iptc_graph"))
    nfl = json.loads(_execute("arena_nfl_event", "nfl-exact-authoritative", "with_iptc_graph"))
    nba = json.loads(_execute("arena_nba_event", "nba-exact-authoritative", "with_iptc_graph"))
    for envelope in (soccer, nfl, nba):
        spatial = envelope["machina_sports_schema"]["event_view"]["observation"]["actions"][0]["spatial_evidence"]
        assert type(spatial["source_position"]["coordinates"]["x"]) is str
        assert type(spatial["source_position"]["coordinates"]["y"]) is str

    cases = (
        ("arena_soccer_longitudinal", "soccer-date-range-string"),
        ("arena_soccer_longitudinal", "soccer-season-number"),
        ("arena_nfl_longitudinal", "nfl-rolling-anchor-number"),
        ("arena_nfl_longitudinal", "nfl-season-string"),
        ("arena_nba_longitudinal", "nba-career-string"),
    )
    for operation, fixture_id in cases:
        envelope = json.loads(_execute(operation, fixture_id, "operational_only"))
        sequence = envelope["machina_longitudinal_schema"]["longitudinal_view"]["records"][0]["period"]["sequence"]
        assert type(sequence) is int


def test_graph_success_is_authoritative_and_operational_success_is_provider_scoped():
    graph = json.loads(_execute("arena_soccer_event", "soccer-exact-authoritative", "with_iptc_graph"))
    graph_identities = graph["machina_sports_schema"]["event_view"]["identity_evidence"]
    assert graph_identities
    assert {item["status"] for item in graph_identities} == {"authoritatively_resolved"}
    operational = json.loads(_execute("arena_soccer_event", "soccer-exact-provider-scoped", "operational_only"))
    identities = operational["machina_sports_schema"]["event_view"]["identity_evidence"]
    assert identities
    assert {item["status"] for item in identities} == {"provider_scoped"}


def test_coverage_claims_and_pointer_expansions_are_complete():
    event = json.loads(_execute("arena_nfl_event", "nfl-exact-provider-scoped", "operational_only"))
    view = event["machina_sports_schema"]["event_view"]
    pointers = {item["collection_pointer"] for item in view["coverage"]}
    assert pointers == {
        "/machina_sports_schema/event_view/observation/actions",
        "/machina_sports_schema/event_view/observation/participants",
        "/machina_sports_schema/event_view/observation/participants/0/statistics",
        "/machina_sports_schema/event_view/observation/participants/1/statistics",
    }
    assert pointers == {item["collection_pointer"] for item in view["collection_claims"]}
    assert all(item["available_total"]["state"] == "known" for item in view["coverage"])


@pytest.mark.parametrize(("operation", "arguments", "mode", "tier", "request_bytes", "reason"), REFUSAL_CASES)
def test_all_11_refusals_are_stable_and_target_specific(operation, arguments, mode, tier, request_bytes, reason):
    from sports_skills import canonical

    with pytest.raises(canonical._successor.CanonicalContractError) as excinfo:
        canonical.to_successor_envelope(
            operation=operation,
            request_bytes=request_bytes,
            operation_arguments_bytes=arguments,
            output_mode=mode,
            consumer_tier=tier,
        )
    assert excinfo.value.reason == reason


def test_source_representation_mismatch_reaches_exact_semantic_validation(monkeypatch):
    from sports_skills import canonical

    activity = {"source_load": 0, "source_reparse": 0, "spatial_parse": 0}
    original_load = canonical._successor._load_source_artifact
    original_reparse = canonical._successor._reparse_source_artifact
    original_spatial_parse = canonical._successor._parse_spatial_source

    def loaded(data, trust):
        activity["source_load"] += 1
        return original_load(data, trust)

    def reparsed(artifact, trust):
        activity["source_reparse"] += 1
        return original_reparse(artifact, trust)

    def parsed(value, representation):
        activity["spatial_parse"] += 1
        return original_spatial_parse(value, representation)

    monkeypatch.setattr(canonical._successor, "_load_source_artifact", loaded)
    monkeypatch.setattr(canonical._successor, "_reparse_source_artifact", reparsed)
    monkeypatch.setattr(canonical._successor, "_parse_spatial_source", parsed)

    with pytest.raises(canonical._successor.CanonicalContractError) as excinfo:
        _execute("arena_soccer_refusal_event", "source-representation-mismatch", "operational_only")

    assert excinfo.value.reason == "source-representation-mismatch"
    assert activity["source_load"] == 1
    assert activity["source_reparse"] >= 1
    assert activity["spatial_parse"] == 1


def test_in_memory_fixture_name_bypass_cannot_turn_representation_mismatch_into_success(monkeypatch):
    from sports_skills import canonical
    from sports_skills.canonical._operations import _document

    original_thaw = _document.successor._thaw

    def renamed(value):
        result = original_thaw(value)
        if (
            isinstance(result, dict)
            and result.get("fixture_id") == "source-representation-mismatch"
            and {"contains_provider_data", "coverage", "event", "identity", "sport", "synthetic"}.issubset(result)
        ):
            result["fixture_id"] = "in-memory-renamed-fixture"
        return result

    monkeypatch.setattr(_document.successor, "_thaw", renamed)
    with pytest.raises(canonical._successor.CanonicalContractError) as excinfo:
        _execute("arena_soccer_refusal_event", "source-representation-mismatch", "operational_only")
    assert excinfo.value.reason == "source-representation-mismatch"


def test_in_memory_fixture_name_bypass_cannot_hide_unpromised_collection(monkeypatch):
    from sports_skills import canonical
    from sports_skills.canonical._operations import _document

    original_thaw = _document.successor._thaw

    def renamed(value):
        result = original_thaw(value)
        if (
            isinstance(result, dict)
            and result.get("fixture_id") == "unpromised-managed-collection"
            and {"contains_provider_data", "coverage", "event", "identity", "sport", "synthetic"}.issubset(result)
        ):
            result["fixture_id"] = "in-memory-renamed-fixture"
        return result

    monkeypatch.setattr(_document.successor, "_thaw", renamed)
    with pytest.raises(canonical._successor.CanonicalContractError) as excinfo:
        _execute("arena_nba_refusal_event", "unpromised-managed-collection", "operational_only")
    assert excinfo.value.reason == "unpromised-managed-collection-present"


@pytest.mark.parametrize("operation", ("event", "longitudinal", "not_registered"))
def test_unregistered_operations_remain_unattested(operation):
    from sports_skills import canonical

    with pytest.raises(
        canonical._successor.CanonicalContractError,
        match="sports-skills-operation-not-attested",
    ):
        canonical.to_successor_envelope(
            operation=operation,
            request_bytes=REQUEST,
            operation_arguments_bytes=b"{}",
            output_mode="operational_only",
            consumer_tier="prototype",
        )


def test_invalid_slash_operation_still_stops_at_wrapper_token_boundary():
    from sports_skills import canonical

    with pytest.raises(ValueError, match="operation must be a canonical token"):
        canonical.to_successor_envelope(
            operation="event/unsafe",
            request_bytes=REQUEST,
            operation_arguments_bytes=b"{}",
            output_mode="operational_only",
            consumer_tier="prototype",
        )


@pytest.mark.parametrize(
    ("arguments", "reason"),
    (
        (b'{"fixture_id":"not-approved"}', "operation-argument-value-not-allowed"),
        (b'{"api_key":"synthetic"}', "secret-operation-argument-forbidden"),
        (b'{"other":"synthetic"}', "unknown-operation-argument"),
    ),
)
def test_argument_refusals_have_zero_adapter_import_and_source_load(monkeypatch, arguments, reason):
    from sports_skills import canonical

    activity = {"import": 0, "source": 0}

    def imported(*args, **kwargs):
        activity["import"] += 1
        raise AssertionError("adapter imported")

    def loaded(*args, **kwargs):
        activity["source"] += 1
        raise AssertionError("source loaded")

    loader = canonical._SPORTS_SKILLS_TRUSTED_ADAPTER_PACKAGE_LOADER
    monkeypatch.setattr(type(loader), "import_adapter", imported)
    monkeypatch.setattr(canonical._successor, "_load_source_artifact", loaded)
    with pytest.raises(canonical._successor.CanonicalContractError) as excinfo:
        canonical.to_successor_envelope(
            operation="arena_nfl_refusal_event",
            request_bytes=REQUEST,
            operation_arguments_bytes=arguments,
            output_mode="operational_only",
            consumer_tier="prototype",
        )
    assert excinfo.value.reason == reason
    assert activity == {"import": 0, "source": 0}


def test_production_refusal_has_zero_adapter_or_fixture_source_activity(monkeypatch):
    from sports_skills import canonical

    activity = {"import": 0, "source": 0}

    def forbidden(name):
        def fail(*args, **kwargs):
            activity[name] += 1
            raise AssertionError(name)

        return fail

    loader = canonical._SPORTS_SKILLS_TRUSTED_ADAPTER_PACKAGE_LOADER
    monkeypatch.setattr(type(loader), "import_adapter", forbidden("import"))
    monkeypatch.setattr(canonical._successor, "_load_source_artifact", forbidden("source"))
    with pytest.raises(canonical._successor.CanonicalContractError) as excinfo:
        canonical.to_successor_envelope(
            operation="arena_nfl_refusal_event",
            request_bytes=REQUEST,
            operation_arguments_bytes=b'{"fixture_id":"rights-ineligible"}',
            output_mode="operational_only",
            consumer_tier="production",
        )
    assert excinfo.value.reason == "consumer-tier-not-allowed"
    assert activity == {"import": 0, "source": 0}


def test_success_execution_imports_invokes_reads_and_loads_exactly_once(monkeypatch):
    from sports_skills import canonical
    from sports_skills.canonical._operations import _adapter

    activity = {"import": 0, "invoke": 0, "fixture_read": 0, "source_load": 0}
    loader = canonical._SPORTS_SKILLS_TRUSTED_ADAPTER_PACKAGE_LOADER
    original_import = type(loader).import_adapter
    original_fetch = _adapter.PackagedFixtureAdapter.fetch
    original_read = Path.read_bytes
    original_load = canonical._successor._load_source_artifact

    def imported(self, trust):
        activity["import"] += 1
        return original_import(self, trust)

    def fetched(self, handle):
        activity["invoke"] += 1
        return original_fetch(self, handle)

    def read_bytes(path):
        if "_operations/fixtures" in path.as_posix():
            activity["fixture_read"] += 1
        return original_read(path)

    def loaded(data, trust):
        activity["source_load"] += 1
        return original_load(data, trust)

    monkeypatch.setattr(type(loader), "import_adapter", imported)
    monkeypatch.setattr(_adapter.PackagedFixtureAdapter, "fetch", fetched)
    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    monkeypatch.setattr(canonical._successor, "_load_source_artifact", loaded)
    _execute("arena_soccer_event", "soccer-exact-provider-scoped", "operational_only")
    assert activity == {"import": 1, "invoke": 1, "fixture_read": 1, "source_load": 1}


def test_repeated_phase1_graph_calls_leave_vendored_context_cache_none(monkeypatch):
    from sports_skills.canonical._vendored import serialize, successor

    context_reads = 0
    original_open = Path.open
    original_successor_context = successor.shared_context

    def opened(path, *args, **kwargs):
        nonlocal context_reads
        if path == serialize.SHARED_CONTEXT_PATH:
            context_reads += 1
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(serialize, "_context_cache", None)
    monkeypatch.setattr(Path, "open", opened)
    assert serialize._context_cache is None
    first = _execute("arena_soccer_event", "soccer-exact-authoritative", "with_iptc_graph")
    assert serialize._context_cache is None
    second = _execute("arena_soccer_event", "soccer-exact-authoritative", "with_iptc_graph")
    assert serialize._context_cache is None
    assert successor.shared_context is original_successor_context
    assert first == second
    assert context_reads >= 4


def test_phase1_graph_ignores_and_preserves_existing_vendored_context_cache(monkeypatch):
    from sports_skills.canonical._vendored import serialize

    existing = {"poisoned": "context"}
    monkeypatch.setattr(serialize, "_context_cache", existing)
    envelope = json.loads(_execute("arena_soccer_event", "soccer-exact-authoritative", "with_iptc_graph"))
    context = envelope["machina_sports_schema"]["sport_schema_graph"]["@context"]
    assert serialize._context_cache is existing
    assert context != existing
    assert context["sport"] == "https://sportschema.org/ontologies/main/"


def test_phase1_boundary_restores_owner_context_and_cache_after_refusal(monkeypatch):
    from sports_skills import canonical
    from sports_skills.canonical._vendored import serialize, successor

    existing = {"existing": "native-context"}
    original_successor_context = successor.shared_context
    monkeypatch.setattr(serialize, "_context_cache", existing)
    with pytest.raises(canonical._successor.CanonicalContractError) as excinfo:
        _execute("arena_soccer_refusal_event", "source-representation-mismatch", "operational_only")
    assert excinfo.value.reason == "source-representation-mismatch"
    assert successor.shared_context is original_successor_context
    assert serialize._context_cache is existing


def test_all_success_and_refusal_paths_are_fail_closed_against_network():
    script = textwrap.dedent(
        f"""
        import http.client
        import json
        import socket
        import sys

        def forbidden(*args, **kwargs):
            raise AssertionError("network attempt")

        def audit(event, args):
            if event.startswith("socket.") or event in ("http.client.connect", "http.client.send"):
                raise AssertionError("network audit event: " + event)

        sys.addaudithook(audit)
        socket.getaddrinfo = forbidden
        socket.create_connection = forbidden
        socket.socket.connect = forbidden
        socket.socket.connect_ex = forbidden
        http.client.HTTPConnection.connect = forbidden
        http.client.HTTPConnection.request = forbidden

        from sports_skills import canonical

        request = {REQUEST!r}
        operations = {OPERATIONS!r}
        successes = {SUCCESS_CASES!r}
        refusals = {REFUSAL_CASES!r}
        for operation, fixture_id, mode in successes:
            arguments = ('{{"fixture_id":"' + fixture_id + '"}}').encode()
            if operations[operation][0] == "longitudinal":
                canonical.to_longitudinal_envelope(
                    operation=operation,
                    request_bytes=request,
                    operation_arguments_bytes=arguments,
                    consumer_tier="prototype",
                )
            else:
                canonical.to_successor_envelope(
                    operation=operation,
                    request_bytes=request,
                    operation_arguments_bytes=arguments,
                    output_mode=mode,
                    consumer_tier="prototype",
                )
        for operation, arguments, mode, tier, request_bytes, reason in refusals:
            try:
                canonical.to_successor_envelope(
                    operation=operation,
                    request_bytes=request_bytes,
                    operation_arguments_bytes=arguments,
                    output_mode=mode,
                    consumer_tier=tier,
                )
            except canonical._successor.CanonicalContractError as error:
                assert error.reason == reason
            else:
                raise AssertionError("refusal path returned success: " + operation)
        """
    )
    subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
    )


def test_phase1_execution_and_operation_package_have_no_cache_or_network_path():
    sources = [
        (VENDORED / "successor.py").read_text(encoding="utf-8"),
        (ROOT / "src/sports_skills/canonical/_phase1.py").read_text(encoding="utf-8"),
    ]
    sources.extend(path.read_text(encoding="utf-8") for path in OPERATIONS_ROOT.rglob("*.py"))
    for source in sources:
        ast.parse(source, feature_version=(3, 9))
        lowered = source.casefold()
        for forbidden in (
            "urllib",
            "requests",
            "http://",
            "https://",
            "socket",
            "ttlcache",
            "lru_cache",
            "cache lookup",
            "cache hit",
            "cache write",
        ):
            assert forbidden not in lowered
