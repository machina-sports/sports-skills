"""Consumer-owned authority and request boundary for Phase 1 execution."""

import hashlib
import importlib
import json
import re
from pathlib import Path
from types import MappingProxyType

from ._operations._document import build_document
from ._vendored.successor import CanonicalContractError

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9._-]{0,127}\Z", re.ASCII)
_PROVIDER_NAMESPACE = "sports-skills/espn"
_OUTPUT_MODES = ("operational_only", "with_iptc_graph")
_CONSUMER_TIERS = ("prototype", "production")
_TRUSTED_MANIFEST_SHA256 = "0fdf5e8a6661e1d2bb7f5190f6c4fe08637f3eab5149254c26885aead557eace"

_SPORTS_SKILLS_CANONICAL_PACKAGE_REF = MappingProxyType(
    {
        "package_name": "sports-skills",
        "package_version": "0.33.0",
        "release_id": "canonical-evidence-step10-operations",
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
    """Static verifier for the closed synthetic Arena Step 10 package."""

    def load_static(self, package_ref, request):
        if package_ref is not _SPORTS_SKILLS_CANONICAL_PACKAGE_REF:
            raise CanonicalContractError("sports-skills-package-ref-required")
        self._verify_vendored_runtime()
        package = self._load_package()
        matches = [
            item
            for item in package["operations"]
            if item["operation"] == request.get("requested_operation")
            and item["output_kind"] == request.get("output_kind")
        ]
        if len(matches) != 1:
            raise CanonicalContractError("sports-skills-operation-not-attested")
        registration = matches[0]
        resources = {
            name: self._load_resource(package, registration[name + "_path"])
            for name in (
                "package_link",
                "descriptor",
                "rights_profile",
                "argument_schema",
                "fixture_manifest",
            )
        }
        link = resources["package_link"]
        descriptor = resources["descriptor"]
        rights = resources["rights_profile"]
        argument_schema = resources["argument_schema"]
        fixture_manifest = resources["fixture_manifest"]
        expected = {
            "provider_namespace": _PROVIDER_NAMESPACE,
            "provider_package": "sports-skills-arena-step10-operations/1",
            "package_name": "sports-skills",
            "approved_distribution_version": "0.33.0",
            "release_id": "canonical-evidence-step10-operations",
            "operation": registration["operation"],
            "output_kind": registration["output_kind"],
        }
        if any(link.get(key) != value for key, value in expected.items()):
            raise CanonicalContractError("sports-skills-package-link-mismatch")
        digest_bindings = {
            "descriptor_digest": descriptor,
            "rights_profile_digest": rights,
            "operation_argument_schema_digest": argument_schema,
            "fixture_manifest_digest": fixture_manifest,
        }
        if any(link.get(name) != self._record_digest(value) for name, value in digest_bindings.items()):
            raise CanonicalContractError("sports-skills-package-link-digest-mismatch")
        if (
            descriptor.get("operation") != registration["operation"]
            or rights.get("operation") != registration["operation"]
            or fixture_manifest.get("operation") != registration["operation"]
        ):
            raise CanonicalContractError("sports-skills-operation-resource-mismatch")
        authority = self._load_resource(package, package["identity_authority_registry_path"])
        if authority.get("synthetic") is not True or authority.get("contains_provider_data") is not False:
            raise CanonicalContractError("sports-skills-identity-authority-not-synthetic")

        root = Path(__file__).resolve().parent / "_vendored"
        closure_values = {
            "descriptor": descriptor,
            "rights_profile": rights,
            "capability_contract": {"mappings": descriptor.get("capability_mappings", [])},
            "identity_registry": authority,
            "statistic_units": self._read_owner_json(root / "data/statistic_unit_registry_v1.json"),
            "statistic_derivations": self._read_owner_json(root / "data/statistic_derivation_manifest_v1.json"),
            "statistic_implementations": {},
            "admissibility": self._read_owner_json(root / "data/official_statistic_admissibility_v1.json"),
            "spatial": {},
            "longitudinal": {},
            "document_builder": build_document,
            "argument_schema": argument_schema,
            "package_release": {
                "name": "machina-sports-canonical",
                "version": "0.4.1",
                "package_artifact_digest": ("sha256:cd454eb8411b5639af7313c713276bfa4a0dc72aab037b66ba451bc3e0f090bd"),
                "release_id": "machina-sports-canonical-v0.4.1",
                "release_digest": ("sha256:96d1817fc0ba4357029860b73b5a2dddcc3738a80240a73cd443c7a30bf25e5b"),
            },
            "closure_id": object(),
        }
        registry_bytes = (root / "data/source_shape_registry_v2.json").read_bytes()
        from ._vendored import successor

        return successor._load_0_4_closure(
            package_ref={
                "owner_package": {"name": "machina-sports-canonical", "version": "0.4.1"},
                "registry_bytes": registry_bytes,
                "package_link": link,
                "fixture_manifest": fixture_manifest,
                "closure_values": closure_values,
            },
            request=request,
        )

    def import_adapter(self, trust_closure):
        package = self._load_package()
        matches = [item for item in package["operations"] if item["operation"] == trust_closure.descriptor["operation"]]
        if len(matches) != 1:
            raise CanonicalContractError("sports-skills-operation-not-attested")
        registration = matches[0]
        manifest = self._load_resource(package, registration["fixture_manifest_path"])
        module = importlib.import_module(trust_closure.descriptor["module_entrypoint"])
        return module.create_adapter(Path(__file__).resolve().parent / "_operations", manifest)

    @staticmethod
    def _record_digest(value):
        payload = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _read_json(path):
        payload = path.read_bytes()
        try:
            value = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CanonicalContractError("sports-skills-resource-invalid") from error
        canonical = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if payload != canonical:
            raise CanonicalContractError("sports-skills-resource-not-canonical")
        return value

    @staticmethod
    def _read_owner_json(path):
        try:
            return json.loads(path.read_bytes().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CanonicalContractError("vendored-runtime-file-mismatch") from error

    @classmethod
    def _load_package(cls):
        root = Path(__file__).resolve().parent / "_operations"
        package = cls._read_json(root / "package.json")
        required = {
            "schema_version",
            "provider_namespace",
            "provider_package",
            "package_name",
            "approved_distribution_version",
            "release_id",
            "owner_distribution",
            "identity_authority_registry_path",
            "operations",
            "resource_digests",
        }
        if (
            set(package) != required
            or package.get("schema_version") != "sports-skills-arena-step10-operations/1"
            or package.get("provider_namespace") != _PROVIDER_NAMESPACE
            or package.get("approved_distribution_version") != "0.33.0"
        ):
            raise CanonicalContractError("sports-skills-operation-package-invalid")
        operations = package.get("operations")
        if (
            not isinstance(operations, list)
            or len(operations) != 9
            or [item.get("operation") for item in operations] != sorted(item.get("operation") for item in operations)
        ):
            raise CanonicalContractError("sports-skills-operation-package-invalid")
        expected_inventory = {
            path.relative_to(root).as_posix() for path in root.rglob("*.json") if path.name != "package.json"
        }
        if set(package.get("resource_digests", {})) != expected_inventory:
            raise CanonicalContractError("sports-skills-resource-inventory-mismatch")
        for relative, expected_digest in package["resource_digests"].items():
            if relative.startswith("fixtures/"):
                continue
            payload = (root / relative).read_bytes()
            if "sha256:" + hashlib.sha256(payload).hexdigest() != expected_digest:
                raise CanonicalContractError("sports-skills-resource-digest-mismatch")
        return package

    @classmethod
    def _load_resource(cls, package, relative):
        value = cls._read_json(Path(__file__).resolve().parent / "_operations" / relative)
        if package["resource_digests"].get(relative) != cls._record_digest(value):
            raise CanonicalContractError("sports-skills-resource-digest-mismatch")
        return value

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


def _execute_attested_operation(*, operation, request_bytes, operation_arguments_bytes):
    """Preserve owner errors, except the one approved package-level duplicate token."""
    from ._vendored import successor

    try:
        return successor.execute_adapter_operation(
            package_ref=_SPORTS_SKILLS_CANONICAL_PACKAGE_REF,
            request_bytes=request_bytes,
            operation_arguments_bytes=operation_arguments_bytes,
            trusted_loader=_SPORTS_SKILLS_TRUSTED_ADAPTER_PACKAGE_LOADER,
        )
    except ValueError as error:
        if operation == "arena_nfl_refusal_event" and type(error.__cause__).__name__ == "_DuplicateKey":
            raise CanonicalContractError("duplicate-json-key") from error
        raise
