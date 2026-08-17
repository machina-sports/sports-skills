"""Step 8 consumer boundary for Canonical Evidence Contract Phase 1."""

import ast
import hashlib
import inspect
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VENDORED = ROOT / "src/sports_skills/canonical/_vendored"

OWNER_SOURCE_COMMIT = "ddf12f04803eeb03016c10759aaf2a2be8e85f84"
OWNER_WHEEL_SHA256 = "52c2b5a321a60ca242166e5522307f72ef974a460e8f906775bb3cf0480d22a1"
OWNER_RUNTIME_DIGEST = "sha256:5b011b72a9d4061099f39555983b73ec6e26ef7dea650311c6bc8910e53521d6"

LEGACY_ALL = (
    "CONSUMER_TIERS",
    "MACHINA_SCHEMA_VERSION",
    "PROFILE_VERSION",
    "SCHEMA_VERSION",
    "canonicalize_event",
    "canonicalize_nba_event",
    "rights_findings",
    "to_envelope",
    "to_observation",
    "to_nba_observation",
)
ADDITIVE_ALL = (
    "LONGITUDINAL_SCHEMA_VERSION",
    "SUCCESSOR_MACHINA_SCHEMA_VERSION",
    "SUCCESSOR_PROFILE_VERSION",
    "SUCCESSOR_SCHEMA_VERSION",
    "to_longitudinal_envelope",
    "to_successor_envelope",
)
PRIVATE_SYMBOLS = (
    "_IdentityResolutionProvider",
    "_load_source_artifact",
    "_build_statistic_fact",
    "_build_period_descriptor",
    "_build_rolling_event_anchor",
    "_validate_identity_occurrence",
    "_derive_provider_scoped_entity_id",
    "_derive_operational_resource_id",
    "_derive_operational_id_ledger",
    "_normalize_spatial_evidence",
    "_derive_spatial_distance",
    "_derive_spatial_zone",
    "_build_canonical_spatial_evidence",
    "_build_coverage_evidence",
    "_expand_managed_collection_patterns",
    "_build_successor_provenance",
    "_build_successor_envelope",
    "_project_successor_graph",
    "_validate_successor_envelope",
    "_validate_successor_envelope_bytes",
    "_validate_longitudinal_envelope_bytes",
    "_statistic_projection_disposition",
    "execute_adapter_operation",
)


def _manifest():
    return json.loads((VENDORED / "VENDORED.json").read_text(encoding="utf-8"))


def _runtime_manifest():
    return json.loads((VENDORED / "data/trusted_loader_manifest_v1.json").read_text(encoding="utf-8"))


def _inventory(records):
    return {item["relative_path"]: (item["byte_length"], item["sha256"]) for item in records}


def test_release_receipt_pins_the_reviewed_owner_source_and_wheel():
    receipt = _manifest()
    assert receipt["source_commit"] == OWNER_SOURCE_COMMIT
    assert receipt["owner_distribution"] == {
        "name": "machina-sports-canonical",
        "version": "0.3.0",
        "wheel_sha256": OWNER_WHEEL_SHA256,
        "aggregate_runtime_digest": OWNER_RUNTIME_DIGEST,
    }


def test_complete_runtime_and_required_data_match_the_owner_manifest():
    runtime = _runtime_manifest()
    expected = _inventory(runtime["runtime_files"] + runtime["required_data_files"])
    receipt = _manifest()
    assert runtime["aggregate_runtime_digest"] == OWNER_RUNTIME_DIGEST
    assert receipt["runtime_files"] == runtime["runtime_files"]
    assert receipt["required_data_files"] == runtime["required_data_files"]

    shipped = {
        path.relative_to(VENDORED).as_posix()
        for path in VENDORED.rglob("*")
        if path.is_file() and path.name != "VENDORED.json" and "__pycache__" not in path.parts
    }
    assert shipped == set(expected) | {"data/trusted_loader_manifest_v1.json"}
    for relative_path, (length, digest) in expected.items():
        payload = (VENDORED / relative_path).read_bytes()
        assert len(payload) == length, relative_path
        assert "sha256:" + hashlib.sha256(payload).hexdigest() == digest, relative_path


def test_private_symbol_receipt_is_exact_and_internal_only():
    from sports_skills import canonical
    from sports_skills.canonical._vendored import successor

    receipt = _manifest()
    assert tuple(item["symbol"] for item in receipt["private_symbols"]) == PRIVATE_SYMBOLS
    assert tuple(item["symbol"] for item in _runtime_manifest()["private_symbols"]) == PRIVATE_SYMBOLS
    for symbol in PRIVATE_SYMBOLS:
        assert hasattr(successor, symbol), symbol
        assert symbol not in canonical.__all__
        assert not hasattr(canonical, symbol), symbol


