"""Sports-Skills-owned execution boundary for the nine replay operations."""

import json
import threading
from contextlib import contextmanager

from .._vendored import serialize, successor

_OWNER_CONTEXT_LOCK = threading.RLock()


def _fresh_owner_context():
    with serialize.SHARED_CONTEXT_PATH.open(encoding="utf-8") as handle:
        document = json.load(handle)
    return {key: value for key, value in document["@context"].items() if isinstance(value, str)}


@contextmanager
def owner_operation_context():
    """Supply fresh owner context bytes without consulting its module cache."""
    with _OWNER_CONTEXT_LOCK:
        original = successor.shared_context
        successor.shared_context = _fresh_owner_context
        try:
            yield
        finally:
            successor.shared_context = original
