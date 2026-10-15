"""Pytest collection policy for immutable historical release proofs."""

import os
from pathlib import Path

#: Each published release's proof, and the variable that opts back into it.
HISTORICAL_RELEASE_TESTS = {
    "test_release_036.py": "SPORTS_SKILLS_VERIFY_RELEASE_036",
    "test_release_037.py": "SPORTS_SKILLS_VERIFY_RELEASE_037",
}


def pytest_ignore_collect(collection_path, config):
    """Keep each proof opt-in after its immutable release.

    The historical checksum test rebuilds the current source tree, so any later
    feature correctly changes its artifacts. Release verification can enable the
    frozen proof explicitly without disabling pytest's other ignore hooks.
    """
    path = Path(str(collection_path))
    variable = HISTORICAL_RELEASE_TESTS.get(path.name)
    if variable is None:
        return None
    return os.environ.get(variable) != "1"
