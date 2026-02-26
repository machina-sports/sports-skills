"""Tennis data connector — ESPN public API (ATP + WTA).

Provides tournament scores, season calendars, rankings, player profiles,
and news for the ATP and WTA tours.

Tennis is an individual sport and structurally different from team sports:
- Events are tournaments; individual matches are nested in groupings.
- Competitors are athletes (singles) or pairs (doubles), not teams.
- Scoring is in sets/games, not quarters or periods.
- Rankings replace standings; there are no rosters or team schedules.
"""

import datetime
import json
import logging

from sports_skills._espn_base import (
    _USER_AGENT,
    ESPN_STATUS_MAP,
    _cache_get,
    _cache_set,
    _http_fetch,
    _resolve_athlete_ref,
    espn_request,
)

logger = logging.getLogger("sports_skills.tennis")

_VALID_TOURS = {"atp", "wta"}

# ESPN ranking IDs per tour
_RANKING_IDS = {"atp": 1, "wta": 2}


# ============================================================
# Helpers
# ============================================================


def _tour_path(tour):
    """Build the ESPN sport path for a tour."""
    return f"tennis/{tour}"


def _validate_tour(tour):
    """Return normalized tour string or error dict."""
    if not tour:
        return None, {"error": True, "message": "tour is required (atp or wta)"}
    t = str(tour).lower().strip()
    if t not in _VALID_TOURS:
        return None, {"error": True, "message": f"Invalid tour '{tour}'. Must be 'atp' or 'wta'."}
    return t, None


def _current_year():
    return datetime.datetime.utcnow().year


def _current_week():
    """Return the current ISO week number (1-based)."""
    return datetime.datetime.utcnow().isocalendar()[1]


# ============================================================
# Normalizers — Tennis-specific
# ============================================================


def _build_set_scores(linescores):
    """Build set scores list, including tiebreak points when present."""
    sets = []
    for s in linescores:
        entry = {"games": int(s.get("value", 0))}
        tb = s.get("tiebreak")
        if tb is not None:
            entry["tiebreak"] = int(tb)
        sets.append(entry)
    return sets


def _normalize_competitor(comp):
    """Normalize a match competitor (singles or doubles)."""
    comp_type = comp.get("type", "athlete")  # "athlete" or "team"
    linescores = comp.get("linescores", [])
    seed = comp.get("curatedRank", {}).get("current")

    if comp_type == "team":
        # Doubles — competitor has a roster with two athletes
        roster = comp.get("roster", {})
        athletes = roster.get("athletes", [])
        name = roster.get("displayName", "")
        country = ""
        if athletes:
            flags = [a.get("flag", {}).get("alt", "") for a in athletes]
            country = " / ".join(f for f in flags if f)
        return {
            "type": "doubles",
            "name": name,
            "country": country,
            "seed": seed,
            "winner": comp.get("winner", False),
            "set_scores": _build_set_scores(linescores),
            "serving": comp.get("possession", False),
            "athletes": [
                {
                    "name": a.get("displayName", ""),
                    "country": a.get("flag", {}).get("alt", ""),
                }
                for a in athletes
            ],
        }
    else:
        # Singles — competitor has a single athlete
        athlete = comp.get("athlete", {})
        return {
            "type": "singles",
            "name": athlete.get("displayName", ""),
            "country": athlete.get("flag", {}).get("alt", ""),
            "seed": seed,
            "winner": comp.get("winner", False),
            "set_scores": _build_set_scores(linescores),
            "serving": comp.get("possession", False),
        }


def _normalize_match(competition):
    """Normalize a single tennis match from ESPN."""
    status_obj = competition.get("status", {})
    status_type = status_obj.get("type", {})
    round_info = competition.get("round", {})
    match_type = competition.get("type", {})
    venue = competition.get("venue", {})
    notes = competition.get("notes", [])

    competitors = [_normalize_competitor(c) for c in competition.get("competitors", [])]

    result_text = ""
    if notes:
        result_text = notes[0].get("text", "")

    return {
        "id": str(competition.get("id", "")),
        "date": competition.get("date", competition.get("startDate", "")),
        "status": ESPN_STATUS_MAP.get(status_type.get("name", ""), status_type.get("name", "")),
        "status_detail": status_type.get("shortDetail", status_type.get("detail", "")),
        "round": round_info.get("displayName", ""),
        "draw": match_type.get("text", ""),
        "court": venue.get("court", ""),
        "result": result_text,
        "competitors": competitors,
        "sets_played": status_obj.get("period", 0),
    }


