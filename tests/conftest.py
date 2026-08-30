"""Pytest collection policy for immutable historical release proofs."""

import os
from pathlib import Path

RELEASE_033_TEST = "test_release_033.py"


def pytest_ignore_collect(collection_path, config):
    """Keep the v0.33 proof opt-in after that immutable release.

    The historical checksum test rebuilds the current source tree, so any later
    feature correctly changes its artifacts. Release verification can enable the
    frozen proof explicitly without disabling pytest's other ignore hooks.
    """
    path = Path(str(collection_path))
    if path.name != RELEASE_033_TEST:
        return None
    return os.environ.get("SPORTS_SKILLS_VERIFY_RELEASE_033") != "1"
