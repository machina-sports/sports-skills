"""Cricket live-ish data connector — ESPN public site API.

Cricket on ESPN has no single league: each series/competition has a
numeric ID used in the league slot of the URL (e.g. 8048 = IPL).
Discover active series IDs with get_series().
"""

import json
import logging
import urllib.parse

from sports_skills._espn_base import (
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
