"""Record/replay for upstream HTTP fetches.

Lets a run be recorded once against live sources and replayed later with zero
network access, so evaluations and bug reports are reproducible.

Controlled by two environment variables, read on every call:

``SPORTS_SKILLS_REPLAY``
    ``off`` (default) — normal live behaviour, nothing is written.
    ``record`` — fetch live, then save each response to the replay directory.
    ``replay`` — serve responses only from the replay directory. A request that
    was never recorded returns an error instead of touching the network.

``SPORTS_SKILLS_REPLAY_DIR``
    Directory holding recorded responses. Required for ``record`` and
    ``replay``; there is deliberately no default, so a run can never read or
    write fixtures from an unexpected place.

What gets recorded:

* successful responses, byte-for-byte;
* deterministic HTTP errors (4xx other than 429), so fallbacks such as the ESPN
  mirror-host retry replay exactly as they ran.

Transient failures (5xx, 429, timeouts, connection errors) are never recorded:
freezing a flaky failure into a fixture would make it look like real data. A
replay of such a request is a miss, which surfaces the gap instead of hiding it.

Recorded payloads come from third-party sources and remain subject to their
terms of use. Check those terms before sharing or publishing a replay directory.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import logging
import os
import tempfile
import urllib.parse
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

logger = logging.getLogger("sports_skills._replay")

MODE_ENV = "SPORTS_SKILLS_REPLAY"
DIR_ENV = "SPORTS_SKILLS_REPLAY_DIR"

OFF = "off"
RECORD = "record"
REPLAY = "replay"
_MODES = (OFF, RECORD, REPLAY)

ENTRY_SCHEMA_VERSION = 1

_NON_RECORDABLE_CODES = {429}


def mode():
    """Return the active mode, or ``None`` when the configured value is invalid."""
    value = (os.environ.get(MODE_ENV) or OFF).strip().lower()
    return value if value in _MODES else None


def replay_dir():
    value = (os.environ.get(DIR_ENV) or "").strip()
    return value or None


def normalize_url(url):
    """Canonical form of a URL for keying: query parameters sorted, rest intact."""
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    normalized_query = urllib.parse.urlencode(sorted(query))
    return urllib.parse.urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, normalized_query, ""))


def request_key(url, method="GET"):
    canonical = f"{method.upper()} {normalize_url(url)}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def entry_path(directory, key):
    return os.path.join(directory, key[:2], f"{key}.json")


def _package_version():
    try:
        return _pkg_version("sports-skills")
    except PackageNotFoundError:
        return "dev"


def _config_error(message):
    return None, {"error": True, "replay_error": True, "message": message}


def _is_recordable_error(err):
    code = err.get("status_code") if isinstance(err, dict) else None
    return isinstance(code, int) and 400 <= code < 500 and code not in _NON_RECORDABLE_CODES


def _encode_body(raw):
    try:
        return "utf-8", raw.decode("utf-8")
    except UnicodeDecodeError:
        return "base64", base64.b64encode(raw).decode("ascii")


def _decode_body(entry):
    body = entry.get("body", "")
    if entry.get("body_encoding") == "base64":
        return base64.b64decode(body)
    return body.encode("utf-8")


def _write_entry(directory, key, entry):
    path = entry_path(directory, key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(entry, handle, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _record(directory, url, raw, err):
    if err is not None and not _is_recordable_error(err):
        return
    entry = {
        "schema_version": ENTRY_SCHEMA_VERSION,
        "method": "GET",
        "url": normalize_url(url),
        "recorded_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sports_skills_version": _package_version(),
    }
    if err is None:
        encoding, body = _encode_body(raw)
        entry.update(
            outcome="ok",
            body_encoding=encoding,
            body=body,
            body_sha256=hashlib.sha256(raw).hexdigest(),
        )
    else:
        entry.update(
            outcome="http_error",
            status_code=err["status_code"],
            message=err.get("message", ""),
        )
    try:
        _write_entry(directory, request_key(url), entry)
    except OSError as exc:
        # Recording is best-effort for the caller: the live result still returns.
        logger.warning("Could not record %s to %s: %s", url, directory, exc)


def _replay(directory, url):
    key = request_key(url)
    path = entry_path(directory, key)
    try:
        with open(path, encoding="utf-8") as handle:
            entry = json.load(handle)
    except FileNotFoundError:
        return None, {
            "error": True,
            "replay_miss": True,
            "message": (
                f"Replay miss: no recorded response for {normalize_url(url)}. "
                f"Record it with {MODE_ENV}=record, or run with {MODE_ENV}=off."
            ),
        }
    except (OSError, ValueError) as exc:
        return None, {
            "error": True,
            "replay_error": True,
            "message": f"Unreadable replay entry {path}: {exc}",
        }

    if entry.get("outcome") == "http_error":
        return None, {
            "error": True,
            "status_code": entry.get("status_code"),
            "message": entry.get("message", ""),
            "replayed": True,
        }

    try:
        raw = _decode_body(entry)
    except (ValueError, TypeError) as exc:
        return None, {
            "error": True,
            "replay_error": True,
            "message": f"Corrupt replay entry {path}: {exc}",
        }
    if hashlib.sha256(raw).hexdigest() != entry.get("body_sha256"):
        return None, {
            "error": True,
            "replay_error": True,
            "message": f"Replay entry {path} failed its integrity check",
        }
    return raw, None


def fetch(url, live_fetch):
    """Serve ``url`` according to the active replay mode.

    ``live_fetch`` is a zero-argument callable performing the real request and
    returning ``(data_bytes, None)`` or ``(None, error_dict)`` — the contract of
    the modules' ``_http_fetch`` helpers. It is never called in replay mode.
    """
    active = mode()
    if active is None:
        return _config_error(f"Invalid {MODE_ENV} value {os.environ.get(MODE_ENV)!r}; use one of: {', '.join(_MODES)}.")
    if active == OFF:
        return live_fetch()

    directory = replay_dir()
    if not directory:
        return _config_error(f"{MODE_ENV}={active} requires {DIR_ENV} to be set.")

    if active == REPLAY:
        return _replay(directory, url)

    raw, err = live_fetch()
    _record(directory, url, raw, err)
    return raw, err
