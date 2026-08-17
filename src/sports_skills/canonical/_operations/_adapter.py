"""Packaged-fixture adapter with no transport or cache path."""

import hashlib
from pathlib import Path

from .._vendored.successor import CanonicalContractError


class PackagedFixtureAdapter:
    def __init__(self, root, manifest):
        self._root = Path(root)
        self._fixtures = {item["fixture_id"]: item for item in manifest["fixtures"]}

    def fetch(self, argument_handle):
        parameters = dict(argument_handle.provider_request_parameters)
        fixture_id = parameters.get("fixture_id")
        fixture = self._fixtures.get(fixture_id)
        if fixture is None:
            raise CanonicalContractError("operation-argument-value-not-allowed")
        payload = (self._root / fixture["path"]).read_bytes()
        if "sha256:" + hashlib.sha256(payload).hexdigest() != fixture["original_bytes_digest"]:
            raise CanonicalContractError("fixture-artifact-digest-mismatch")
        return payload
