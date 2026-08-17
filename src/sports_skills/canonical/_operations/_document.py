"""Build canonical documents only from one validated packaged source artifact."""

import copy

from .._vendored import successor

_PROVIDER = "sports-skills/espn"
_OBSERVED_AT = "2026-08-17T00:00:00Z"
_MEDTOP = {
    "soccer": "20001065",
    "american-football": "20000865",
    "basketball": "20000875",
}


def _record(records, kind, source_record_id, **variant):
    record = {
        "id": f"synthetic-evidence-{len(records)}",
        "version": "1",
        "kind": kind,
        "source": {"kind": "machina_record", "record_id": source_record_id},
    }
    record.update(variant)
    record["digest"] = successor.evidence_record_digest(record)
    records.append(record)
    return f"/evidence_records/{len(records) - 1}"


def _source_value(records, artifact, pointer, fixture_id):
    return _record(
        records,
        "source_value",
        f"sports-skills-synthetic:{fixture_id}:{pointer}",
        source_value={
            "schema_version": "machina-source-value-evidence/1",
            "artifact_digest": artifact.artifact_digest,
            "value_pointer": pointer,
            "value_digest": successor.derive_source_value_digest(artifact.artifact_digest, pointer),
        },
    )


def _template_ref(template):
    return {
        "binding_id": template["binding_id"],
        "binding_version": template["binding_version"],
        "binding_digest": successor._sha256(["machina-source-semantic-binding-template-v1", template]),
    }


def _identity(records, artifact, source, registry, fixture_id, pointer):
    entity_type = source["entity_type"]
    provider_id = source["provider_id"]
    status = source["status"]
    provider = {"namespace": _PROVIDER, "id": provider_id}
    if status == "authoritatively_resolved":
        matches = [
            item
            for item in registry["registrations"]
            if item["authority_record_id"] == source["authority_id"]
            and item["entity_type"] == entity_type
            and item["provider_id"] == provider_id
        ]
        if len(matches) != 1:
            raise successor.CanonicalContractError("synthetic-authority-registration-mismatch")
        registration = matches[0]
        authority = {
            "kind": registration["authority_kind"],
            "issuer_id": registration["authority_issuer_id"],
            "issuer_version": registration["authority_issuer_version"],
            "resolver_id": registration["resolver_id"],
            "resolver_version": registration["resolver_version"],
            "snapshot_digest": registration["authority_snapshot_digest"],
            "record_id": registration["authority_record_id"],
            "record_version": registration["authority_record_version"],
            "digest": registration["authority_record_digest"],
        }
        method_source = _record(
            records,
            "identity_authority_record",
            f"sports-skills-synthetic-authority:{source['authority_id']}",
        )
        return {
            "entity_type": entity_type,
            "status": status,
            "resolution_method": "authoritative_registry",
            "provider": provider,
            "canonical_id": registration["canonical_id"],
            "authority": authority,
            "method_source_ref": method_source,
        }
    method_source = _source_value(records, artifact, pointer, fixture_id)
    identity = {
        "entity_type": entity_type,
        "status": status,
        "resolution_method": "provider_native" if status == "provider_scoped" else "declared",
        "provider": provider,
        "method_source_ref": method_source,
    }
    if status == "provider_scoped":
        identity["provider_scoped_id"] = successor._provider_scoped_id(_PROVIDER, entity_type, provider_id)
    elif status == "ambiguous":
        identity["candidate_ids"] = [
            f"urn:machina:candidate:{provider_id}:a",
            f"urn:machina:candidate:{provider_id}:b",
        ]
    return identity


def _source_fact(records, artifact, trust, fixture_id, canonical_pointer, source_pointer):
    templates = trust.source_shape["statistic_source_binding_templates"]
    matches = [
        item
        for item in templates
        if successor._pointer_matches_pattern(canonical_pointer, item["canonical_statistic_pointer_pattern"])
    ]
    if len(matches) != 1:
        raise successor.CanonicalContractError("statistic-source-binding-not-unique")
    template = matches[0]
    parsed = successor._reparse_source_artifact(artifact, trust)
    raw = successor.resolve_json_pointer(parsed, source_pointer)
    lexical = successor._parse_statistic_source(raw, template["source_representation"], template["value_kind"])
    value = {"kind": template["value_kind"], "lexical": lexical}
    disposition = template["unit_disposition"]
    if disposition["kind"] == "unit":
        value["unit"] = successor._thaw(disposition["unit"])
    return {
        "kind": template["statistic_kind"],
        "scope": template["statistic_scope"],
        "name": template["statistic_name"],
        "value": value,
        "source_ref": _source_value(records, artifact, source_pointer, fixture_id),
    }


