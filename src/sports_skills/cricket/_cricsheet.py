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


# Dismissal kinds credited to the bowler (standard convention)
_BOWLER_CREDITED = {"bowled", "caught", "lbw", "stumped", "hit wicket", "caught and bowled"}


def get_match_deliveries(request_data):
    """Ball-by-ball deliveries for one match, optionally one innings."""
    params = request_data.get("params", {})
    code, err = _validate_competition(params.get("competition"))
    if err:
        return err
    match_id = params.get("match_id")
    if not match_id:
        return {"error": True, "message": "match_id is required — see get_matches"}
    innings_filter = params.get("innings")
    zf, stale, err = _open_competition(code)
    if err:
        return err
    filename = f"{match_id}.json"
    with zf:
        if filename not in zf.namelist():
            return {
                "error": True,
                "message": f"Match '{match_id}' not found in competition '{code}'",
            }
        with zf.open(filename) as f:
            data = json.load(f)
    info = data.get("info", {})
    innings_out = []
    for idx, inn in enumerate(data.get("innings", []), start=1):
        if innings_filter is not None and idx != int(innings_filter):
            continue
        deliveries = []
        for over in inn.get("overs", []):
            over_num = over.get("over", 0)
            for ball_idx, d in enumerate(over.get("deliveries", []), start=1):
                entry = {
                    "over": over_num,
                    "ball": ball_idx,
                    "batter": d.get("batter", ""),
                    "bowler": d.get("bowler", ""),
                    "non_striker": d.get("non_striker", ""),
                    "runs": d.get("runs", {}),
                }
                if d.get("extras"):
                    entry["extras"] = d["extras"]
                if d.get("wickets"):
                    entry["wickets"] = d["wickets"]
                deliveries.append(entry)
        innings_out.append({
            "innings": idx,
            "team": inn.get("team", ""),
            "deliveries": deliveries,
            "count": len(deliveries),
        })
    result = {
        "match": _match_summary(filename, info),
        "innings": innings_out,
        "attribution": _ATTRIBUTION,
    }
    if stale:
        result["stale"] = True
    return result


def get_player_stats(request_data):
    """Aggregate batting and bowling stats for a player across a competition.

    Conventions: batting balls faced exclude wides (no-balls faced);
    bowling balls exclude wides and no-balls; bowler concedes batter runs
    + wides + no-balls (not byes/leg-byes/penalty); run outs etc. are not
    credited to the bowler.
    """
    params = request_data.get("params", {})
    code, err = _validate_competition(params.get("competition"))
    if err:
        return err
    player = params.get("player")
    if not player:
        return {"error": True, "message": "player is required — exact name as in Cricsheet (see find_player)"}
    season = params.get("season")
    zf, stale, err = _open_competition(code)
    if err:
        return err

    matches_played = 0
    bat = {"runs": 0, "balls": 0, "fours": 0, "sixes": 0, "dismissals": 0}
    bowl = {"balls": 0, "runs_conceded": 0, "wickets": 0}

    with zf:
        for name in zf.namelist():
            if not name.endswith(".json"):
                continue
            with zf.open(name) as f:
                data = json.load(f)
            info = data.get("info", {})
            if not _season_matches(info.get("season", ""), season):
                continue
            all_players = [p for team in info.get("players", {}).values() for p in team]
            if player not in all_players:
                continue
            matches_played += 1
            for inn in data.get("innings", []):
                for over in inn.get("overs", []):
                    for d in over.get("deliveries", []):
                        runs = d.get("runs", {})
                        extras = d.get("extras", {})
                        wides = extras.get("wides", 0)
                        noballs = extras.get("noballs", 0)
                        if d.get("batter") == player:
                            if not wides:
                                bat["balls"] += 1
                            batter_runs = runs.get("batter", 0)
                            bat["runs"] += batter_runs
                            if not runs.get("non_boundary"):
                                if batter_runs == 4:
                                    bat["fours"] += 1
                                elif batter_runs == 6:
                                    bat["sixes"] += 1
                        if d.get("bowler") == player:
                            if not wides and not noballs:
                                bowl["balls"] += 1
                            bowl["runs_conceded"] += runs.get("batter", 0) + wides + noballs
                            for w in d.get("wickets", []):
                                if w.get("kind") in _BOWLER_CREDITED:
                                    bowl["wickets"] += 1
                        for w in d.get("wickets", []):
                            if w.get("player_out") == player:
                                bat["dismissals"] += 1

    if matches_played == 0:
        return {
            "error": True,
            "message": f"No matches found for player '{player}' in '{code}'"
            + (f" season {season}" if season else "")
            + " — names must match Cricsheet exactly (see find_player)",
        }

    bat["strike_rate"] = round(bat["runs"] / bat["balls"] * 100, 2) if bat["balls"] else 0.0
    bat["average"] = round(bat["runs"] / bat["dismissals"], 2) if bat["dismissals"] else None
    bowl["economy"] = round(bowl["runs_conceded"] / (bowl["balls"] / 6), 2) if bowl["balls"] else None
    bowl["overs"] = f"{bowl['balls'] // 6}.{bowl['balls'] % 6}"

    result = {
        "player": player,
        "competition": code,
        "season": season,
        "matches": matches_played,
        "batting": bat,
        "bowling": bowl,
        "attribution": _ATTRIBUTION,
    }
    if stale:
        result["stale"] = True
    return result


_REGISTRY_URL = "https://cricsheet.org/register/people.csv"
_MAX_PLAYER_RESULTS = 25


def find_player(request_data):
    """Search the Cricsheet player registry by name substring.

    Returns Cricsheet IDs plus the ESPNcricinfo ID mapping (key_cricinfo),
    which bridges Cricsheet data to ESPN match data.
    """
    params = request_data.get("params", {})
    name = params.get("name")
    if not name:
        return {"error": True, "message": "name is required"}
    path, stale, err = _fetch_file(_REGISTRY_URL, "people.csv", _REGISTRY_TTL)
    if err:
        return err
    needle = str(name).lower().strip()
    players = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            haystack = f"{row.get('name', '')} {row.get('unique_name', '')}".lower()
            if needle in haystack:
                players.append({
                    "cricsheet_id": row.get("identifier", ""),
                    "name": row.get("name", ""),
                    "unique_name": row.get("unique_name", ""),
                    "cricinfo_id": row.get("key_cricinfo", ""),
                })
                if len(players) >= _MAX_PLAYER_RESULTS:
                    break
    result = {"players": players, "count": len(players), "attribution": _ATTRIBUTION}
    if stale:
        result["stale"] = True
    return result
