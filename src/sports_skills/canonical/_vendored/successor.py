"""Opt-in Canonical Evidence Contract Phase 1 runtime.

The released 0.2 APIs remain in :mod:`observation` and :mod:`serialize`.  This
module is additive and deliberately does not teach those functions about the
successor versions.  Construction helpers are private; the sequence-owning
``execute_adapter_operation`` function is the only engine that may call them.

Vendored byte-exact into ``sports-skills``: Python 3.9-compatible and standard
library only.
"""

from __future__ import annotations

import copy
import datetime
import decimal
import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol

from . import (
    ACCEPTED_SCHEMA_VERSIONS,
    LONGITUDINAL_MACHINA_SCHEMA_VERSION,
    LONGITUDINAL_SCHEMA_VERSION,
    SUCCESSOR_MACHINA_SCHEMA_VERSION,
    SUCCESSOR_PROFILE_VERSION,
    SUCCESSOR_SCHEMA_VERSION,
)
from .observation import derive_bounds, validate_observation
from .serialize import shared_context


_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,127}$")
_NAMESPACE_SEGMENT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{0,63}$")
_INTEGER_RE = re.compile(r"^(?:0|-[1-9][0-9]*|[1-9][0-9]*)$")
_NON_NEGATIVE_INTEGER_RE = re.compile(r"^(?:0|[1-9][0-9]*)$")
_DECIMAL_RE = re.compile(r"^-?(?:0|[1-9][0-9]*)\.(?:0|[0-9]*[1-9])$")
_SPATIAL_RE = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.(?:0|[0-9]*[1-9]))?$")
_DURATION_RE = re.compile(
    r"^P(?:(?:0|[1-9][0-9]*)D)?(?:T(?:(?:0|[1-9][0-9]*)H)?"
    r"(?:(?:0|[1-9][0-9]*)M)?(?:(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?S)?)?$"
)
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_POINTER_ESCAPE_RE = re.compile(r"~(?:[^01]|$)")
_UUID7_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_RFC3339_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.[0-9]+)?"
    r"(?:Z|[+-](\d{2}):(\d{2}))$"
)

_EVENT_TOP_KEYS = {
    "schema_version", "observation", "coordinate_system_registry",
    "period_registry", "evidence_records", "collection_claims", "coverage",
    "identity_subjects", "identity_evidence",
}
_LONGITUDINAL_TOP_KEYS = {
    "schema_version", "observed_at", "subject", "scope", "records",
    "aggregates", "evidence_records", "collection_claims", "coverage",
    "identity_subjects", "identity_evidence", "provenance", "rights",
}
_PROVIDER_NAMESPACE_FIELDS = frozenset({
    "provider_namespace", "requested_provider",
})
_TOTAL_STATES = frozenset({"known", "unavailable"})
_COMPLETENESS = frozenset({"complete", "partial", "unknown"})
_STATISTIC_KINDS = frozenset({"official", "provider_native", "derived"})
_STATISTIC_SCOPES = frozenset({
    "event", "period", "season", "career", "rolling_window", "date_range",
})
_IDENTITY_STATUSES = frozenset({
    "provider_scoped", "authoritatively_resolved", "ambiguous", "unresolved",
})
_IDENTITY_METHODS = frozenset({
    "provider_native", "declared", "ordinal_derived", "authoritative_registry",
})
_ENTITY_TYPES = frozenset({
    "competition", "season", "phase", "site", "event", "team", "athlete",
})
_OUTPUT_MODES = frozenset({"operational_only", "with_iptc_graph"})
_CONSUMER_TIERS = frozenset({"prototype", "production"})


class CanonicalContractError(ValueError):
    """A closed Phase 1 contract refusal."""

    def __init__(self, reason, details=()):
        self.reason = reason
        self.details = tuple(details)
        message = reason
        if self.details:
            message += ":\n" + "\n".join("  - " + item for item in self.details)
        super().__init__(message)


class GraphSelectionRefused(CanonicalContractError):
    """A graph-selected operation cannot produce a complete trusted graph."""


class _IdentityResolutionProvider(Protocol):
    resolver_id: str
    resolver_version: str

    def resolve(self, request: Mapping[str, Any]) -> Mapping[str, Any]: ...


class _DuplicateKey(ValueError):
    pass


class _JsonNumber(str):
    """Raw RFC 8259 number token retained for attested source parsing."""


def _pairs_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey("duplicate JSON object key: {0}".format(key))
        result[key] = value
    return result


def _reject_nonfinite(value):
    raise ValueError("non-finite JSON constant is forbidden: {0}".format(value))


def _contains_invalid_text(value):
    if isinstance(value, str):
        if "\ufffd" in value:
            return True
        return any(0xD800 <= ord(character) <= 0xDFFF for character in value)
    if isinstance(value, Mapping):
        return any(_contains_invalid_text(key) or _contains_invalid_text(item)
                   for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_invalid_text(item) for item in value)
    return False


def _strict_json_object(data, *, preserve_numbers=False):
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError("UTF-8 BOM is forbidden")
    try:
        text = data.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise ValueError("malformed UTF-8") from error
    if "\ufffd" in text:
        raise ValueError("U+FFFD is forbidden")
    options = {
        "object_pairs_hook": _pairs_no_duplicates,
        "parse_constant": _reject_nonfinite,
    }
    if preserve_numbers:
        options["parse_int"] = _JsonNumber
        options["parse_float"] = _JsonNumber
    try:
        value = json.loads(text, **options)
    except (json.JSONDecodeError, _DuplicateKey, ValueError) as error:
        raise ValueError("invalid strict JSON: {0}".format(error)) from error
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    if _contains_invalid_text(value):
        raise ValueError("U+FFFD and unpaired surrogates are forbidden")
    return value


def canonical_json_bytes(value):
    """D4 canonical UTF-8 JSON bytes used by every Phase 1 digest."""
    _assert_serializable(value)
    value = _canonical_plain(value)
    try:
        text = json.dumps(
            value, ensure_ascii=False, allow_nan=False, sort_keys=True,
            separators=(",", ":"),
        )
        encoded = text.encode("utf-8", "strict")
    except (TypeError, ValueError, UnicodeError) as error:
        raise TypeError("value is not canonical-JSON serializable") from error
    if b"\xef\xbf\xbd" in encoded:
        raise ValueError("U+FFFD is forbidden")
    return encoded


def _canonical_plain(value):
    if isinstance(value, Mapping):
        return {key: _canonical_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_plain(item) for item in value]
    return value


def _assert_serializable(value, path="$", seen=None):
    if seen is None:
        seen = set()
    if isinstance(value, _RuntimeOnly):
        raise TypeError("{0}: runtime-only object cannot serialize".format(path))
    if isinstance(value, bytes) or callable(value):
        raise TypeError("{0}: bytes and callables cannot serialize".format(path))
    if isinstance(value, float):
        raise TypeError("{0}: binary floats are forbidden".format(path))
    if isinstance(value, str):
        if _contains_invalid_text(value):
            raise ValueError("{0}: invalid Unicode text".format(path))
        return
    if value is None or isinstance(value, (bool, int)):
        return
    marker = id(value)
    if marker in seen:
        raise TypeError("{0}: cyclic value".format(path))
    if isinstance(value, Mapping):
        seen.add(marker)
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("{0}: object keys must be strings".format(path))
            _assert_serializable(key, path + ".<key>", seen)
            _assert_serializable(item, path + "." + key, seen)
        seen.remove(marker)
        return
    if isinstance(value, (list, tuple)):
        seen.add(marker)
        for index, item in enumerate(value):
            _assert_serializable(item, "{0}[{1}]".format(path, index), seen)
        seen.remove(marker)
        return
    raise TypeError("{0}: unsupported runtime value {1}".format(path, type(value).__name__))


def _sha256(preimage):
    return "sha256:" + hashlib.sha256(canonical_json_bytes(preimage)).hexdigest()


def validate_provider_namespace(value):
    if not isinstance(value, str):
        raise ValueError("ProviderNamespace must be text")
    try:
        encoded = value.encode("ascii", "strict")
    except UnicodeEncodeError as error:
        raise ValueError("ProviderNamespace must be ASCII") from error
    if len(encoded) > 129:
        raise ValueError("ProviderNamespace is longer than 129 bytes")
    segments = value.split("/")
    if len(segments) not in (1, 2) or any(
            _NAMESPACE_SEGMENT_RE.fullmatch(segment) is None
            for segment in segments):
        raise ValueError("invalid ProviderNamespace")
    return value


def validate_json_pointer(pointer):
    if not isinstance(pointer, str):
        raise ValueError("JSON pointer must be text")
    if pointer == "":
        return pointer
    if not pointer.startswith("/") or pointer.startswith("//"):
        raise ValueError("JSON pointer must be canonical RFC 6901")
    if "#" in pointer or _POINTER_ESCAPE_RE.search(pointer):
        raise ValueError("JSON pointer has invalid syntax")
    return pointer


def _pointer_parts(pointer):
    validate_json_pointer(pointer)
    if not pointer:
        return []
    return [part.replace("~1", "/").replace("~0", "~")
            for part in pointer[1:].split("/")]


def resolve_json_pointer(document, pointer):
    node = document
    for part in _pointer_parts(pointer):
        if isinstance(node, Mapping):
            if part not in node:
                raise ValueError("JSON pointer does not resolve: {0}".format(pointer))
            node = node[part]
        elif isinstance(node, (list, tuple)):
            if not _NON_NEGATIVE_INTEGER_RE.fullmatch(part):
                raise ValueError("array pointer segment is not canonical")
            index = int(part)
            if index >= len(node):
                raise ValueError("JSON pointer does not resolve: {0}".format(pointer))
            node = node[index]
        else:
            raise ValueError("JSON pointer traverses a scalar: {0}".format(pointer))
    return node


def validate_statistic_lexical(kind, lexical):
    if not isinstance(lexical, str) or _contains_invalid_text(lexical):
        raise ValueError("statistic lexical value must be valid text")
    valid = False
    if kind == "integer":
        valid = _INTEGER_RE.fullmatch(lexical) is not None
    elif kind == "decimal":
        valid = _DECIMAL_RE.fullmatch(lexical) is not None
        if valid and lexical.startswith("-") and decimal.Decimal(lexical) == 0:
            valid = False
    elif kind == "boolean":
        valid = lexical in ("true", "false")
    elif kind == "duration":
        valid = _valid_duration(lexical)
    elif kind == "text":
        valid = bool(lexical)
    else:
        raise ValueError("unknown statistic value kind")
    if not valid:
        raise ValueError("non-canonical {0} lexical value".format(kind))
    return lexical


def _valid_duration(value):
    if value == "PT0S":
        return True
    if _DURATION_RE.fullmatch(value) is None or value in ("P", "PT"):
        return False
    if value.startswith("P0D") or "T0H" in value or "H0M" in value:
        return False
    return True


def validate_spatial_decimal(value):
    if not isinstance(value, str) or _SPATIAL_RE.fullmatch(value) is None:
        raise ValueError("SpatialDecimal must be a canonical JSON string")
    parsed = decimal.Decimal(value)
    if parsed == 0 and value.startswith("-"):
        raise ValueError("negative zero is forbidden")
    return value


def _parse_rfc3339(value):
    if not isinstance(value, str) or _RFC3339_RE.fullmatch(value) is None:
        raise ValueError("expected exact RFC 3339 instant")
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError("invalid RFC 3339 instant") from error


def _validate_endpoint(endpoint):
    if not isinstance(endpoint, Mapping):
        raise ValueError("temporal endpoint must be an object")
    state = endpoint.get("state")
    if state == "exact":
        if set(endpoint) != {"state", "instant", "source_ref"}:
            raise ValueError("exact endpoint has an invalid member set")
        validate_json_pointer(endpoint["source_ref"])
        return state, _parse_rfc3339(endpoint["instant"]), None
    if state != "bounded":
        raise ValueError("temporal endpoint state must be exact or bounded")
    expected = {
        "state", "source_value", "precision", "lower_inclusive",
        "upper_exclusive", "provenance", "source_ref",
    }
    if set(endpoint) != expected or endpoint.get("precision") != "minute":
        raise ValueError("bounded endpoint has an invalid member set")
    validate_json_pointer(endpoint["source_ref"])
    lower, upper = derive_bounds(endpoint["source_value"], "minute")
    if endpoint["lower_inclusive"] != lower or endpoint["upper_exclusive"] != upper:
        raise ValueError("bounded endpoint is not recomputable")
    return state, _parse_rfc3339(lower), _parse_rfc3339(upper)


def validate_temporal_range(value):
    if not isinstance(value, Mapping) or set(value) != {
            "schema_version", "interval_semantics", "start", "end"}:
        raise ValueError("TemporalRangeV1 has an invalid member set")
    if value.get("schema_version") != "canonical-temporal-range/1" or value.get(
            "interval_semantics") != "start_inclusive_end_exclusive":
        raise ValueError("invalid temporal range contract")
    start_state, start_lower, start_upper = _validate_endpoint(value["start"])
    end_state, end_lower, _end_upper = _validate_endpoint(value["end"])
    if start_state == "exact" and end_state == "exact":
        valid = start_lower < end_lower
    elif start_state == "bounded":
        valid = start_upper <= end_lower
    else:
        valid = start_lower < end_lower
    if not valid:
        raise ValueError("temporal range is empty, inverted, or uncertain-overlapping")
    return value


def derive_source_value_digest(artifact_digest, pointer, binding_ref=None):
    if _DIGEST_RE.fullmatch(artifact_digest or "") is None:
        raise ValueError("invalid artifact digest")
    validate_json_pointer(pointer)
    if binding_ref is None:
        preimage = ["machina-source-value-ref-digest-v1", artifact_digest, pointer]
    else:
        required = ("binding_id", "binding_version", "binding_digest")
        if not isinstance(binding_ref, Mapping) or any(key not in binding_ref for key in required):
            raise ValueError("invalid binding ref")
        preimage = ["machina-bound-source-value-ref-digest-v1", artifact_digest,
                    pointer] + [binding_ref[key] for key in required]
    return _sha256(preimage)


def derive_source_marker_digest(artifact_digest, pointer, probe_ref=None):
    if _DIGEST_RE.fullmatch(artifact_digest or "") is None:
        raise ValueError("invalid artifact digest")
    validate_json_pointer(pointer)
    if probe_ref is None:
        preimage = ["machina-source-marker-ref-digest-v1", artifact_digest, pointer]
    else:
        required = ("probe_template_id", "probe_template_version",
                    "probe_template_digest")
        if not isinstance(probe_ref, Mapping) or any(key not in probe_ref for key in required):
            raise ValueError("invalid probe ref")
        preimage = ["machina-bound-source-marker-ref-digest-v1", artifact_digest,
                    pointer] + [probe_ref[key] for key in required]
    return _sha256(preimage)


def evidence_record_digest(record):
    if not isinstance(record, Mapping):
        raise ValueError("evidence record must be an object")
    body = {key: value for key, value in record.items() if key != "digest"}
    return _sha256(["machina-evidence-record-digest-v1", body])


def document_fingerprint(document):
    if not isinstance(document, Mapping):
        raise TypeError("document must be a Mapping")
    schema_version = document.get("schema_version")
    if schema_version not in (SUCCESSOR_SCHEMA_VERSION, LONGITUDINAL_SCHEMA_VERSION):
        raise ValueError("unsupported document fingerprint version")
    generated_free = _remove_generated_ids(copy.deepcopy(dict(document)))
    return _sha256(["machina-document-fingerprint-v1", schema_version, generated_free])


def _remove_generated_ids(value):
    if isinstance(value, dict):
        for key in list(value):
            if key in ("provider_scoped_id", "operational_id"):
                del value[key]
            else:
                value[key] = _remove_generated_ids(value[key])
    elif isinstance(value, list):
        value = [_remove_generated_ids(item) for item in value]
    return value


class _RuntimeOnly:
    __slots__ = ()

    def __reduce__(self):
        raise TypeError("runtime-only object cannot be serialized")


class _ArtifactSession(_RuntimeOnly):
    __slots__ = ("__artifacts",)

    def __init__(self, seal):
        if seal is not _SESSION_SEAL:
            raise TypeError("artifact sessions are execution-created")
        object.__setattr__(self, "_ArtifactSession__artifacts", [])

    def register(self, artifact, seal):
        if seal is not _SESSION_SEAL:
            raise TypeError("artifact registration is wrapper-owned")
        self.__artifacts.append(artifact)

    def snapshot(self):
        return tuple(self.__artifacts)


class LoadedCanonicalTrustClosureV1(_RuntimeOnly):
    """Opaque, loader-created and indivisible Phase 1 trust closure."""

    __slots__ = (
        "_seal", "descriptor", "rights_profile", "source_shape", "operation_contract",
        "capability_contract", "identity_registry", "statistic_units",
        "statistic_derivations", "statistic_implementations", "admissibility",
        "spatial", "longitudinal", "_artifact_session", "document_builder",
        "argument_schema", "package_release", "closure_id",
        "_requested_consumer_tier", "_required_capabilities",
    )

    def __init__(self, seal, **values):
        if seal is not _TRUST_SEAL:
            raise TypeError("LoadedCanonicalTrustClosureV1 is loader-created")
        object.__setattr__(self, "_seal", seal)
        for name in self.__slots__[1:]:
            if name == "_artifact_session":
                object.__setattr__(self, name, _ArtifactSession(_SESSION_SEAL))
            elif name in ("document_builder", "closure_id", "_requested_consumer_tier",
                          "_required_capabilities"):
                object.__setattr__(self, name, values.get(name))
            else:
                object.__setattr__(self, name, _deep_freeze(values.get(name)))

    def __setattr__(self, name, value):
        raise TypeError("loaded trust closures are immutable")

    @property
    def source_artifacts(self):
        return self._artifact_session.snapshot()


