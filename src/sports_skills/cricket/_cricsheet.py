"""Cricket historical data connector — Cricsheet.org open data.

Ball-by-ball (delivery-level) data for completed matches, distributed as
zipped JSON files per competition. License: ODC-BY 1.0 — attribution
required, so every response includes an `attribution` field.

Data lags live play: matches appear roughly a day after completion.
"""

import csv
import io
import json
import logging
import os
import time
import urllib.request
import zipfile

from sports_skills._espn_base import _USER_AGENT

logger = logging.getLogger("sports_skills.cricket")

_ATTRIBUTION = "Data from Cricsheet (cricsheet.org), ODC-BY 1.0"

# Cricsheet competition codes — every code verified live 2026-06-03
# against https://cricsheet.org/downloads/{code}_json.zip
_COMPETITIONS = {
    "tests": "Test matches (men)",
    "odis": "One-day internationals (men)",
    "t20s": "T20 internationals (men)",
    "ipl": "Indian Premier League",
    "bbl": "Big Bash League",
    "psl": "Pakistan Super League",
    "cpl": "Caribbean Premier League",
    "hnd": "The Hundred (men)",
    "ntb": "T20 Blast",
    "cch": "County Championship",
    "sat": "SA20",
    "msl": "Mzansi Super League",
    "lpl": "Lanka Premier League",
    "ilt": "International League T20",
    "wbb": "Women's Big Bash League",
    "wpl": "Women's Premier League",
}


def get_competitions(request_data):
    """List supported Cricsheet competition codes."""
    competitions = [
        {"code": code, "name": name} for code, name in sorted(_COMPETITIONS.items())
    ]
    return {
        "competitions": competitions,
        "count": len(competitions),
        "attribution": _ATTRIBUTION,
    }


_ZIP_TTL = 24 * 3600          # competition zips: 24h
_REGISTRY_TTL = 7 * 24 * 3600  # player registry: 7 days


def _cache_dir():
    """Return (and create) the on-disk cache directory."""
    base = os.environ.get(
        "XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")
    )
    path = os.path.join(base, "sports-skills", "cricsheet")
    os.makedirs(path, exist_ok=True)
    return path


def _download(url, dest):
    """Download url to dest atomically (write to .tmp, then rename)."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    tmp = dest + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dest)


def _fetch_file(url, filename, ttl):
    """Return a local path to a cached copy of url, downloading if missing/expired.

    Returns (path, stale, error): on download failure with a stale copy
    present, serves the stale copy with stale=True instead of erroring.
    """
    path = os.path.join(_cache_dir(), filename)
    if os.path.exists(path) and (time.time() - os.path.getmtime(path)) < ttl:
        return path, False, None
    try:
        _download(url, path)
        return path, False, None
    except Exception as e:  # noqa: BLE001 — any failure falls back to stale/error
        if os.path.exists(path):
            logger.warning("cricsheet download failed, serving stale %s: %s", filename, e)
            return path, True, None
        return None, False, {"error": True, "message": f"Cricsheet download failed: {e}"}
