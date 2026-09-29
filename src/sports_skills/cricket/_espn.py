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
    ESPN_STATUS_MAP,
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


def _series_for_event(event_id):
    """Series id of an event listed in ESPN's active-series header, or None.

    The header only lists current series, so older matches do not resolve.
    """
    data = _header_request()
    if data.get("error"):
        return None
    for sport in data.get("sports", []):
        for lg in sport.get("leagues", []):
            if any(str(e.get("id", "")) == str(event_id) for e in lg.get("events", [])):
                return str(lg.get("id", "")) or None
    return None


def _num(value):
    """ESPN stat displayValue as int/float when numeric, else as sent."""
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return float(value)
        except (TypeError, ValueError):
            return value


def _innings_scorecards(rosters):
    """Batting and bowling card for every innings, rebuilt from the rosters.

    ESPN's ``matchcards`` only carry the latest innings and the summary takes
    no innings parameter, but each roster player's ``linescores`` hold their
    figures per innings (``period``).
    """
    cards = {}
    for team in rosters or []:
        team_name = (team.get("team") or {}).get("displayName", "")
        for player in team.get("roster") or []:
            athlete = player.get("athlete") or {}
            who = {"player_id": str(athlete.get("id", "")), "player": athlete.get("displayName", "")}
            for ls in player.get("linescores") or []:
                n = _num(ls.get("period"))
                for sub in ls.get("linescores") or []:
                    stats = {
                        s.get("name"): s.get("displayValue")
                        for cat in ((sub.get("statistics") or {}).get("categories") or [])
                        for s in cat.get("stats") or []
                    }
                    card = cards.setdefault(n, {
                        "innings": n, "batting_team": "", "bowling_team": "",
                        "batting": [], "bowling": [],
                    })
                    if stats.get("batted") == "1":
                        card["batting_team"] = team_name
                        card["batting"].append({
                            **who,
                            "position": _num(stats.get("battingPosition")),
                            "runs": _num(stats.get("runs")),
                            "balls": _num(stats.get("ballsFaced")),
                            "fours": _num(stats.get("fours")),
                            "sixes": _num(stats.get("sixes")),
                            "strike_rate": _num(stats.get("strikeRate")),
                            "not_out": stats.get("outs") == "0",
                            "dismissal": stats.get("dismissalCard", ""),
                        })
                    if stats.get("bowled") == "1":
                        card["bowling_team"] = team_name
                        card["bowling"].append({
                            **who,
                            "position": _num(stats.get("bowlingPosition")),
                            "overs": _num(stats.get("overs")),
                            "maidens": _num(stats.get("maidens")),
                            "runs": _num(stats.get("conceded")),
                            "wickets": _num(stats.get("wickets")),
                            "economy": _num(stats.get("economyRate")),
                            "wides": _num(stats.get("wides")),
                            "noballs": _num(stats.get("noballs")),
                        })
    out = []
    for n in sorted(cards, key=lambda k: k if isinstance(k, int) else 99):
        card = cards[n]
        if not card["batting"] and not card["bowling"]:
            continue
        for key in ("batting", "bowling"):
            card[key].sort(key=lambda r: r["position"] if isinstance(r["position"], int) else 99)
        out.append(card)
    return out


def get_game_summary(request_data):
    """Match detail: rosters, leaders, matchcards, game info, header.

    ``series_id`` is optional: when omitted it is resolved from the event,
    which works for matches in ESPN's currently-active series.
    """
    params = request_data.get("params", {})
    event_id = params.get("event_id")
    if not event_id:
        return {"error": True, "message": "event_id is required — see get_scoreboard"}
    if params.get("series_id"):
        series_id = str(params["series_id"]).strip()
    else:
        series_id = _series_for_event(event_id)
        if not series_id:
            return {
                "error": True,
                "message": (
                    f"series_id is required for event {event_id}: it is not in a currently-active "
                    "series, so it could not be resolved. series_id is the series (league) id, "
                    "not a match id: e.g. 8048 for the IPL. Get it from get_series or from the "
                    "scoreboard entry of the match."
                ),
            }
    data = espn_summary(f"cricket/{series_id}", str(event_id))
    if data is None:
        # Agents read a bare "request failed" as "try another series_id" and
        # walked through match-like numbers (Sports Agent Bench v1).
        return {
            "error": True,
            "message": (
                f"ESPN returned no summary for event {event_id} in series {series_id}. "
                "series_id is the series (league) id, not a match id: e.g. 8048 for the IPL. "
                "Get it from get_series or from the scoreboard entry of the match. "
                "If the ids are right, ESPN may be unavailable; retry later."
            ),
        }
    if isinstance(data, dict) and data.get("error"):
        return data
    return {
        "event_id": str(event_id),
        "series_id": series_id,
        "header": data.get("header", {}),
        "game_info": data.get("gameInfo", {}),
        "notes": data.get("notes", []),
        "rosters": data.get("rosters", []),
        "leaders": data.get("leaders", []),
        "matchcards": data.get("matchcards", {}),
        # matchcards hold only the latest innings; this has every innings.
        "scorecards": _innings_scorecards(data.get("rosters")),
        "article": data.get("article", {}),
    }


def get_news(request_data):
    """News articles for a series."""
    params = request_data.get("params", {})
    series_id, err = _validate_series_id(params.get("series_id"))
    if err:
        return err
    data = espn_request(f"cricket/{series_id}", "news")
    if data.get("error"):
        return data
    articles = []
    for a in data.get("articles", []):
        articles.append({
            "headline": a.get("headline", ""),
            "description": a.get("description", ""),
            "published": a.get("published", ""),
            "type": a.get("type", ""),
            "link": a.get("links", {}).get("web", {}).get("href", ""),
        })
    return {"header": data.get("header", ""), "articles": articles, "count": len(articles)}