class ValidatedDocumentHandleV1(_RuntimeOnly):
    __slots__ = ("_document", "document_fingerprint", "schema_version", "_closure_id")

    def __init__(self, seal, document, fingerprint, closure):
        if seal is not _HANDLE_SEAL:
            raise TypeError("ValidatedDocumentHandleV1 is validator-created")
        self._document = _deep_freeze(document)
        self.document_fingerprint = fingerprint
        self.schema_version = document["schema_version"]
        self._closure_id = closure.closure_id


class ValidatedIdentityOccurrenceHandleV1(_RuntimeOnly):
    __slots__ = ("document_handle", "identity_ref", "entity_type", "provider_namespace",
                 "provider_id", "_closure_id")

    def __init__(self, seal, document_handle, identity_ref, identity, closure):
        if seal is not _HANDLE_SEAL:
            raise TypeError("identity handles are validator-created")
        self.document_handle = document_handle
        self.identity_ref = identity_ref
        self.entity_type = identity["entity_type"]
        self.provider_namespace = identity["provider"]["namespace"]
        self.provider_id = identity["provider"]["id"]
        self._closure_id = closure.closure_id


class ValidatedOperationArgumentsHandleV1(_RuntimeOnly):
    __slots__ = ("_arguments", "canonical_arguments_bytes", "provider_request_parameters",
                 "_closure_id")

    def __init__(self, seal, arguments, parameters, closure):
        if seal is not _HANDLE_SEAL:
            raise TypeError("argument handles are validator-created")
        self._arguments = _deep_freeze(arguments)
        self.canonical_arguments_bytes = canonical_json_bytes(arguments)
        self.provider_request_parameters = tuple(parameters)
        self._closure_id = closure.closure_id


class LoadedSourceValueHandleV1(_RuntimeOnly):
    __slots__ = ("source_artifact", "semantic_kind", "template",
                 "occurrence_binding_tuple", "expanded_pointers", "_closure_id")

    def __init__(self, seal, artifact, semantic_kind, template, bindings,
                 expanded_pointers, closure):
        if seal is not _HANDLE_SEAL:
            raise TypeError("source-value handles are wrapper-created")
        if not isinstance(artifact, SourceArtifactV1) or artifact._closure_id is not closure.closure_id:
            raise TypeError("source artifact does not belong to this closure")
        self.source_artifact = artifact
        self.semantic_kind = semantic_kind
        self.template = _deep_freeze(template)
        self.occurrence_binding_tuple = _deep_freeze(bindings)
        self.expanded_pointers = _deep_freeze(expanded_pointers)
        self._closure_id = closure.closure_id


class SourceArtifactV1(_RuntimeOnly):
    __slots__ = ("media_type", "source_shape_ref", "original_bytes", "artifact_digest",
                 "parsed_projection", "_closure_id", "_locked")

    def __init__(self, seal, data, parsed, trust):
        if seal is not _ARTIFACT_SEAL:
            raise TypeError("SourceArtifactV1 is wrapper-created")
        object.__setattr__(self, "media_type", trust.source_shape.get(
            "media_type", "application/json"))
        object.__setattr__(self, "source_shape_ref", _deep_freeze(
            trust.source_shape.get("source_shape_ref", {})))
        object.__setattr__(self, "original_bytes", bytes(data))
        object.__setattr__(self, "artifact_digest",
                           "sha256:" + hashlib.sha256(self.original_bytes).hexdigest())
        object.__setattr__(self, "parsed_projection", _deep_freeze(parsed))
        object.__setattr__(self, "_closure_id", trust.closure_id)
        object.__setattr__(self, "_locked", True)

    def __setattr__(self, name, value):
        if getattr(self, "_locked", False):
            raise TypeError("source artifacts are immutable")
        object.__setattr__(self, name, value)


class CollectionExpansionWitnessSetV1(_RuntimeOnly):
    __slots__ = ("witnesses",)

    def __init__(self, witnesses):
        self.witnesses = tuple(_deep_freeze(item) for item in witnesses)


class OperationalIdLedgerV1(_RuntimeOnly):
    __slots__ = ("document_handle", "ids_by_input_pointer")

    def __init__(self, handle, values):
        self.document_handle = handle
        self.ids_by_input_pointer = MappingProxyType(dict(values))


_TRUST_SEAL = object()
_HANDLE_SEAL = object()
_ARTIFACT_SEAL = object()
_SESSION_SEAL = object()


def _deep_freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_deep_freeze(item) for item in value)
    return value


def _thaw(value):
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _require_trust(trust_closure):
    if not isinstance(trust_closure, LoadedCanonicalTrustClosureV1) or trust_closure._seal is not _TRUST_SEAL:
        raise TypeError("trust_closure must be a loader-created LoadedCanonicalTrustClosureV1")
    try:
        validate_provider_namespace(trust_closure.descriptor.get("provider_namespace"))
    except (AttributeError, ValueError) as error:
        raise TypeError("loaded trust descriptor has an invalid provider namespace") from error
    return trust_closure


def _construct_loaded_trust_closure(**overrides):
    """Internal constructor used only after a trusted loader verifies package bytes."""
    data_root = Path(__file__).resolve().parent / "data"
    defaults = {
        "descriptor": {
            "schema_version": "machina-adapter-descriptor/1",
            "provider_namespace": "provider-a", "operation": "event",
            "capabilities": [], "module_entrypoint": "fixture",
        },
        "rights_profile": {
            "profile_id": "fixture-open", "profile_version": "1",
            "provider_namespace": "provider-a", "operation": "event",
            "data_class": "open-public", "prototype_only": True,
            "commercial_use": False, "allowed_consumer_tiers": ["prototype"],
            "rights_profile_digest": "sha256:" + "1" * 64,
        },
        "source_shape": {"media_type": "application/json", "source_shape_ref": {}},
        "operation_contract": {"promised_collections": [],
                               "promised_non_collection_evidence": []},
        "capability_contract": {"mappings": []},
        "identity_registry": {}, "statistic_units": {}, "statistic_derivations": {},
        "statistic_implementations": {}, "admissibility": _read_optional_json(
            data_root / "official_statistic_admissibility_v1.json", {"entries": []}),
        "spatial": {}, "longitudinal": {},
        "document_builder": None,
        "argument_schema": {"fields": [], "unknown_fields": "forbidden",
                            "secret_fields": "forbidden"},
        "package_release": {
            "name": "machina-sports-canonical", "version": "0.3.0",
            "package_artifact_digest": "sha256:" + "2" * 64,
            "release_id": "fixture", "release_digest": "sha256:" + "3" * 64,
        },
        "closure_id": object(),
        "_requested_consumer_tier": None,
        "_required_capabilities": (),
    }
    defaults.update(overrides)
    return LoadedCanonicalTrustClosureV1(_TRUST_SEAL, **defaults)


def _read_optional_json(path, default):
    if not path.is_file():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def parse_legacy_observation_bytes(data: bytes) -> dict[str, Any]:
    document = _strict_json_object(data)
    if document.get("schema_version") not in ACCEPTED_SCHEMA_VERSIONS:
        raise CanonicalContractError("legacy-observation-version-required")
    errors = validate_observation(document)
    if errors:
        raise CanonicalContractError("invalid-legacy-observation", errors)
    return document


def parse_successor_observation_bytes(
    data: bytes, *, trust_closure: LoadedCanonicalTrustClosureV1
) -> dict[str, Any]:
    trust = _require_trust(trust_closure)
    document = _strict_json_object(data)
    if document.get("schema_version") != SUCCESSOR_SCHEMA_VERSION:
        raise CanonicalContractError("successor-observation-version-required")
    validate_successor_observation(document, trust_closure=trust)
    return document


def parse_longitudinal_bytes(
    data: bytes, *, trust_closure: LoadedCanonicalTrustClosureV1
) -> dict[str, Any]:
    trust = _require_trust(trust_closure)
    document = _strict_json_object(data)
    if document.get("schema_version") != LONGITUDINAL_SCHEMA_VERSION:
        raise CanonicalContractError("longitudinal-document-version-required")
    validate_longitudinal_document(document, trust_closure=trust)
    return document


def validate_successor_observation(
    document: Mapping[str, Any], *,
    trust_closure: LoadedCanonicalTrustClosureV1
) -> ValidatedDocumentHandleV1:
    trust = _require_trust(trust_closure)
    if not isinstance(document, Mapping):
        raise TypeError("document must be a Mapping")
    errors = []
    _closed_keys(document, _EVENT_TOP_KEYS, _EVENT_TOP_KEYS, "$", errors)
    if document.get("schema_version") != SUCCESSOR_SCHEMA_VERSION:
        errors.append("schema_version must be {0}".format(SUCCESSOR_SCHEMA_VERSION))
    _validate_event_body(document.get("observation"), trust, errors)
    _validate_provider_namespaces(document, "$", errors)
    _validate_array(document, "coordinate_system_registry", errors)
    _validate_array(document, "period_registry", errors)
    _validate_evidence_records(document.get("evidence_records"), trust, errors)
    _validate_coverage(document, trust, "event", errors)
    _validate_identity(document, trust, "event", errors)
    _validate_runtime_free(document, errors)
    if errors:
        raise CanonicalContractError("invalid-successor-observation", errors)
    owned = copy.deepcopy(dict(document))
    handle = ValidatedDocumentHandleV1(
        _HANDLE_SEAL, owned, document_fingerprint(owned), trust)
    _rebuild_all_statistics(handle, trust)
    return handle


def validate_longitudinal_document(
    document: Mapping[str, Any], *,
    trust_closure: LoadedCanonicalTrustClosureV1
) -> ValidatedDocumentHandleV1:
    trust = _require_trust(trust_closure)
    if not isinstance(document, Mapping):
        raise TypeError("document must be a Mapping")
    errors = []
    _closed_keys(document, _LONGITUDINAL_TOP_KEYS, _LONGITUDINAL_TOP_KEYS,
                 "$", errors)
    if document.get("schema_version") != LONGITUDINAL_SCHEMA_VERSION:
        errors.append("schema_version must be {0}".format(LONGITUDINAL_SCHEMA_VERSION))
    _validate_exact_instant(document.get("observed_at"), "observed_at", errors)
    _validate_longitudinal_scope(document.get("scope"), errors)
    _validate_provider_namespaces(document, "$", errors)
    _validate_longitudinal_subject(document.get("subject"), errors)
    records = document.get("records")
    aggregates = document.get("aggregates")
    if not isinstance(records, list):
        errors.append("records must be an array")
    else:
        _validate_longitudinal_records(records, document.get("scope"), trust, errors)
    if not isinstance(aggregates, list):
        errors.append("aggregates must be an array")
    else:
        for index, fact in enumerate(aggregates):
            _validate_statistic_fact(
                fact, "/aggregates/{0}".format(index),
                document.get("scope", {}).get("kind"), trust, errors)
    _validate_evidence_records(document.get("evidence_records"), trust, errors)
    _validate_coverage(document, trust, "longitudinal", errors)
    _validate_identity(document, trust, "longitudinal", errors)
    _validate_longitudinal_references(document, trust, errors)
    _validate_successor_provenance(document.get("provenance"),
                                   LONGITUDINAL_SCHEMA_VERSION, trust, errors)
    _validate_envelope_rights(document.get("rights"), trust, errors)
    _validate_runtime_free(document, errors)
    if errors:
        raise CanonicalContractError("invalid-longitudinal-document", errors)
    owned = copy.deepcopy(dict(document))
    handle = ValidatedDocumentHandleV1(
        _HANDLE_SEAL, owned, document_fingerprint(owned), trust)
    _rebuild_all_statistics(handle, trust)
    return handle


def _rebuild_all_statistics(handle, trust):
    document = _thaw(handle._document)
    pointers = []
    if handle.schema_version == SUCCESSOR_SCHEMA_VERSION:
        for p_index, participant in enumerate(document["observation"].get(
                "participants", [])):
            for s_index in range(len(participant.get("statistics", []))):
                pointers.append("/observation/participants/{0}/statistics/{1}".format(
                    p_index, s_index))
    else:
        for r_index, record in enumerate(document.get("records", [])):
            for s_index in range(len(record.get("statistics", []))):
                pointers.append("/records/{0}/statistics/{1}".format(r_index, s_index))
        for s_index in range(len(document.get("aggregates", []))):
            pointers.append("/aggregates/{0}".format(s_index))
    for pointer in pointers:
        _build_statistic_fact(handle, fact_ref=pointer, trust_closure=trust)


def _closed_keys(node, allowed, required, path, errors):
    if not isinstance(node, Mapping):
        errors.append("{0} must be an object".format(path))
        return
    extras = sorted(set(node) - set(allowed))
    missing = sorted(set(required) - set(node))
    if extras:
        errors.append("{0} has unknown members: {1}".format(path, ", ".join(extras)))
    if missing:
        errors.append("{0} is missing members: {1}".format(path, ", ".join(missing)))


def _validate_array(document, key, errors):
    if not isinstance(document.get(key), list):
        errors.append("{0} must be an array".format(key))


def _validate_exact_instant(value, path, errors):
    try:
        _parse_rfc3339(value)
    except ValueError as error:
        errors.append("{0}: {1}".format(path, error))


def _validate_event_body(body, trust, errors):
    if not isinstance(body, Mapping):
        errors.append("observation must be an object")
        return
    legacy = copy.deepcopy(dict(body))
    for participant in legacy.get("participants", []):
        if isinstance(participant, dict) and isinstance(participant.get("statistics"), list):
            participant.pop("statistics", None)
    for action in legacy.get("actions", []):
        if isinstance(action, dict):
            action.pop("spatial_evidence", None)
    legacy_errors = validate_observation({"schema_version": "canonical-observation/1.1",
                                          "observation": legacy})
    errors.extend("inherited " + error for error in legacy_errors)
    participants = body.get("participants")
    if isinstance(participants, list):
        for p_index, participant in enumerate(participants):
            if not isinstance(participant, Mapping):
                continue
            statistics = participant.get("statistics")
            if statistics is not None and not isinstance(statistics, list):
                errors.append("participants/{0}/statistics must be an array".format(p_index))
            elif isinstance(statistics, list):
                for s_index, fact in enumerate(statistics):
                    _validate_statistic_fact(
                        fact,
                        "/observation/participants/{0}/statistics/{1}".format(
                            p_index, s_index), "event", trust, errors)
    actions = body.get("actions")
    if isinstance(actions, list):
        for index, action in enumerate(actions):
            if isinstance(action, Mapping) and "spatial_evidence" in action:
                _validate_spatial_input(action["spatial_evidence"], index, errors)


def _validate_statistic_fact(fact, pointer, expected_scope, trust, errors):
    if not isinstance(fact, Mapping):
        errors.append("{0} must be a StatisticFactV1".format(pointer))
        return
    kind = fact.get("kind")
    scope = fact.get("scope")
    if kind not in _STATISTIC_KINDS:
        errors.append("{0}/kind is invalid".format(pointer))
    if scope not in _STATISTIC_SCOPES or scope != expected_scope:
        errors.append("{0}/scope must be {1}".format(pointer, expected_scope))
    name = fact.get("name")
    if not isinstance(name, str) or not name:
        errors.append("{0}/name must be non-empty text".format(pointer))
    value = fact.get("value")
    if not isinstance(value, Mapping) or set(value) - {"kind", "lexical", "unit"}:
        errors.append("{0}/value is invalid".format(pointer))
    else:
        try:
            validate_statistic_lexical(value.get("kind"), value.get("lexical"))
        except ValueError as error:
            errors.append("{0}/value: {1}".format(pointer, error))
        _validate_statistic_unit(value, trust, pointer, errors)
    if kind in ("official", "provider_native"):
        if set(fact) != {"kind", "scope", "name", "value", "source_ref"}:
            errors.append("{0} source-backed fact has an invalid member set".format(pointer))
        try:
            validate_json_pointer(fact.get("source_ref"))
        except ValueError as error:
            errors.append("{0}/source_ref: {1}".format(pointer, error))
        if kind == "official" and (not isinstance(name, str) or name.count(":") != 1):
            errors.append("{0}/name must be a full official CURIE".format(pointer))
        if kind == "provider_native":
            namespace = trust.descriptor.get("provider_namespace")
            if not isinstance(name, str) or not name.startswith(namespace + ":"):
                errors.append("{0}/name must use the descriptor namespace".format(pointer))
    elif kind == "derived":
        if set(fact) != {"kind", "scope", "name", "value", "derivation"}:
            errors.append("{0} derived fact has an invalid member set".format(pointer))
        _validate_derivation(fact.get("derivation"), trust, pointer, errors)


