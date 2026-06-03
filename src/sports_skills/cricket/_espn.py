"""Cricket live-ish data connector — ESPN public site API.

Cricket on ESPN has no single league: each series/competition has a
numeric ID used in the league slot of the URL (e.g. 8048 = IPL).
Discover active series IDs with get_series().
"""

import json
import logging
import urllib.parse

from sports_skills._espn_base import (
    ESPN_STATUS_MAP,
    _USER_AGENT,
    _cache_get,
    _cache_set,
    _espn_rate_limiter,
    _http_fetch,
    espn_request,
    espn_summary,
)

logger = logging.getLogger("sports_skills.cricket")

_HEADER_URL = "https://site.web.api.espn.com/apis/personalized/v2/scoreboard/header"


def _validate_series_id(series_id):
    """Return normalized series_id string or error dict."""
    if not series_id:
        return None, {
            "error": True,
            "message": "series_id is required — discover active series IDs with get_series",
        }
    return str(series_id).strip(), None


def _header_request():
    """Fetch the cricket scoreboard header (active series). Cached 120s."""
    cache_key = "espn:cricket:header"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    url = _HEADER_URL + "?" + urllib.parse.urlencode({"sport": "cricket"})
    raw, err = _http_fetch(
        url, headers={"User-Agent": _USER_AGENT}, rate_limiter=_espn_rate_limiter
    )
    if err:
        return err
    try:
        data = json.loads(raw.decode())
    except (json.JSONDecodeError, ValueError):
        return {"error": True, "message": "ESPN returned invalid JSON"}
    _cache_set(cache_key, data, ttl=120)
    return data


def get_series(request_data):
    """List currently-active cricket series with their ESPN series IDs."""
    data = _header_request()
    if data.get("error"):
        return data
    sports = data.get("sports", [])
    leagues = sports[0].get("leagues", []) if sports else []
    series = []
    for lg in leagues:
        events = lg.get("events", [])
        series.append({
            "series_id": str(lg.get("id", "")),
            "name": lg.get("name", ""),
            "abbreviation": lg.get("abbreviation", ""),
            "is_tournament": lg.get("isTournament", False),
            "event_count": len(events),
            "events": [
                {
                    "event_id": str(e.get("id", "")),
                    "name": e.get("name", ""),
                    "date": e.get("date", ""),
                    "status": e.get("status", ""),
                    "summary": e.get("summary", ""),
                }
                for e in events
            ],
        })
    return {"series": series, "count": len(series)}


def _normalize_competitor(comp):
    """Normalize a cricket competitor (a team with innings linescores)."""
    team = comp.get("team", {})
    return {
        "team_id": str(team.get("id", "")),
        "team": team.get("displayName", ""),
        "abbreviation": team.get("abbreviation", ""),
        "home_away": comp.get("homeAway", ""),
        "winner": comp.get("winner", False),
        "score": comp.get("score", ""),
        "innings": [
            {
                "innings": ls.get("period", 0),
                "runs": ls.get("runs", 0),
                "wickets": ls.get("wickets", 0),
                "overs": ls.get("overs", 0),
                "is_batting": ls.get("isBatting", False),
                "description": ls.get("description", ""),
            }
            for ls in comp.get("linescores", [])
        ],
    }


def _normalize_event(event):
    """Normalize one scoreboard event (a cricket match)."""
    competitions = event.get("competitions", [])
    comp = competitions[0] if competitions else {}
    status_type = comp.get("status", {}).get("type", {})
    venue = comp.get("venue", {})
    notes = comp.get("notes", [])
    return {
        "event_id": str(event.get("id", "")),
        "name": event.get("name", ""),
        "short_name": event.get("shortName", ""),
        "date": event.get("date", ""),
        "description": comp.get("description", ""),
        "status": ESPN_STATUS_MAP.get(status_type.get("name", ""), status_type.get("name", "")),
        "status_detail": status_type.get("shortDetail", status_type.get("detail", "")),
        "venue": venue.get("fullName", venue.get("displayName", "")),
        "note": notes[0].get("text", "") if notes else "",
        "competitors": [_normalize_competitor(c) for c in comp.get("competitors", [])],
    }


def _fetch_scoreboard(series_id, date=None):
    """Fetch the raw scoreboard payload for a series."""
    espn_params = {}
    if date:
        espn_params["dates"] = str(date).replace("-", "")
    return espn_request(f"cricket/{series_id}", "scoreboard", espn_params or None)


def get_scoreboard(request_data):
    """Scoreboard (events + scores) for one series. Use get_series for IDs."""
    params = request_data.get("params", {})
    series_id, err = _validate_series_id(params.get("series_id"))
    if err:
        return err
    data = _fetch_scoreboard(series_id, params.get("date"))
    if data.get("error"):
        return data
    leagues = data.get("leagues", [])
    league = leagues[0] if leagues else {}
    events = [_normalize_event(e) for e in data.get("events", [])]
    return {
        "series": {
            "series_id": series_id,
            "name": league.get("name", ""),
            "abbreviation": league.get("abbreviation", ""),
        },
        "events": events,
        "count": len(events),
    }


def get_standings(request_data):
    """Points table for a series, extracted from the scoreboard payload."""
    params = request_data.get("params", {})
    series_id, err = _validate_series_id(params.get("series_id"))
    if err:
        return err
    data = _fetch_scoreboard(series_id)
    if data.get("error"):
        return data
    standings = []
    for row in data.get("standings", []):
        team = row.get("team", {})
        standings.append({
            "team_id": str(team.get("id", "")),
            "team": team.get("displayName", ""),
            "abbreviation": team.get("abbreviation", ""),
            "stats": {s.get("name", ""): s.get("value") for s in row.get("stats", [])},
        })
    if not standings:
        return {
            "series_id": series_id,
            "standings": [],
            "count": 0,
            "message": "No standings published for this series (common for bilateral tours)",
        }
    return {"series_id": series_id, "standings": standings, "count": len(standings)}