def test_public_versions_exports_and_wrapper_signatures_are_exact():
    from sports_skills import canonical

    assert canonical.SCHEMA_VERSION == "canonical-observation/1.1"
    assert canonical.PROFILE_VERSION == "machina-iptc-profile/1.2"
    assert canonical.MACHINA_SCHEMA_VERSION == "machina-sports-schema/1"
    assert canonical.SUCCESSOR_SCHEMA_VERSION == "canonical-observation/1.2"
    assert canonical.SUCCESSOR_PROFILE_VERSION == "machina-iptc-profile/1.3"
    assert canonical.SUCCESSOR_MACHINA_SCHEMA_VERSION == "machina-sports-schema/1.1"
    assert canonical.LONGITUDINAL_SCHEMA_VERSION == "canonical-longitudinal-statistics/1"
    assert tuple(canonical.__all__) == LEGACY_ALL + ADDITIVE_ALL
    assert len(canonical.__all__) == len(set(canonical.__all__))

    assert str(inspect.signature(canonical.to_successor_envelope)) == (
        "(*, operation, request_bytes, operation_arguments_bytes, output_mode, consumer_tier) -> bytes"
    )
    assert str(inspect.signature(canonical.to_longitudinal_envelope)) == (
        "(*, operation, request_bytes, operation_arguments_bytes, consumer_tier) -> bytes"
    )


def test_wrappers_delegate_once_with_package_owned_authority(monkeypatch):
    from sports_skills import canonical

    calls = []
    sentinel = b"final-validated-envelope"

    def execute(**kwargs):
        calls.append(kwargs)
        return sentinel

    monkeypatch.setattr(canonical._successor, "execute_adapter_operation", execute)
    request = b'{"requires":[],"optional":[]}'
    arguments = b'{"event_id":"synthetic-1"}'

    assert (
        canonical.to_successor_envelope(
            operation="event",
            request_bytes=request,
            operation_arguments_bytes=arguments,
            output_mode="operational_only",
            consumer_tier="prototype",
        )
        is sentinel
    )
    assert len(calls) == 1
    assert calls[0]["package_ref"] is canonical._SPORTS_SKILLS_CANONICAL_PACKAGE_REF
    assert calls[0]["trusted_loader"] is canonical._SPORTS_SKILLS_TRUSTED_ADAPTER_PACKAGE_LOADER
    assert calls[0]["operation_arguments_bytes"] is arguments
    assert json.loads(calls[0]["request_bytes"]) == {
        "requested_provider": "sports-skills/espn",
        "requested_operation": "event",
        "output_kind": "event",
        "output_mode": "operational_only",
        "consumer_tier": "prototype",
        "requires": [],
        "optional": [],
    }

    calls.clear()
    assert (
        canonical.to_longitudinal_envelope(
            operation="season_statistics",
            request_bytes=request,
            operation_arguments_bytes=arguments,
            consumer_tier="prototype",
        )
        is sentinel
    )
    assert len(calls) == 1
    assert json.loads(calls[0]["request_bytes"])["output_kind"] == "longitudinal"
    assert json.loads(calls[0]["request_bytes"])["output_mode"] == "operational_only"


def test_wrapper_preserves_execution_errors_without_remapping(monkeypatch):
    from sports_skills import canonical

    class Refusal(Exception):
        pass

    refusal = Refusal("typed-refusal")

    def execute(**kwargs):
        raise refusal

    monkeypatch.setattr(canonical._successor, "execute_adapter_operation", execute)
    with pytest.raises(Refusal) as excinfo:
        canonical.to_successor_envelope(
            operation="event",
            request_bytes=b'{"requires":[],"optional":[]}',
            operation_arguments_bytes=b"{}",
            output_mode="operational_only",
            consumer_tier="prototype",
        )
    assert excinfo.value is refusal