def _validate_statistic_unit(value, trust, pointer, errors):
    kind = value.get("kind")
    unit = value.get("unit")
    if kind in ("duration", "boolean", "text") and unit is not None:
        errors.append("{0}/value unit is forbidden for {1}".format(pointer, kind))
    if unit is None:
        return
    if kind not in ("integer", "decimal") or not isinstance(unit, Mapping):
        errors.append("{0}/value/unit is invalid".format(pointer))
        return
    expected = {"registry_id": "machina-statistic-units", "registry_version": 1}
    if any(unit.get(key) != item for key, item in expected.items()):
        errors.append("{0}/value/unit registry is invalid".format(pointer))
    entries = trust.statistic_units.get("entries", []) if isinstance(
        trust.statistic_units, Mapping) else []
    if entries and len([entry for entry in entries
                        if entry.get("unit_id") == unit.get("unit_id")]) != 1:
        errors.append("{0}/value/unit does not resolve exactly once".format(pointer))


def _validate_derivation(derivation, trust, pointer, errors):
    required = {"id", "version", "algorithm_digest", "input_refs", "result_digest"}
    if not isinstance(derivation, Mapping) or set(derivation) != required:
        errors.append("{0}/derivation has an invalid member set".format(pointer))
        return
    refs = derivation.get("input_refs")
    if not isinstance(refs, list) or not refs or len(refs) != len(set(refs)):
        errors.append("{0}/derivation input_refs must be non-empty and unique".format(pointer))
    else:
        for ref in refs:
            try:
                validate_json_pointer(ref)
            except ValueError as error:
                errors.append("{0}/derivation input ref: {1}".format(pointer, error))
    key = (derivation.get("id"), derivation.get("version"),
           derivation.get("algorithm_digest"))
    entries = trust.statistic_derivations.get("entries", []) if isinstance(
        trust.statistic_derivations, Mapping) else []
    manifest_keys = {(entry.get("derivation_id"), entry.get("derivation_version"),
                      entry.get("algorithm_digest")) for entry in entries}
    implementation_keys = set(trust.statistic_implementations or {})
    if manifest_keys != implementation_keys:
        errors.append("statistic derivation manifest/implementation key sets differ")
    if entries and key not in manifest_keys:
        errors.append("{0}/derivation exact key is not registered".format(pointer))
    for digest_key in ("algorithm_digest", "result_digest"):
        if _DIGEST_RE.fullmatch(derivation.get(digest_key) or "") is None:
            errors.append("{0}/derivation/{1} is invalid".format(pointer, digest_key))


def _validate_spatial_input(value, action_index, errors):
    if not isinstance(value, Mapping):
        errors.append("actions/{0}/spatial_evidence must be an object".format(action_index))
        return
    allowed = {"source_position_source", "normalization", "distance", "zone"}
    if set(value) - allowed or "source_position_source" not in value:
        errors.append("actions/{0}/spatial_evidence has invalid members".format(action_index))
    if any(key in value for key in ("x", "y", "source_position", "coordinates")):
        errors.append("caller-authored spatial coordinates are forbidden")
    source = value.get("source_position_source")
    if not isinstance(source, Mapping) or set(source) != {"source_ref", "binding_template_ref"}:
        errors.append("spatial source_position_source is invalid")
    distance = value.get("distance")
    if isinstance(distance, Mapping) and distance.get("origin") == "source_reported":
        if set(distance) != {"origin", "source_ref"}:
            errors.append("source-reported distance cannot carry value or unit")
    zone = value.get("zone")
    if isinstance(zone, Mapping) and zone.get("origin") == "provider_native":
        if set(zone) != {"origin", "source_ref"}:
            errors.append("provider-native zone cannot carry provider, scheme, or value")


def _validate_evidence_records(records, trust, errors):
    if not isinstance(records, list):
        errors.append("evidence_records must be an array")
        return
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            errors.append("evidence_records/{0} must be an object".format(index))
            continue
        if _DIGEST_RE.fullmatch(record.get("digest") or "") is None:
            errors.append("evidence_records/{0}/digest is invalid".format(index))
        elif evidence_record_digest(record) != record.get("digest"):
            errors.append("evidence_records/{0}/digest does not recompute".format(index))
        if any(isinstance(value, (bytes, _RuntimeOnly)) for value in record.values()):
            errors.append("evidence_records/{0} contains runtime-only data".format(index))
        kind = record.get("kind")
        variant_members = {
            "source_value": {"source_value"},
            "source_coordinates": {"source_coordinates"},
            "coverage_source": {"coverage_source"},
            "period_source": {"period_source"},
            "longitudinal_period_source": {"longitudinal_period_source"},
            "rolling_event_anchor_source": {"rolling_event_anchor_source"},
            "identity_authority_record": set(),
            "provider_crosswalk": set(),
        }
        if kind not in variant_members:
            errors.append("evidence_records/{0}/kind is invalid".format(index))
            continue
        expected = {"id", "version", "kind", "source", "digest"} | variant_members[kind]
        if set(record) != expected:
            errors.append("evidence_records/{0} has an invalid closed member set".format(index))
        source = record.get("source")
        allowed_source = {"kind", "record_id", "provider_namespace"}
        if not isinstance(source, Mapping) or set(source) - allowed_source or not isinstance(
                source.get("record_id"), str) or not source.get("record_id"):
            errors.append("evidence_records/{0}/source is invalid".format(index))
        elif source.get("kind") == "provider_record":
            try:
                validate_provider_namespace(source.get("provider_namespace"))
            except ValueError as error:
                errors.append("evidence_records/{0}/source: {1}".format(index, error))
        elif source.get("kind") not in (
                "machina_record", "governing_body_record", "tenant_record"):
            errors.append("evidence_records/{0}/source kind is invalid".format(index))
        if kind == "source_value":
            _validate_source_value_evidence(record.get("source_value"), trust, index, errors)


def _validate_source_value_evidence(value, trust, index, errors):
    required = {"schema_version", "artifact_digest", "value_pointer", "value_digest"}
    if not isinstance(value, Mapping) or set(value) != required or value.get(
            "schema_version") != "machina-source-value-evidence/1":
        errors.append("evidence_records/{0}/source_value is invalid".format(index))
        return
    try:
        validate_json_pointer(value.get("value_pointer"))
    except ValueError as error:
        errors.append("evidence_records/{0}/source_value: {1}".format(index, error))
        return
    artifacts = [artifact for artifact in trust.source_artifacts
                 if artifact.artifact_digest == value.get("artifact_digest")]
    if len(artifacts) != 1:
        errors.append("evidence_records/{0} source artifact is not registered".format(index))
        return
    parsed = _reparse_source_artifact(artifacts[0], trust)
    try:
        resolve_json_pointer(parsed, value["value_pointer"])
    except ValueError as error:
        errors.append("evidence_records/{0} source pointer: {1}".format(index, error))
    expected = derive_source_value_digest(
        value["artifact_digest"], value["value_pointer"])
    if value.get("value_digest") != expected:
        errors.append("evidence_records/{0} source value digest mismatch".format(index))


def _validate_coverage(document, trust, document_kind, errors):
    claims = document.get("collection_claims")
    coverage = document.get("coverage")
    if not isinstance(claims, list) or not isinstance(coverage, list):
        errors.append("collection_claims and coverage must be arrays")
        return
    claim_pointers = []
    coverage_pointers = []
    for claim in claims:
        if not isinstance(claim, Mapping):
            errors.append("collection claim must be an object")
            continue
        try:
            validate_json_pointer(claim.get("collection_pointer"))
        except ValueError as error:
            errors.append("collection claim pointer: {0}".format(error))
        claim_pointers.append(claim.get("collection_pointer"))
    for item in coverage:
        if not isinstance(item, Mapping):
            errors.append("coverage record must be an object")
            continue
        allowed_coverage = {"target", "collection_pointer", "returned_count",
                            "available_total", "completeness", "truncation",
                            "limitations", "source_ref", "limit"}
        required_coverage = allowed_coverage - {"limit"}
        _closed_keys(item, allowed_coverage, required_coverage,
                     "coverage record", errors)
        coverage_pointers.append(item.get("collection_pointer"))
        pointer = item.get("collection_pointer")
        try:
            collection = resolve_json_pointer(document, pointer)
        except ValueError as error:
            errors.append("coverage collection pointer: {0}".format(error))
            collection = None
        if isinstance(collection, list) and item.get("returned_count") != len(collection):
            errors.append("coverage returned_count does not equal collection length")
        available = item.get("available_total")
        if not isinstance(available, Mapping) or available.get("state") not in _TOTAL_STATES:
            errors.append("coverage available_total state must be known or unavailable")
        if item.get("completeness") not in _COMPLETENESS:
            errors.append("coverage completeness is invalid")
        if available and available.get("state") == "unavailable" and item.get(
                "completeness") == "complete":
            errors.append("unavailable total cannot imply complete coverage")
    if len(claim_pointers) != len(set(claim_pointers)):
        errors.append("duplicate collection claims")
    if len(coverage_pointers) != len(set(coverage_pointers)):
        errors.append("duplicate coverage records")
    if set(claim_pointers) != set(coverage_pointers):
        errors.append("claim and coverage pointer sets differ")
    promised = trust.operation_contract.get("promised_collections", []) if isinstance(
        trust.operation_contract, Mapping) else []
    promised_patterns = {item.get("pointer_pattern") for item in promised
                         if isinstance(item, Mapping)}
    present = set(_present_managed_collections(document, document_kind))
    for pattern in promised_patterns:
        if "{" not in pattern and pattern not in present:
            errors.append("promised-managed-root-absent: {0}".format(pattern))
        if pattern.endswith("/statistics") and "{" in pattern:
            parent = document.get("observation", {}).get("participants", []) \
                if document_kind == "event" else document.get("records", [])
            for index in range(len(parent)):
                pointer = pattern.replace(
                    "{participant_index}" if document_kind == "event" else
                    "{record_index}", str(index))
                if pointer not in present:
                    errors.append("promised-managed-child-absent: {0}".format(pointer))
    for pointer in present:
        if not any(_pointer_matches_pattern(pointer, pattern)
                   for pattern in promised_patterns):
            errors.append("unpromised-managed-collection-present: {0}".format(pointer))
    if present != set(claim_pointers) or present != set(coverage_pointers):
        errors.append("present, promised, claim, and coverage pointer sets differ")
    target_by_pointer = {}
    for pointer in present:
        if pointer.endswith("/participants"):
            target_by_pointer[pointer] = "participants"
        elif pointer.endswith("/actions"):
            target_by_pointer[pointer] = "actions"
        elif pointer.endswith("/records"):
            target_by_pointer[pointer] = "records"
        elif pointer.endswith("/aggregates"):
            target_by_pointer[pointer] = "aggregates"
        else:
            target_by_pointer[pointer] = "statistics"
    for claim in claims:
        if isinstance(claim, Mapping) and claim.get("target") != target_by_pointer.get(
                claim.get("collection_pointer")):
            errors.append("collection claim target mismatch")
    for item in coverage:
        if not isinstance(item, Mapping):
            continue
        pointer = item.get("collection_pointer")
        if item.get("target") != target_by_pointer.get(pointer):
            errors.append("coverage target mismatch")
        try:
            source = resolve_json_pointer(document, item.get("source_ref"))
        except ValueError as error:
            errors.append("coverage source_ref: {0}".format(error))
            continue
        coverage_source = source.get("coverage_source") if isinstance(source, Mapping) else None
        if not isinstance(source, Mapping) or source.get("kind") != "coverage_source" or not isinstance(coverage_source, Mapping):
            errors.append("coverage source_ref must target CoverageEvidenceRecordV1")
        elif coverage_source.get("collection_pointer") != pointer:
            errors.append("coverage source collection pointer mismatch")
        else:
            required_source = {"schema_version", "collection_pointer", "artifact_digest",
                               "fields", "reported_total", "truncation", "cursor",
                               "page_cap", "request_limit"}
            if set(coverage_source) != required_source or coverage_source.get(
                    "schema_version") != "machina-coverage-source-evidence/1":
                errors.append("coverage source evidence has an invalid closed member set")
            digest = coverage_source.get("artifact_digest")
            artifacts = [artifact for artifact in trust.source_artifacts
                         if artifact.artifact_digest == digest]
            if len(artifacts) != 1:
                errors.append("coverage source artifact is not registered exactly once")
            else:
                _validate_coverage_recomputation(
                    item, coverage_source, artifacts[0], trust, errors)


def _validate_coverage_recomputation(item, source, artifact, trust, errors):
    parsed = _reparse_source_artifact(artifact, trust)
    total = source.get("reported_total")
    available = item.get("available_total")
    if not isinstance(total, Mapping):
        errors.append("coverage source reported_total is invalid")
        return
    if total.get("state") == "known":
        pointers = total.get("value_pointers")
        if not isinstance(pointers, (list, tuple)) or not pointers:
            errors.append("known coverage total requires value pointers")
            return
        values = []
        for pointer in pointers:
            try:
                raw = resolve_json_pointer(parsed, pointer)
                values.append(int(str(raw)))
            except (ValueError, TypeError):
                errors.append("coverage total source pointer is invalid")
                return
        if any(value != total.get("count") for value in values):
            errors.append("coverage reported total does not match source bytes")
        if available != {"state": "known", "count": total.get("count")}:
            errors.append("coverage available_total does not match source evidence")
    elif total.get("state") == "unavailable":
        if available != {"state": "unavailable"}:
            errors.append("unavailable source total does not match available_total")
    else:
        errors.append("coverage source total state must be known or unavailable")
    truncation = source.get("truncation")
    source_truncated = None
    if isinstance(truncation, Mapping) and truncation.get("state") in (
            "truncated", "not_truncated"):
        pointers = truncation.get("value_pointers")
        if not isinstance(pointers, (list, tuple)) or not pointers:
            errors.append("coverage truncation requires value pointers")
        else:
            values = []
            for pointer in pointers:
                try:
                    values.append(resolve_json_pointer(parsed, pointer))
                except ValueError:
                    errors.append("coverage truncation source pointer is invalid")
                    return
            expected_boolean = truncation["state"] == "truncated"
            if any(value is not expected_boolean for value in values):
                errors.append("coverage truncation does not match source bytes")
            source_truncated = truncation["state"]
    if source_truncated is not None and item.get("truncation") != source_truncated:
        errors.append("coverage truncation disposition does not match source evidence")
    cursor_present = _validate_optional_coverage_fact(
        source.get("cursor"), parsed, "cursor", trust, artifact, errors)
    page_cap = _validate_optional_coverage_fact(
        source.get("page_cap"), parsed, "page_cap", trust, artifact, errors)
    request_limit = _validate_optional_coverage_fact(
        source.get("request_limit"), parsed, "request_limit", trust, artifact, errors)
    if isinstance(request_limit, int):
        if item.get("limit") != request_limit:
            errors.append("coverage request limit does not match source evidence")
    elif "limit" in item:
        errors.append("coverage limit has no source evidence")
    returned = item.get("returned_count")
    if total.get("state") == "known" and isinstance(returned, int):
        count = total.get("count")
        expected = "partial" if source_truncated == "truncated" or count > returned \
            or cursor_present is True or isinstance(page_cap, int) \
            or isinstance(request_limit, int) \
            else "complete" if count == returned else None
        if expected is None or item.get("completeness") != expected:
            errors.append("coverage completeness does not recompute")
    elif total.get("state") == "unavailable":
        expected = "partial" if source_truncated == "truncated" or cursor_present is True \
            or isinstance(page_cap, int) or isinstance(request_limit, int) else "unknown"
        if item.get("completeness") != expected:
            errors.append("coverage completeness does not recompute")


def _validate_optional_coverage_fact(fact, parsed, name, trust, artifact, errors):
    if not isinstance(fact, Mapping):
        errors.append("coverage source {0} is invalid".format(name))
        return None
    state = fact.get("state")
    if name == "cursor" and state == "present":
        if set(fact) != {"state", "value_digest", "value_pointers"}:
            errors.append("coverage cursor present record is open or incomplete")
        pointers = fact.get("value_pointers")
        if not isinstance(pointers, (list, tuple)) or not pointers:
            errors.append("coverage cursor requires value pointers")
            return None
        values = []
        for pointer in pointers:
            try:
                values.append(resolve_json_pointer(parsed, pointer))
            except ValueError:
                errors.append("coverage cursor source pointer is invalid")
                return None
        return any(value not in (None, "", False) for value in values)
    if name in ("page_cap", "request_limit") and state == "known":
        if set(fact) != {"state", "count", "value_pointers"}:
            errors.append("coverage {0} known record is open or incomplete".format(name))
        pointers = fact.get("value_pointers")
        if not isinstance(pointers, (list, tuple)) or not pointers:
            errors.append("coverage {0} requires value pointers".format(name))
            return None
        try:
            values = [int(str(resolve_json_pointer(parsed, pointer))) for pointer in pointers]
        except (ValueError, TypeError):
            errors.append("coverage {0} source pointer is invalid".format(name))
            return None
        if any(value <= 0 or value != fact.get("count") for value in values):
            errors.append("coverage {0} does not match source bytes".format(name))
            return None
        return fact.get("count")
    allowed_absent = ("absent", "unavailable") if name == "cursor" \
        else ("none_reported", "unavailable")
    if state not in allowed_absent:
        errors.append("coverage source {0} state is invalid".format(name))
        return None
    required = {"state", "absence_probes"} | ({"reason"} if state == "unavailable" else set())
    if set(fact) != required:
        errors.append("coverage source {0} absence record is open or incomplete".format(name))
        return None
    probes = fact.get("absence_probes")
    if not isinstance(probes, (list, tuple)) or not probes:
        errors.append("coverage source {0} absence requires probes".format(name))
        return None
    kinds = set()
    for probe in probes:
        if not isinstance(probe, Mapping):
            errors.append("coverage source {0} absence probe is invalid".format(name))
            continue
        kind = probe.get("probe")
        pointer = probe.get("pointer")
        kinds.add(kind)
        try:
            validate_json_pointer(pointer)
        except ValueError as error:
            errors.append("coverage source {0} probe: {1}".format(name, error))
            continue
        if kind == "member_absent":
            try:
                resolve_json_pointer(parsed, pointer)
            except ValueError:
                pass
            else:
                errors.append("coverage source {0} absent probe found a value".format(name))
        elif kind in ("shape_not_exposed", "not_applicable_by_shape"):
            attested = trust.source_shape.get("safe_absence_probe_templates", [])
            if not any(item.get("probe") == kind and item.get(
                    "pointer_template") == pointer for item in attested):
                errors.append("coverage source {0} probe is not shape-attested".format(name))
        elif kind == "access_denied_marker":
            try:
                resolve_json_pointer(parsed, pointer)
            except ValueError:
                errors.append("coverage source {0} access marker is absent".format(name))
            expected = derive_source_marker_digest(artifact.artifact_digest, pointer)
            if probe.get("marker_value_digest") != expected:
                errors.append("coverage source {0} marker digest mismatch".format(name))
        else:
            errors.append("coverage source {0} probe kind is invalid".format(name))
    if len(kinds) != 1:
        errors.append("coverage source {0} mixes absence probe kinds".format(name))
    return None


