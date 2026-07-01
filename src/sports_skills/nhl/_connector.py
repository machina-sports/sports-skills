"""NHL data connector — ESPN public API.

Provides scores, standings, rosters, schedules, game summaries,
statistical leaders, and news for the NHL.
"""

import json
import logging

from sports_skills._espn_base import (
    _USER_AGENT,
    ESPN_STATUS_MAP,
    _cache_get,
    _cache_set,
    _current_year,
    _http_fetch,
    _resolve_leaders,
    espn_core_request,
    espn_request,
    espn_summary,
    espn_web_request,
    normalize_boxscore,
    normalize_core_stats,
    normalize_futures,
    normalize_injuries,
    normalize_odds,
    normalize_scoring_plays,
    normalize_transactions,
)

logger = logging.getLogger("sports_skills.nhl")

SPORT_PATH = "hockey/nhl"


# ============================================================
# ESPN Response Normalizers
# ============================================================


def _normalize_event(espn_event):
    """Normalize an ESPN scoreboard event to a standard format."""
    comp = espn_event.get("competitions", [{}])[0]
    status_obj = comp.get("status", espn_event.get("status", {}))
    status_type = status_obj.get("type", {}).get("name", "")
    status_detail = status_obj.get("type", {}).get("shortDetail", "")

    competitors = []
    for c in comp.get("competitors", []):
        team = c.get("team", {})
        linescores = c.get("linescores", [])
        records = c.get("records", [])
        competitors.append({
            "team": {
                "id": str(team.get("id", "")),
                "name": team.get("displayName", ""),
                "abbreviation": team.get("abbreviation", ""),
                "logo": team.get("logo", ""),
            },
            "home_away": c.get("homeAway", ""),
            "score": c.get("score", "0"),
            "period_scores": [int(p.get("value", 0)) for p in linescores],
            "record": records[0].get("summary", "") if records else "",
            "winner": c.get("winner", False),
        })

    odds = normalize_odds(comp.get("odds", []))

    broadcasts = []
    for b in comp.get("broadcasts", []):
        for name in b.get("names", []):
            broadcasts.append(name)

    return {
        "id": str(espn_event.get("id", "")),
        "name": espn_event.get("name", ""),
        "short_name": espn_event.get("shortName", ""),
        "status": ESPN_STATUS_MAP.get(status_type, status_type),
        "status_detail": status_detail,
        "start_time": comp.get("date", espn_event.get("date", "")),
        "venue": {
            "name": comp.get("venue", {}).get("fullName", ""),
            "city": comp.get("venue", {}).get("address", {}).get("city", ""),
            "state": comp.get("venue", {}).get("address", {}).get("state", ""),
        },
        "competitors": competitors,
        "odds": odds,
        "broadcasts": broadcasts,
    }


def _normalize_standings_entries(standings_data):
    """Parse entries from an ESPN standings block."""
    entries = []
    for entry in standings_data.get("entries", []):
        team = entry.get("team", {})
        stats = {s["name"]: s.get("displayValue", s.get("value", ""))
                 for s in entry.get("stats", [])}
        entries.append({
            "team": {
                "id": str(team.get("id", "")),
                "name": team.get("displayName", ""),
                "abbreviation": team.get("abbreviation", ""),
                "logo": team.get("logos", [{}])[0].get("href", "") if team.get("logos") else "",
            },
            "wins": stats.get("wins", "0"),
            "losses": stats.get("losses", "0"),
            "overtime_losses": stats.get("OTLosses", stats.get("otLosses", "0")),
            "points": stats.get("points", "0"),
            "regulation_wins": stats.get("regulationWins", stats.get("RW", "")),
            "goals_for": stats.get("pointsFor", stats.get("goalsFor", "")),
            "goals_against": stats.get("pointsAgainst", stats.get("goalsAgainst", "")),
            "goal_diff": stats.get("differential", stats.get("diff", "")),
            "games_played": stats.get("gamesPlayed", ""),
            "streak": stats.get("streak", ""),
            "home_record": stats.get("Home", stats.get("homeRecord", "")),
            "away_record": stats.get("Road", stats.get("awayRecord", "")),
            "last_ten": stats.get("L10", stats.get("last10Record", "")),
            "playoff_seed": stats.get("playoffSeed", ""),
        })
    return entries


def _normalize_standings(espn_data):
    """Normalize ESPN standings with conference/division groups.

    Handles two ESPN structures:
    - Conference -> Divisions -> Entries
    - Conference -> Direct Entries
    """
    groups = []
    for child in espn_data.get("children", []):
        conference_name = child.get("name", child.get("abbreviation", ""))

        # Check for division sub-groups first
        if child.get("children"):
            for division in child["children"]:
                division_name = division.get("name", "")
                standings = division.get("standings", {})
                entries = _normalize_standings_entries(standings)
                if entries:
                    groups.append({
                        "conference": conference_name,
                        "division": division_name,
                        "entries": entries,
                    })
        # Fall back to direct standings on the conference
        elif child.get("standings"):
            entries = _normalize_standings_entries(child["standings"])
            if entries:
                groups.append({
                    "conference": conference_name,
                    "division": "",
                    "entries": entries,
                })
    return groups


