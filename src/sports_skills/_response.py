"""Unified response wrapper for all sports-skills connectors."""


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
    """
    if not isinstance(result, dict):
        return success(result)

    # Already in standard format
    if "status" in result and "data" in result:
        return result

    # Error format from connectors
    if result.get("error"):
        wrapped = error(result.get("message", "Unknown error"))
        if "status_code" in result:
            wrapped["status_code"] = result["status_code"]
        return wrapped

    # Plain data dict (success responses)
    return success(result)
