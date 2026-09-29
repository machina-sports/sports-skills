"""Golf data connector — ESPN public API.

Provides tournament leaderboards, season schedules, golfer profiles,
and news for PGA Tour, LPGA, and DP World Tour.
"""

from __future__ import annotations

import json
import logging

from sports_skills._espn_base import (
    _USER_AGENT,
    ESPN_STATUS_MAP,
    _cache_get,
    _cache_set,
    _espn_rate_limiter,
    _http_fetch,
    espn_request,
)

logger = logging.getLogger("sports_skills.golf")

_VALID_TOURS = {"pga", "lpga", "eur"}

# Map from tour slug to ESPN sport path
_TOUR_PATHS = {
    "pga": "golf/pga",
    "lpga": "golf/lpga",
    "eur": "golf/eur",
}

# Friendly names
_TOUR_NAMES = {
    "pga": "PGA Tour",
    "lpga": "LPGA Tour",
    "eur": "DP World Tour",
}

# Golf-specific status mapping (extends the base map)
_GOLF_STATUS_MAP = {
    **ESPN_STATUS_MAP,
    "STATUS_PLAY_COMPLETE": "round_complete",
}


def _validate_tour(tour):
    """Validate and normalize tour parameter."""
    if not tour:
        return None, {"error": True, "message": "tour is required. Use 'pga', 'lpga', or 'eur'."}
    tour = tour.lower().strip()
    if tour not in _VALID_TOURS:
        return None, {
            "error": True,
            "message": f"Invalid tour '{tour}'. Use 'pga', 'lpga', or 'eur' (DP World Tour).",
        }
    return tour, None


# ============================================================
# ESPN Response Normalizers
# ============================================================


def _round_strokes(ls):
    """Strokes for a round linescore; None when ESPN marks the round unplayed ("-")."""
    if ls.get("value") is None or ls.get("displayValue") == "-":
        return None
    return int(ls["value"])


def _holes_played(ls):
    """Holes in the nested card, or None when ESPN sent no hole detail.

    A withdrawal's round keeps the strokes for the holes played (e.g. 4 strokes,
    "E" after one hole), so a count below 18 marks an incomplete round.
    """
    holes = [h for h in ls.get("linescores", []) if 1 <= h.get("period", 0) <= 18]
    return len(holes) if holes else None


def _normalize_golfer(competitor):
    """Normalize a golfer from the scoreboard competitors list."""
    athlete = competitor.get("athlete", {})
    flag = athlete.get("flag", {})

    # Round-by-round scores
    rounds = []
    for ls in competitor.get("linescores", []):
        period = ls.get("period", 0)
        if period < 1 or period > 4:
            continue
        rounds.append({
            "round": period,
            "strokes": _round_strokes(ls),
            "score": ls.get("displayValue", ""),
            "holes_played": _holes_played(ls),
        })

    return {
        "position": competitor.get("order", ""),
        "id": str(competitor.get("id", "")),
        "name": athlete.get("displayName", athlete.get("fullName", "")),
        "country": flag.get("alt", ""),
        "score": competitor.get("score", ""),
        "rounds": rounds,
    }