def _coverage(records, artifact, trust, document, fixture_id, kind):
    claims = []
    coverage = []
    if kind == "event":
        actual = ["/observation/participants"]
        if "actions" in document["observation"]:
            actual.append("/observation/actions")
        for index, participant in enumerate(document["observation"]["participants"]):
            if "statistics" in participant:
                actual.append(f"/observation/participants/{index}/statistics")
    else:
        actual = ["/records", "/aggregates"]
        actual.extend(
            f"/records/{index}/statistics" for index, record in enumerate(document["records"]) if "statistics" in record
        )
    promises = trust.output_collection_contract["promised_collections"]
    for pointer in actual:
        matches = [
            promise for promise in promises if successor._pointer_matches_pattern(pointer, promise["pointer_pattern"])
        ]
        if len(matches) != 1:
            raise successor.CanonicalContractError("unpromised-managed-collection-present")
        promise = matches[0]
        bindings = successor._bindings_from_pointer(promise["pointer_pattern"], pointer)
        base = successor._instantiate_template(promise["source_base_pointer_template"], bindings)
        source_fields = {}
        for name, contract in promise["source_fields"].items():
            source_fields[name] = {
                key: [successor._instantiate_template(item, bindings) for item in value]
                if key == "value_pointer_templates"
                else value
                for key, value in contract.items()
            }
        parsed = successor._reparse_source_artifact(artifact, trust)
        total_pointer = source_fields["total"]["value_pointer_templates"][0]
        truncated_pointer = source_fields["truncation"]["value_pointer_templates"][0]
        cursor_pointer = source_fields["cursor"]["value_pointer_templates"][0]
        page_cap_pointer = source_fields["page_cap"]["value_pointer_templates"][0]
        request_limit_pointer = source_fields["request_limit"]["value_pointer_templates"][0]
        total = int(str(successor.resolve_json_pointer(parsed, total_pointer)))
        truncated = bool(successor.resolve_json_pointer(parsed, truncated_pointer))
        successor.resolve_json_pointer(parsed, cursor_pointer)
        page_cap = int(str(successor.resolve_json_pointer(parsed, page_cap_pointer)))
        request_limit = int(str(successor.resolve_json_pointer(parsed, request_limit_pointer)))
        nested = {
            "schema_version": "machina-coverage-source-evidence/1",
            "collection_pointer": pointer,
            "artifact_digest": artifact.artifact_digest,
            "fields": source_fields,
            "reported_total": {"state": "known", "count": total, "value_pointers": [total_pointer]},
            "truncation": {
                "state": "truncated" if truncated else "not_truncated",
                "value_pointers": [truncated_pointer],
            },
            "cursor": {
                "state": "present",
                "value_pointers": [cursor_pointer],
                "value_digest": successor.derive_source_value_digest(artifact.artifact_digest, cursor_pointer),
            },
            "page_cap": {"state": "known", "count": page_cap, "value_pointers": [page_cap_pointer]},
            "request_limit": {"state": "known", "count": request_limit, "value_pointers": [request_limit_pointer]},
        }
        source_ref = _record(
            records,
            "coverage_source",
            f"sports-skills-synthetic:{fixture_id}:{base}",
            coverage_source=nested,
        )
        target = "statistics"
        if pointer.endswith("/participants"):
            target = "participants"
        elif pointer.endswith("/actions"):
            target = "actions"
        elif pointer == "/records":
            target = "records"
        elif pointer == "/aggregates":
            target = "aggregates"
        collection = successor.resolve_json_pointer(document, pointer)
        claims.append({"target": target, "collection_pointer": pointer, "source_ref": source_ref})
        coverage.append(
            {
                "target": target,
                "collection_pointer": pointer,
                "returned_count": len(collection),
                "available_total": {"state": "known", "count": total},
                "completeness": "partial",
                "truncation": "truncated" if truncated else "not_truncated",
                "limitations": [],
                "source_ref": source_ref,
                "limit": request_limit,
            }
        )
    return claims, coverage


