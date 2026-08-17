"""Consumer-owned authority and request boundary for Phase 1 execution."""

import hashlib
import json
import re
from pathlib import Path
from types import MappingProxyType

from ._vendored.successor import CanonicalContractError

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9._-]{0,127}\Z", re.ASCII)
_PROVIDER_NAMESPACE = "sports-skills/espn"
_OUTPUT_MODES = ("operational_only", "with_iptc_graph")
_CONSUMER_TIERS = ("prototype", "production")
_TRUSTED_MANIFEST_SHA256 = "57ac4df94da8fee87a1e526b77455cb93399ffb35d1928555d4f97138ed5f23b"

_SPORTS_SKILLS_CANONICAL_PACKAGE_REF = MappingProxyType(
    {
        "package_name": "sports-skills",
        "package_version": "0.32.0",
        "release_id": "canonical-evidence-phase1",
    }
)


def _strict_request_object(data):
    if not isinstance(data, bytes):
        raise TypeError("request_bytes must be bytes")
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("request_bytes must be valid UTF-8") from error
    if text.startswith("\ufeff") or "\ufffd" in text:
        raise ValueError("request_bytes contains forbidden Unicode")

    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("request_bytes contains a duplicate key")
            result[key] = value
        return result

    try:
        value = json.loads(
            text,
            object_pairs_hook=object_pairs,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                ValueError("request_bytes contains a non-finite number")
            ),
        )
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("request_bytes must be a JSON object") from error
    if not isinstance(value, dict):
        raise ValueError("request_bytes must be a JSON object")
    if _contains_forbidden_text(value):
        raise ValueError("request_bytes contains forbidden Unicode")
    return value


def _contains_forbidden_text(value):
    if isinstance(value, str):
        if "\ufffd" in value:
            return True
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeEncodeError:
            return True
        return False
    if isinstance(value, dict):
        return any(_contains_forbidden_text(key) or _contains_forbidden_text(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden_text(item) for item in value)
    return False


def _execution_request_bytes(operation, request_bytes, output_kind, output_mode, consumer_tier):
    if not isinstance(operation, str) or _TOKEN_RE.fullmatch(operation) is None:
        raise ValueError("operation must be a canonical token")
    if output_mode not in _OUTPUT_MODES:
        raise ValueError("unsupported output_mode")
    if consumer_tier not in _CONSUMER_TIERS:
        raise ValueError("unsupported consumer_tier")
    request = _strict_request_object(request_bytes)
    if set(request) != {"requires", "optional"}:
        raise ValueError("request_bytes must contain only requires and optional")
    for name in ("requires", "optional"):
        values = request[name]
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise ValueError("request capability lists must contain strings")
        if len(values) != len(set(values)):
            raise ValueError("request capability lists must be unique")
    if set(request["requires"]).intersection(request["optional"]):
        raise ValueError("required and optional capabilities must be disjoint")
    document = {
        "requested_provider": _PROVIDER_NAMESPACE,
        "requested_operation": operation,
        "output_kind": output_kind,
        "output_mode": output_mode,
        "consumer_tier": consumer_tier,
        "requires": request["requires"],
        "optional": request["optional"],
    }
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class _SportsSkillsTrustedAdapterPackageLoader:
    """Static verifier for consumer-owned operation packages.

    The reviewed 0.3.0 owner release contains no sports-skills operation contract.
    Until a separately reviewed adapter package adds one, valid wrapper calls fail
    at this static boundary without importing provider code.
    """

    def load_static(self, package_ref, request):
        if package_ref is not _SPORTS_SKILLS_CANONICAL_PACKAGE_REF:
            raise CanonicalContractError("sports-skills-package-ref-required")
        self._verify_vendored_runtime()
        raise CanonicalContractError("sports-skills-operation-not-attested")

    def import_adapter(self, trust_closure):
        raise CanonicalContractError("adapter-import-before-static-preflight")

    @staticmethod
    def _verify_vendored_runtime():
        root = Path(__file__).resolve().parent / "_vendored"
        receipt = json.loads((root / "VENDORED.json").read_text(encoding="utf-8"))
        trusted_path = root / "data/trusted_loader_manifest_v1.json"
        trusted_bytes = trusted_path.read_bytes()
        if hashlib.sha256(trusted_bytes).hexdigest() != _TRUSTED_MANIFEST_SHA256:
            raise CanonicalContractError("trusted-loader-manifest-digest-mismatch")
        trusted = json.loads(trusted_bytes.decode("utf-8"))
        for key in ("runtime_files", "required_data_files", "private_symbols"):
            if receipt.get(key) != trusted.get(key):
                raise CanonicalContractError("vendored-runtime-receipt-mismatch")
        if receipt.get("aggregate_runtime_digest") != trusted.get("aggregate_runtime_digest"):
            raise CanonicalContractError("vendored-runtime-aggregate-mismatch")
        for item in trusted["runtime_files"] + trusted["required_data_files"]:
            payload = (root / item["relative_path"]).read_bytes()
            digest = "sha256:" + hashlib.sha256(payload).hexdigest()
            if len(payload) != item["byte_length"] or digest != item["sha256"]:
                raise CanonicalContractError("vendored-runtime-file-mismatch")


_SPORTS_SKILLS_TRUSTED_ADAPTER_PACKAGE_LOADER = _SportsSkillsTrustedAdapterPackageLoader()