def _normalize_tournament(espn_event):
    """Normalize a golf tournament from the scoreboard."""
    comp = espn_event.get("competitions", [{}])[0]
    status_obj = comp.get("status", espn_event.get("status", {}))
    status_type = status_obj.get("type", {}).get("name", "")
    status_detail = status_obj.get("type", {}).get("shortDetail", "")
    current_round = status_obj.get("period", 0)

    # Venue
    venue_list = espn_event.get("courses", comp.get("venue", []))
    venue = {}
    if isinstance(venue_list, list) and venue_list:
        v = venue_list[0]
        venue = {
            "name": v.get("name", v.get("fullName", "")),
            "city": v.get("address", {}).get("city", "") if isinstance(v.get("address"), dict) else "",
            "state": v.get("address", {}).get("state", "") if isinstance(v.get("address"), dict) else "",
            "country": v.get("address", {}).get("country", "") if isinstance(v.get("address"), dict) else "",
        }
    elif isinstance(venue_list, dict):
        venue = {
            "name": venue_list.get("fullName", ""),
            "city": venue_list.get("address", {}).get("city", ""),
        }

    # Broadcasts
    broadcasts = []
    for b in comp.get("broadcasts", []):
        for name in b.get("names", []):
            broadcasts.append(name)

    # Leaderboard (competitors sorted by position)
    competitors = comp.get("competitors", [])
    leaderboard = [_normalize_golfer(c) for c in sorted(competitors, key=lambda x: x.get("order", 999))]

    return {
        "id": str(espn_event.get("id", "")),
        "name": espn_event.get("name", ""),
        "short_name": espn_event.get("shortName", ""),
        "status": _GOLF_STATUS_MAP.get(status_type, status_type),
        "status_detail": status_detail,
        "current_round": current_round,
        "start_date": espn_event.get("date", comp.get("date", "")),
        "end_date": espn_event.get("endDate", ""),
        "venue": venue,
        "broadcasts": broadcasts,
        "leaderboard": leaderboard,
        "field_size": len(leaderboard),
    }


def _normalize_calendar_event(cal_event):
    """Normalize a calendar event from the leagues calendar."""
    return {
        "id": str(cal_event.get("id", "")),
        "name": cal_event.get("label", cal_event.get("name", "")),
        "start_date": cal_event.get("startDate", cal_event.get("date", "")),
        "end_date": cal_event.get("endDate", ""),
    }


def _normalize_player_overview(data):
    """Normalize player overview from ESPN common/v3 overview endpoint."""
    # Season stats from statistics.splits
    stats_raw = data.get("statistics", {})
    splits = []
    stat_labels = stats_raw.get("labels", [])
    stat_names = stats_raw.get("names", [])
    for split in stats_raw.get("splits", []):
        split_stats = split.get("stats", [])
        if not split_stats:
            continue
        entry = {"name": split.get("displayName", "")}
        for i, val in enumerate(split_stats):
            if i < len(stat_names):
                entry[stat_names[i]] = val
            elif i < len(stat_labels):
                entry[stat_labels[i]] = val
        splits.append(entry)

    season_stats = {
        "display_name": stats_raw.get("displayName", ""),
        "splits": splits,
    }

    # Season rankings from seasonRankings.categories
    rankings_raw = data.get("seasonRankings", {})
    rankings = []
    for cat in rankings_raw.get("categories", []):
        rankings.append({
            "name": cat.get("displayName", cat.get("name", "")),
            "abbreviation": cat.get("abbreviation", cat.get("name", "")),
            "value": cat.get("displayValue", str(cat.get("value", ""))),
            "rank": cat.get("rank", ""),
            "rank_display": cat.get("rankDisplayValue", ""),
        })

    # Recent tournaments
    recent = []
    for tourney in data.get("recentTournaments", []):
        events_stats = tourney.get("eventsStats", [])
        for ev in events_stats:
            comp = (ev.get("competitions", [{}]) or [{}])[0]
            competitors = comp.get("competitors", [{}])
            score_obj = competitors[0].get("score", {}) if competitors else {}
            recent.append({
                "name": ev.get("name", ev.get("shortName", "")),
                "date": ev.get("date", ""),
                "score": score_obj.get("displayValue", str(score_obj.get("value", ""))),
            })

    # ESPN groups recent tournaments per tour (PGA, then DP World, ...); newest first.
    recent.sort(key=lambda t: t["date"] or "", reverse=True)

    return {
        "season_stats": season_stats,
        "rankings": rankings,
        "recent_tournaments": recent,
    }