def _event_document(artifact, request, trust, parsed, registry):
    fixture_id = parsed["fixture_id"]
    records = []
    source_event = parsed["event"]
    reduced = source_event["start"]["state"] == "bounded"
    event = {
        "provider_id": source_event["id"],
        "label": f"Synthetic event {fixture_id}",
        "status": source_event["status"],
    }
    if reduced:
        lower, upper = successor.derive_bounds(source_event["start"]["value"], "minute")
        event["temporal_evidence"] = {
            "kind": "start",
            "source_value": source_event["start"]["value"],
            "precision": "minute",
            "lower_inclusive": lower,
            "upper_exclusive": upper,
            "provenance": {
                "derivation": "declared_precision_interval",
                "adapter": "sports-skills-arena-step10",
                "version": "1",
            },
        }
    else:
        event["start_time"] = source_event["start"]["value"]
    participants = []
    operation = trust.descriptor["operation"]
    include_actions = operation != "arena_nba_refusal_event" or request["output_mode"] == "operational_only"
    include_statistics = "refusal" not in operation
    for p_index, source_participant in enumerate(source_event["participants"]):
        participant = {
            "kind": "team" if source_participant["kind"] == "team" else "individual",
            "provider_id": source_participant["id"],
            "name": f"Synthetic participant {p_index + 1}",
        }
        for key in ("alignment", "score"):
            if key in source_participant:
                participant[key] = source_participant[key]
        if include_statistics:
            participant["statistics"] = []
            for s_index, _source_statistic in enumerate(source_participant["statistics"]):
                canonical_pointer = f"/observation/participants/{p_index}/statistics/{s_index}"
                source_pointer = f"/event/participants/{p_index}/statistics/{s_index}/value"
                participant["statistics"].append(
                    _source_fact(records, artifact, trust, fixture_id, canonical_pointer, source_pointer)
                )
        participants.append(participant)
    observation = {
        "provider": {"namespace": _PROVIDER, "family": "synthetic-replay"},
        "observed_at": _OBSERVED_AT,
        "adapter": {
            "name": trust.descriptor["module_entrypoint"],
            "version": "1",
            "source_refs": [{"kind": "artifact-class", "value": "synthetic-normalized-replay"}],
        },
        "rights": {
            "data_class": trust.rights_profile["data_class"],
            "prototype_only": trust.rights_profile["prototype_only"],
            "commercial_use": trust.rights_profile["commercial_use"],
        },
        "sport": {"medtop": _MEDTOP[parsed["sport"]], "key": parsed["sport"]},
        "competition": {
            "provider_id": source_event["competition_id"],
            "name": "Synthetic competition",
        },
        "event": event,
        "participants": participants,
    }
    if include_actions:
        actions = []
        include_spatial = "refusal" not in operation or request["output_mode"] == "operational_only"
        coordinate_template = next(
            (
                item
                for item in trust.source_shape["semantic_binding_templates"]
                if item["semantic_kind"] == "source_position_coordinates"
            ),
            None,
        )
        coordinate_ref = _template_ref(coordinate_template) if coordinate_template else None
        for index, source_action in enumerate(source_event["actions"]):
            action = {
                "provider_id": source_action["id"],
                "label": "Synthetic action",
            }
            if not include_spatial:
                actions.append(action)
                continue
            source_ref = _record(
                records,
                "source_coordinates",
                f"sports-skills-synthetic:{fixture_id}:coordinates:{index}",
                source_coordinates={
                    "schema_version": "machina-source-coordinate-evidence/1",
                    "artifact_digest": artifact.artifact_digest,
                    "x_pointer": f"/event/actions/{index}/spatial/x",
                    "y_pointer": f"/event/actions/{index}/spatial/y",
                },
            )
            spatial = {
                "source_position_source": {
                    "source_ref": source_ref,
                    "binding_template_ref": coordinate_ref,
                }
            }
            semantic_kinds = {item["semantic_kind"] for item in trust.source_shape["semantic_binding_templates"]}
            if "distance" in source_action.get("spatial", {}) and "source_reported_distance" in semantic_kinds:
                spatial["distance"] = {"origin": "source_reported", "source_ref": source_ref}
            if "zone" in source_action.get("spatial", {}) and "provider_native_zone" in semantic_kinds:
                spatial["zone"] = {"origin": "provider_native", "source_ref": source_ref}
            action["spatial_evidence"] = spatial
            actions.append(action)
        observation["actions"] = actions
    document = {
        "schema_version": successor.SUCCESSOR_SCHEMA_VERSION,
        "observation": observation,
        "coordinate_system_registry": [{"id": "normalized-pitch", "version": "1"}],
        "period_registry": copy.deepcopy(source_event["periods"]),
        "evidence_records": records,
        "collection_claims": [],
        "coverage": [],
        "identity_subjects": [],
        "identity_evidence": [],
    }
    identity_by_key = {}
    for index, source_identity in enumerate(parsed["identity"]):
        built = _identity(records, artifact, source_identity, registry, fixture_id, f"/identity/{index}")
        identity_by_key[(built["entity_type"], built["provider"]["id"])] = len(document["identity_evidence"])
        document["identity_evidence"].append(built)
    inventory = [
        ("competition", "/observation/competition/provider_id", source_event["competition_id"]),
        ("event", "/observation/event/provider_id", source_event["id"]),
    ]
    inventory.extend(
        (
            "team" if participant["kind"] == "team" else "athlete",
            f"/observation/participants/{index}/provider_id",
            participant["provider_id"],
        )
        for index, participant in enumerate(participants)
    )
    for entity_type, pointer, provider_id in inventory:
        identity_index = identity_by_key[(entity_type, provider_id)]
        document["identity_subjects"].append(
            {
                "entity_type": entity_type,
                "subject_ref": pointer.rsplit("/provider_id", 1)[0],
                "identity_evidence_ref": f"/identity_evidence/{identity_index}",
                "inherited_provider": {
                    "provider_id_ref": pointer,
                    "provider": {"namespace": _PROVIDER, "id": provider_id},
                },
            }
        )
    claims, coverage = _coverage(records, artifact, trust, document, fixture_id, "event")
    document["collection_claims"] = claims
    document["coverage"] = coverage
    return document


