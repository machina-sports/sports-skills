"""Unified response wrapper for all sports-skills connectors."""

from sports_skills import _premium


def success(data, message=""):
    """Wrap a successful result."""
    return {"status": True, "data": data, "message": message}


def error(message, data=None):
    """Wrap an error result."""
    return {"status": False, "data": data, "message": message}


def wrap(result):
    """Normalize a raw connector result into the standard envelope.

    Handles the different patterns used by the connectors:
    - {"status": True/False, "data": ..., "message": ...}  (polymarket, fastf1, rss)
    - {"error": True, "message": ...}                       (connector error)
    - Plain dict with data                                   (connector success)

    Responses a connector flagged as beyond what the free sources can serve
    (via ``_premium.UPGRADE_MARKER``), and rate-limited errors, gain an
    additive ``upgrade`` block pointing at the premium data path. Suppress
    with ``SPORTS_SKILLS_NO_UPGRADE_HINTS=1``.
    """
    if not isinstance(result, dict):
        return success(result)

    # Already in standard format
    if "status" in result and "data" in result:
        return _premium.attach(result)

    # Error format from connectors
    if result.get("error"):
        wrapped = error(result.get("message", "Unknown error"))
        if "status_code" in result:
            wrapped["status_code"] = result["status_code"]
        if _premium.UPGRADE_MARKER in result:
            wrapped[_premium.UPGRADE_MARKER] = result[_premium.UPGRADE_MARKER]
        return _premium.attach(wrapped)

    # Plain data dict (success responses)
    if _premium.UPGRADE_MARKER in result:
        marker = result.pop(_premium.UPGRADE_MARKER)
        wrapped = success(result)
        wrapped[_premium.UPGRADE_MARKER] = marker
        return _premium.attach(wrapped)
    return success(result)