def _normalize_scorecard(competitor, tournament_name=""):
    """Normalize hole-by-hole scorecard from scoreboard competitor data."""
    athlete = competitor.get("athlete", {})
    flag = athlete.get("flag", {})

    rounds = []
    for ls in competitor.get("linescores", []):
        period = ls.get("period", 0)
        if period < 1 or period > 4:
            continue

        # Nested linescores contain hole-by-hole data
        holes = []
        for hole_ls in ls.get("linescores", []):
            hole_num = hole_ls.get("period", 0)
            if hole_num < 1 or hole_num > 18:
                continue
            score_type = hole_ls.get("scoreType", {})
            holes.append({
                "hole": hole_num,
                "strokes": int(hole_ls.get("value", 0)) if hole_ls.get("value") is not None else None,
                "score": score_type.get("displayValue", ""),
            })

        rounds.append({
            "round": period,
            "total_strokes": _round_strokes(ls),
            "total_score": ls.get("displayValue", ""),
            "holes_played": len(holes) if holes else None,
            "holes": holes,
        })

    return {
        "player": {
            "id": str(competitor.get("id", "")),
            "name": athlete.get("displayName", athlete.get("fullName", "")),
            "country": flag.get("alt", ""),
        },
        "tournament": tournament_name,
        "overall_score": competitor.get("score", ""),
        "rounds": rounds,
    }


def _normalize_news(espn_data):
    """Normalize ESPN news response."""
    articles = []
    for article in espn_data.get("articles", []):
        articles.append({
            "headline": article.get("headline", ""),
            "description": article.get("description", ""),
            "published": article.get("published", ""),
            "type": article.get("type", ""),
            "premium": article.get("premium", False),
            "link": "",
            "images": [img.get("url", "") for img in article.get("images", [])[:1]],
        })
        links = article.get("links", {})
        web = links.get("web", {})
        if web.get("href"):
            articles[-1]["link"] = web["href"]
        elif links.get("api", {}).get("self", {}).get("href"):
            articles[-1]["link"] = links["api"]["self"]["href"]
    return articles


# ============================================================
# Command Functions
# ============================================================


def _event_start_date(tour, event_id):
    """Start date (YYYYMMDD) of an ESPN golf event, from the core API event record."""
    cache_key = f"golf_event_date:{tour}:{event_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached, None
    url = f"https://sports.core.api.espn.com/v2/sports/golf/leagues/{tour}/events/{event_id}"
    raw, err = _http_fetch(url, headers={"User-Agent": _USER_AGENT}, rate_limiter=_espn_rate_limiter)
    if err:
        return None, {
            "error": True,
            "message": f"Could not look up {_TOUR_NAMES[tour]} event {event_id} on ESPN "
            f"({err.get('message', 'request failed')}). Check the id with get_schedule, "
            "or pass date=YYYY-MM-DD (any day of the tournament).",
        }
    try:
        date = json.loads(raw.decode()).get("date", "")[:10].replace("-", "")
    except (json.JSONDecodeError, ValueError, AttributeError):
        date = ""
    if len(date) != 8:
        return None, {
            "error": True,
            "message": f"ESPN has no date for {_TOUR_NAMES[tour]} event {event_id}; "
            "pass date=YYYY-MM-DD (any day of the tournament).",
        }
    _cache_set(cache_key, date, ttl=86400)
    return date, None


def _scoreboard_events(tour, event_id=None, date=None):
    """Scoreboard events for the current week, a given date, or a given event.

    ESPN's golf scoreboard ignores an ``event`` parameter, so a past event is
    reached through ``dates=YYYYMMDD`` (its start date when only the id is given).
    Returns (events, error).
    """
    espn_params = None
    if date:
        day = str(date).replace("-", "")
        if len(day) != 8 or not day.isdigit():
            return None, {"error": True, "message": f"Invalid date '{date}'. Use YYYY-MM-DD."}
        espn_params = {"dates": day}
    elif event_id:
        day, err = _event_start_date(tour, event_id)
        if err:
            return None, err
        espn_params = {"dates": day}
    data = espn_request(_TOUR_PATHS[tour], "scoreboard", espn_params)
    if data.get("error"):
        return None, data
    events = data.get("events", [])
    if event_id:
        events = [e for e in events if str(e.get("id", "")) == str(event_id)]
        if not events:
            return None, {
                "tour": _TOUR_NAMES[tour],
                "error": True,
                "message": f"Event {event_id} is not on the {_TOUR_NAMES[tour]} scoreboard"
                + (f" for {date}" if date else "")
                + ". Check the id and tour with get_schedule.",
            }
    return events, None


