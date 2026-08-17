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

VERSION = "0.32.0"

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
try:
    importlib.import_module("machina_sports_canonical")
except ModuleNotFoundError:
    pass
else:
    raise SystemExit("external machina_sports_canonical dependency is present")