def test_real_static_refusal_has_zero_later_boundary_activity(monkeypatch):
    from sports_skills import canonical

    counters = {
        "import": 0,
        "bootstrap": 0,
        "client": 0,
        "transport": 0,
        "provider": 0,
        "source": 0,
        "graph": 0,
        "serialize": 0,
        "persistence": 0,
        "dispatch": 0,
        "return": 0,
    }

    def activity(name):
        def record(*args, **kwargs):
            counters[name] += 1
            raise AssertionError(name)

        return record

    loader = canonical._SPORTS_SKILLS_TRUSTED_ADAPTER_PACKAGE_LOADER
    monkeypatch.setattr(type(loader), "import_adapter", activity("import"))
    monkeypatch.setattr(canonical._successor, "_load_source_artifact", activity("source"))
    monkeypatch.setattr(canonical._successor, "_project_successor_graph", activity("graph"))
    monkeypatch.setattr(canonical._successor, "canonical_json_bytes", activity("serialize"))

    with pytest.raises(
        canonical._successor.CanonicalContractError,
        match="sports-skills-operation-not-attested",
    ):
        canonical.to_successor_envelope(
            operation="event",
            request_bytes=b'{"requires":[],"optional":[]}',
            operation_arguments_bytes=b"{}",
            output_mode="operational_only",
            consumer_tier="prototype",
        )
        counters["return"] += 1
    assert counters == {name: 0 for name in counters}


@pytest.mark.parametrize(
    "request_bytes",
    (
        b'{"requires":[],"requires":[],"optional":[]}',
        b'{"requires":[],"optional":[],"api_key":"secret"}',
        b'{"requires":["bad\\ufffdvalue"],"optional":[]}',
        b'{"requires":["bad\\ud800value"],"optional":[]}',
    ),
)
def test_request_byte_refusals_do_not_enter_the_execution_engine(monkeypatch, request_bytes):
    from sports_skills import canonical

    calls = []
    monkeypatch.setattr(
        canonical._successor,
        "execute_adapter_operation",
        lambda **kwargs: calls.append(kwargs),
    )
    with pytest.raises(ValueError):
        canonical.to_successor_envelope(
            operation="event",
            request_bytes=request_bytes,
            operation_arguments_bytes=b"{}",
            output_mode="operational_only",
            consumer_tier="prototype",
        )
    assert calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    (("operation", "bad operation"), ("output_mode", "automatic"), ("consumer_tier", "admin")),
)
def test_wrapper_static_refusals_do_not_enter_the_execution_engine(monkeypatch, field, value):
    from sports_skills import canonical

    calls = []
    monkeypatch.setattr(
        canonical._successor,
        "execute_adapter_operation",
        lambda **kwargs: calls.append(kwargs),
    )
    kwargs = {
        "operation": "event",
        "request_bytes": b'{"requires":[],"optional":[]}',
        "operation_arguments_bytes": b"{}",
        "output_mode": "operational_only",
        "consumer_tier": "prototype",
    }
    kwargs[field] = value
    with pytest.raises(ValueError):
        canonical.to_successor_envelope(**kwargs)
    assert calls == []


def test_vendored_execution_has_no_cache_or_external_canonical_path():
    successor_path = VENDORED / "successor.py"
    source = successor_path.read_text(encoding="utf-8")
    tree = ast.parse(source, feature_version=(3, 9))
    execute = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "execute_adapter_operation"
    )
    execute_source = ast.get_source_segment(source, execute)
    assert execute_source is not None
    for forbidden in ("cache", "machina_sports_canonical", "pip", "http://", "https://"):
        assert forbidden not in execute_source.casefold()


def test_postflight_refusal_cannot_return_candidate_bytes(monkeypatch):
    from sports_skills.canonical._vendored import successor

    counters = {
        "candidate": 0,
        "serialize": 0,
        "validate": 0,
        "postflight": 0,
        "persistence": 0,
        "dispatch": 0,
        "return": 0,
    }

    class Handle:
        schema_version = successor.SUCCESSOR_SCHEMA_VERSION
        _document = {}

    monkeypatch.setattr(successor, "_same_execution", lambda handle, trust: trust)
    monkeypatch.setattr(successor, "_derive_operational_id_ledger", lambda *args, **kwargs: object())

    def candidate(*args):
        counters["candidate"] += 1
        return {"candidate": True}

    def serialize(value):
        counters["serialize"] += 1
        return b"candidate"

    def validate(value, **kwargs):
        counters["validate"] += 1
        return value

    def refuse(*args):
        counters["postflight"] += 1
        raise successor.CanonicalContractError("postflight-drift")

    monkeypatch.setattr(successor, "_event_envelope_candidate", candidate)
    monkeypatch.setattr(successor, "canonical_json_bytes", serialize)
    monkeypatch.setattr(successor, "_validate_successor_envelope_bytes", validate)
    monkeypatch.setattr(successor, "_postflight", refuse)

    with pytest.raises(successor.CanonicalContractError, match="postflight-drift"):
        successor._build_successor_envelope(Handle(), output_mode="operational_only", trust_closure=object())
        counters["return"] += 1
    assert counters == {
        "candidate": 1,
        "serialize": 1,
        "validate": 1,
        "postflight": 1,
        "persistence": 0,
        "dispatch": 0,
        "return": 0,
    }