def _longitudinal_document(artifact, request, trust, parsed, registry):
    fixture_id = parsed["fixture_id"]
    records = []
    identity_evidence = []
    identity_by_key = {}
    for index, source_identity in enumerate(parsed["identity"]):
        built = _identity(records, artifact, source_identity, registry, fixture_id, f"/identity/{index}")
        identity_by_key[(built["entity_type"], built["provider"]["id"])] = len(identity_evidence)
        identity_evidence.append(built)
    subject_index = identity_by_key[(parsed["subject"]["entity_type"], parsed["subject"]["provider_id"])]
    subject = {"entity_type": parsed["subject"]["entity_type"], "identity_ref": f"/identity_evidence/{subject_index}"}
    source_scope = parsed["scope"]
    scope_kind = source_scope["kind"].replace("-", "_")
    scope = {"kind": scope_kind, "sport": parsed["sport"]}
    if scope_kind == "season":
        season_index = identity_by_key[("season", source_scope["season_id"])]
        scope["season_identity_ref"] = f"/identity_evidence/{season_index}"
        scope["stated_boundary"] = copy.deepcopy(parsed["records"][0]["period"]["boundary"])
    elif scope_kind == "date_range":
        scope["range"] = {
            "schema_version": "canonical-temporal-range/1",
            "start": {"state": "exact", "instant": source_scope["start"], "source_ref": "/synthetic/scope/start"},
            "end": {"state": "exact", "instant": source_scope["end"], "source_ref": "/synthetic/scope/end"},
            "interval_semantics": "start_inclusive_end_exclusive",
        }
    elif scope_kind == "rolling_window":
        anchor_source = source_scope["anchor"]
        source_identity = {
            "entity_type": "event",
            "provider_id": anchor_source["provider_id"],
            "resolution_method": "synthetic_provider_scoped",
            "status": "provider_scoped",
        }
        event_identity = _identity(
            records, artifact, source_identity, registry, fixture_id, "/scope/anchor/provider_id"
        )
        event_index = len(identity_evidence)
        identity_evidence.append(event_identity)
        templates = [
            item
            for item in trust.source_shape["semantic_binding_templates"]
            if item["semantic_kind"] == "rolling_event_anchor"
        ]
        source_binding_ref = _record(
            records,
            "rolling_event_anchor_source",
            f"sports-skills-synthetic:{fixture_id}:rolling-anchor",
            rolling_event_anchor_source={
                "artifact_digest": artifact.artifact_digest,
                "binding_template_ref": _template_ref(templates[0]),
            },
        )
        event_source_ref = _source_value(records, artifact, "/scope/anchor/source_record_id", fixture_id)
        scope.update(
            {
                "window_size": int(str(source_scope["window_size"])),
                "window_unit": "event",
                "anchor": {
                    "kind": "event",
                    "event_identity_ref": f"/identity_evidence/{event_index}",
                    "event_source_ref": event_source_ref,
                    "source_binding_ref": source_binding_ref,
                },
            }
        )
    output_records = []
    period_templates = [
        item
        for item in trust.source_shape["semantic_binding_templates"]
        if item["semantic_kind"] == "longitudinal_period" and fixture_id in item["fixture_ids"]
    ]
    if len(period_templates) != 1:
        raise successor.CanonicalContractError("longitudinal-period-template-not-unique")
    for r_index, source_record in enumerate(parsed["records"]):
        period_source_ref = _record(
            records,
            "longitudinal_period_source",
            f"sports-skills-synthetic:{fixture_id}:period:{r_index}",
            longitudinal_period_source={
                "artifact_digest": artifact.artifact_digest,
                "binding_template_ref": _template_ref(period_templates[0]),
            },
        )
        handle = successor._load_source_value_handle(artifact, period_templates[0], {"record_index": r_index}, trust)
        period = successor._build_period_descriptor(handle, record_ref=f"/records/{r_index}", loaded_trust=trust)
        semantics = source_record["semantics"]
        record = {
            **period,
            "period_source_ref": period_source_ref,
            "semantics": semantics,
            "scope": copy.deepcopy(scope),
            "statistics": [],
        }
        for s_index, _source_statistic in enumerate(source_record["statistics"]):
            canonical_pointer = f"/records/{r_index}/statistics/{s_index}"
            source_pointer = f"/records/{r_index}/statistics/{s_index}/value"
            record["statistics"].append(
                _source_fact(records, artifact, trust, fixture_id, canonical_pointer, source_pointer)
            )
        output_records.append(record)
    aggregates = []
    for index, _source_aggregate in enumerate(parsed["aggregates"]):
        aggregates.append(
            _source_fact(records, artifact, trust, fixture_id, f"/aggregates/{index}", f"/aggregates/{index}/value")
        )
    document = {
        "schema_version": successor.LONGITUDINAL_SCHEMA_VERSION,
        "observed_at": _OBSERVED_AT,
        "subject": subject,
        "scope": scope,
        "records": output_records,
        "aggregates": aggregates,
        "evidence_records": records,
        "collection_claims": [],
        "coverage": [],
        "identity_subjects": [],
        "identity_evidence": identity_evidence,
        "provenance": {
            "schema_version": "machina-successor-provenance/1",
            "canonical_input_version": successor.LONGITUDINAL_SCHEMA_VERSION,
            "canonical_package": copy.deepcopy(dict(trust.package_release)),
            "adapter": {
                "provider_namespace": _PROVIDER,
                "operation": trust.descriptor["operation"],
                "descriptor_digest": successor._sha256(["machina-adapter-descriptor-v1", trust.descriptor]),
            },
            "source_artifact_digests": [artifact.artifact_digest],
        },
        "rights": copy.deepcopy(dict(trust.rights_profile)),
    }
    for index, identity in enumerate(identity_evidence):
        if identity["entity_type"] == subject["entity_type"] and index == subject_index:
            subject_ref = "/subject"
        elif identity["entity_type"] == "season":
            subject_ref = "/scope/season_identity_ref"
        else:
            subject_ref = "/scope/anchor"
        document["identity_subjects"].append(
            {
                "entity_type": identity["entity_type"],
                "subject_ref": subject_ref,
                "identity_evidence_ref": f"/identity_evidence/{index}",
            }
        )
    claims, coverage = _coverage(records, artifact, trust, document, fixture_id, "longitudinal")
    document["collection_claims"] = claims
    document["coverage"] = coverage
    return document


def build_document(artifact, argument_handle, request, trust):
    parsed = successor._thaw(artifact.parsed_projection)
    registry = successor._thaw(trust.identity_registry)
    if request["output_kind"] == "event":
        return _event_document(artifact, request, trust, parsed, registry)
    return _longitudinal_document(artifact, request, trust, parsed, registry)
