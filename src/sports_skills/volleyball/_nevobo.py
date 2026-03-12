"""Nevobo (Nederlandse Volleybalbond) data connector.

Fetches volleyball data from the open Nevobo API at https://api.nevobo.nl.
Two interfaces:
  - JSON-LD / Hydra: paginated collections (competitions, poules, clubs, regions)
  - RSS Export: per-poule standings, schedules, results; per-club feeds
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

import feedparser

_BASE = "https://api.nevobo.nl"

# Simple rate limiter: min seconds between requests
_MIN_INTERVAL = 0.5
_last_request_time = 0.0

# TTL cache for Hydra responses
_cache: dict[str, tuple[float, object]] = {}
_CACHE_TTL = 300  # seconds


def _throttle():
    global _last_request_time
    now = time.monotonic()
    elapsed = now - _last_request_time
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_request_time = time.monotonic()


def _hydra_request(path, params=None):
    """Fetch a JSON-LD / Hydra endpoint and return parsed JSON."""
    url = f"{_BASE}{path}"
    if params:
        qs = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in params.items() if v is not None)
        if qs:
            url = f"{url}?{qs}"

    now = time.monotonic()
    cached = _cache.get(url)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    _throttle()
    req = urllib.request.Request(url, headers={
        "Accept": "application/ld+json",
        "User-Agent": "sports-skills/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        _cache[url] = (time.monotonic(), data)
        return data
    except urllib.error.HTTPError as e:
        return {"error": True, "message": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": True, "message": f"Connection error: {e.reason}"}
    except Exception as e:
        return {"error": True, "message": str(e)}


def _rss_request(export_path):
    """Fetch and parse an RSS export feed."""
    url = f"{_BASE}/export/{export_path}"
    _throttle()
    try:
        feed = feedparser.parse(url)
        if hasattr(feed, "status") and feed.status >= 400:
            return {"error": True, "message": f"HTTP {feed.status}"}
        if feed.bozo and not feed.entries:
            return {"error": True, "message": f"Feed parse error: {feed.bozo_exception}"}
        return feed
    except Exception as e:
        return {"error": True, "message": str(e)}


# ---------------------------------------------------------------------------
# Standings parser
# ---------------------------------------------------------------------------

def _parse_standings_description(description):
    """Parse standings from a single RSS entry description.

    The Nevobo RSS returns all standings in one entry's description,
    with rows separated by <br /> tags. Each row looks like:
        "1. Team Name, wedstr: 14, punten: 40"
    """
    if not description:
        return []

    lines = re.split(r"<br\s*/?>", description)
    standings = []
    for line in lines:
        line = re.sub(r"<[^>]+>", "", line).strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"(\d+)\.\s+(.+)", line)
        if not m:
            continue
        rank = int(m.group(1))
        rest = m.group(2).strip()

        row = {"rank": rank}

        # Extract "wedstr: N" (matches played)
        wedstr = re.search(r"wedstr:\s*(\d+)", rest)
        if wedstr:
            row["matches_played"] = int(wedstr.group(1))

        # Extract "punten: N" (points)
        punten = re.search(r"punten:\s*(\d+)", rest)
        if punten:
            row["points"] = int(punten.group(1))

        # Team name is everything before the first comma
        team = rest.split(",")[0].strip()
        row["team"] = team

        standings.append(row)

    return standings


def get_poule_standings(poule_path):
    """Get standings for a poule from RSS."""
    feed = _rss_request(f"poule/{poule_path}/stand.rss")
    if isinstance(feed, dict) and feed.get("error"):
        return feed

    standings = []
    for entry in feed.entries:
        desc = entry.get("description", entry.get("summary", ""))
        standings.extend(_parse_standings_description(desc))

    return {
        "poule_path": poule_path,
        "standings": standings,
        "count": len(standings),
    }


# ---------------------------------------------------------------------------
# Schedule parser
# ---------------------------------------------------------------------------

def _parse_schedule_entry(entry):
    """Parse a schedule RSS entry.

    Title format: "12 mrt 19:30: Team A - Team B"
    Description: "Wedstrijd: ..., Datum: ..., Speellocatie: ..."
    """
    title = entry.get("title", "")
    desc = entry.get("description", entry.get("summary", ""))
    published = entry.get("published", "")

    match = {}

    # Strip date/time prefix from title: "12 mrt 19:30: Team A - Team B"
    teams_part = title
    prefix_m = re.match(r"\d{1,2}\s+\w+\s+\d{1,2}:\d{2}:\s*(.+)", title)
    if prefix_m:
        teams_part = prefix_m.group(1)

    t = teams_part.split(" - ", 1)
    if len(t) == 2:
        match["home_team"] = t[0].strip()
        match["away_team"] = t[1].strip()

    if desc:
        text = re.sub(r"<[^>]+>", " ", desc).strip()
        # Extract venue from "Speellocatie: ..."
        venue_m = re.search(r"Speellocatie:\s*(.+?)(?:,\s*Datum:|$)", text)
        if not venue_m:
            venue_m = re.search(r"Speellocatie:\s*(.+)", text)
        if venue_m:
            match["venue"] = venue_m.group(1).strip().rstrip(",")

    if published:
        match["date"] = published

    return match


def get_poule_schedule(poule_path):
    """Get upcoming schedule for a poule from RSS."""
    feed = _rss_request(f"poule/{poule_path}/programma.rss")
    if isinstance(feed, dict) and feed.get("error"):
        return feed

    matches = [_parse_schedule_entry(e) for e in feed.entries]
    return {
        "poule_path": poule_path,
        "matches": matches,
        "count": len(matches),
    }


# ---------------------------------------------------------------------------
# Results parser
# ---------------------------------------------------------------------------

def _parse_result_entry(entry):
    """Parse a results RSS entry.

    Title format: "Team A - Team B, Uitslag: 3-1"
    Description: "Wedstrijd: Team A - Team B, Uitslag: 3-1, Setstanden: 25-21, 25-18, 21-25, 25-20"
    """
    title = entry.get("title", "")
    desc = entry.get("description", entry.get("summary", ""))
    published = entry.get("published", "")

    result = {}

    # Split title on ", Uitslag:" to separate teams from score
    uitslag_m = re.match(r"(.+?),\s*Uitslag:\s*(\d+-\d+)", title)
    if uitslag_m:
        teams_part = uitslag_m.group(1).strip()
        result["score"] = uitslag_m.group(2).strip()
        # Split teams on " - " (the separator between home and away)
        t = teams_part.split(" - ", 1)
        if len(t) == 2:
            result["home_team"] = t[0].strip()
            result["away_team"] = t[1].strip()
    else:
        # Fallback: try simple split
        t = title.split(" - ", 1)
        if len(t) == 2:
            result["home_team"] = t[0].strip()
            result["away_team"] = t[1].strip()

    if desc:
        # Extract set scores after "Setstanden:"
        setstanden_m = re.search(r"Setstanden:\s*(.+)", desc)
        if setstanden_m:
            set_part = setstanden_m.group(1).strip()
            set_scores = re.findall(r"\d{1,2}-\d{1,2}", set_part)
            if set_scores:
                result["set_scores"] = set_scores

    if published:
        result["date"] = published

    return result


def get_poule_results(poule_path):
    """Get results for a poule from RSS."""
    feed = _rss_request(f"poule/{poule_path}/resultaten.rss")
    if isinstance(feed, dict) and feed.get("error"):
        return feed

    results = [_parse_result_entry(e) for e in feed.entries]
    return {
        "poule_path": poule_path,
        "results": results,
        "count": len(results),
    }


# ---------------------------------------------------------------------------
# Club feeds
# ---------------------------------------------------------------------------

def get_club_schedule(club_id):
    """Get upcoming schedule for a club across all teams."""
    feed = _rss_request(f"vereniging/{club_id}/programma.rss")
    if isinstance(feed, dict) and feed.get("error"):
        return feed

    matches = [_parse_schedule_entry(e) for e in feed.entries]
    return {
        "club_id": club_id,
        "matches": matches,
        "count": len(matches),
    }


def get_club_results(club_id):
    """Get results for a club across all teams."""
    feed = _rss_request(f"vereniging/{club_id}/resultaten.rss")
    if isinstance(feed, dict) and feed.get("error"):
        return feed

    results = [_parse_result_entry(e) for e in feed.entries]
    return {
        "club_id": club_id,
        "results": results,
        "count": len(results),
    }


# ---------------------------------------------------------------------------
# Hydra / JSON-LD endpoints
# ---------------------------------------------------------------------------

def _extract_hydra_items(data):
    """Extract items from a Hydra collection response."""
    if isinstance(data, dict) and data.get("error"):
        return data
    members = data.get("hydra:member", data.get("member", []))
    total = data.get("hydra:totalItems", data.get("totalItems", len(members)))
    return {"items": members, "total": total}


def get_poules(params=None):
    """List poules from the Hydra API."""
    data = _hydra_request("/competitie/poules", params)
    return _extract_hydra_items(data)


def get_clubs(params=None):
    """List clubs from the Hydra API."""
    data = _hydra_request("/relatiebeheer/verenigingen", params)
    return _extract_hydra_items(data)


def get_competitions():
    """List competitions from the Hydra API."""
    data = _hydra_request("/competitie/competities")
    return _extract_hydra_items(data)


# ---------------------------------------------------------------------------
# General RSS feeds
# ---------------------------------------------------------------------------

def get_tournaments(limit=None):
    """Get tournament calendar from RSS."""
    feed = _rss_request("toernooien.rss")
    if isinstance(feed, dict) and feed.get("error"):
        return feed

    items = []
    for entry in feed.entries:
        items.append({
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "date": entry.get("published", ""),
            "description": entry.get("description", entry.get("summary", "")),
        })

    if limit:
        items = items[:int(limit)]

    return {"tournaments": items, "count": len(items)}


def get_news(limit=None):
    """Get federation news from RSS."""
    feed = _rss_request("nieuws.rss")
    if isinstance(feed, dict) and feed.get("error"):
        return feed

    items = []
    for entry in feed.entries:
        items.append({
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "date": entry.get("published", ""),
            "summary": entry.get("summary", entry.get("description", "")),
        })

    if limit:
        items = items[:int(limit)]

    return {"news": items, "count": len(items)}