def _normalize_tournament(espn_event, include_matches=True):
    """Normalize a tournament event from ESPN scoreboard."""
    venue = espn_event.get("venue", {})
    status_obj = espn_event.get("status", {})
    status_type = status_obj.get("type", {})

    tournament = {
        "id": str(espn_event.get("id", "")),
        "name": espn_event.get("name", ""),
        "short_name": espn_event.get("shortName", ""),
        "start_date": espn_event.get("date", ""),
        "end_date": espn_event.get("endDate", ""),
        "venue": venue.get("displayName", venue.get("fullName", "")),
        "major": espn_event.get("major", False),
        "status": ESPN_STATUS_MAP.get(status_type.get("name", ""), status_type.get("name", "")),
        "status_detail": status_type.get("shortDetail", ""),
    }

    # Previous winners
    prev_winners = []
    for w in espn_event.get("previousWinners", []):
        athlete = w.get("athlete", {})
        prev_winners.append({
            "year": w.get("season", ""),
            "name": athlete.get("displayName", ""),
        })
    if prev_winners:
        tournament["previous_winners"] = prev_winners

    if not include_matches:
        return tournament

    # Matches from groupings
    draws = []
    for grouping in espn_event.get("groupings", []):
        group_info = grouping.get("grouping", {})
        matches = [_normalize_match(c) for c in grouping.get("competitions", [])]
        if matches:
            draws.append({
                "name": group_info.get("displayName", ""),
                "slug": group_info.get("slug", ""),
                "matches": matches,
                "count": len(matches),
            })
    tournament["draws"] = draws

    return tournament


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


def get_scoreboard(request_data):
    """Get active tournaments with matches for a tour (ATP or WTA)."""
    params = request_data.get("params", {})
    tour, err = _validate_tour(params.get("tour"))
    if err:
        return err

    espn_params = {}
    date = params.get("date")
    if date:
        espn_params["dates"] = date.replace("-", "")

    data = espn_request(_tour_path(tour), "scoreboard", espn_params or None)
    if data.get("error"):
        return data

    tournaments = [_normalize_tournament(e, include_matches=True) for e in data.get("events", [])]

    return {
        "tour": tour.upper(),
        "tournaments": tournaments,
        "count": len(tournaments),
    }


def get_calendar(request_data):
    """Get full season calendar for a tour (ATP or WTA)."""
    params = request_data.get("params", {})
    tour, err = _validate_tour(params.get("tour"))
    if err:
        return err

    year = params.get("year") or _current_year()

    # Using dates=YYYY returns the full year of tournaments (no match details)
    data = espn_request(_tour_path(tour), "scoreboard", {"dates": str(year)})
    if data.get("error"):
        return data

    tournaments = [_normalize_tournament(e, include_matches=False) for e in data.get("events", [])]

    return {
        "tour": tour.upper(),
        "year": year,
        "tournaments": tournaments,
        "count": len(tournaments),
    }