def get_leaderboard(request_data):
    """Get a tournament leaderboard (current, or the given event_id / date)."""
    params = request_data.get("params", {})
    tour, err = _validate_tour(params.get("tour"))
    if err:
        return err

    events, err = _scoreboard_events(tour, params.get("event_id"), params.get("date"))
    if err:
        return err
    if not events:
        return {
            "tour": _TOUR_NAMES[tour],
            "tournament": None,
            "message": "No tournament on the scoreboard"
            + (f" for {params['date']}." if params.get("date") else " right now."),
        }

    # Return the requested, or the current/most recent, tournament
    tournament = _normalize_tournament(events[0])
    return {
        "tour": _TOUR_NAMES[tour],
        "tournament": tournament,
    }


def get_schedule(request_data):
    """Get full season schedule/calendar."""
    params = request_data.get("params", {})
    tour, err = _validate_tour(params.get("tour"))
    if err:
        return err
    year = params.get("year")

    sport_path = _TOUR_PATHS[tour]
    espn_params = {"dates": str(year) if year else "2026"}

    # The season calendar comes with every scoreboard response; limit=1 keeps
    # ESPN from also sending every event's full field (~26 MB for a PGA season
    # vs ~13 KB). The full body is only fetched if the calendar is missing.
    data = espn_request(sport_path, "scoreboard", {**espn_params, "limit": 1})
    if data.get("error"):
        return data
    if not any(league.get("calendar") for league in data.get("leagues", [])):
        data = espn_request(sport_path, "scoreboard", espn_params)
        if data.get("error"):
            return data

    # Calendar is in leagues[0].calendar[]
    tournaments = []
    for league in data.get("leagues", []):
        for cal_event in league.get("calendar", []):
            tournaments.append(_normalize_calendar_event(cal_event))

    # Also extract events if they have more info
    if not tournaments:
        for event in data.get("events", []):
            tournaments.append({
                "id": str(event.get("id", "")),
                "name": event.get("name", ""),
                "start_date": event.get("date", ""),
                "end_date": event.get("endDate", ""),
            })

    season_info = data.get("season", {})
    return {
        "tour": _TOUR_NAMES[tour],
        "season": season_info.get("year", year or ""),
        "tournaments": tournaments,
        "count": len(tournaments),
    }


def _fetch_player(player_id, tour):
    """Fetch player profile from ESPN common/v3 API for a given tour."""
    url = (
        f"https://site.web.api.espn.com/apis/common/v3/sports/golf/{tour}"
        f"/athletes/{player_id}"
    )
    headers = {"User-Agent": _USER_AGENT}
    raw, err = _http_fetch(url, headers=headers)
    if err:
        return None, err
    try:
        data = json.loads(raw.decode())
    except (json.JSONDecodeError, ValueError):
        return None, {"error": True, "message": "ESPN returned invalid JSON"}
    return data, None


def get_player_info(request_data):
    """Get golfer profile via ESPN common/v3 API."""
    params = request_data.get("params", {})
    player_id = params.get("player_id")
    tour = params.get("tour", "pga")
    if not player_id:
        return {"error": True, "message": "player_id is required"}

    tour = tour.lower().strip()
    if tour not in _VALID_TOURS:
        tour = "pga"

    cache_key = f"golf_player:{player_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # Try specified tour first, then fall back to others
    # (LPGA player profiles are not available via ESPN's API)
    tours_to_try = [tour] + [t for t in ("pga", "eur") if t != tour]
    data = None
    last_err = None
    for t in tours_to_try:
        data, last_err = _fetch_player(player_id, t)
        if data is not None:
            break

    if data is None:
        return last_err or {"error": True, "message": f"Player {player_id} not found"}

    athlete = data.get("athlete", data)
    headshot = athlete.get("headshot", {})

    result = {
        "id": str(athlete.get("id", player_id)),
        "name": athlete.get("displayName", athlete.get("fullName", "")),
        "age": athlete.get("age", ""),
        "date_of_birth": athlete.get("dateOfBirth", ""),
        "citizenship": athlete.get("citizenship", ""),
        "birthplace": athlete.get("birthPlace", {}).get("city", "") + ", " + athlete.get("birthPlace", {}).get("state", "") if athlete.get("birthPlace") else "",
        "height": athlete.get("displayHeight", ""),
        "weight": athlete.get("displayWeight", ""),
        "turned_pro": athlete.get("turnedPro", ""),
        "college": athlete.get("college", {}).get("name", "") if isinstance(athlete.get("college"), dict) else str(athlete.get("college", "")),
        "headshot": headshot.get("href", "") if isinstance(headshot, dict) else "",
        "status": athlete.get("status", ""),
        "link": f"https://www.espn.com/golf/player/_/id/{player_id}",
    }
    _cache_set(cache_key, result, ttl=3600)
    return result