def _present_managed_collections(document, kind):
    pointers = []
    if kind == "event":
        body = document.get("observation")
        if not isinstance(body, Mapping):
            return pointers
        for key in ("participants", "actions"):
            if key in body:
                pointers.append("/observation/" + key)
        for index, participant in enumerate(body.get("participants", [])):
            if isinstance(participant, Mapping) and "statistics" in participant:
                pointers.append("/observation/participants/{0}/statistics".format(index))
    else:
        for key in ("records", "aggregates"):
            if key in document:
                pointers.append("/" + key)
        for index, record in enumerate(document.get("records", [])):
            if isinstance(record, Mapping) and "statistics" in record:
                pointers.append("/records/{0}/statistics".format(index))
    return pointers


def _pointer_matches_pattern(pointer, pattern):
    if not isinstance(pattern, str):
        return False
    expression = re.escape(pattern)
    expression = re.sub(r"\\\{[A-Za-z][A-Za-z0-9._-]*\\\}", r"[0-9]+", expression)
    return re.fullmatch(expression, pointer) is not None


def _validate_identity(document, trust, document_kind, errors):
    subjects = document.get("identity_subjects")
    evidence = document.get("identity_evidence")
    if not isinstance(subjects, list) or not isinstance(evidence, list):
        errors.append("identity_subjects and identity_evidence must be arrays")
        return
    evidence_refs = set()
    subject_refs = set()
    for index, identity in enumerate(evidence):
        pointer = "/identity_evidence/{0}".format(index)
        if not isinstance(identity, Mapping):
            errors.append("{0} must be an object".format(pointer))
            continue
        _validate_identity_evidence(identity, trust, pointer, errors)
        try:
            method_source = resolve_json_pointer(document, identity.get("method_source_ref"))
        except ValueError as error:
            errors.append("{0}/method_source_ref: {1}".format(pointer, error))
        else:
            expected_kind = "identity_authority_record" if identity.get(
                "resolution_method") == "authoritative_registry" else "source_value"
            if not isinstance(method_source, Mapping) or method_source.get("kind") != expected_kind:
                errors.append("{0}/method_source_ref has wrong evidence kind".format(pointer))
    for claim in subjects:
        if not isinstance(claim, Mapping):
            errors.append("identity subject claim must be an object")
            continue
        subject_ref = claim.get("subject_ref")
        evidence_ref = claim.get("identity_evidence_ref")
        try:
            subject = resolve_json_pointer(document, subject_ref)
            identity = resolve_json_pointer(document, evidence_ref)
        except ValueError as error:
            errors.append("identity subject: {0}".format(error))
            continue
        if not isinstance(identity, Mapping) or identity.get("entity_type") != claim.get(
                "entity_type"):
            errors.append("identity claim entity type does not match")
        if subject_ref in subject_refs:
            errors.append("duplicate identity subject pointer")
        subject_refs.add(subject_ref)
        evidence_refs.add(evidence_ref)
        inherited = claim.get("inherited_provider")
        if inherited is not None:
            _validate_inherited_provider(document, inherited, identity,
                                         claim.get("entity_type"), trust, errors)
        if subject is None:
            errors.append("identity subject cannot be null")
    expected_refs = {"/identity_evidence/{0}".format(index)
                     for index in range(len(evidence))}
    if evidence_refs != expected_refs:
        errors.append("identity evidence census is incomplete or orphaned")
    if document_kind == "event":
        _validate_event_provider_inventory(document, subjects, trust, errors)


def _validate_identity_evidence(identity, trust, pointer, errors):
    entity_type = identity.get("entity_type")
    status = identity.get("status")
    method = identity.get("resolution_method")
    provider = identity.get("provider")
    if entity_type not in _ENTITY_TYPES or status not in _IDENTITY_STATUSES:
        errors.append("{0} has invalid entity type or status".format(pointer))
    if method not in _IDENTITY_METHODS:
        errors.append("{0} has invalid resolution method".format(pointer))
    if not isinstance(provider, Mapping) or set(provider) != {"namespace", "id"}:
        errors.append("{0}/provider is invalid".format(pointer))
        return
    try:
        validate_provider_namespace(provider.get("namespace"))
    except ValueError as error:
        errors.append("{0}/provider/namespace: {1}".format(pointer, error))
    if not isinstance(provider.get("id"), str) or not provider.get("id"):
        errors.append("{0}/provider/id must be non-empty text".format(pointer))
    if status == "provider_scoped":
        expected = _provider_scoped_id(provider.get("namespace"), entity_type,
                                       provider.get("id"))
        if identity.get("provider_scoped_id") != expected:
            errors.append("{0}/provider_scoped_id does not recompute".format(pointer))
        if "canonical_id" in identity or "authority" in identity:
            errors.append("provider_scoped identity cannot assert canonical authority")
    elif status == "authoritatively_resolved":
        if method != "authoritative_registry":
            errors.append("authoritative identity requires authoritative_registry")
        canonical_id = identity.get("canonical_id")
        prefix = "urn:machina:sports:{0}:".format(entity_type)
        if not isinstance(canonical_id, str) or not canonical_id.startswith(prefix) or \
                _UUID7_RE.fullmatch(canonical_id[len(prefix):]) is None:
            errors.append("{0}/canonical_id is not a matching UUIDv7 URN".format(pointer))
        if not _authority_registered(identity, trust):
            errors.append("{0} has no exact loaded authority registration".format(pointer))
    elif status == "ambiguous":
        candidates = identity.get("candidate_ids")
        if not isinstance(candidates, list) or len(set(candidates)) < 2:
            errors.append("ambiguous identity requires two distinct candidates")
        if "canonical_id" in identity or "authority" in identity:
            errors.append("ambiguous identity cannot be resolved")
    elif status == "unresolved":
        if any(key in identity for key in ("canonical_id", "authority", "candidate_ids",
                                           "provider_scoped_id")):
            errors.append("unresolved identity cannot carry an identifier")
    if "confidence" in identity or "same" + "As" in identity:
        errors.append("confidence and sameness assertions are forbidden")


def _provider_scoped_id(namespace, entity_type, provider_id):
    return "urn:machina:provider-scoped:{0}:sha256:{1}".format(
        entity_type,
        hashlib.sha256(canonical_json_bytes([
            "machina-provider-scoped-entity-id-v1", namespace, entity_type, provider_id,
        ])).hexdigest(),
    )


def _authority_registered(identity, trust):
    authority = identity.get("authority")
    if not isinstance(authority, Mapping):
        return False
    registrations = trust.identity_registry.get("registrations", []) if isinstance(
        trust.identity_registry, Mapping) else []
    provider = identity.get("provider", {})
    expected = (
        authority.get("kind"), authority.get("issuer_id"),
        authority.get("issuer_version"), authority.get("resolver_id"),
        authority.get("resolver_version"), authority.get("snapshot_digest"),
        identity.get("entity_type"), provider.get("namespace"), provider.get("id"),
        identity.get("canonical_id"), authority.get("record_id"),
        authority.get("record_version"), authority.get("digest"),
    )
    matches = []
    for item in registrations:
        key = (
            item.get("authority_kind"), item.get("authority_issuer_id"),
            item.get("authority_issuer_version"), item.get("resolver_id"),
            item.get("resolver_version"), item.get("authority_snapshot_digest"),
            item.get("entity_type"), item.get("provider_namespace"),
            item.get("provider_id"), item.get("canonical_id"),
            item.get("authority_record_id"), item.get("authority_record_version"),
            item.get("authority_record_digest"),
        )
        if key == expected:
            matches.append(item)
    return len(matches) == 1


def _validate_inherited_provider(document, inherited, identity, entity_type, trust, errors):
    if not isinstance(inherited, Mapping) or set(inherited) != {"provider_id_ref", "provider"}:
        errors.append("inherited_provider is invalid")
        return
    try:
        provider_id = resolve_json_pointer(document, inherited.get("provider_id_ref"))
    except ValueError as error:
        errors.append("inherited provider pointer: {0}".format(error))
        return
    echoed = inherited.get("provider")
    namespace = trust.descriptor.get("provider_namespace")
    if not isinstance(echoed, Mapping) or echoed.get("namespace") != namespace or \
            echoed.get("id") != provider_id or identity.get("provider") != echoed or \
            identity.get("entity_type") != entity_type:
        errors.append("inherited provider tuple contradicts its identity evidence")


def _event_inventory(document):
    body = document.get("observation", {})
    inventory = []
    competition = body.get("competition")
    if isinstance(competition, Mapping):
        if "provider_id" in competition:
            inventory.append(("competition", "/observation/competition/provider_id"))
        season = competition.get("season")
        if isinstance(season, Mapping) and "provider_id" in season:
            inventory.append(("season", "/observation/competition/season/provider_id"))
    for key, entity_type in (("phase", "phase"), ("site", "site"), ("event", "event")):
        value = body.get(key)
        if isinstance(value, Mapping) and "provider_id" in value:
            inventory.append((entity_type, "/observation/{0}/provider_id".format(key)))
    for index, participant in enumerate(body.get("participants", [])):
        if isinstance(participant, Mapping) and "provider_id" in participant:
            entity_type = "team" if participant.get("kind") == "team" else "athlete"
            inventory.append((entity_type,
                              "/observation/participants/{0}/provider_id".format(index)))
    return inventory


def _validate_event_provider_inventory(document, subjects, trust, errors):
    linked = {}
    for claim in subjects:
        inherited = claim.get("inherited_provider") if isinstance(claim, Mapping) else None
        if isinstance(inherited, Mapping):
            pointer = inherited.get("provider_id_ref")
            if pointer in linked:
                errors.append("inherited provider ID is linked more than once")
            linked[pointer] = claim.get("entity_type")
    expected = dict((pointer, entity_type) for entity_type, pointer in _event_inventory(document))
    if linked != expected:
        errors.append("inherited provider-ID inventory is not linked exactly")


def _validate_longitudinal_subject(subject, errors):
    if not isinstance(subject, Mapping) or set(subject) != {"entity_type", "identity_ref"}:
        errors.append("subject must be a closed LongitudinalSubjectV1")
        return
    if subject.get("entity_type") not in ("team", "athlete"):
        errors.append("longitudinal subject must be team or athlete")
    try:
        validate_json_pointer(subject.get("identity_ref"))
    except ValueError as error:
        errors.append("subject identity_ref: {0}".format(error))


def _validate_longitudinal_scope(scope, errors):
    if not isinstance(scope, Mapping):
        errors.append("scope must be an object")
        return
    kind = scope.get("kind")
    if kind not in ("season", "career", "rolling_window", "date_range"):
        errors.append("scope kind is invalid")
        return
    if not isinstance(scope.get("sport"), str) or _TOKEN_RE.fullmatch(scope["sport"]) is None:
        errors.append("scope sport must be a token")
    required = {"kind", "sport"}
    permitted = set(required)
    if kind == "season":
        required.add("season_identity_ref")
        permitted |= {"season_identity_ref", "competition_identity_ref", "stated_boundary"}
    elif kind == "career":
        permitted |= {"competition_identity_ref", "stated_boundary"}
    elif kind == "rolling_window":
        required |= {"window_size", "window_unit", "anchor"}
        permitted |= required
    else:
        required.add("range")
        permitted |= required
    _closed_keys(scope, permitted, required, "scope", errors)
    for key in ("stated_boundary", "range"):
        if key in scope:
            try:
                validate_temporal_range(scope[key])
            except ValueError as error:
                errors.append("scope/{0}: {1}".format(key, error))
    if kind == "rolling_window":
        if not isinstance(scope.get("window_size"), int) or isinstance(
                scope.get("window_size"), bool) or scope["window_size"] <= 0:
            errors.append("rolling window_size must be a positive integer")
        if scope.get("window_unit") not in ("event", "day", "week"):
            errors.append("rolling window_unit is invalid")
        _validate_rolling_anchor(scope.get("anchor"), errors)


def _validate_rolling_anchor(anchor, errors):
    if not isinstance(anchor, Mapping) or anchor.get("kind") not in ("event", "instant"):
        errors.append("rolling anchor is invalid")
        return
    if anchor["kind"] == "event":
        required = {"kind", "event_identity_ref", "event_source_ref", "source_binding_ref"}
        if set(anchor) != required:
            errors.append("event rolling anchor has invalid members")
    else:
        if set(anchor) != {"kind", "endpoint"}:
            errors.append("instant rolling anchor has invalid members")
        else:
            try:
                _validate_endpoint(anchor["endpoint"])
            except ValueError as error:
                errors.append("rolling anchor endpoint: {0}".format(error))


def _validate_longitudinal_records(records, outer_scope, trust, errors):
    prior = -1
    identities = set()
    sequences = set()
    for index, record in enumerate(records):
        pointer = "/records/{0}".format(index)
        required = {"period", "period_source_ref", "semantics", "scope", "statistics"}
        allowed = required | {"period_boundary"}
        _closed_keys(record, allowed, required, pointer, errors)
        if not isinstance(record, Mapping):
            continue
        if record.get("scope") != outer_scope:
            errors.append("{0}/scope must equal outer scope".format(pointer))
        period = record.get("period")
        if not isinstance(period, Mapping) or set(period) != {"scheme", "value", "sequence"}:
            errors.append("{0}/period is invalid".format(pointer))
            continue
        sequence = period.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
            errors.append("{0}/period/sequence must be non-negative integer".format(pointer))
        elif sequence <= prior:
            errors.append("longitudinal records must be strictly sequence ordered")
        else:
            prior = sequence
        pair = (period.get("scheme"), period.get("value"))
        seq_pair = (period.get("scheme"), sequence)
        if pair in identities or seq_pair in sequences:
            errors.append("longitudinal period descriptors must be unique")
        identities.add(pair)
        sequences.add(seq_pair)
        semantics = record.get("semantics")
        if semantics not in ("period_delta", "cumulative_through_period",
                             "snapshot_at_period"):
            errors.append("{0}/semantics is invalid".format(pointer))
        expected_scope = "period" if semantics == "period_delta" else outer_scope.get("kind")
        statistics = record.get("statistics")
        if not isinstance(statistics, list):
            errors.append("{0}/statistics must be an array".format(pointer))
        else:
            for s_index, fact in enumerate(statistics):
                _validate_statistic_fact(
                    fact, pointer + "/statistics/{0}".format(s_index),
                    expected_scope, trust, errors)
        if "period_boundary" in record:
            try:
                validate_temporal_range(record["period_boundary"])
            except ValueError as error:
                errors.append("{0}/period_boundary: {1}".format(pointer, error))