def get_rankings(request_data):
    """Get current rankings for a tour (ATP or WTA).

    Fetches from the ESPN Core API with $ref resolution for athlete names.
    """
    params = request_data.get("params", {})
    tour, err = _validate_tour(params.get("tour"))
    if err:
        return err

    limit = params.get("limit", 50)
    year = _current_year()
    week = _current_week()
    ranking_id = _RANKING_IDS[tour]

    cache_key = f"tennis_rankings:{tour}:{year}:{week}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # Try current week, then fall back to previous weeks if no data
    rankings_data = None
    for week_offset in range(0, 4):
        try_week = week - week_offset
        if try_week < 1:
            break
        url = (
            f"https://sports.core.api.espn.com/v2/sports/tennis/leagues/{tour}"
            f"/seasons/{year}/types/2/weeks/{try_week}/rankings/{ranking_id}"
        )
        headers = {"User-Agent": _USER_AGENT}
        raw, fetch_err = _http_fetch(url, headers=headers, max_retries=1)
        if fetch_err:
            continue
        try:
            data = json.loads(raw.decode())
            ranks = data.get("ranks", [])
            if ranks:
                rankings_data = data
                break
        except (json.JSONDecodeError, ValueError):
            continue

    if not rankings_data:
        return {"error": True, "message": f"No {tour.upper()} rankings available for {year}"}

    # Normalize rankings, resolving $ref athlete links
    ranks = rankings_data.get("ranks", [])
    entries = []
    for rank in ranks[:limit]:
        current = rank.get("current", "")
        previous = rank.get("previous", "")
        points = rank.get("points", 0)
        trend = rank.get("trend", "")

        # Resolve athlete name and ID from $ref
        athlete = rank.get("athlete", {})
        if isinstance(athlete, dict):
            ref_url = athlete.get("$ref", "")
            athlete_id = str(athlete.get("id", ""))
            name = athlete.get("displayName") or athlete.get("fullName") or ""
            if (not name or not athlete_id) and ref_url:
                resolved = _resolve_athlete_ref(ref_url)
                if not name:
                    name = resolved["name"]
                if not athlete_id:
                    athlete_id = resolved["id"]
        else:
            name = ""
            athlete_id = ""

        entries.append({
            "rank": current,
            "previous_rank": previous,
            "id": athlete_id,
            "name": name,
            "points": points,
            "trend": trend,
        })

    headline = rankings_data.get("headline", "")
    result = {
        "tour": tour.upper(),
        "headline": headline,
        "rankings": entries,
        "count": len(entries),
    }
    _cache_set(cache_key, result, ttl=3600)  # rankings update weekly
    return result


def get_player_info(request_data):
    """Get player profile from ESPN Core API."""
    params = request_data.get("params", {})
    player_id = params.get("player_id")
    if not player_id:
        return {"error": True, "message": "player_id is required"}

    cache_key = f"tennis_player:{player_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    url = f"https://sports.core.api.espn.com/v2/sports/tennis/athletes/{player_id}"
    headers = {"User-Agent": _USER_AGENT}
    raw, err = _http_fetch(url, headers=headers)
    if err:
        return err

    try:
        data = json.loads(raw.decode())
    except (json.JSONDecodeError, ValueError):
        return {"error": True, "message": "ESPN returned invalid JSON"}

    hand = data.get("hand", {})
    birth = data.get("birthPlace", {})

    result = {
        "id": str(data.get("id", "")),
        "name": data.get("displayName", data.get("fullName", "")),
        "first_name": data.get("firstName", ""),
        "last_name": data.get("lastName", ""),
        "country": birth.get("country", ""),
        "birthplace": birth.get("summary", ""),
        "date_of_birth": data.get("dateOfBirth", ""),
        "age": data.get("age", ""),
        "height": data.get("displayHeight", ""),
        "weight": data.get("displayWeight", ""),
        "hand": hand.get("displayValue", ""),
        "active": data.get("active", True),
        "debut_year": data.get("debutYear", ""),
        "experience_years": data.get("experience", {}).get("years", ""),
    }

    # Add player links
    links = []
    for link in data.get("links", []):
        rels = link.get("rel", [])
        if "playercard" in rels:
            result["espn_url"] = link.get("href", "")
        links.append({
            "type": rels[0] if rels else "",
            "href": link.get("href", ""),
        })

    _cache_set(cache_key, result, ttl=3600)
    return result


def get_news(request_data):
    """Get tennis news articles for a tour (ATP or WTA)."""
    params = request_data.get("params", {})
    tour, err = _validate_tour(params.get("tour"))
    if err:
        return err

    data = espn_request(_tour_path(tour), "news")
    if data.get("error"):
        return data

    articles = _normalize_news(data)
    return {"tour": tour.upper(), "articles": articles, "count": len(articles)}
