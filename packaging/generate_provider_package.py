"""Generate the immutable Design 034 Sports Skills operation package."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src/sports_skills/canonical/_operations"
VENDORED = ROOT / "src/sports_skills/canonical/_vendored"
PROVIDER = "sports-skills/espn"

OPERATIONS = {
    "arena_soccer_event": (
        "event",
        [
            "soccer-exact-authoritative",
            "soccer-exact-provider-scoped",
            "soccer-reduced-provider-scoped",
        ],
    ),
    "arena_nfl_event": ("event", ["nfl-exact-authoritative", "nfl-exact-provider-scoped"]),
    "arena_nba_event": ("event", ["nba-exact-authoritative", "nba-exact-provider-scoped"]),
    "arena_soccer_longitudinal": ("longitudinal", ["soccer-date-range-string", "soccer-season-number"]),
    "arena_nfl_longitudinal": ("longitudinal", ["nfl-rolling-anchor-number", "nfl-season-string"]),
    "arena_nba_longitudinal": ("longitudinal", ["nba-career-string"]),
    "arena_soccer_refusal_event": (
        "event",
        ["provider-scoped-graph", "reduced-graph", "source-representation-mismatch"],
    ),
    "arena_nfl_refusal_event": ("event", ["rights-ineligible", "unsupported-capability"]),
    "arena_nba_refusal_event": (
        "event",
        ["ambiguous-identity", "unpromised-managed-collection", "unresolved-identity"],
    ),
}

EVENT_CAPABILITIES = [
    "adapter.can_supply.event.action.spatial_evidence",
    "adapter.can_supply.event.participation_statistics",
    "adapter.can_supply.identity.resolution_evidence",
    "adapter.can_supply.result.coverage.actions",
    "adapter.can_supply.result.coverage.participants",
    "adapter.can_supply.result.coverage.statistics",
]
LONGITUDINAL_CAPABILITIES = [
    "adapter.can_supply.identity.resolution_evidence",
    "adapter.can_supply.longitudinal.statistics",
    "adapter.can_supply.result.coverage.aggregates",
    "adapter.can_supply.result.coverage.records",
    "adapter.can_supply.result.coverage.statistics",
]


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def digest_bytes(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


def record_digest(value):
    return digest_bytes(canonical_bytes(value))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def coverage(total):
    return {
        "cursor": "synthetic-cursor",
        "page_cap": max(total, 1),
        "request_limit": max(total, 1),
        "total": total,
        "truncated": False,
    }


def temporal_range(start="2026-08-16T20:00:00Z", end="2026-08-16T21:00:00Z"):
    return {
        "schema_version": "canonical-temporal-range/1",
        "start": {"state": "exact", "instant": start, "source_ref": "/synthetic/start"},
        "end": {"state": "exact", "instant": end, "source_ref": "/synthetic/end"},
        "interval_semantics": "start_inclusive_end_exclusive",
    }


def identity_rows(prefix, status, entity_types=("competition", "event", "team", "team")):
    method = {
        "authoritatively_resolved": "synthetic_authority",
        "provider_scoped": "synthetic_provider_scoped",
        "ambiguous": "synthetic_ambiguous",
        "unresolved": "synthetic_unresolved",
    }[status]
    ids = (f"{prefix}-competition", f"{prefix}-event", f"{prefix}-home", f"{prefix}-away")
    rows = []
    for index, (entity_type, provider_id) in enumerate(zip(entity_types, ids), 1):
        row = {
            "entity_type": entity_type,
            "provider_id": provider_id,
            "resolution_method": method,
            "status": status,
        }
        if status == "authoritatively_resolved":
            row["authority_id"] = f"synthetic-authority-{prefix}-{index}"
        rows.append(row)
    return rows


def event_fixture(operation, fixture_id, sport, number_spatial, statistic_name, statistic_value):
    prefix = fixture_id.replace("-exact", "").replace("-provider-scoped", "").replace("-authoritative", "")
    authoritative = fixture_id.endswith("authoritative")
    reduced = "reduced" in fixture_id
    status = "authoritatively_resolved" if authoritative else "provider_scoped"
    coordinate = ("0.25", "0.75", "12.5")
    if number_spatial:
        coordinate = (0.25, 0.75, 12.5)
    participants = []
    for alignment, suffix, score in (("home", "home", "2"), ("away", "away", "1")):
        participants.append(
            {
                "id": f"{prefix}-{suffix}",
                "kind": "team",
                "alignment": alignment,
                "score": score,
                "statistics": [{"field_id": statistic_name, "value": statistic_value}],
            }
        )
    sequence = 1 if number_spatial else "1"
    return {
        "fixture_id": fixture_id,
        "synthetic": True,
        "contains_provider_data": False,
        "sport": sport,
        "event": {
            "id": f"{prefix}-event",
            "competition_id": f"{prefix}-competition",
            "start": {
                "state": "bounded" if reduced else "exact",
                "value": "2026-08-16T20:00Z" if reduced else "2026-08-16T20:00:00Z",
            },
            "status": "closed",
            "participants": participants,
            "actions": [
                {
                    "id": f"{prefix}-action-1",
                    "team_id": f"{prefix}-home",
                    "period_ref": "/period_registry/0",
                    "spatial": {
                        "x": coordinate[0],
                        "y": coordinate[1],
                        "distance": coordinate[2],
                        "zone": "synthetic-zone",
                    },
                }
            ],
            "periods": [
                {
                    "scheme": "period",
                    "value": "period1",
                    "sequence": sequence,
                    "boundary": temporal_range(),
                    "event_provider_namespace": PROVIDER,
                    "event_provider_id": f"{prefix}-event",
                    "event_resolution_method": "provider_native",
                }
            ],
        },
        "coverage": {
            "participants": coverage(2),
            "actions": coverage(1),
            "participant_statistics": [coverage(1), coverage(1)],
        },
        "identity": identity_rows(prefix, status),
    }


def refusal_event_fixture(operation, fixture_id, sport, number_spatial):
    if fixture_id == "ambiguous-identity":
        status = "ambiguous"
    elif fixture_id == "unresolved-identity":
        status = "unresolved"
    elif fixture_id == "reduced-graph":
        status = "authoritatively_resolved"
    else:
        status = "provider_scoped"
    statistic_name = "spsocstat:cornerKicks" if sport == "soccer" else "spbkbstat:minutesPlayed"
    statistic_value = "5"
    fixture = event_fixture(operation, fixture_id, sport, number_spatial, statistic_name, statistic_value)
    prefix = fixture_id
    fixture["identity"] = identity_rows(prefix, status)
    fixture["event"]["id"] = f"{prefix}-event"
    fixture["event"]["competition_id"] = f"{prefix}-competition"
    for index, suffix in enumerate(("home", "away")):
        fixture["event"]["participants"][index]["id"] = f"{prefix}-{suffix}"
    fixture["event"]["actions"][0]["team_id"] = f"{prefix}-home"
    fixture["event"]["periods"][0]["event_provider_id"] = f"{prefix}-event"
    fixture["event"]["periods"][0]["sequence"] = "1" if sport == "soccer" else 1
    if fixture_id == "reduced-graph":
        fixture["event"]["start"] = {"state": "bounded", "value": "2026-08-16T20:00Z"}
    return fixture


def longitudinal_fixture(operation, fixture_id, sport, sequence, value_kind, scope_kind, semantics):
    prefix = fixture_id
    statistic = {
        "arena_soccer_longitudinal": "spsocstat:cornerKicks",
        "arena_nfl_longitudinal": "spamfstat:rushesAttempts",
        "arena_nba_longitudinal": "spbkbstat:minutesPlayed",
    }[operation]
    value = "9" if value_kind == "string" else 9
    scope = {"kind": scope_kind}
    if scope_kind == "season":
        scope["season_id"] = f"{prefix}-season"
    elif scope_kind == "date-range":
        scope.update(start="2026-01-01T00:00:00Z", end="2026-08-17T00:00:00Z")
    elif scope_kind == "rolling-window":
        scope.update(
            window_size=3,
            anchor={
                "provider_namespace": PROVIDER,
                "provider_id": f"{prefix}-event",
                "resolution_method": "provider_native",
                "source_record_id": f"{prefix}-event-source",
            },
        )
    identities = [
        {
            "entity_type": "team",
            "provider_id": f"{prefix}-team",
            "resolution_method": "synthetic_provider_scoped",
            "status": "provider_scoped",
        }
    ]
    if scope_kind == "season":
        identities.append(
            {
                "entity_type": "season",
                "provider_id": f"{prefix}-season",
                "resolution_method": "synthetic_provider_scoped",
                "status": "provider_scoped",
            }
        )
    return {
        "fixture_id": fixture_id,
        "synthetic": True,
        "contains_provider_data": False,
        "sport": sport,
        "subject": {"entity_type": "team", "provider_id": f"{prefix}-team"},
        "scope": scope,
        "records": [
            {
                "period": {"scheme": "period", "value": "period1", "sequence": sequence, "boundary": temporal_range()},
                "semantics": semantics,
                "statistics": [{"field_id": statistic, "value": value}],
            }
        ],
        "aggregates": [{"field_id": statistic, "value": value}],
        "coverage": {
            "records": coverage(1),
            "record_statistics": [coverage(1)],
            "aggregates": coverage(1),
        },
        "identity": identities,
    }


def fixtures():
    values = {}
    for fixture_id in OPERATIONS["arena_soccer_event"][1]:
        values[fixture_id] = event_fixture(
            "arena_soccer_event", fixture_id, "soccer", False, "spsocstat:cornerKicks", "5"
        )
    for fixture_id in OPERATIONS["arena_nfl_event"][1]:
        values[fixture_id] = event_fixture(
            "arena_nfl_event", fixture_id, "american-football", True, "spamfstat:rushesAttempts", 23
        )
    for fixture_id in OPERATIONS["arena_nba_event"][1]:
        values[fixture_id] = event_fixture(
            "arena_nba_event", fixture_id, "basketball", True, "spbkbstat:minutesPlayed", 36
        )
    values["soccer-date-range-string"] = longitudinal_fixture(
        "arena_soccer_longitudinal", "soccer-date-range-string", "soccer", "1", "string", "date-range", "period_delta"
    )
    values["soccer-date-range-string"]["aggregates"] = []
    values["soccer-date-range-string"]["coverage"]["aggregates"] = coverage(0)
    values["soccer-season-number"] = longitudinal_fixture(
        "arena_soccer_longitudinal",
        "soccer-season-number",
        "soccer",
        1,
        "string",
        "season",
        "cumulative_through_period",
    )
    values["soccer-season-number"]["records"][0]["statistics"] = []
    values["soccer-season-number"]["coverage"]["record_statistics"] = [coverage(0)]
    values["nfl-rolling-anchor-number"] = longitudinal_fixture(
        "arena_nfl_longitudinal",
        "nfl-rolling-anchor-number",
        "american-football",
        1,
        "number",
        "rolling-window",
        "snapshot_at_period",
    )
    values["nfl-rolling-anchor-number"]["records"][0]["statistics"] = []
    values["nfl-rolling-anchor-number"]["aggregates"] = []
    values["nfl-rolling-anchor-number"]["coverage"]["record_statistics"] = [coverage(0)]
    values["nfl-rolling-anchor-number"]["coverage"]["aggregates"] = coverage(0)
    values["nfl-season-string"] = longitudinal_fixture(
        "arena_nfl_longitudinal", "nfl-season-string", "american-football", "1", "number", "season", "period_delta"
    )
    values["nba-career-string"] = longitudinal_fixture(
        "arena_nba_longitudinal",
        "nba-career-string",
        "basketball",
        "1",
        "number",
        "career",
        "cumulative_through_period",
    )
    values["nba-career-string"]["records"][0]["statistics"] = []
    values["nba-career-string"]["coverage"]["record_statistics"] = [coverage(0)]
    for fixture_id in OPERATIONS["arena_soccer_refusal_event"][1]:
        values[fixture_id] = refusal_event_fixture("arena_soccer_refusal_event", fixture_id, "soccer", True)
    values["rights-ineligible"] = {
        "fixture_id": "rights-ineligible",
        "synthetic": True,
        "contains_provider_data": False,
        "sport": "american-football",
    }
    values["unsupported-capability"] = {
        "fixture_id": "unsupported-capability",
        "synthetic": True,
        "contains_provider_data": False,
        "sport": "american-football",
    }
    for fixture_id in OPERATIONS["arena_nba_refusal_event"][1]:
        values[fixture_id] = refusal_event_fixture("arena_nba_refusal_event", fixture_id, "basketball", False)
    return values


def capabilities(operation, output_kind):
    if operation == "arena_nfl_refusal_event":
        return [
            "adapter.can_supply.event.participation_statistics",
            "adapter.can_supply.identity.resolution_evidence",
            "adapter.can_supply.result.coverage.participants",
        ]
    if operation == "arena_nba_refusal_event":
        return [
            "adapter.can_supply.identity.resolution_evidence",
            "adapter.can_supply.result.coverage.participants",
        ]
    return EVENT_CAPABILITIES if output_kind == "event" else LONGITUDINAL_CAPABILITIES


def capability_mappings(output_kind):
    prefix = "longitudinal." if output_kind == "longitudinal" else ""
    pairs = [
        ("adapter.can_supply.result.coverage.participants", "result.coverage.participants"),
        ("adapter.can_supply.result.coverage.actions", "result.coverage.actions"),
        ("adapter.can_supply.result.coverage.statistics", "result.coverage.statistics"),
        ("adapter.can_supply.result.coverage.records", "longitudinal.result.coverage.records"),
        ("adapter.can_supply.result.coverage.aggregates", "longitudinal.result.coverage.aggregates"),
        ("adapter.can_supply.longitudinal.statistics", "longitudinal.statistics"),
        ("adapter.can_supply.event.participation_statistics", "event.participation_statistics"),
        ("adapter.can_supply.event.action.spatial_evidence", "event.action.spatial_evidence"),
        ("adapter.can_supply.identity.resolution_evidence", prefix + "identity.resolution_evidence"),
    ]
    return [
        {"adapter_capability": adapter, "output_kind": output_kind, "record_capability": record}
        for adapter, record in pairs
        if (output_kind == "longitudinal") == record.startswith("longitudinal.")
    ]


def field_evidence(schema):
    rows = []

    def visit(node, pointer=""):
        kind = node["kind"]
        if kind == "fixture-discriminated":
            for branch in node["branches"]:
                visit(branch["shape"], pointer)
        elif kind == "object":
            for name, child in sorted(node["members"].items()):
                child_pointer = pointer + "/" + name
                rows.append(
                    {
                        "pointer_template": child_pointer,
                        "classification": "synthetic-replay-only",
                    }
                )
                visit(child, child_pointer)
        elif kind == "array":
            visit(node["items"], pointer + "/{index}")

    visit(schema)
    unique = {(row["pointer_template"], row["classification"]): row for row in rows}
    return [unique[key] for key in sorted(unique)]


def main():
    registry = json.loads((VENDORED / "data/source_shape_registry_v2.json").read_bytes())
    by_operation = {
        group: {record["operation"]: record for record in registry[group]}
        for group in ("shapes", "operation_contracts", "output_collection_contracts")
    }
    if TARGET.exists():
        for path in TARGET.rglob("*.json"):
            path.unlink()
    else:
        TARGET.mkdir(parents=True)

    record_directories = {
        "shapes": "source-shapes",
        "operation_contracts": "operation-contracts",
        "output_collection_contracts": "output-collection-contracts",
    }
    for group, directory in record_directories.items():
        for record in registry[group]:
            write_json(TARGET / "owner-records" / directory / f"{record['operation']}.json", record)

    fixture_values = fixtures()
    fixture_paths = {}
    for fixture_id, value in fixture_values.items():
        relative = f"fixtures/{fixture_id}.json"
        write_json(TARGET / relative, value)
        fixture_paths[fixture_id] = relative

    authoritative = []
    for fixture_id, value in fixture_values.items():
        for item in value.get("identity", []):
            if item["status"] == "authoritatively_resolved":
                authoritative.append((item["authority_id"], item["entity_type"], item["provider_id"]))
    snapshot = digest_bytes(canonical_bytes(sorted(authoritative)))
    registrations = []
    for index, (authority_id, entity_type, provider_id) in enumerate(sorted(set(authoritative)), 1):
        canonical_id = f"urn:machina:sports:{entity_type}:018f0000-0000-7000-8000-{index:012d}"
        record_id = authority_id
        record_digest_value = digest_bytes(
            canonical_bytes(
                [
                    "sports-skills-synthetic-authority-record-v1",
                    entity_type,
                    provider_id,
                    canonical_id,
                ]
            )
        )
        registrations.append(
            {
                "authority_kind": "synthetic_replay_registry",
                "authority_issuer_id": "sports-skills",
                "authority_issuer_version": "0.33.0",
                "resolver_id": "sports-skills-synthetic-authority",
                "resolver_version": "1",
                "authority_snapshot_digest": snapshot,
                "entity_type": entity_type,
                "provider_namespace": PROVIDER,
                "provider_id": provider_id,
                "canonical_id": canonical_id,
                "authority_record_id": record_id,
                "authority_record_version": "1",
                "authority_record_digest": record_digest_value,
            }
        )
    authority_registry = {
        "schema_version": "machina-identity-authority-registry/1",
        "registry_id": "sports-skills-synthetic-step10-authorities",
        "registry_version": "1",
        "synthetic": True,
        "contains_provider_data": False,
        "registrations": registrations,
    }
    write_json(TARGET / "identity-authority-registry.json", authority_registry)

    resources = {}
    package_operations = []
    basis = {
        "arena_soccer_event": "football-normalized-event",
        "arena_nfl_event": "nfl-normalized-event-summary-drive",
        "arena_nba_event": "nba-normalized-event-play",
        "arena_soccer_longitudinal": "synthetic-only",
        "arena_nfl_longitudinal": "shared-normalized-core-stats",
        "arena_nba_longitudinal": "shared-normalized-core-stats",
        "arena_soccer_refusal_event": "synthetic-only",
        "arena_nfl_refusal_event": "synthetic-only",
        "arena_nba_refusal_event": "synthetic-only",
    }
    for operation in sorted(OPERATIONS):
        output_kind, fixture_ids = OPERATIONS[operation]
        shape = by_operation["shapes"][operation]
        operation_contract = by_operation["operation_contracts"][operation]
        output_contract = by_operation["output_collection_contracts"][operation]
        descriptor = {
            "schema_version": "machina-adapter-descriptor/1",
            "provider_namespace": PROVIDER,
            "provider_package": "sports-skills-arena-step10-operations/1",
            "operation": operation,
            "output_kind": output_kind,
            "capabilities": sorted(capabilities(operation, output_kind)),
            "capability_mappings": capability_mappings(output_kind),
            "module_entrypoint": f"sports_skills.canonical._operations.adapters.{operation}",
        }
        rights = {
            "profile_id": f"sports-skills-{operation}-prototype-only",
            "profile_version": "1",
            "provider_namespace": PROVIDER,
            "operation": operation,
            "data_class": "synthetic-provider-data-free-replay",
            "prototype_only": True,
            "commercial_use": False,
            "allowed_consumer_tiers": ["prototype"],
        }
        rights["rights_profile_digest"] = digest_bytes(
            canonical_bytes(
                [
                    "machina-adapter-rights-profile-v1",
                    rights,
                ]
            )
        )
        argument_schema = {
            "fields": [
                {
                    "name": "fixture_id",
                    "semantic_class": "selector",
                    "value_kind": "string",
                    "required": True,
                    "canonical_lexical_rule": "exact-operation-fixture-enum/1",
                    "provider_parameter_name": "fixture_id",
                    "allowed_values": sorted(fixture_ids),
                }
            ],
            "unknown_fields": "forbidden",
            "secret_fields": "forbidden",
        }
        manifest_fixtures = []
        for fixture_id in sorted(fixture_ids):
            path = fixture_paths[fixture_id]
            payload = (TARGET / path).read_bytes()
            manifest_fixtures.append(
                {
                    "owner": "sports-skills",
                    "artifact_kind": "synthetic-normalized-replay-json",
                    "fixture_id": fixture_id,
                    "synthetic": True,
                    "contains_provider_data": False,
                    "media_type": "application/json",
                    "original_bytes_digest": digest_bytes(payload),
                    "source_shape_ref": operation_contract["source_shape_ref"],
                    "native_semantics_basis": basis[operation],
                    "path": path,
                }
            )
        fixture_manifest = {
            "schema_version": "sports-skills-fixture-manifest/1",
            "operation": operation,
            "fixture_ids": sorted(fixture_ids),
            "fixtures": manifest_fixtures,
            "field_evidence": field_evidence(shape["artifact_schema"]),
        }
        link = {
            "provider_namespace": PROVIDER,
            "provider_package": "sports-skills-arena-step10-operations/1",
            "package_name": "sports-skills",
            "approved_distribution_version": "0.33.0",
            "release_id": "canonical-evidence-step10-operations",
            "operation": operation,
            "output_kind": output_kind,
            "descriptor_digest": record_digest(descriptor),
            "rights_profile_digest": record_digest(rights),
            "source_shape_ref": operation_contract["source_shape_ref"],
            "source_shape_digest": record_digest(shape),
            "operation_contract_digest": record_digest(operation_contract),
            "output_collection_contract_digest": record_digest(output_contract),
            "operation_argument_schema_digest": record_digest(argument_schema),
            "fixture_manifest_digest": record_digest(fixture_manifest),
        }
        paths = {}
        for name, value in (
            ("package_link", link),
            ("descriptor", descriptor),
            ("rights_profile", rights),
            ("argument_schema", argument_schema),
            ("fixture_manifest", fixture_manifest),
        ):
            relative = f"{name.replace('_', '-')}s/{operation}.json"
            write_json(TARGET / relative, value)
            paths[f"{name}_path"] = relative
        package_operations.append({"operation": operation, "output_kind": output_kind, **paths})

    for path in sorted(TARGET.rglob("*.json")):
        relative = path.relative_to(TARGET).as_posix()
        resources[relative] = digest_bytes(path.read_bytes())
    package = {
        "schema_version": "sports-skills-arena-step10-operations/1",
        "provider_namespace": PROVIDER,
        "provider_package": "sports-skills-arena-step10-operations/1",
        "package_name": "sports-skills",
        "approved_distribution_version": "0.33.0",
        "release_id": "canonical-evidence-step10-operations",
        "owner_distribution": {
            "name": "machina-sports-canonical",
            "version": "0.4.1",
            "wheel_sha256": "cd454eb8411b5639af7313c713276bfa4a0dc72aab037b66ba451bc3e0f090bd",
        },
        "identity_authority_registry_path": "identity-authority-registry.json",
        "operations": package_operations,
        "resource_digests": resources,
    }
    write_json(TARGET / "package.json", package)


if __name__ == "__main__":
    main()