def _validate_longitudinal_references(document, trust, errors):
    subject = document.get("subject", {})
    try:
        subject_identity = resolve_json_pointer(document, subject.get("identity_ref"))
    except ValueError as error:
        errors.append("subject identity_ref: {0}".format(error))
    else:
        if not isinstance(subject_identity, Mapping) or subject_identity.get(
                "entity_type") != subject.get("entity_type"):
            errors.append("subject identity_ref entity type mismatch")
    scope = document.get("scope", {})
    for key, entity_type in (("competition_identity_ref", "competition"),
                             ("season_identity_ref", "season")):
        if key not in scope:
            continue
        try:
            identity = resolve_json_pointer(document, scope[key])
        except (ValueError, TypeError) as error:
            errors.append("scope/{0}: {1}".format(key, error))
        else:
            if not isinstance(identity, Mapping) or identity.get("entity_type") != entity_type:
                errors.append("scope/{0} entity type mismatch".format(key))
    templates = trust.source_shape.get("semantic_binding_templates", [])
    for index, record in enumerate(document.get("records", [])):
        source_ref = record.get("period_source_ref") if isinstance(record, Mapping) else None
        try:
            evidence = resolve_json_pointer(document, source_ref)
        except (ValueError, TypeError) as error:
            errors.append("records/{0}/period_source_ref: {1}".format(index, error))
            continue
        period_source = evidence.get("longitudinal_period_source") \
            if isinstance(evidence, Mapping) else None
        if not isinstance(period_source, Mapping) or evidence.get(
                "kind") != "longitudinal_period_source":
            errors.append("record period_source_ref has wrong evidence kind")
            continue
        template = _template_by_ref(
            templates, period_source.get("binding_template_ref"), "longitudinal_period")
        try:
            artifact = _artifact_for_digest(period_source.get("artifact_digest"), trust)
            handle = _load_source_value_handle(
                artifact, template, {"record_index": index}, trust)
            built = _build_period_descriptor(
                handle, record_ref="/records/{0}".format(index), loaded_trust=trust)
        except (TypeError, ValueError) as error:
            errors.append("records/{0} period rebuild: {1}".format(index, error))
            continue
        expected = {"period": record.get("period")}
        if "period_boundary" in record:
            expected["period_boundary"] = record["period_boundary"]
        if built != expected:
            errors.append("records/{0} period does not match artifact rebuild".format(index))
    anchor = scope.get("anchor")
    if isinstance(anchor, Mapping) and anchor.get("kind") == "event":
        try:
            evidence = resolve_json_pointer(document, anchor.get("source_binding_ref"))
            anchor_source = evidence.get("rolling_event_anchor_source")
            template = _template_by_ref(
                templates, anchor_source.get("binding_template_ref"),
                "rolling_event_anchor")
            artifact = _artifact_for_digest(anchor_source.get("artifact_digest"), trust)
            handle = _load_source_value_handle(artifact, template, {}, trust)
            built = _build_rolling_event_anchor(
                handle, anchor_ref="/scope/anchor", loaded_trust=trust)
            identity = resolve_json_pointer(document, anchor.get("event_identity_ref"))
            event_source_record = resolve_json_pointer(
                document, anchor.get("event_source_ref"))
        except (AttributeError, TypeError, ValueError) as error:
            errors.append("rolling event anchor rebuild: {0}".format(error))
        else:
            source_value = event_source_record.get("source_value") \
                if isinstance(event_source_record, Mapping) else None
            if not isinstance(identity, Mapping) or identity.get("entity_type") != "event":
                errors.append("rolling event anchor identity is not an event")
            elif built.get("provider") != identity.get("provider") or built.get(
                    "resolution_method") != identity.get("resolution_method"):
                errors.append("rolling event anchor tuple does not match identity")
            if not isinstance(event_source_record, Mapping) or event_source_record.get(
                    "kind") != "source_value" or not isinstance(source_value, Mapping):
                errors.append("rolling event anchor event_source_ref has wrong evidence kind")
            elif source_value.get("artifact_digest") != anchor_source.get(
                    "artifact_digest") or source_value.get("value_pointer") != handle.expanded_pointers.get(
                        "event_source"):
                errors.append("rolling event anchor event source evidence mismatch")
            else:
                actual = resolve_json_pointer(
                    _reparse_source_artifact(artifact, trust), source_value["value_pointer"])
                if built.get("event_source") != actual:
                    errors.append("rolling event anchor source value does not recompute")


def _template_by_ref(templates, ref, semantic_kind):
    if not isinstance(ref, Mapping):
        raise CanonicalContractError("semantic template ref is invalid")
    matches = [template for template in templates
               if template.get("semantic_kind") == semantic_kind
               and template.get("binding_id") == ref.get("binding_id")
               and template.get("binding_version") == ref.get("binding_version")]
    if len(matches) != 1:
        raise CanonicalContractError("semantic template ref does not resolve exactly once")
    expected = _sha256(["machina-source-semantic-binding-template-v1", matches[0]])
    if ref.get("binding_digest") != expected:
        raise CanonicalContractError("semantic template ref digest mismatch")
    return matches[0]


def _artifact_for_digest(digest, trust):
    matches = [artifact for artifact in trust.source_artifacts
               if artifact.artifact_digest == digest]
    if len(matches) != 1:
        raise CanonicalContractError("source artifact digest does not resolve exactly once")
    return matches[0]


def _validate_successor_provenance(value, input_version, trust, errors):
    required = {"schema_version", "canonical_input_version", "canonical_package",
                "adapter", "source_artifact_digests"}
    _closed_keys(value, required, required, "provenance", errors)
    if not isinstance(value, Mapping):
        return
    if value.get("schema_version") != "machina-successor-provenance/1" or value.get(
            "canonical_input_version") != input_version:
        errors.append("successor provenance version is invalid")
    forbidden = {"rights", "rights_profile", "rights_profile_digest", "consumer_tier"}
    if forbidden.intersection(value):
        errors.append("successor provenance cannot contain rights")
    digests = value.get("source_artifact_digests")
    if not isinstance(digests, list) or digests != sorted(set(digests)) or any(
            _DIGEST_RE.fullmatch(item or "") is None for item in digests):
        errors.append("source artifact digests must be sorted and unique")


def _validate_envelope_rights(value, trust, errors):
    required = {"profile_id", "profile_version", "provider_namespace", "operation",
                "data_class", "prototype_only", "commercial_use",
                "allowed_consumer_tiers", "rights_profile_digest"}
    _closed_keys(value, required, required, "rights", errors)
    if isinstance(value, Mapping):
        expected = trust.rights_profile
        if any(value.get(key) != _thaw(expected.get(key)) for key in required):
            errors.append("rights do not equal the attested profile projection")


def _validate_runtime_free(value, errors):
    try:
        _assert_serializable(value)
    except (TypeError, ValueError) as error:
        errors.append(str(error))


def _validate_provider_namespaces(value, path, errors, parent_key=None):
    if isinstance(value, Mapping):
        for key, item in value.items():
            current = path + "/" + str(key)
            if key in _PROVIDER_NAMESPACE_FIELDS or key == "namespace" and parent_key in (
                    "provider", "source"):
                try:
                    validate_provider_namespace(item)
                except ValueError as error:
                    errors.append("{0}: {1}".format(current, error))
            _validate_provider_namespaces(item, current, errors, key)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_provider_namespaces(
                item, path + "/" + str(index), errors, parent_key)


def _load_source_artifact(
    data: bytes, loaded_trust: LoadedCanonicalTrustClosureV1
) -> SourceArtifactV1:
    trust = _require_trust(loaded_trust)
    media_type = trust.source_shape.get("media_type", "application/json")
    if media_type == "application/json":
        parsed = _strict_json_object(data, preserve_numbers=True)
    elif media_type in ("text/plain", "text/csv"):
        if not isinstance(data, bytes):
            raise TypeError("source artifact must be bytes")
        try:
            text = data.decode("utf-8", "strict")
        except UnicodeDecodeError as error:
            raise ValueError("malformed UTF-8 source artifact") from error
        if _contains_invalid_text(text):
            raise ValueError("invalid textual source artifact")
        parsed = {"text": text}
    elif media_type == "application/octet-stream":
        parsed = {"byte_length": len(data)}
    else:
        raise CanonicalContractError("unsupported-source-media-type")
    artifact = SourceArtifactV1(_ARTIFACT_SEAL, data, parsed, trust)
    trust._artifact_session.register(artifact, _SESSION_SEAL)
    return artifact


def _reparse_source_artifact(artifact, trust):
    if not isinstance(artifact, SourceArtifactV1) or artifact._closure_id is not trust.closure_id:
        raise TypeError("source artifact does not belong to this execution closure")
    digest = "sha256:" + hashlib.sha256(artifact.original_bytes).hexdigest()
    if digest != artifact.artifact_digest:
        raise CanonicalContractError("source-artifact-digest-mismatch")
    if artifact.media_type == "application/json":
        return _strict_json_object(artifact.original_bytes, preserve_numbers=True)
    if artifact.media_type in ("text/plain", "text/csv"):
        return {"text": artifact.original_bytes.decode("utf-8", "strict")}
    return {"byte_length": len(artifact.original_bytes)}


def _load_source_value_handle(artifact, template, bindings, trust_closure):
    """Create one same-tuple source handle inside the current artifact session."""
    trust = _require_trust(trust_closure)
    if not isinstance(artifact, SourceArtifactV1) or artifact._closure_id is not trust.closure_id:
        raise TypeError("current-execution source artifact required")
    if not isinstance(template, Mapping) or not isinstance(bindings, Mapping):
        raise TypeError("loaded template and binding tuple required")
    semantic_kind = template.get("semantic_kind")
    pointer_fields = {
        "scheme_pointer_template": "scheme", "value_pointer_template": "value",
        "sequence_pointer_template": "sequence", "boundary_pointer_template": "boundary",
        "provider_namespace_pointer_template": "provider_namespace",
        "provider_id_pointer_template": "provider_id",
        "resolution_method_pointer_template": "resolution_method",
        "event_source_pointer_template": "event_source",
    }
    expanded = {}
    for field, name in pointer_fields.items():
        if field in template:
            expanded[name] = _instantiate_template(template[field], bindings)
    if semantic_kind == "longitudinal_period":
        required = {"scheme", "value", "sequence"}
    elif semantic_kind == "rolling_event_anchor":
        required = {"provider_namespace", "provider_id", "resolution_method", "event_source"}
    else:
        raise CanonicalContractError("unsupported-source-value-handle-semantic-kind")
    if not required.issubset(expanded):
        raise CanonicalContractError("source-value-handle-template-incomplete")
    _reparse_source_artifact(artifact, trust)
    return LoadedSourceValueHandleV1(
        _HANDLE_SEAL, artifact, semantic_kind, template, dict(bindings), expanded, trust)


def _build_statistic_fact(
    document_handle: ValidatedDocumentHandleV1, *, fact_ref: str,
    trust_closure: LoadedCanonicalTrustClosureV1
) -> dict[str, Any]:
    trust = _same_execution(document_handle, trust_closure)
    document = _thaw(document_handle._document)
    fact = resolve_json_pointer(document, fact_ref)
    errors = []
    expected_scope = "event" if document_handle.schema_version == SUCCESSOR_SCHEMA_VERSION \
        else fact.get("scope") if isinstance(fact, Mapping) else None
    _validate_statistic_fact(fact, fact_ref, expected_scope, trust, errors)
    if errors:
        raise CanonicalContractError("invalid-statistic-fact", errors)
    if fact.get("kind") in ("official", "provider_native"):
        rebuilt = _rebuild_source_statistic(document, fact_ref, fact, trust)
        if rebuilt != fact:
            raise CanonicalContractError("source-statistic-binding-mismatch")
    _validate_statistic_dependency_graph(document, fact_ref, trust)
    return copy.deepcopy(dict(fact))


def _rebuild_source_statistic(document, fact_ref, fact, trust):
    templates = trust.source_shape.get("statistic_source_binding_templates", [])
    matches = []
    for template in templates:
        pattern = template.get("canonical_statistic_pointer_pattern")
        if _pointer_matches_pattern(fact_ref, pattern):
            matches.append(template)
    if len(matches) != 1:
        raise CanonicalContractError("statistic-source-binding-not-unique")
    template = matches[0]
    bindings = _bindings_from_pointer(
        template["canonical_statistic_pointer_pattern"], fact_ref)
    source_pointer = _instantiate_template(
        template["source_value_pointer_template"], bindings)
    evidence = resolve_json_pointer(document, fact["source_ref"])
    artifact = _artifact_for_evidence(evidence, trust)
    parsed = _reparse_source_artifact(artifact, trust)
    source_value = resolve_json_pointer(parsed, source_pointer)
    lexical = _parse_statistic_source(
        source_value, template["source_representation"], template["value_kind"])
    value = {"kind": template["value_kind"], "lexical": lexical}
    disposition = template["unit_disposition"]
    if disposition.get("kind") == "unit":
        value["unit"] = _thaw(disposition["unit"])
    return {"kind": template["statistic_kind"],
            "scope": template["statistic_scope"],
            "name": template["statistic_name"], "value": value,
            "source_ref": fact["source_ref"]}


def _parse_statistic_source(value, representation, output_kind):
    number_representations = {
        "json-number-exact-integer/1", "json-number-exact-decimal/1",
    }
    string_representations = {
        "json-string-canonical-integer/1", "json-string-canonical-decimal/1",
        "json-string-canonical-boolean/1", "json-string-canonical-duration/1",
        "json-string-text/1",
    }
    if representation in number_representations:
        if not isinstance(value, _JsonNumber):
            raise CanonicalContractError("statistic-source-representation-mismatch")
        parsed = decimal.Decimal(str(value))
        if not parsed.is_finite() or parsed == 0 and str(value).startswith("-"):
            raise CanonicalContractError("invalid-statistic-source-number")
        if output_kind == "integer":
            if parsed != parsed.to_integral_value():
                raise CanonicalContractError("statistic-source-is-not-integer")
            lexical = str(int(parsed))
        else:
            lexical = _canonical_decimal(parsed)
    elif representation == "json-boolean-exact/1":
        if not isinstance(value, bool):
            raise CanonicalContractError("statistic-source-representation-mismatch")
        lexical = "true" if value else "false"
    elif representation in string_representations:
        if isinstance(value, _JsonNumber) or not isinstance(value, str):
            raise CanonicalContractError("statistic-source-representation-mismatch")
        lexical = value
    else:
        raise CanonicalContractError("unknown-statistic-source-representation")
    return validate_statistic_lexical(output_kind, lexical)


