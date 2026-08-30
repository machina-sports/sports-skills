"""Tests for repository-wide pytest collection policy."""

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("collection_policy", Path(__file__).with_name("conftest.py"))
assert SPEC and SPEC.loader
collection_policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(collection_policy)


def test_non_release_paths_defer_to_other_ignore_hooks():
    assert collection_policy.pytest_ignore_collect(Path("tests/test_markets.py"), None) is None


def test_release_proof_is_opt_in(monkeypatch):
    path = Path("tests/test_release_033.py")
    monkeypatch.delenv("SPORTS_SKILLS_VERIFY_RELEASE_033", raising=False)
    assert collection_policy.pytest_ignore_collect(path, None) is True

    monkeypatch.setenv("SPORTS_SKILLS_VERIFY_RELEASE_033", "1")
    assert collection_policy.pytest_ignore_collect(path, None) is False