def get_news(request_data):
    """Get golf news articles."""
    params = request_data.get("params", {})
    tour, err = _validate_tour(params.get("tour"))
    if err:
        return err

    sport_path = _TOUR_PATHS[tour]
    data = espn_request(sport_path, "news")
    if data.get("error"):
        return data

    articles = _normalize_news(data)
    return {
        "tour": _TOUR_NAMES[tour],
        "articles": articles,
        "count": len(articles),
    }


def _fetch_player_overview(player_id, tour):
    """Fetch player overview from ESPN common/v3 overview endpoint."""
    url = (
        f"https://site.web.api.espn.com/apis/common/v3/sports/golf/{tour}"
        f"/athletes/{player_id}/overview"
    )
    headers = {"User-Agent": _USER_AGENT}
    raw, err = _http_fetch(url, headers=headers)
    if err:
        return None, err
    try:
        data = json.loads(raw.decode())
    except (json.JSONDecodeError, ValueError):
        return None, {"error": True, "message": "ESPN returned invalid JSON"}
    return data, None


def get_player_overview(request_data):
    """Get golfer season overview: stats, rankings, and recent tournaments."""
    params = request_data.get("params", {})
    player_id = params.get("player_id")
    tour = params.get("tour", "pga")
    if not player_id:
        return {"error": True, "message": "player_id is required"}

    tour = tour.lower().strip()
    if tour not in _VALID_TOURS:
        tour = "pga"

    cache_key = f"golf_overview:{player_id}:{tour}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # Try specified tour first, then fall back
    tours_to_try = [tour] + [t for t in ("pga", "eur") if t != tour]
    data = None
    last_err = None
    for t in tours_to_try:
        data, last_err = _fetch_player_overview(player_id, t)
        if data is not None:
            break

    if data is None:
        return last_err or {"error": True, "message": f"Player {player_id} overview not found"}

    overview = _normalize_player_overview(data)
    overview["id"] = str(player_id)

    _cache_set(cache_key, overview, ttl=600)
    return overview


def get_scorecard(request_data):
    """Get hole-by-hole scorecard for a golfer (current tournament, or event_id / date)."""
    params = request_data.get("params", {})
    tour, err = _validate_tour(params.get("tour"))
    if err:
        return err
    player_id = params.get("player_id")
    if not player_id:
        return {"error": True, "message": "player_id is required"}

    events, err = _scoreboard_events(tour, params.get("event_id"), params.get("date"))
    if err:
        return err
    if not events:
        return {
            "tour": _TOUR_NAMES[tour],
            "error": True,
            "message": "No tournament on the scoreboard"
            + (f" for {params['date']}." if params.get("date") else " right now.")
            + " Pass event_id (from get_schedule) for a completed tournament.",
        }

    # Search for the golfer in the current tournament
    event = events[0]
    tournament_name = event.get("name", "")
    comp = event.get("competitions", [{}])[0]
    competitors = comp.get("competitors", [])

    player_id_str = str(player_id)
    for competitor in competitors:
        if str(competitor.get("id", "")) == player_id_str:
            scorecard = _normalize_scorecard(competitor, tournament_name)
            scorecard["tour"] = _TOUR_NAMES[tour]
            return scorecard

    return {
        "tour": _TOUR_NAMES[tour],
        "tournament": tournament_name,
        "error": True,
        "message": f"Player {player_id} not found in the {tournament_name or 'tournament'} field.",
    }