def _validate_statistic_dependency_graph(document, root_ref, trust):
    nodes = set()
    edges = set()
    visiting = set()
    completed = set()

    def visit(pointer):
        if pointer in visiting:
            raise CanonicalContractError("statistic-derivation-cycle")
        if pointer in completed:
            return
        fact = resolve_json_pointer(document, pointer)
        if not isinstance(fact, Mapping) or fact.get("kind") not in _STATISTIC_KINDS:
            raise CanonicalContractError("statistic-input-not-a-fact")
        nodes.add(pointer)
        visiting.add(pointer)
        if fact.get("kind") == "derived":
            refs = fact.get("derivation", {}).get("input_refs", [])
            if len(refs) != len(set(refs)):
                raise CanonicalContractError("duplicate-statistic-input")
            for dependency in refs:
                edge = (dependency, pointer)
                if edge in edges or dependency == pointer:
                    raise CanonicalContractError("duplicate-or-self-statistic-edge")
                edges.add(edge)
                visit(dependency)
        elif "source_ref" not in fact:
            raise CanonicalContractError("statistic-leaf-not-source-backed")
        visiting.remove(pointer)
        completed.add(pointer)

    visit(root_ref)
    indegree = dict((node, 0) for node in nodes)
    outgoing = defaultdict(list)
    for dependency, dependent in edges:
        indegree[dependent] += 1
        outgoing[dependency].append(dependent)
    ready = sorted(node for node, count in indegree.items() if count == 0)
    order = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for dependent in sorted(outgoing[node]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
                ready.sort()
    if len(order) != len(nodes):
        raise CanonicalContractError("statistic-derivation-cycle")
    for pointer in order:
        fact = resolve_json_pointer(document, pointer)
        if fact.get("kind") != "derived":
            continue
        derivation = fact["derivation"]
        key = (derivation["id"], derivation["version"], derivation["algorithm_digest"])
        implementation = (trust.statistic_implementations or {}).get(key)
        if implementation is None:
            raise CanonicalContractError("statistic-implementation-key-missing")
        operands = [resolve_json_pointer(document, ref)["value"]
                    for ref in derivation["input_refs"]]
        result = implementation(tuple(copy.deepcopy(operands)))
        if result != fact["value"]:
            raise CanonicalContractError("derived-statistic-recomputation-mismatch")


def _build_period_descriptor(source_value_handle, *, record_ref: str,
                             loaded_trust: LoadedCanonicalTrustClosureV1) -> dict[str, Any]:
    trust = _require_trust(loaded_trust)
    handle = _require_source_handle(source_value_handle, "longitudinal_period", trust)
    if not _pointer_matches_pattern(record_ref, "/records/{record_index}"):
        raise CanonicalContractError("longitudinal-record-ref-mismatch")
    expected_bindings = _bindings_from_pointer("/records/{record_index}", record_ref)
    if dict(handle.occurrence_binding_tuple) != expected_bindings:
        raise CanonicalContractError("longitudinal-period-binding-tuple-mismatch")
    parsed = _reparse_source_artifact(handle.source_artifact, trust)
    values = dict((name, resolve_json_pointer(parsed, pointer))
                  for name, pointer in handle.expanded_pointers.items())
    template = handle.template
    scheme = values.get("scheme")
    value = values.get("value")
    sequence = _parse_non_negative_integer_source(
        values.get("sequence"),
        template["interpretation"]["sequence_numeric_parser"])
    if scheme not in template["interpretation"]["scheme_values"] or \
            not isinstance(value, str) or _TOKEN_RE.fullmatch(value) is None:
        raise CanonicalContractError("invalid-longitudinal-period-source-value")
    result = {"period": {"scheme": scheme, "value": value, "sequence": sequence}}
    if "boundary" in handle.expanded_pointers:
        boundary = values["boundary"]
        validate_temporal_range(boundary)
        result["period_boundary"] = copy.deepcopy(boundary)
    return result


def _build_rolling_event_anchor(source_value_handle, *, anchor_ref: str,
                                loaded_trust: LoadedCanonicalTrustClosureV1) -> dict[str, Any]:
    trust = _require_trust(loaded_trust)
    handle = _require_source_handle(source_value_handle, "rolling_event_anchor", trust)
    if anchor_ref != "/scope/anchor" or dict(handle.occurrence_binding_tuple):
        raise CanonicalContractError("rolling-anchor-binding-tuple-mismatch")
    parsed = _reparse_source_artifact(handle.source_artifact, trust)
    values = dict((name, resolve_json_pointer(parsed, pointer))
                  for name, pointer in handle.expanded_pointers.items())
    validate_provider_namespace(values.get("provider_namespace"))
    if values.get("resolution_method") not in _IDENTITY_METHODS:
        raise CanonicalContractError("rolling-anchor-resolution-method-invalid")
    if not isinstance(values.get("provider_id"), str) or not values["provider_id"]:
        raise CanonicalContractError("rolling-anchor-provider-id-invalid")
    return {"kind": "event", "provider": {
        "namespace": values["provider_namespace"], "id": values["provider_id"]},
        "resolution_method": values["resolution_method"],
        "event_source": copy.deepcopy(values["event_source"])}


def _require_source_handle(handle, semantic_kind, trust):
    if not isinstance(handle, LoadedSourceValueHandleV1) or \
            handle._closure_id is not trust.closure_id or \
            handle.semantic_kind != semantic_kind:
        raise TypeError("current-execution {0} source-value handle required".format(
            semantic_kind))
    return handle


def _parse_non_negative_integer_source(value, parser_ref):
    representation = parser_ref.get("source_representation") \
        if isinstance(parser_ref, Mapping) else None
    if representation == "json-number-exact-non-negative-integer/1":
        if not isinstance(value, _JsonNumber):
            raise CanonicalContractError("integer-source-representation-mismatch")
        lexical = str(value)
        try:
            parsed = decimal.Decimal(lexical)
        except decimal.InvalidOperation as error:
            raise CanonicalContractError("invalid-integer-source") from error
        if parsed != parsed.to_integral_value():
            raise CanonicalContractError("integer-source-is-fractional")
        lexical = str(int(parsed))
    elif representation == "json-string-canonical-non-negative-integer/1":
        if isinstance(value, _JsonNumber) or not isinstance(value, str):
            raise CanonicalContractError("integer-source-representation-mismatch")
        lexical = value
    else:
        raise CanonicalContractError("period-sequence-parser-is-not-non-negative-integer")
    if _NON_NEGATIVE_INTEGER_RE.fullmatch(lexical) is None:
        raise CanonicalContractError("period-sequence-is-not-canonical-non-negative-integer")
    return int(lexical)


def _validate_identity_occurrence(
    document_handle: ValidatedDocumentHandleV1, *, identity_ref: str,
    loaded_trust: LoadedCanonicalTrustClosureV1
) -> ValidatedIdentityOccurrenceHandleV1:
    trust = _same_execution(document_handle, loaded_trust)
    document = _thaw(document_handle._document)
    identity = resolve_json_pointer(document, identity_ref)
    errors = []
    _validate_identity_evidence(identity, trust, identity_ref, errors)
    if errors:
        raise CanonicalContractError("invalid-identity-occurrence", errors)
    if identity.get("provider", {}).get("namespace") != trust.descriptor.get(
            "provider_namespace"):
        raise CanonicalContractError("identity-descriptor-namespace-mismatch")
    return ValidatedIdentityOccurrenceHandleV1(
        _HANDLE_SEAL, document_handle, identity_ref, identity, trust)


def _derive_provider_scoped_entity_id(
    identity_occurrence_handle: ValidatedIdentityOccurrenceHandleV1
) -> str:
    if not isinstance(identity_occurrence_handle, ValidatedIdentityOccurrenceHandleV1):
        raise TypeError("validator-produced identity handle required")
    return _provider_scoped_id(
        identity_occurrence_handle.provider_namespace,
        identity_occurrence_handle.entity_type,
        identity_occurrence_handle.provider_id,
    )


def _derive_operational_resource_id(
    document_handle: ValidatedDocumentHandleV1, *, resource_kind: str,
    canonical_rfc6901_pointer: str
) -> str:
    if not isinstance(document_handle, ValidatedDocumentHandleV1):
        raise TypeError("validator-produced document handle required")
    if resource_kind not in ("participation", "action", "evidence", "projection"):
        raise ValueError("invalid operational resource kind")
    document = _thaw(document_handle._document)
    resolve_json_pointer(document, canonical_rfc6901_pointer)
    digest = hashlib.sha256(canonical_json_bytes([
        "machina-operational-resource-id-v1", document_handle.document_fingerprint,
        resource_kind, canonical_rfc6901_pointer,
    ])).hexdigest()
    return "urn:machina:resource:{0}:sha256:{1}".format(resource_kind, digest)


def _derive_operational_id_ledger(
    document_handle: ValidatedDocumentHandleV1, *,
    trust_closure: LoadedCanonicalTrustClosureV1
) -> OperationalIdLedgerV1:
    _same_execution(document_handle, trust_closure)
    document = _thaw(document_handle._document)
    values = {}
    if document_handle.schema_version == SUCCESSOR_SCHEMA_VERSION:
        body = document["observation"]
        for index in range(len(body.get("participants", []))):
            pointer = "/observation/participants/{0}".format(index)
            values[("participation", pointer)] = _derive_operational_resource_id(
                document_handle, resource_kind="participation",
                canonical_rfc6901_pointer=pointer)
        for index in range(len(body.get("actions", []))):
            pointer = "/observation/actions/{0}".format(index)
            values[("action", pointer)] = _derive_operational_resource_id(
                document_handle, resource_kind="action",
                canonical_rfc6901_pointer=pointer)
    for index in range(len(document.get("evidence_records", []))):
        pointer = "/evidence_records/{0}".format(index)
        values[("evidence", pointer)] = _derive_operational_resource_id(
            document_handle, resource_kind="evidence", canonical_rfc6901_pointer=pointer)
    return OperationalIdLedgerV1(document_handle, values)


def _same_execution(handle, trust_closure):
    trust = _require_trust(trust_closure)
    if not isinstance(handle, ValidatedDocumentHandleV1) or handle._closure_id is not trust.closure_id:
        raise TypeError("document handle and trust closure are not from one execution")
    return trust


def _normalize_spatial_evidence(
    document_handle: ValidatedDocumentHandleV1, *, action_ref: str,
    trust_closure: LoadedCanonicalTrustClosureV1
) -> dict[str, Any]:
    trust = _same_execution(document_handle, trust_closure)
    document = _thaw(document_handle._document)
    action = resolve_json_pointer(document, action_ref)
    request = action.get("spatial_evidence") if isinstance(action, Mapping) else None
    if not isinstance(request, Mapping):
        raise CanonicalContractError("action-has-no-spatial-evidence")
    source = request.get("source_position_source", {})
    evidence = resolve_json_pointer(document, source.get("source_ref"))
    binding_ref = source.get("binding_template_ref")
    template = _resolve_semantic_template(trust, binding_ref, "source_position_coordinates")
    artifact = _artifact_for_evidence(evidence, trust)
    parsed = _reparse_source_artifact(artifact, trust)
    action_index = int(action_ref.rsplit("/", 1)[-1])
    x_pointer = _instantiate_template(template["x_pointer_template"],
                                      {"action_index": action_index})
    y_pointer = _instantiate_template(template["y_pointer_template"],
                                      {"action_index": action_index})
    x = _parse_spatial_source(resolve_json_pointer(parsed, x_pointer),
                              template["x_source_representation"])
    y = _parse_spatial_source(resolve_json_pointer(parsed, y_pointer),
                              template["y_source_representation"])
    position = {
        "coordinate_system_ref": _thaw(
            template["interpretation"]["coordinate_system_ref"]),
        "coordinates": {"x": x, "y": y},
    }
    result = {"source_position": position, "effective_fidelity": "provider_native",
              "source_ref": source["source_ref"]}
    normalization = request.get("normalization")
    if isinstance(normalization, Mapping):
        current = position
        intermediates = []
        fidelity = "lossless_normalized"
        for ref in normalization.get("lineage", []):
            current, step_fidelity = _execute_transform(current, ref, trust)
            intermediates.append(current)
            if step_fidelity == "lossy_normalized":
                fidelity = step_fidelity
        if current.get("coordinate_system_ref") != normalization.get(
                "target_coordinate_system_ref"):
            raise CanonicalContractError("spatial-transform-target-mismatch")
        result.update({"normalized_position": current,
                       "normalization_lineage": copy.deepcopy(normalization["lineage"]),
                       "intermediate_positions": intermediates,
                       "effective_fidelity": fidelity})
    return result


def _parse_spatial_source(value, representation):
    if representation == "json-number-exact-spatial-decimal/1":
        if not isinstance(value, _JsonNumber):
            raise CanonicalContractError("spatial-source-representation-mismatch")
        parsed = decimal.Decimal(str(value))
        if not parsed.is_finite() or parsed == 0 and str(value).startswith("-"):
            raise CanonicalContractError("invalid-spatial-source-number")
        return _canonical_decimal(parsed)
    if representation == "json-string-canonical-spatial-decimal/1":
        if isinstance(value, _JsonNumber) or not isinstance(value, str):
            raise CanonicalContractError("spatial-source-representation-mismatch")
        return validate_spatial_decimal(value)
    raise CanonicalContractError("unknown-spatial-source-representation")


def _canonical_decimal(value):
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".") if not text.endswith(".0") else text
    if "." not in text:
        text += ".0"
    validate_spatial_decimal(text)
    return text


def _resolve_semantic_template(trust, binding_ref, semantic_kind):
    templates = trust.source_shape.get("semantic_binding_templates", [])
    matches = [item for item in templates if item.get("binding_id") == binding_ref.get(
        "binding_id") and item.get("binding_version") == binding_ref.get("binding_version")
        and item.get("semantic_kind") == semantic_kind]
    if len(matches) != 1:
        raise CanonicalContractError("semantic-binding-template-not-unique")
    expected_digest = _sha256(["machina-source-semantic-binding-template-v1", matches[0]])
    if binding_ref.get("binding_digest") != expected_digest:
        raise CanonicalContractError("semantic-binding-template-digest-mismatch")
    return matches[0]


def _artifact_for_evidence(evidence, trust):
    digest = None
    if isinstance(evidence, Mapping):
        for key in ("source_coordinates", "source_value", "period_source",
                    "coverage_source"):
            nested = evidence.get(key)
            if isinstance(nested, Mapping) and nested.get("artifact_digest"):
                digest = nested["artifact_digest"]
                break
    matches = [item for item in trust.source_artifacts if item.artifact_digest == digest]
    if len(matches) != 1:
        raise CanonicalContractError("source-artifact-not-registered-exactly-once")
    return matches[0]


def _instantiate_template(template, bindings):
    value = template
    for name, index in bindings.items():
        value = value.replace("{" + name + "}", str(index))
    if "{" in value or "}" in value:
        raise CanonicalContractError("source-template-binding-incomplete")
    validate_json_pointer(value)
    return value


def _execute_transform(position, ref, trust):
    entries = trust.spatial.get("transforms", {}).get("entries", [])
    key = (ref.get("id"), ref.get("version"), ref.get("algorithm_digest"))
    matches = [item for item in entries if (
        item.get("transform_id"), item.get("transform_version"),
        item.get("algorithm_digest")) == key]
    implementations = trust.spatial.get("transform_implementations", {})
    if len(matches) != 1 or key not in implementations:
        raise CanonicalContractError("spatial-transform-key-mismatch")
    x = decimal.Decimal(position["coordinates"]["x"])
    y = decimal.Decimal(position["coordinates"]["y"])
    out_x, out_y = implementations[key](x, y)
    entry = matches[0]
    scale = int(entry.get("output_scale", 4))
    quantum = decimal.Decimal(1).scaleb(-scale)
    out_x = out_x.quantize(quantum, rounding=decimal.ROUND_HALF_EVEN)
    out_y = out_y.quantize(quantum, rounding=decimal.ROUND_HALF_EVEN)
    return ({"coordinate_system_ref": _thaw(entry["output_coordinate_system"]),
             "coordinates": {"x": _canonical_decimal(out_x),
                             "y": _canonical_decimal(out_y)}},
            entry["reviewed_fidelity"])


def _derive_spatial_distance(
    document_handle: ValidatedDocumentHandleV1, *, action_ref: str,
    normalized_spatial: Mapping[str, Any],
    trust_closure: LoadedCanonicalTrustClosureV1
) -> dict[str, Any]:
    trust = _same_execution(document_handle, trust_closure)
    document = _thaw(document_handle._document)
    action = resolve_json_pointer(document, action_ref)
    request = action["spatial_evidence"].get("distance")
    if not isinstance(request, Mapping):
        raise CanonicalContractError("spatial-distance-not-requested")
    if request.get("origin") == "source_reported":
        evidence = resolve_json_pointer(document, request["source_ref"])
        artifact = _artifact_for_evidence(evidence, trust)
        parsed = _reparse_source_artifact(artifact, trust)
        action_index = int(action_ref.rsplit("/", 1)[-1])
        templates = [item for item in trust.source_shape.get(
            "semantic_binding_templates", []) if item.get(
                "semantic_kind") == "source_reported_distance"]
        if len(templates) != 1:
            raise CanonicalContractError("distance-template-not-unique")
        template = templates[0]
        pointer = _instantiate_template(template["value_pointer_template"],
                                        {"action_index": action_index})
        value = _parse_spatial_source(resolve_json_pointer(parsed, pointer),
                                      template["source_representation"])
        if decimal.Decimal(value) < 0:
            raise CanonicalContractError("source-distance-must-be-non-negative")
        return {"origin": "source_reported", "value": value,
                "unit": _thaw(template["interpretation"]["unit"]),
                "source_ref": request["source_ref"]}
    if request.get("origin") != "derived":
        raise CanonicalContractError("invalid-spatial-distance-origin")
    ref = request.get("metric_ref", {})
    key = (ref.get("id"), ref.get("version"), ref.get("algorithm_digest"))
    entries = trust.spatial.get("metrics", {}).get("entries", [])
    matches = [item for item in entries if (
        item.get("metric_ref", {}).get("id"),
        item.get("metric_ref", {}).get("version"),
        item.get("metric_ref", {}).get("algorithm_digest")) == key]
    if len(matches) != 1:
        raise CanonicalContractError("spatial-metric-key-mismatch")
    entry = matches[0]
    operands = request.get("operands")
    if not isinstance(operands, list) or len(operands) != 2:
        raise CanonicalContractError("spatial-metric-requires-two-operands")
    positions = [_resolve_spatial_operand(
        document_handle, action_ref, normalized_spatial, operand, trust)
                 for operand in operands]
    context = decimal.Context(prec=50, rounding=decimal.ROUND_HALF_EVEN)
    x1, y1 = (decimal.Decimal(positions[0]["coordinates"][key]) for key in ("x", "y"))
    x2, y2 = (decimal.Decimal(positions[1]["coordinates"][key]) for key in ("x", "y"))
    with decimal.localcontext(context):
        result = ((x2 - x1) ** 2 + (y2 - y1) ** 2).sqrt()
        scale = int(entry.get("output_scale", 1))
        result = result.quantize(decimal.Decimal(1).scaleb(-scale),
                                 rounding=decimal.ROUND_HALF_EVEN)
    return {"origin": "derived", "value": _canonical_decimal(result),
            "unit": _thaw(entry["output_unit"]),
            "metric_ref": copy.deepcopy(ref), "operands": copy.deepcopy(operands)}


def _resolve_spatial_operand(document_handle, own_action_ref, own, operand, trust):
    kind = operand.get("kind") if isinstance(operand, Mapping) else None
    if kind == "self_source_position":
        return own["source_position"]
    if kind == "self_normalized_position" and "normalized_position" in own:
        return own["normalized_position"]
    if kind == "document_position":
        pointer = operand.get("position_ref")
        match = re.fullmatch(
            r"/observation/actions/(0|[1-9][0-9]*)/spatial_evidence/(source_position|normalized_position)",
            pointer or "")
        if match is not None:
            referenced_action = "/observation/actions/{0}".format(match.group(1))
            if referenced_action == own_action_ref:
                raise CanonicalContractError("spatial-metric-self-document-operand")
            built = _normalize_spatial_evidence(
                document_handle, action_ref=referenced_action, trust_closure=trust)
            if match.group(2) in built:
                return built[match.group(2)]
    raise CanonicalContractError("invalid-spatial-metric-operand")