def _normalize_team(espn_team):
    """Normalize an ESPN team object."""
    team = espn_team.get("team", espn_team)
    logos = team.get("logos", [])
    return {
        "id": str(team.get("id", "")),
        "name": team.get("displayName", ""),
        "abbreviation": team.get("abbreviation", ""),
        "nickname": team.get("nickname", team.get("shortDisplayName", "")),
        "location": team.get("location", ""),
        "color": team.get("color", ""),
        "logo": logos[0].get("href", "") if logos else "",
        "is_active": team.get("isActive", True),
    }


def _normalize_roster(espn_data):
    """Normalize ESPN roster response.

    NHL rosters may come as flat lists or grouped by position.
    """
    athletes = []
    raw_athletes = espn_data.get("athletes", [])

    for athlete in raw_athletes:
        # Grouped format (position -> items)
        if "items" in athlete:
            for item in athlete.get("items", []):
                athletes.append(_parse_athlete(item, athlete.get("position", "")))
        else:
            # Flat format
            athletes.append(_parse_athlete(athlete))

    return athletes


def _parse_athlete(athlete, default_position=""):
    """Parse a single athlete record."""
    position = athlete.get("position", {})
    if isinstance(position, dict):
        pos = position.get("abbreviation", default_position)
    else:
        pos = str(position) or default_position
    return {
        "id": str(athlete.get("id", "")),
        "name": athlete.get("displayName", athlete.get("fullName", "")),
        "jersey": athlete.get("jersey", ""),
        "position": pos,
        "age": athlete.get("age", ""),
        "height": athlete.get("displayHeight", ""),
        "weight": athlete.get("displayWeight", ""),
        "experience": athlete.get("experience", {}).get("years", ""),
        "birthplace": athlete.get("birthPlace", {}).get("city", "") if isinstance(athlete.get("birthPlace"), dict) else "",
        "shoots_catches": athlete.get("hand", {}).get("displayValue", "") if isinstance(athlete.get("hand"), dict) else "",
        "status": athlete.get("status", {}).get("type", ""),
    }


