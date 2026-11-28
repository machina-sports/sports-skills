"""Pytest collection policy for immutable historical release proofs."""

import itertools
import os
from pathlib import Path

import pytest

HISTORICAL_RELEASE_TESTS = {
    "test_release_036.py": "SPORTS_SKILLS_VERIFY_RELEASE_036",
    "test_release_037.py": "SPORTS_SKILLS_VERIFY_RELEASE_037",
    "test_release_038.py": "SPORTS_SKILLS_VERIFY_RELEASE_038",
    "test_release_039.py": "SPORTS_SKILLS_VERIFY_RELEASE_039",
    "test_release_040.py": "SPORTS_SKILLS_VERIFY_RELEASE_040",
    "test_release_0401.py": "SPORTS_SKILLS_VERIFY_RELEASE_0401",
    "test_release_0402.py": "SPORTS_SKILLS_VERIFY_RELEASE_0402",
    "test_release_0403.py": "SPORTS_SKILLS_VERIFY_RELEASE_0403",
    "test_release_0404.py": "SPORTS_SKILLS_VERIFY_RELEASE_0404",
    "test_release_0405.py": "SPORTS_SKILLS_VERIFY_RELEASE_0405",
    "test_release_0406.py": "SPORTS_SKILLS_VERIFY_RELEASE_0406",
    "test_release_0407.py": "SPORTS_SKILLS_VERIFY_RELEASE_0407",
    "test_release_0408.py": "SPORTS_SKILLS_VERIFY_RELEASE_0408",
    "test_release_0409.py": "SPORTS_SKILLS_VERIFY_RELEASE_0409",
    "test_release_0410.py": "SPORTS_SKILLS_VERIFY_RELEASE_0410",
    "test_release_041.py": "SPORTS_SKILLS_VERIFY_RELEASE_041",
    "test_release_0411.py": "SPORTS_SKILLS_VERIFY_RELEASE_0411",
    "test_release_0412.py": "SPORTS_SKILLS_VERIFY_RELEASE_0412",
}


def pytest_ignore_collect(collection_path, config):
    """Keep published release proofs opt-in after their immutable releases.

    The historical checksum tests rebuild the current source tree, so any later
    feature correctly changes their artifacts. Release verification can enable a
    frozen proof explicitly without disabling pytest's other ignore hooks.
    """
    path = Path(str(collection_path))
    variable = HISTORICAL_RELEASE_TESTS.get(path.name)
    if variable is None:
        return None
    return os.environ.get(variable) != "1"


_cache_homes = itertools.count()


@pytest.fixture(scope="session")
def _cache_root(tmp_path_factory):
    return tmp_path_factory.mktemp("xdg-cache")


@pytest.fixture(autouse=True)
def _private_cache_home(monkeypatch, _cache_root):
    """Disk caches (football seasons, Sleeper, cricsheet) never touch the real home directory.

    Each test gets its own path under one session directory, kept apart from ``tmp_path``
    since the replay tests count files there. The caches create it on first write.
    """
    monkeypatch.setenv("XDG_CACHE_HOME", str(_cache_root / str(next(_cache_homes))))