def _derive_spatial_zone(
    document_handle: ValidatedDocumentHandleV1, *, action_ref: str,
    normalized_spatial: Mapping[str, Any],
    trust_closure: LoadedCanonicalTrustClosureV1
) -> dict[str, Any]:
    trust = _same_execution(document_handle, trust_closure)
    document = _thaw(document_handle._document)
    action = resolve_json_pointer(document, action_ref)
    request = action["spatial_evidence"].get("zone")
    if not isinstance(request, Mapping):
        raise CanonicalContractError("spatial-zone-not-requested")
    if request.get("origin") == "provider_native":
        evidence = resolve_json_pointer(document, request["source_ref"])
        artifact = _artifact_for_evidence(evidence, trust)
        parsed = _reparse_source_artifact(artifact, trust)
        templates = [item for item in trust.source_shape.get(
            "semantic_binding_templates", []) if item.get(
                "semantic_kind") == "provider_native_zone"]
        if len(templates) != 1:
            raise CanonicalContractError("zone-template-not-unique")
        template = templates[0]
        action_index = int(action_ref.rsplit("/", 1)[-1])
        pointer = _instantiate_template(template["value_pointer_template"],
                                        {"action_index": action_index})
        source = resolve_json_pointer(parsed, pointer)
        interpretation = template["interpretation"]
        value = _interpret_provider_zone(source, interpretation, trust)
        return {"origin": "provider_native",
                "scheme_ref": _thaw(interpretation["scheme_ref"]),
                "value": value, "source_ref": request["source_ref"],
                "provider_namespace": trust.descriptor["provider_namespace"]}
    if request.get("origin") != "derived" or "normalized_position" not in normalized_spatial:
        raise CanonicalContractError("derived-zone-requires-normalized-position")
    ref = request.get("scheme_ref", {})
    entries = trust.spatial.get("zones", {}).get("entries", [])
    matches = [entry for entry in entries if entry.get("scheme_ref") == ref]
    if len(matches) != 1:
        raise CanonicalContractError("zone-scheme-ref-mismatch")
    entry = matches[0]
    position = normalized_spatial["normalized_position"]
    x = decimal.Decimal(position["coordinates"]["x"])
    y = decimal.Decimal(position["coordinates"]["y"])
    matched = []
    for region in entry.get("regions", []):
        rectangle = region["rectangle"]
        if (decimal.Decimal(rectangle["min_x"]) <= x <= decimal.Decimal(rectangle["max_x"])
                and decimal.Decimal(rectangle["min_y"]) <= y <= decimal.Decimal(rectangle["max_y"])):
            matched.append(region)
    if not matched:
        raise CanonicalContractError("point-not-in-zone-scheme")
    region = sorted(matched, key=lambda item: item["order"])[0]
    return {"origin": "derived", "scheme_ref": copy.deepcopy(ref),
            "value": region["zone_value"],
            "normalized_position_ref": action_ref + "/spatial_evidence/normalized_position"}


def _interpret_provider_zone(source, interpretation, trust):
    kind = interpretation.get("kind")
    if kind == "closed_vocabulary" and source in interpretation.get("allowed_source_values", []):
        return source
    if kind == "value_mapping":
        matches = [entry["zone_value"] for entry in interpretation.get("entries", [])
                   if entry.get("source_lexical") == source]
        if len(matches) == 1:
            return matches[0]
    if kind == "deterministic_field":
        ref = interpretation.get("interpreter", {})
        key = (ref.get("id"), ref.get("version"), ref.get("algorithm_digest"))
        implementation = trust.spatial.get("zone_interpreters", {}).get(key)
        if implementation is not None:
            value = implementation(source)
            if value in interpretation.get("allowed_output_values", []):
                return value
    raise CanonicalContractError("provider-zone-interpretation-failed")


def _build_canonical_spatial_evidence(
    document_handle: ValidatedDocumentHandleV1, *, action_ref: str,
    trust_closure: LoadedCanonicalTrustClosureV1
) -> dict[str, Any]:
    result = _normalize_spatial_evidence(
        document_handle, action_ref=action_ref, trust_closure=trust_closure)
    document = _thaw(document_handle._document)
    request = resolve_json_pointer(document, action_ref)["spatial_evidence"]
    if "distance" in request:
        result["distance"] = _derive_spatial_distance(
            document_handle, action_ref=action_ref, normalized_spatial=result,
            trust_closure=trust_closure)
    if "zone" in request:
        result["zone"] = _derive_spatial_zone(
            document_handle, action_ref=action_ref, normalized_spatial=result,
            trust_closure=trust_closure)
    return result


def _build_coverage_evidence(
    document: Mapping[str, Any], *, claim_ref: str,
    source_artifact: SourceArtifactV1,
    loaded_trust: LoadedCanonicalTrustClosureV1
) -> dict[str, Any]:
    trust = _require_trust(loaded_trust)
    parsed = _reparse_source_artifact(source_artifact, trust)
    claim = resolve_json_pointer(document, claim_ref)
    collection_pointer = claim["collection_pointer"]
    collection = resolve_json_pointer(document, collection_pointer)
    if not isinstance(collection, list):
        raise CanonicalContractError("coverage-target-is-not-array")
    promise = _promise_for_pointer(collection_pointer, trust)
    source_fields = promise.get("source_fields", {})
    facts = _read_coverage_source_facts(parsed, source_fields)
    returned = len(collection)
    total = facts["total"]
    if total["state"] == "known" and total["count"] < returned:
        raise CanonicalContractError("coverage-total-less-than-returned")
    positive_partial = (
        facts["truncation"].get("state") == "truncated"
        or facts["cursor"].get("state") == "present"
        or total.get("state") == "known" and total.get("count") > returned
    )
    if total.get("state") == "known" and total.get("count") == returned and not positive_partial:
        completeness = "complete"
    elif positive_partial:
        completeness = "partial"
    else:
        completeness = "unknown"
    return {"target": claim["target"], "collection_pointer": collection_pointer,
            "returned_count": returned, "available_total": total,
            "completeness": completeness,
            "truncation": facts["truncation"].get("state", "unknown"),
            "limitations": [], "source_ref": claim.get("source_ref", claim_ref)}


def _promise_for_pointer(pointer, trust):
    matches = [item for item in trust.operation_contract.get("promised_collections", [])
               if _pointer_matches_pattern(pointer, item.get("pointer_pattern"))]
    if len(matches) != 1:
        raise CanonicalContractError("collection-promise-not-unique")
    return matches[0]


def _read_coverage_source_facts(parsed, source_fields):
    result = {}
    for name in ("total", "truncation", "cursor", "page_cap", "request_limit"):
        contract = source_fields.get(name, {})
        if contract.get("state") == "value":
            pointers = contract.get("value_pointer_templates", [])
            if len(pointers) != 1:
                raise CanonicalContractError("coverage-value-pointer-not-unique")
            value = resolve_json_pointer(parsed, pointers[0])
            if name == "total":
                result[name] = {"state": "known", "count": int(str(value))}
            elif name == "truncation":
                result[name] = {"state": "truncated" if bool(value) else "not_truncated"}
            elif name == "cursor":
                result[name] = {"state": "present" if value else "absent"}
            else:
                result[name] = {"state": "known", "count": int(str(value))}
        else:
            probes = contract.get("absence_probe_templates", [])
            for probe in probes:
                pointer = probe.get("pointer_template")
                if probe.get("probe") == "member_absent":
                    try:
                        resolve_json_pointer(parsed, pointer)
                    except ValueError:
                        continue
                    raise CanonicalContractError("coverage-absence-probe-failed")
            if name == "total":
                result[name] = {"state": "unavailable"}
            elif name == "truncation":
                result[name] = {"state": "unavailable"}
            else:
                result[name] = {"state": contract.get("result", "unavailable")}
    return result


def _expand_managed_collection_patterns(
    document_handle: ValidatedDocumentHandleV1, *,
    loaded_trust: LoadedCanonicalTrustClosureV1
) -> CollectionExpansionWitnessSetV1:
    trust = _same_execution(document_handle, loaded_trust)
    document = _thaw(document_handle._document)
    kind = "event" if document_handle.schema_version == SUCCESSOR_SCHEMA_VERSION else "longitudinal"
    census = _event_census() if kind == "event" else _longitudinal_census()
    promises = trust.operation_contract.get("promised_collections", [])
    promised = {item.get("pointer_pattern") for item in promises}
    present = set(_present_managed_collections(document, kind))
    witnesses = []
    for pattern in census:
        matches = sorted(pointer for pointer in present if _pointer_matches_pattern(pointer, pattern))
        state = "promised" if pattern in promised else "not_promised"
        if state == "not_promised" and matches:
            raise CanonicalContractError("unpromised-managed-collection-present")
        variables = re.findall(r"\{([A-Za-z][A-Za-z0-9._-]*)\}", pattern)
        bindings = []
        for pointer in matches:
            bindings.append({"values": _bindings_from_pointer(pattern, pointer),
                             "collection_pointer": pointer,
                             "instantiated_source_pointers": []})
        if state == "promised" and not variables and not matches:
            raise CanonicalContractError("promised-managed-root-absent")
        witnesses.append({"pointer_pattern": pattern,
                          "parent_pointer": pattern.rsplit("/", 1)[0],
                          "expansion_kind": "wildcard" if variables else "exact",
                          "promise_state": state, "wildcard_variables": variables,
                          "bindings": bindings, "resolved_occurrence_pointers": matches,
                          "occurrence_count": len(matches)})
    return CollectionExpansionWitnessSetV1(witnesses)


def _event_census():
    return ("/observation/participants", "/observation/actions",
            "/observation/participants/{participant_index}/statistics")


def _longitudinal_census():
    return ("/records", "/aggregates", "/records/{record_index}/statistics")


def _bindings_from_pointer(pattern, pointer):
    names = re.findall(r"\{([A-Za-z][A-Za-z0-9._-]*)\}", pattern)
    expression = re.escape(pattern)
    for name in names:
        expression = expression.replace(re.escape("{" + name + "}"), r"([0-9]+)", 1)
    match = re.fullmatch(expression, pointer)
    return dict((name, int(value)) for name, value in zip(names, match.groups()))


def _build_successor_provenance(
    document_handle: ValidatedDocumentHandleV1, *,
    source_artifacts: Sequence[SourceArtifactV1],
    loaded_trust: LoadedCanonicalTrustClosureV1
) -> dict[str, Any]:
    trust = _same_execution(document_handle, loaded_trust)
    if any(not isinstance(item, SourceArtifactV1) or item._closure_id is not trust.closure_id
           for item in source_artifacts):
        raise TypeError("source artifacts must belong to the current execution")
    package = trust.package_release
    descriptor = trust.descriptor
    descriptor_digest = _sha256(["machina-adapter-descriptor-v1", descriptor])
    return {
        "schema_version": "machina-successor-provenance/1",
        "canonical_input_version": document_handle.schema_version,
        "canonical_package": {
            "name": package["name"], "version": package["version"],
            "package_artifact_digest": package["package_artifact_digest"],
            "release_id": package["release_id"],
            "release_digest": package["release_digest"],
        },
        "adapter": {
            "provider_namespace": descriptor["provider_namespace"],
            "operation": descriptor["operation"],
            "descriptor_digest": descriptor_digest,
        },
        "source_artifact_digests": sorted(set(
            artifact.artifact_digest for artifact in source_artifacts)),
    }


def _build_successor_envelope(
    document_handle: ValidatedDocumentHandleV1, *, output_mode: str,
    trust_closure: LoadedCanonicalTrustClosureV1
) -> bytes:
    trust = _same_execution(document_handle, trust_closure)
    if output_mode not in _OUTPUT_MODES:
        raise CanonicalContractError("invalid-output-mode")
    ledger = _derive_operational_id_ledger(
        document_handle, trust_closure=trust)
    document = _thaw(document_handle._document)
    if document_handle.schema_version == SUCCESSOR_SCHEMA_VERSION:
        candidate = _event_envelope_candidate(document_handle, ledger, output_mode, trust)
    elif document_handle.schema_version == LONGITUDINAL_SCHEMA_VERSION:
        if output_mode != "operational_only":
            raise CanonicalContractError("longitudinal-output-mode-operational-only")
        candidate = _longitudinal_envelope_candidate(document_handle, ledger, trust)
    else:
        raise CanonicalContractError("unsupported-successor-document")
    candidate_bytes = canonical_json_bytes(candidate)
    if document_handle.schema_version == SUCCESSOR_SCHEMA_VERSION:
        validated = _validate_successor_envelope_bytes(
            candidate_bytes, trust_closure=trust)
    else:
        validated = _validate_longitudinal_envelope_bytes(
            candidate_bytes, trust_closure=trust)
    _postflight(candidate, output_mode, trust)
    return validated


def _event_envelope_candidate(handle, ledger, output_mode, trust):
    document = _thaw(handle._document)
    body = copy.deepcopy(document["observation"])
    body.pop("adapter", None)
    body.pop("rights", None)
    for index, action in enumerate(body.get("actions", [])):
        if isinstance(action, dict) and "spatial_evidence" in action:
            action["spatial_evidence"] = _build_canonical_spatial_evidence(
                handle, action_ref="/observation/actions/{0}".format(index),
                trust_closure=trust)
    view = {
        "observation": body,
        "coordinate_system_registry": copy.deepcopy(document["coordinate_system_registry"]),
        "period_registry": copy.deepcopy(document["period_registry"]),
        "evidence_records": copy.deepcopy(document["evidence_records"]),
        "collection_claims": copy.deepcopy(document["collection_claims"]),
        "coverage": copy.deepcopy(document["coverage"]),
        "identity_subjects": copy.deepcopy(document["identity_subjects"]),
        "identity_evidence": copy.deepcopy(document["identity_evidence"]),
        "statistic_projections": [],
    }
    exact = "start_time" in document["observation"].get("event", {})
    graph = None
    if output_mode == "with_iptc_graph":
        if not exact:
            raise GraphSelectionRefused("exact-event-start-time-required")
        if any(item.get("status") != "authoritatively_resolved"
               for item in document["identity_evidence"]):
            raise GraphSelectionRefused("canonical-identity-required-for-graph")
        graph = _project_successor_graph(
            handle, operational_id_ledger=ledger, trust_closure=trust)
    spatial = []
    for p_index, participant in enumerate(body.get("participants", [])):
        for s_index, fact in enumerate(participant.get("statistics", [])):
            pointer = "/machina_sports_schema/event_view/observation/participants/{0}/statistics/{1}".format(p_index, s_index)
            disposition = _statistic_projection_disposition(
                handle,
                statistic_ref="/observation/participants/{0}/statistics/{1}".format(
                    p_index, s_index), output_mode=output_mode, trust_closure=trust)
            disposition["statistic_ref"] = pointer
            view["statistic_projections"].append(disposition)
    for index, action in enumerate(body.get("actions", [])):
        if "spatial_evidence" not in action:
            continue
        reason = "closed-shape-not-admitted" if graph is not None else (
            "graph-unavailable-reduced-time" if not exact else
            "output-mode-operational-only")
        spatial.append({
            "spatial_ref": "/machina_sports_schema/event_view/observation/actions/{0}/spatial_evidence".format(index),
            "emission_status": "not_projected", "reason": reason,
        })
    if spatial:
        view["spatial_projections"] = spatial
    root = {
        "schema_version": SUCCESSOR_MACHINA_SCHEMA_VERSION,
        "profile": SUCCESSOR_PROFILE_VERSION,
        "event_view": _rebase_pointers(view, "event"),
    }
    if graph is not None:
        root["sport_schema_graph"] = graph
    root["capabilities"] = _event_capability_report(document, exact, output_mode, trust)
    root["provenance"] = _build_successor_provenance(
        handle, source_artifacts=tuple(trust.source_artifacts), loaded_trust=trust)
    root["rights"] = _project_envelope_rights(trust)
    return {"machina_sports_schema": root}


def _longitudinal_envelope_candidate(handle, ledger, trust):
    document = _thaw(handle._document)
    view = {
        key: copy.deepcopy(document[key])
        for key in ("observed_at", "subject", "scope", "records", "aggregates",
                    "evidence_records", "collection_claims", "coverage",
                    "identity_subjects", "identity_evidence")
    }
    projections = []
    for r_index, record in enumerate(document["records"]):
        for s_index, _fact in enumerate(record["statistics"]):
            projections.append({
                "statistic_ref": "/machina_longitudinal_schema/longitudinal_view/records/{0}/statistics/{1}".format(r_index, s_index),
                "emission_status": "not_projected",
                "reason": "longitudinal-contract-no-iptc-projection",
            })
    for index, _fact in enumerate(document["aggregates"]):
        projections.append({
            "statistic_ref": "/machina_longitudinal_schema/longitudinal_view/aggregates/{0}".format(index),
            "emission_status": "not_projected",
            "reason": "longitudinal-contract-no-iptc-projection",
        })
    view["statistic_projections"] = projections
    view = _rebase_pointers(view, "longitudinal")
    root = {
        "schema_version": LONGITUDINAL_MACHINA_SCHEMA_VERSION,
        "longitudinal_view": view,
        "capabilities": _longitudinal_capability_report(document, trust),
        "provenance": _build_successor_provenance(
            handle, source_artifacts=tuple(trust.source_artifacts), loaded_trust=trust),
        "rights": _project_envelope_rights(trust),
    }
    return {"machina_longitudinal_schema": root}


def _rebase_pointers(value, kind):
    prefix = "/machina_sports_schema/event_view" if kind == "event" \
        else "/machina_longitudinal_schema/longitudinal_view"
    if isinstance(value, dict):
        return dict((key, _rebase_pointers(item, kind)) for key, item in value.items())
    if isinstance(value, list):
        return [_rebase_pointers(item, kind) for item in value]
    if isinstance(value, str) and value.startswith("/"):
        return prefix + value
    return value