def _normalize_game_summary(summary_data):
    """Normalize ESPN game summary with box score and scoring plays."""
    if not summary_data:
        return {"error": True, "message": "No summary data available"}

    header = summary_data.get("header", {})
    competitions = header.get("competitions", [{}])
    comp = competitions[0] if competitions else {}

    # Basic game info
    game_info = {
        "id": header.get("id", ""),
        "status": comp.get("status", {}).get("type", {}).get("name", ""),
        "status_detail": comp.get("status", {}).get("type", {}).get("shortDetail", ""),
        "venue": {
            "name": summary_data.get("gameInfo", {}).get("venue", {}).get("fullName", ""),
            "city": summary_data.get("gameInfo", {}).get("venue", {}).get("address", {}).get("city", ""),
        },
    }

    # Competitors from header
    competitors = []
    for c in comp.get("competitors", []):
        team = c.get("team", [{}])
        if isinstance(team, list):
            team = team[0] if team else {}
        competitors.append({
            "team": {
                "id": str(team.get("id", "")),
                "name": team.get("displayName", team.get("location", "")),
                "abbreviation": team.get("abbreviation", ""),
                "logo": team.get("logo", ""),
            },
            "home_away": c.get("homeAway", ""),
            "score": c.get("score", "0"),
            "winner": c.get("winner", False),
            "record": c.get("record", ""),
            "linescores": [ls.get("displayValue", "0") for ls in c.get("linescores", [])],
        })

    # Box score — player tables live under boxscore["players"], not ["teams"].
    box_teams = normalize_boxscore(summary_data.get("boxscore", {}))

    # Scoring plays — derived from plays[] when ESPN omits top-level scoringPlays
    # (it does for NHL); the helper backfills team identity from competitors.
    scoring_plays = normalize_scoring_plays(summary_data, competitors)

    # Leaders
    leaders = []
    for leader_group in summary_data.get("leaders", []):
        team = leader_group.get("team", {})
        categories = []
        for cat in leader_group.get("leaders", []):
            top = cat.get("leaders", [{}])
            top_leader = top[0] if top else {}
            athlete = top_leader.get("athlete", {})
            categories.append({
                "category": cat.get("displayName", cat.get("name", "")),
                "leader": {
                    "name": athlete.get("displayName", ""),
                    "position": athlete.get("position", {}).get("abbreviation", ""),
                    "value": top_leader.get("displayValue", ""),
                },
            })
        leaders.append({
            "team": {
                "id": str(team.get("id", "")),
                "name": team.get("displayName", ""),
            },
            "categories": categories,
        })

    return {
        "game_info": game_info,
        "competitors": competitors,
        "boxscore": box_teams,
        "scoring_plays": scoring_plays,
        "leaders": leaders,
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
        # Extract link
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
    """Get live/recent NHL scores."""
    params = request_data.get("params", {})
    date = params.get("date")

    espn_params = {}
    if date:
        espn_params["dates"] = date.replace("-", "")

    data = espn_request(SPORT_PATH, "scoreboard", espn_params or None)
    if data.get("error"):
        return data

    events = [_normalize_event(e) for e in data.get("events", [])]
    day_info = data.get("day", {})

    return {
        "events": events,
        "day": day_info.get("date", ""),
        "count": len(events),
    }


def get_standings(request_data):
    """Get NHL standings by conference and division."""
    params = request_data.get("params", {})
    season = params.get("season")

    espn_params = {}
    if season:
        espn_params["season"] = season

    data = espn_web_request(SPORT_PATH, "standings", espn_params or None)
    if data.get("error"):
        return data

    groups = _normalize_standings(data)
    return {
        "groups": groups,
        "season": data.get("season", {}).get("year", ""),
    }


def get_teams(request_data=None):
    """Get all NHL teams."""
    data = espn_request(SPORT_PATH, "teams")
    if data.get("error"):
        return data

    teams = []
    for sport in data.get("sports", []):
        for league in sport.get("leagues", []):
            for team_wrapper in league.get("teams", []):
                teams.append(_normalize_team(team_wrapper))

    return {"teams": teams, "count": len(teams)}


def get_team_roster(request_data):
    """Get roster for an NHL team."""
    params = request_data.get("params", {})
    team_id = params.get("team_id")
    if not team_id:
        return {"error": True, "message": "team_id is required"}

    data = espn_request(SPORT_PATH, f"teams/{team_id}/roster")
    if data.get("error"):
        return data

    athletes = _normalize_roster(data)
    team_info = data.get("team", {})

    return {
        "team": {
            "id": str(team_info.get("id", team_id)),
            "name": team_info.get("displayName", ""),
            "abbreviation": team_info.get("abbreviation", ""),
        },
        "athletes": athletes,
        "count": len(athletes),
    }


def get_team_schedule(request_data):
    """Get schedule for a specific NHL team."""
    params = request_data.get("params", {})
    team_id = params.get("team_id")
    season = params.get("season")
    if not team_id:
        return {"error": True, "message": "team_id is required"}

    espn_params = {}
    if season:
        espn_params["season"] = season

    data = espn_request(SPORT_PATH, f"teams/{team_id}/schedule", espn_params or None)
    if data.get("error"):
        return data

    events = []
    for event in data.get("events", []):
        events.append(_normalize_event(event))

    team_info = data.get("team", {})
    return {
        "team": {
            "id": str(team_info.get("id", team_id)),
            "name": team_info.get("displayName", ""),
            "abbreviation": team_info.get("abbreviation", ""),
        },
        "events": events,
        "season": data.get("season", {}).get("year", ""),
        "count": len(events),
    }


def get_game_summary(request_data):
    """Get detailed game summary with box score."""
    params = request_data.get("params", {})
    event_id = params.get("event_id")
    if not event_id:
        return {"error": True, "message": "event_id is required"}

    data = espn_summary(SPORT_PATH, event_id)
    if not data:
        return {"error": True, "message": f"No summary data found for event {event_id}"}

    return _normalize_game_summary(data)


def _nhl_current_season():
    """Detect the most recent active NHL season year (season starts Oct, ends Jun)."""
    import datetime
    now = datetime.datetime.utcnow()
    # NHL season starts in October; if Oct-Dec use current year, else previous year
    return now.year if now.month >= 10 else now.year - 1


def get_leaders(request_data):
    """Get NHL statistical leaders via ESPN core API."""
    params = request_data.get("params", {})
    season = params.get("season")

    # Always use season-scoped URL with regular season type (2) for reliability.
    resolved = season or _nhl_current_season()
    url = f"https://sports.core.api.espn.com/v2/sports/hockey/leagues/nhl/seasons/{resolved}/types/2/leaders"

    cache_key = f"nhl_leaders:{resolved}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    headers = {"User-Agent": _USER_AGENT}
    raw, err = _http_fetch(url, headers=headers)
    if err:
        return err
    try:
        data = json.loads(raw.decode())
    except (json.JSONDecodeError, ValueError):
        return {"error": True, "message": "ESPN core API returned invalid JSON"}

    result = {
        "categories": _resolve_leaders(data.get("categories", [])),
        "season": data.get("season", {}).get("year", season or ""),
    }
    _cache_set(cache_key, result, ttl=300)
    return result


def get_news(request_data):
    """Get NHL news articles."""
    params = request_data.get("params", {})
    team_id = params.get("team_id")

    resource = f"teams/{team_id}/news" if team_id else "news"
    data = espn_request(SPORT_PATH, resource)
    if data.get("error"):
        return data

    articles = _normalize_news(data)
    return {"articles": articles, "count": len(articles)}


def get_schedule(request_data):
    """Get NHL schedule for a date."""
    params = request_data.get("params", {})
    date = params.get("date")
    season = params.get("season")

    espn_params = {}
    if date:
        espn_params["dates"] = date.replace("-", "")
    elif season:
        espn_params["season"] = str(season)

    data = espn_request(SPORT_PATH, "scoreboard", espn_params or None)
    if data.get("error"):
        return data

    events = [_normalize_event(e) for e in data.get("events", [])]
    day_info = data.get("day", {})

    return {
        "events": events,
        "day": day_info.get("date", ""),
        "count": len(events),
    }


# ============================================================
# Play-by-Play
# ============================================================


def _normalize_plays(summary_data):
    """Normalize play-by-play data from ESPN summary."""
    plays_raw = summary_data.get("plays", [])
    if not plays_raw:
        return {"error": True, "message": "No play-by-play data available"}

    plays = []
    for p in plays_raw:
        play_type = p.get("type", {})
        team = p.get("team", {})
        plays.append({
            "id": str(p.get("id", "")),
            "text": p.get("text", ""),
            "type": play_type.get("text", ""),
            "period": p.get("period", {}).get("number", ""),
            "clock": p.get("clock", {}).get("displayValue", ""),
            "home_score": p.get("homeScore", ""),
            "away_score": p.get("awayScore", ""),
            "scoring_play": p.get("scoringPlay", False),
            "score_value": p.get("scoreValue", 0),
            "team_id": str(team.get("id", "")) if team else "",
            "shooting_play": p.get("shootingPlay", False),
        })

    return {"plays": plays, "count": len(plays)}


def get_play_by_play(request_data):
    """Get full play-by-play log for an NHL game."""
    params = request_data.get("params", {})
    event_id = params.get("event_id")
    if not event_id:
        return {"error": True, "message": "event_id is required"}

    data = espn_summary(SPORT_PATH, event_id)
    if not data:
        return {"error": True, "message": f"No data found for event {event_id}"}

    return _normalize_plays(data)


# ============================================================
# Injuries, Transactions, Futures, Stats
# ============================================================


def get_injuries(request_data=None):
    """Get current NHL injury report."""
    data = espn_request(SPORT_PATH, "injuries")
    if data.get("error"):
        return data
    return normalize_injuries(data)


def get_transactions(request_data=None):
    """Get recent NHL transactions."""
    params = (request_data or {}).get("params", {})
    limit = params.get("limit", 50)
    data = espn_request(SPORT_PATH, "transactions", {"limit": limit})
    if data.get("error"):
        return data
    return normalize_transactions(data)


def get_futures(request_data=None):
    """Get NHL futures odds (e.g. Stanley Cup winner, Hart Trophy)."""
    params = (request_data or {}).get("params", {})
    limit = params.get("limit", 10)
    season_year = params.get("season_year") or _current_year()
    data = espn_core_request(SPORT_PATH, f"seasons/{season_year}/futures")
    if data.get("error"):
        return data
    result = normalize_futures(data, limit=limit)
    result["season_year"] = season_year
    return result


def get_team_stats(request_data):
    """Get NHL team season statistics."""
    params = request_data.get("params", {})
    team_id = params.get("team_id")
    if not team_id:
        return {"error": True, "message": "team_id is required"}
    season_year = params.get("season_year") or _current_year()
    season_type = params.get("season_type", 2)
    data = espn_core_request(
        SPORT_PATH,
        f"seasons/{season_year}/types/{season_type}/teams/{team_id}/statistics",
    )
    if data.get("error"):
        return data
    result = normalize_core_stats(data)
    result["team_id"] = str(team_id)
    result["season_year"] = season_year
    result["season_type"] = season_type
    return result


def get_player_stats(request_data):
    """Get NHL player season statistics."""
    params = request_data.get("params", {})
    player_id = params.get("player_id")
    if not player_id:
        return {"error": True, "message": "player_id is required"}
    season_year = params.get("season_year") or _current_year()
    season_type = params.get("season_type", 2)
    data = espn_core_request(
        SPORT_PATH,
        f"seasons/{season_year}/types/{season_type}/athletes/{player_id}/statistics",
    )
    if data.get("error"):
        return data
    result = normalize_core_stats(data)
    result["player_id"] = str(player_id)
    result["season_year"] = season_year
    result["season_type"] = season_type
    return result
