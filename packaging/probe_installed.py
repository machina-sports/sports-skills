"""Probe the installed canonical package without importing unrelated dependencies."""

import hashlib
import importlib
import importlib.metadata
import importlib.resources
import inspect
import json
import sys
import types
from pathlib import Path

VERSION = "0.33.0"

distribution = importlib.metadata.distribution("sports-skills")
if distribution.version != VERSION:
    raise SystemExit(f"installed {distribution.version}, expected {VERSION}")
root = Path(distribution.locate_file("")).resolve()

# sports_skills eagerly imports its feedparser-backed news module. The release
# contract probes the stdlib-only canonical subtree after a --no-deps install.
package = types.ModuleType("sports_skills")
package.__path__ = [str(root / "sports_skills")]
package.__package__ = "sports_skills"
sys.modules["sports_skills"] = package

canonical = importlib.import_module("sports_skills.canonical")
football = importlib.import_module("sports_skills.canonical.adapters.football")
nba = importlib.import_module("sports_skills.canonical.adapters.nba")
for module in (canonical, football, nba):
    if root not in Path(module.__file__).resolve().parents:
        raise SystemExit(f"worktree import detected: {module.__file__}")

expected_signatures = {
    "to_successor_envelope": "(*, operation, request_bytes, operation_arguments_bytes, output_mode, consumer_tier) -> bytes",
    "to_longitudinal_envelope": "(*, operation, request_bytes, operation_arguments_bytes, consumer_tier) -> bytes",
}
for name, expected in expected_signatures.items():
    if str(inspect.signature(getattr(canonical, name))) != expected:
        raise SystemExit(f"signature drift: {name}")

vendored = importlib.resources.files("sports_skills.canonical._vendored")
receipt = json.loads(vendored.joinpath("VENDORED.json").read_text(encoding="utf-8"))
runtime = json.loads(vendored.joinpath("data/trusted_loader_manifest_v1.json").read_text(encoding="utf-8"))
for key in ("runtime_files", "required_data_files", "private_symbols"):
    if receipt[key] != runtime[key]:
        raise SystemExit(f"owner inventory mismatch: {key}")
for item in runtime["runtime_files"] + runtime["required_data_files"]:
    payload = vendored.joinpath(item["relative_path"]).read_bytes()
    if len(payload) != item["byte_length"] or "sha256:" + hashlib.sha256(payload).hexdigest() != item["sha256"]:
        raise SystemExit(f"owner byte mismatch: {item['relative_path']}")
successor = importlib.import_module("sports_skills.canonical._vendored.successor")
for item in runtime["private_symbols"]:
    if not hasattr(successor, item["symbol"]):
        raise SystemExit(f"private symbol missing: {item['symbol']}")

operations = importlib.resources.files("sports_skills.canonical._operations")
operation_package = json.loads(operations.joinpath("package.json").read_text(encoding="utf-8"))
if len(operation_package["operations"]) != 9:
    raise SystemExit("provider-attested operation inventory is not nine")
for relative, expected in operation_package["resource_digests"].items():
    payload = operations.joinpath(relative).read_bytes()
    if "sha256:" + hashlib.sha256(payload).hexdigest() != expected:
        raise SystemExit(f"operation resource byte mismatch: {relative}")

request = b'{"requires":[],"optional":[]}'
successes = (
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
for operation, fixture_id, mode in successes:
    arguments = f'{{"fixture_id":"{fixture_id}"}}'.encode()
    if "longitudinal" in operation:
        output = canonical.to_longitudinal_envelope(
            operation=operation,
            request_bytes=request,
            operation_arguments_bytes=arguments,
            consumer_tier="prototype",
        )
        root = json.loads(output)["machina_longitudinal_schema"]
    else:
        output = canonical.to_successor_envelope(
            operation=operation,
            request_bytes=request,
            operation_arguments_bytes=arguments,
            output_mode=mode,
            consumer_tier="prototype",
        )
        root = json.loads(output)["machina_sports_schema"]
    if root["rights"]["operation"] != operation:
        raise SystemExit(f"installed operation returned wrong rights: {operation}")

refusals = (
    (
        "arena_soccer_refusal_event",
        b'{"fixture_id":"provider-scoped-graph"}',
        "with_iptc_graph",
        "prototype",
        request,
        "canonical-identity-required-for-graph",
    ),
    (
        "arena_soccer_refusal_event",
        b'{"fixture_id":"reduced-graph"}',
        "with_iptc_graph",
        "prototype",
        request,
        "exact-event-start-time-required",
    ),
    (
        "arena_soccer_refusal_event",
        b'{"fixture_id":"source-representation-mismatch"}',
        "operational_only",
        "prototype",
        request,
        "source-representation-mismatch",
    ),
    (
        "arena_nfl_refusal_event",
        b'{"fixture_id":"rights-ineligible"}',
        "operational_only",
        "production",
        request,
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
        request,
        "canonical-identity-required-for-graph",
    ),
    (
        "arena_nba_refusal_event",
        b'{"fixture_id":"unpromised-managed-collection"}',
        "operational_only",
        "prototype",
        request,
        "unpromised-managed-collection-present",
    ),
    (
        "arena_nba_refusal_event",
        b'{"fixture_id":"unresolved-identity"}',
        "with_iptc_graph",
        "prototype",
        request,
        "canonical-identity-required-for-graph",
    ),
    (
        "arena_nfl_refusal_event",
        b'{"event_id":"1","event_id":"2"}',
        "operational_only",
        "prototype",
        request,
        "duplicate-json-key",
    ),
    (
        "arena_nfl_refusal_event",
        b'{"api_key":"synthetic-not-a-secret"}',
        "operational_only",
        "prototype",
        request,
        "secret-operation-argument-forbidden",
    ),
    (
        "arena_nfl_refusal_event",
        b'{"undeclared_selector":"synthetic"}',
        "operational_only",
        "prototype",
        request,
        "unknown-operation-argument",
    ),
)
for operation, arguments, mode, tier, request_bytes, expected in refusals:
    try:
        canonical.to_successor_envelope(
            operation=operation,
            request_bytes=request_bytes,
            operation_arguments_bytes=arguments,
            output_mode=mode,
            consumer_tier=tier,
        )
    except successor.CanonicalContractError as error:
        if error.reason != expected:
            raise SystemExit(f"installed refusal drift: {operation}: {error.reason}") from error
    else:
        raise SystemExit(f"installed refusal unexpectedly succeeded: {operation}")

try:
    importlib.import_module("machina_sports_canonical")
except ModuleNotFoundError:
    pass
else:
    raise SystemExit("external machina_sports_canonical dependency is present")