def _project_envelope_rights(trust):
    rights = copy.deepcopy(dict(trust.rights_profile))
    if "rights_profile_digest" not in rights:
        rights["rights_profile_digest"] = _sha256([
            "machina-adapter-rights-profile-v1", rights])
    return rights


def _event_capability_report(document, exact, output_mode, trust):
    present = []
    body = document["observation"]
    if any(participant.get("statistics") for participant in body.get("participants", [])):
        present.append("event.participation_statistics")
    if any("spatial_evidence" in action for action in body.get("actions", [])):
        present.append("event.action.spatial_evidence")
    if document.get("identity_evidence"):
        present.append("identity.resolution_evidence")
    target_map = {"participants": "result.coverage.participants",
                  "actions": "result.coverage.actions",
                  "statistics": "result.coverage.statistics"}
    for item in document.get("coverage", []):
        if item.get("target") in target_map:
            present.append(target_map[item["target"]])
    report = {"tier": None, "tiers_satisfied": [], "present": sorted(set(present)),
              "absent": [], "not_expressible": [], "by_tier": {}, "violations": []}
    if not exact:
        report["graph_unavailable_reason"] = "exact-event-start-time-required"
    return report


def _longitudinal_capability_report(document, trust):
    present = []
    if any(record.get("statistics") for record in document["records"]) or document["aggregates"]:
        present.append("longitudinal.statistics")
    targets = {"records": "longitudinal.result.coverage.records",
               "statistics": "longitudinal.result.coverage.statistics",
               "aggregates": "longitudinal.result.coverage.aggregates"}
    for item in document["coverage"]:
        if item.get("target") in targets:
            present.append(targets[item["target"]])
    if document["identity_evidence"]:
        present.append("longitudinal.identity.resolution_evidence")
    return {"schema_version": "machina-longitudinal-capabilities/1", "tier": None,
            "tiers_satisfied": [], "present": sorted(set(present)), "absent": [],
            "not_expressible": [], "by_tier": {}, "violations": []}


def _project_successor_graph(
    document_handle: ValidatedDocumentHandleV1, *,
    operational_id_ledger: OperationalIdLedgerV1,
    trust_closure: LoadedCanonicalTrustClosureV1
) -> Mapping[str, Any]:
    trust = _same_execution(document_handle, trust_closure)
    if operational_id_ledger.document_handle is not document_handle:
        raise TypeError("operational ID ledger belongs to another document")
    document = _thaw(document_handle._document)
    if any(item.get("status") != "authoritatively_resolved"
           for item in document["identity_evidence"]):
        raise GraphSelectionRefused("canonical-identity-required-for-graph")
    graph = []
    entries = trust.admissibility.get("entries", []) if isinstance(
        trust.admissibility, Mapping) else []
    for p_index, participant in enumerate(document["observation"].get("participants", [])):
        properties = {}
        for fact in participant.get("statistics", []):
            matches = [entry for entry in entries if entry.get("curie") == fact.get("name")
                       and entry.get("participation_kind") == participant.get("kind")]
            if len(matches) == 1 and matches[0].get("admitted") is True:
                properties[fact["name"]] = {"@value": fact["value"]["lexical"],
                                             "@type": matches[0]["shacl_datatype"]}
        if properties:
            pointer = "/observation/participants/{0}".format(p_index)
            node = {"@id": operational_id_ledger.ids_by_input_pointer[
                ("participation", pointer)],
                    "@type": "sport:TeamParticipation" if participant.get(
                        "kind") == "team" else "sport:IndividualParticipation"}
            node.update(properties)
            graph.append(node)
    return {"@context": shared_context(), "@graph": graph}


def _statistic_projection_disposition(
    document_handle: ValidatedDocumentHandleV1, *, statistic_ref: str,
    output_mode: str, trust_closure: LoadedCanonicalTrustClosureV1
) -> dict[str, str]:
    trust = _same_execution(document_handle, trust_closure)
    document = _thaw(document_handle._document)
    fact = resolve_json_pointer(document, statistic_ref)
    if document_handle.schema_version == LONGITUDINAL_SCHEMA_VERSION:
        return {"emission_status": "not_projected",
                "reason": "longitudinal-contract-no-iptc-projection"}
    exact = "start_time" in document["observation"].get("event", {})
    if not exact:
        return {"emission_status": "not_projected",
                "reason": "graph-unavailable-reduced-time"}
    if output_mode == "operational_only":
        return {"emission_status": "not_projected",
                "reason": "output-mode-operational-only"}
    if fact.get("kind") == "provider_native":
        return {"emission_status": "not_projected",
                "reason": "provider-native-not-official"}
    if fact.get("kind") == "derived":
        return {"emission_status": "not_projected", "reason": "derived-not-official"}
    participant = resolve_json_pointer(document, statistic_ref.rsplit("/statistics/", 1)[0])
    matches = [entry for entry in trust.admissibility.get("entries", [])
               if entry.get("curie") == fact.get("name")
               and entry.get("participation_kind") == participant.get("kind")]
    if len(matches) != 1 or matches[0].get("admitted") is not True:
        return {"emission_status": "not_projected",
                "reason": "closed-shape-not-admitted"}
    if not matches[0].get("lexicalization"):
        return {"emission_status": "not_projected",
                "reason": "datatype-conversion-unrepresentable"}
    return {"emission_status": "projected", "reason": "shape-admitted"}


def _validate_successor_envelope(
    envelope: Mapping[str, Any], *, source_artifacts: Sequence[SourceArtifactV1],
    trust_closure: LoadedCanonicalTrustClosureV1
) -> list[str]:
    trust = _require_trust(trust_closure)
    errors = []
    if not isinstance(envelope, Mapping) or set(envelope) != {"machina_sports_schema"}:
        return ["envelope must contain only machina_sports_schema"]
    root = envelope["machina_sports_schema"]
    allowed = {"schema_version", "profile", "event_view", "sport_schema_graph",
               "capabilities", "provenance", "rights"}
    required = allowed - {"sport_schema_graph"}
    _closed_keys(root, allowed, required, "machina_sports_schema", errors)
    if not isinstance(root, Mapping):
        return errors
    if root.get("schema_version") != SUCCESSOR_MACHINA_SCHEMA_VERSION or root.get(
            "profile") != SUCCESSOR_PROFILE_VERSION:
        errors.append("successor envelope versions are invalid")
    _validate_successor_provenance(root.get("provenance"), SUCCESSOR_SCHEMA_VERSION,
                                   trust, errors)
    _validate_envelope_rights(root.get("rights"), trust, errors)
    graph = root.get("sport_schema_graph")
    if graph is not None:
        if not isinstance(graph, Mapping) or list(graph) != ["@context", "@graph"]:
            errors.append("sport_schema_graph has invalid members/order")
        elif graph.get("@context") != shared_context():
            errors.append("sport_schema_graph context differs from pinned context")
        else:
            for node in graph.get("@graph", []):
                if not isinstance(node, Mapping) or str(node.get("@type", "")).startswith(
                        "machina:") or any(str(key).startswith("machina:") for key in node):
                    errors.append("profile 1.3 graph contains a Machina resource/property")
    _validate_runtime_free(envelope, errors)
    expected = sorted(artifact.artifact_digest for artifact in source_artifacts)
    actual = root.get("provenance", {}).get("source_artifact_digests", [])
    if expected != actual:
        errors.append("successor provenance artifact set differs")
    return errors


def _validate_successor_envelope_bytes(
    candidate_bytes: bytes, *, trust_closure: LoadedCanonicalTrustClosureV1
) -> bytes:
    trust = _require_trust(trust_closure)
    envelope = _strict_json_object(candidate_bytes)
    errors = _validate_successor_envelope(
        envelope, source_artifacts=tuple(trust.source_artifacts), trust_closure=trust)
    if errors:
        raise CanonicalContractError("invalid-final-successor-envelope", errors)
    if canonical_json_bytes(envelope) != candidate_bytes:
        raise CanonicalContractError("final-envelope-bytes-not-canonical")
    return bytes(candidate_bytes)


def _validate_longitudinal_envelope_bytes(
    candidate_bytes: bytes, *, trust_closure: LoadedCanonicalTrustClosureV1
) -> bytes:
    trust = _require_trust(trust_closure)
    envelope = _strict_json_object(candidate_bytes)
    errors = []
    if set(envelope) != {"machina_longitudinal_schema"}:
        errors.append("longitudinal envelope root is invalid")
    else:
        root = envelope["machina_longitudinal_schema"]
        required = {"schema_version", "longitudinal_view", "capabilities",
                    "provenance", "rights"}
        _closed_keys(root, required, required, "machina_longitudinal_schema", errors)
        if isinstance(root, Mapping):
            if root.get("schema_version") != LONGITUDINAL_MACHINA_SCHEMA_VERSION:
                errors.append("longitudinal envelope version is invalid")
            _validate_successor_provenance(
                root.get("provenance"), LONGITUDINAL_SCHEMA_VERSION, trust, errors)
            _validate_envelope_rights(root.get("rights"), trust, errors)
            if "sport_schema_graph" in root:
                errors.append("longitudinal envelope cannot contain an IPTC graph")
    _validate_runtime_free(envelope, errors)
    if errors:
        raise CanonicalContractError("invalid-final-longitudinal-envelope", errors)
    if canonical_json_bytes(envelope) != candidate_bytes:
        raise CanonicalContractError("final-envelope-bytes-not-canonical")
    return bytes(candidate_bytes)


def _postflight(candidate, output_mode, trust):
    key = "machina_sports_schema" if "machina_sports_schema" in candidate \
        else "machina_longitudinal_schema"
    root = candidate[key]
    rights = root.get("rights", {})
    tier = getattr(trust, "_requested_consumer_tier", None)
    if tier is not None and tier not in rights.get("allowed_consumer_tiers", []):
        raise CanonicalContractError("consumer-tier-not-allowed")
    required = getattr(trust, "_required_capabilities", ())
    present = set(root.get("capabilities", {}).get("present", []))
    output_kind = "event" if key == "machina_sports_schema" else "longitudinal"
    mappings = trust.capability_contract.get("mappings", []) if isinstance(
        trust.capability_contract, Mapping) else []
    for capability in required:
        records = [item.get("record_capability") for item in mappings
                   if item.get("adapter_capability") == capability
                   and item.get("output_kind") == output_kind]
        if len(records) != 1 or records[0] not in present:
            raise CanonicalContractError("required-record-capability-missing")


class TrustedAdapterPackageLoaderV1(Protocol):
    def load_static(self, package_ref, request): ...
    def import_adapter(self, trust_closure): ...


def execute_adapter_operation(
    *, package_ref: Mapping[str, Any], request_bytes: bytes,
    operation_arguments_bytes: bytes,
    trusted_loader: TrustedAdapterPackageLoaderV1
) -> bytes:
    request = _strict_json_object(request_bytes)
    required_request = {"requested_provider", "requested_operation", "output_kind",
                        "output_mode", "consumer_tier", "requires", "optional"}
    if set(request) != required_request:
        raise CanonicalContractError("invalid-execution-request-members")
    validate_provider_namespace(request["requested_provider"])
    if request["output_mode"] not in _OUTPUT_MODES or request["consumer_tier"] not in _CONSUMER_TIERS:
        raise CanonicalContractError("invalid-output-mode-or-consumer-tier")
    if request["output_kind"] not in ("event", "longitudinal"):
        raise CanonicalContractError("invalid-output-kind")
    if request["output_kind"] == "longitudinal" and request["output_mode"] != "operational_only":
        raise CanonicalContractError("longitudinal-output-mode-operational-only")
    for key in ("requires", "optional"):
        if not isinstance(request[key], list) or len(request[key]) != len(set(request[key])):
            raise CanonicalContractError("capability-lists-must-be-unique")
    if set(request["requires"]).intersection(request["optional"]):
        raise CanonicalContractError("required-and-optional-capabilities-overlap")
    if not hasattr(trusted_loader, "load_static") or not hasattr(trusted_loader, "import_adapter"):
        raise TypeError("trusted_loader does not implement TrustedAdapterPackageLoaderV1")
    trust = _require_trust(trusted_loader.load_static(package_ref, request))
    if trust.source_artifacts or trust._requested_consumer_tier is not None or \
            trust._required_capabilities:
        raise CanonicalContractError("loaded-trust-closure-reused")
    descriptor = trust.descriptor
    if descriptor.get("provider_namespace") != request["requested_provider"] or descriptor.get(
            "operation") != request["requested_operation"]:
        raise CanonicalContractError("request-descriptor-mismatch")
    descriptor_capabilities = set(descriptor.get("capabilities", []))
    if not set(request["requires"]).issubset(descriptor_capabilities):
        raise CanonicalContractError("required-adapter-capability-missing")
    argument_handle = _validate_operation_arguments(operation_arguments_bytes, trust)
    object.__setattr__(trust, "_requested_consumer_tier", request["consumer_tier"])
    object.__setattr__(trust, "_required_capabilities", tuple(request["requires"]))
    if request["consumer_tier"] not in trust.rights_profile.get("allowed_consumer_tiers", []):
        raise CanonicalContractError("consumer-tier-not-allowed")
    adapter = trusted_loader.import_adapter(trust)
    if not hasattr(adapter, "fetch"):
        raise TypeError("attested adapter has no fetch operation")
    raw_source = adapter.fetch(argument_handle)
    artifact = _load_source_artifact(raw_source, trust)
    if not callable(trust.document_builder):
        raise CanonicalContractError("package-document-builder-missing")
    document = trust.document_builder(artifact, argument_handle, request, trust)
    document_bytes = canonical_json_bytes(document)
    if request["output_kind"] == "event":
        parsed = parse_successor_observation_bytes(document_bytes, trust_closure=trust)
        handle = validate_successor_observation(parsed, trust_closure=trust)
    else:
        parsed = parse_longitudinal_bytes(document_bytes, trust_closure=trust)
        handle = validate_longitudinal_document(parsed, trust_closure=trust)
    return _build_successor_envelope(
        handle, output_mode=request["output_mode"], trust_closure=trust)


def _validate_operation_arguments(data, trust):
    arguments = _strict_json_object(data)
    fields = trust.argument_schema.get("fields", [])
    schemas = dict((item["name"], item) for item in fields)
    unknown = sorted(set(arguments) - set(schemas))
    if unknown:
        raise CanonicalContractError("unknown-operation-argument")
    forbidden_markers = ("api_key", "authorization", "token", "secret", "password",
                         "cookie", "credential")
    if any(any(marker in key.casefold() for marker in forbidden_markers)
           for key in arguments):
        raise CanonicalContractError("secret-operation-argument-forbidden")
    parameters = []
    for name, schema in schemas.items():
        if schema.get("required") and name not in arguments:
            raise CanonicalContractError("required-operation-argument-missing")
        if name not in arguments:
            continue
        value = arguments[name]
        kinds = {"string": str, "integer": int, "boolean": bool, "string_array": list}
        expected = kinds.get(schema.get("value_kind"))
        if expected is None or not isinstance(value, expected) or \
                expected is int and isinstance(value, bool):
            raise CanonicalContractError("operation-argument-type-mismatch")
        if expected is list and any(not isinstance(item, str) for item in value):
            raise CanonicalContractError("operation-string-array-type-mismatch")
        parameters.append((schema["provider_parameter_name"], copy.deepcopy(value)))
    return ValidatedOperationArgumentsHandleV1(
        _HANDLE_SEAL, arguments, parameters, trust)


def check_event_compatibility(
    document: Mapping[str, Any], capabilities: Mapping[str, Any], *,
    requires: Sequence[str] = (), optional: Sequence[str] = (),
    requires_canonical_identity_for: Sequence[str] = ()
) -> dict[str, Any]:
    return _check_compatibility(document, capabilities, requires, optional,
                                requires_canonical_identity_for, "event")


def check_longitudinal_compatibility(
    document: Mapping[str, Any], capabilities: Mapping[str, Any], *,
    requires: Sequence[str] = (), optional: Sequence[str] = (),
    requires_canonical_identity_for: Sequence[str] = ()
) -> dict[str, Any]:
    return _check_compatibility(document, capabilities, requires, optional,
                                requires_canonical_identity_for, "longitudinal")


def _check_compatibility(document, capabilities, requires, optional,
                         identity_pointers, kind):
    if set(requires).intersection(optional) or len(requires) != len(set(requires)) or \
            len(optional) != len(set(optional)):
        raise ValueError("compatibility capability lists must be disjoint and unique")
    present = set(capabilities.get("present", []))
    prefix = "longitudinal." if kind == "longitudinal" else None
    for capability in tuple(requires) + tuple(optional):
        if prefix and not capability.startswith(prefix):
            raise ValueError("event capability used for longitudinal compatibility")
        if not prefix and capability.startswith("longitudinal."):
            raise ValueError("longitudinal capability used for event compatibility")
    missing = sorted(set(requires) - present)
    identity_missing = []
    for pointer in identity_pointers:
        claim = resolve_json_pointer(document, pointer)
        identity = resolve_json_pointer(document, claim["identity_evidence_ref"])
        if identity.get("status") != "authoritatively_resolved":
            identity_missing.append(pointer)
    return {"compatible": not missing and not identity_missing,
            "missing_required": missing,
            "optional_present": sorted(set(optional).intersection(present)),
            "optional_absent": sorted(set(optional) - present),
            "canonical_identity_missing": identity_missing}
