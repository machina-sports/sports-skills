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


def _validate_competition(code):
    """Return normalized competition code or error dict."""
    if not code:
        return None, {
            "error": True,
            "message": "competition is required — see get_competitions for codes",
        }
    c = str(code).lower().strip()
    if c not in _COMPETITIONS:
        return None, {
            "error": True,
            "message": f"Unknown competition '{code}'. Valid: {', '.join(sorted(_COMPETITIONS))}",
        }
    return c, None


def _open_competition(code):
    """Return (ZipFile, stale, error) for a competition's cached zip."""
    url = f"https://cricsheet.org/downloads/{code}_json.zip"
    path, stale, err = _fetch_file(url, f"{code}_json.zip", _ZIP_TTL)
    if err:
        return None, False, err
    return zipfile.ZipFile(path), stale, None


def _season_matches(season_value, season_filter):
    """Prefix match so --season=2020 matches Cricsheet's '2020/21'."""
    if season_filter is None:
        return True
    return str(season_value).startswith(str(season_filter))


def _match_summary(name, info):
    """Build a one-line match summary from a Cricsheet info block."""
    outcome = info.get("outcome", {})
    return {
        "match_id": name[:-5],
        "date": (info.get("dates") or [""])[0],
        "teams": info.get("teams", []),
        "venue": info.get("venue", ""),
        "city": info.get("city", ""),
        "season": str(info.get("season", "")),
        "match_type": info.get("match_type", ""),
        "gender": info.get("gender", ""),
        "event": info.get("event", {}).get("name", ""),
        "winner": outcome.get("winner", outcome.get("result", "")),
        "outcome": outcome,
    }


def get_matches(request_data):
    """List completed matches for a Cricsheet competition, newest first."""
    params = request_data.get("params", {})
    code, err = _validate_competition(params.get("competition"))
    if err:
        return err
    season = params.get("season")
    zf, stale, err = _open_competition(code)
    if err:
        return err
    matches = []
    with zf:
        for name in zf.namelist():
            if not name.endswith(".json"):
                continue
            with zf.open(name) as f:
                data = json.load(f)
            info = data.get("info", {})
            if not _season_matches(info.get("season", ""), season):
                continue
            matches.append(_match_summary(name, info))
    matches.sort(key=lambda m: m["date"], reverse=True)
    result = {
        "competition": code,
        "matches": matches,
        "count": len(matches),
        "attribution": _ATTRIBUTION,
    }
    if stale:
        result["stale"] = True
    return result
