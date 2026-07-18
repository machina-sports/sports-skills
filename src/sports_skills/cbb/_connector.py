"""College Basketball (CBB) data connector — ESPN public API.

Provides scores, standings, rosters, schedules, game summaries,
rankings (AP/Coaches polls), and news for NCAA Division I men's basketball.
"""

from __future__ import annotations

import logging

from sports_skills._espn_base import (
    ESPN_STATUS_MAP,
    _current_year,
    espn_core_request,
    espn_fitt_request,
    espn_request,
    espn_summary,
    espn_web_request,
    normalize_boxscore,
    normalize_core_stats,
    normalize_futures,
    normalize_odds,
    normalize_scoring_plays,
)

logger = logging.getLogger("sports_skills.cbb")

SPORT_PATH = "basketball/mens-college-basketball"

# CBB has 362+ D1 teams — default ESPN limit (50) is too low.
_TEAMS_LIMIT = 500


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

        # College-specific: curatedRank (AP poll ranking, 99 = unranked)
        curated = c.get("curatedRank", {})
        rank = curated.get("current", 99)

        competitors.append({
            "team": {
                "id": str(team.get("id", "")),
                "name": team.get("displayName", ""),
                "abbreviation": team.get("abbreviation", ""),
                "logo": team.get("logo", ""),
                "conference_id": team.get("conferenceId", ""),
            },
            "home_away": c.get("homeAway", ""),
            "score": c.get("score", "0"),
            "period_scores": [int(p.get("value", 0)) for p in linescores],
            "record": records[0].get("summary", "") if records else "",
            "winner": c.get("winner", False),
            "rank": rank if rank != 99 else None,
        })

    odds = normalize_odds(comp.get("odds", []))

    broadcasts = []
    for b in comp.get("broadcasts", []):
        for name in b.get("names", []):
            broadcasts.append(name)

    # Conference competition metadata
    groups = comp.get("groups", {})

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
        "conference": groups.get("name", "") if groups else "",
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
            "wins": stats.get("wins", stats.get("overall", {}) if isinstance(stats.get("overall"), dict) else "0"),
            "losses": stats.get("losses", "0"),
            "win_pct": stats.get("winPercent", stats.get("winPct", "0")),
            "conference_record": stats.get("conferenceRecord", stats.get("vs. Conf.", "")),
            "streak": stats.get("streak", ""),
        })
    return entries


def _normalize_standings(espn_data):
    """Normalize ESPN standings with conference groups.

    Handles two ESPN response structures:
    - All conferences: children[] array with each conference
    - Single conference (group filter): root object IS the conference
    """
    groups = []

    # When filtered by group, the root object IS the conference (no children[])
    if not espn_data.get("children") and espn_data.get("standings"):
        conference_name = espn_data.get("name", espn_data.get("abbreviation", ""))
        entries = _normalize_standings_entries(espn_data["standings"])
        if entries:
            groups.append({
                "conference": conference_name,
                "division": "",
                "entries": entries,
            })
        return groups

    for child in espn_data.get("children", []):
        conference_name = child.get("name", child.get("abbreviation", ""))

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

    CBB rosters can be a flat athlete list (unlike NFL's positional groups).
    Handles both formats gracefully.
    """
    athletes = []

    athlete_list = espn_data.get("athletes", [])
    if not athlete_list:
        return athletes

    # Check if it's positional groups (list of dicts with "items" key)
    # or a flat list of athletes
    first = athlete_list[0] if athlete_list else {}
    if isinstance(first, dict) and "items" in first:
        # Positional group format
        for group in athlete_list:
            position_group = group.get("position", "")
            for item in group.get("items", []):
                athletes.append({
                    "id": str(item.get("id", "")),
                    "name": item.get("displayName", item.get("fullName", "")),
                    "jersey": item.get("jersey", ""),
                    "position": item.get("position", {}).get("abbreviation", position_group),
                    "age": item.get("age", ""),
                    "height": item.get("displayHeight", ""),
                    "weight": item.get("displayWeight", ""),
                    "experience": item.get("experience", {}).get("displayValue", ""),
                    "status": item.get("status", {}).get("type", ""),
                })
    else:
        # Flat list format (common for CBB)
        for athlete in athlete_list:
            if not isinstance(athlete, dict):
                continue
            athletes.append({
                "id": str(athlete.get("id", "")),
                "name": athlete.get("displayName", athlete.get("fullName", "")),
                "jersey": athlete.get("jersey", ""),
                "position": athlete.get("position", {}).get("abbreviation", "") if isinstance(athlete.get("position"), dict) else str(athlete.get("position", "")),
                "age": athlete.get("age", ""),
                "height": athlete.get("displayHeight", ""),
                "weight": athlete.get("displayWeight", ""),
                "experience": athlete.get("experience", {}).get("displayValue", "") if isinstance(athlete.get("experience"), dict) else str(athlete.get("experience", "")),
                "status": athlete.get("status", {}).get("type", "") if isinstance(athlete.get("status"), dict) else "",
            })
    return athletes


def _normalize_game_summary(summary_data):
    """Normalize ESPN game summary with box score and scoring plays."""
    if not summary_data:
        return {"error": True, "message": "No summary data available"}

    header = summary_data.get("header", {})
    competitions = header.get("competitions", [{}])
    comp = competitions[0] if competitions else {}

    game_info = {
        "id": header.get("id", ""),
        "status": comp.get("status", {}).get("type", {}).get("name", ""),
        "status_detail": comp.get("status", {}).get("type", {}).get("shortDetail", ""),
        "venue": {
            "name": summary_data.get("gameInfo", {}).get("venue", {}).get("fullName", ""),
            "city": summary_data.get("gameInfo", {}).get("venue", {}).get("address", {}).get("city", ""),
        },
    }

    competitors = []
    for c in comp.get("competitors", []):
        team = c.get("team", [{}])
        if isinstance(team, list):
            team = team[0] if team else {}
        rank = c.get("rank", "")
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
            "rank": rank if rank else None,
            "linescores": [ls.get("displayValue", "0") for ls in c.get("linescores", [])],
        })

    # Box score — player tables live under boxscore["players"], not ["teams"].
    box_teams = normalize_boxscore(summary_data.get("boxscore", {}))

    # Scoring plays — ESPN omits top-level scoringPlays for college basketball, so
    # the helper derives them from plays[] and backfills team identity.
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


def _normalize_rankings(espn_data):
    """Normalize ESPN rankings (AP Top 25, Coaches Poll, etc.)."""
    polls = []
    for ranking in espn_data.get("rankings", []):
        teams = []
        for entry in ranking.get("ranks", []):
            team = entry.get("team", {})
            teams.append({
                "rank": entry.get("current", ""),
                "previous_rank": entry.get("previous", ""),
                "trend": entry.get("trend", ""),
                "team": team.get("nickname", team.get("displayName", team.get("location", ""))),
                "team_id": str(team.get("id", "")),
                "abbreviation": team.get("abbreviation", ""),
                "logo": team.get("logo", ""),
                "record": entry.get("recordSummary", ""),
                "points": entry.get("points", ""),
                "first_place_votes": entry.get("firstPlaceVotes", 0),
            })
        polls.append({
            "name": ranking.get("name", ranking.get("shortName", "")),
            "short_name": ranking.get("shortName", ""),
            "type": ranking.get("type", ""),
            "teams": teams,
        })
    return polls


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
    """Get live/recent college basketball scores."""
    params = request_data.get("params", {})
    date = params.get("date")
    group = params.get("group")
    limit = params.get("limit")

    espn_params = {}
    if date:
        espn_params["dates"] = date.replace("-", "")
    if group:
        espn_params["groups"] = group
    if limit:
        espn_params["limit"] = limit

    data = espn_request(SPORT_PATH, "scoreboard", espn_params or None)
    if data.get("error"):
        return data

    events = [_normalize_event(e) for e in data.get("events", [])]
    season_info = data.get("season", {})

    return {
        "events": events,
        "season": {
            "year": season_info.get("year", ""),
            "type": season_info.get("type", ""),
        },
        "count": len(events),
    }


def get_standings(request_data):
    """Get college basketball standings by conference."""
    params = request_data.get("params", {})
    season = params.get("season")
    group = params.get("group")

    espn_params = {}
    if season:
        espn_params["season"] = season
    if group:
        espn_params["group"] = group

    data = espn_web_request(SPORT_PATH, "standings", espn_params or None)
    if data.get("error"):
        return data

    groups = _normalize_standings(data)
    return {
        "groups": groups,
        "season": data.get("season", {}).get("year", ""),
    }


def get_teams(request_data=None):
    """Get all D1 men's college basketball teams."""
    data = espn_request(SPORT_PATH, "teams", {"limit": _TEAMS_LIMIT})
    if data.get("error"):
        return data

    teams = []
    for sport in data.get("sports", []):
        for league in sport.get("leagues", []):
            for team_wrapper in league.get("teams", []):
                teams.append(_normalize_team(team_wrapper))

    return {"teams": teams, "count": len(teams)}


def get_team_roster(request_data):
    """Get roster for a college basketball team."""
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
    """Get schedule for a specific college basketball team."""
    params = request_data.get("params", {})
    team_id = params.get("team_id")
    season = params.get("season")
    if not team_id:
        return {"error": True, "message": "team_id is required"}

    espn_params = {}
    if season:
        espn_params["season"] = season

    resource = f"teams/{team_id}/schedule"
    data = espn_request(SPORT_PATH, resource, espn_params or None)
    if data.get("error"):
        return data

    events = [_normalize_event(event) for event in data.get("events", [])]

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


def get_rankings(request_data):
    """Get college basketball rankings (AP Top 25, Coaches Poll)."""
    params = request_data.get("params", {})
    season = params.get("season")
    week = params.get("week")

    espn_params = {}
    if season:
        espn_params["seasons"] = season
    if week:
        espn_params["weeks"] = week

    data = espn_request(SPORT_PATH, "rankings", espn_params or None)
    if data.get("error"):
        return data

    polls = _normalize_rankings(data)
    return {
        "polls": polls,
        "season": data.get("season", {}).get("year", ""),
        "week": data.get("week", ""),
    }


def get_news(request_data):
    """Get college basketball news articles."""
    params = request_data.get("params", {})
    team_id = params.get("team_id")

    resource = f"teams/{team_id}/news" if team_id else "news"
    data = espn_request(SPORT_PATH, resource)
    if data.get("error"):
        return data

    articles = _normalize_news(data)
    return {"articles": articles, "count": len(articles)}


def get_schedule(request_data):
    """Get college basketball schedule."""
    params = request_data.get("params", {})
    date = params.get("date")
    season = params.get("season")
    group = params.get("group")

    espn_params = {}
    if date:
        espn_params["dates"] = date.replace("-", "")
    elif season:
        espn_params["dates"] = str(season)
    if group:
        espn_params["groups"] = group

    data = espn_request(SPORT_PATH, "scoreboard", espn_params or None)
    if data.get("error"):
        return data

    events = [_normalize_event(e) for e in data.get("events", [])]
    season_info = data.get("season", {})

    return {
        "events": events,
        "season": {
            "year": season_info.get("year", ""),
            "type": season_info.get("type", ""),
        },
        "count": len(events),
    }


# ============================================================
# Play-by-Play & Win Probability
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
        play = {
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
        }
        coord = p.get("coordinate", {})
        if coord and coord.get("x") is not None:
            play["coordinate"] = {"x": coord.get("x"), "y": coord.get("y")}
        plays.append(play)

    return {"plays": plays, "count": len(plays)}


def _normalize_win_probability(summary_data):
    """Normalize win probability timeline from ESPN summary."""
    wp_raw = summary_data.get("winprobability", [])
    if not wp_raw:
        return {"error": True, "message": "No win probability data available for this game"}

    timeline = []
    for entry in wp_raw:
        timeline.append({
            "play_id": str(entry.get("playId", "")),
            "home_win_pct": round(entry.get("homeWinPercentage", 0) * 100, 1),
            "tie_pct": round(entry.get("tiePercentage", 0) * 100, 1),
        })

    return {"timeline": timeline, "count": len(timeline)}


def get_play_by_play(request_data):
    """Get full play-by-play log for a college basketball game."""
    params = request_data.get("params", {})
    event_id = params.get("event_id")
    if not event_id:
        return {"error": True, "message": "event_id is required"}

    data = espn_summary(SPORT_PATH, event_id)
    if not data:
        return {"error": True, "message": f"No data found for event {event_id}"}

    return _normalize_plays(data)


def get_win_probability(request_data):
    """Get win probability timeline for a college basketball game."""
    params = request_data.get("params", {})
    event_id = params.get("event_id")
    if not event_id:
        return {"error": True, "message": "event_id is required"}

    data = espn_summary(SPORT_PATH, event_id)
    if not data:
        return {"error": True, "message": f"No data found for event {event_id}"}

    return _normalize_win_probability(data)


# ============================================================
# Futures, Stats
# ============================================================


def get_futures(request_data=None):
    """Get college basketball futures odds (e.g. national championship)."""
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
    """Get college basketball team season statistics."""
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
    """Get college basketball player season statistics."""
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


# ============================================================
# BPI (Basketball Power Index) — ESPN FITT API
# ============================================================

# BPI field mappings: ESPN returns positional arrays, we map to named fields.
_BPI_FIELDS = [
    "bpi", "bpi_rank", "rank_change", "bpi_offense", "bpi_defense",
    "win_pct", "sos_rank", "wins", "losses", "proj_wins", "proj_losses",
    "conf_wins", "conf_losses", "proj_conf_wins", "proj_conf_losses",
]

_RESUME_FIELDS = [
    "sor_rank", "proj_seed", "scurve", "quality_wins", "quality_losses",
    "sos_past_rank", "nonconf_sos_rank",
]

_TOURNAMENT_FIELDS = [
    "seed", "actual_seed", "_region",
    "championship_pct", "champ_game_pct", "final_four_pct",
    "elite_eight_pct", "sweet_sixteen_pct", "round_of_32_pct",
]


def _normalize_bpi_team(team_entry):
    """Normalize a single team entry from the ESPN BPI response."""
    team = team_entry.get("team", {})
    result = {
        "team": {
            "id": str(team.get("id", "")),
            "name": team.get("displayName", team.get("nickname", "")),
            "abbreviation": team.get("abbreviation", ""),
            "logo": team.get("logos", [{}])[0].get("href", "") if team.get("logos") else "",
        },
    }

    # Parse BPI categories (positional arrays)
    for cat in team_entry.get("categories", []):
        cat_name = cat.get("name", "")
        values = cat.get("values", [])

        if cat_name in ("bpi", "bpiPlayoff"):
            field_map = _BPI_FIELDS
            dest_key = "bpi"
        elif cat_name == "resume":
            field_map = _RESUME_FIELDS
            dest_key = "resume"
        elif cat_name in ("tournament", "bpiTournament"):
            field_map = _TOURNAMENT_FIELDS
            dest_key = "tournament"
        else:
            continue

        parsed = {}
        for i, field_name in enumerate(field_map):
            if field_name.startswith("_"):
                continue  # Skip placeholder fields
            if i < len(values):
                val = values[i]
                # Try to convert numeric strings
                if isinstance(val, str):
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        pass
                # Convert to int where appropriate (ranks, counts, not percentages/ratings)
                if isinstance(val, float) and val == int(val) and "pct" not in field_name and field_name != "bpi":
                    val = int(val)
                parsed[field_name] = val
            else:
                parsed[field_name] = None
        result[dest_key] = parsed

    # Extract region from tournament totals (position 2 in totals array)
    for cat in team_entry.get("categories", []):
        if cat.get("name") in ("tournament", "bpiTournament"):
            totals = cat.get("totals", [])
            if isinstance(totals, list) and len(totals) > 2 and "tournament" in result:
                result["tournament"]["region"] = totals[2] if totals[2] else ""

    return result


def _fetch_bpi_for_team(team_id):
    """Fetch BPI data for a specific team by paginating through results.

    The ESPN BPI endpoint doesn't support server-side team filtering,
    so we paginate and search client-side.
    """
    team_id_str = str(team_id)
    page = 1
    while page <= 8:  # Max 8 pages of 50 = 400 teams (covers all D1)
        espn_params = {
            "region": "us",
            "lang": "en",
            "contentorigin": "espn",
            "limit": 50,
            "page": page,
        }
        data = espn_fitt_request(SPORT_PATH, "powerindex", espn_params)
        if data.get("error"):
            return None

        for entry in data.get("teams", []):
            if str(entry.get("team", {}).get("id", "")) == team_id_str:
                return _normalize_bpi_team(entry)

        pagination = data.get("pagination", {})
        if page >= pagination.get("pageCount", 1):
            break
        page += 1
    return None


def get_power_index(request_data):
    """Get BPI (Basketball Power Index) ratings for college basketball teams.

    Args:
        team_id: Optional ESPN team ID to filter to one team.
        limit: Max teams to return (default 25).
        page: Page number for pagination (default 1).
    """
    params = request_data.get("params", {})
    team_id = params.get("team_id")
    limit = params.get("limit", 25)
    page = params.get("page", 1)

    # Single-team lookup requires client-side filtering
    if team_id:
        team = _fetch_bpi_for_team(team_id)
        if not team:
            return {"error": True, "message": f"No BPI data found for team {team_id}"}
        return {"teams": [team], "count": 1}

    espn_params = {
        "region": "us",
        "lang": "en",
        "contentorigin": "espn",
        "limit": limit,
        "page": page,
    }

    data = espn_fitt_request(SPORT_PATH, "powerindex", espn_params)
    if data.get("error"):
        return data

    teams = []
    for entry in data.get("teams", []):
        teams.append(_normalize_bpi_team(entry))

    result = {"teams": teams, "count": len(teams)}

    # Include pagination info if available
    pagination = data.get("pagination", {})
    if pagination:
        result["page"] = pagination.get("page", page)
        result["page_count"] = pagination.get("pageCount", 1)
        result["total"] = pagination.get("count", len(teams))

    return result


def get_tournament_projections(request_data=None):
    """Get NCAA tournament projections with seeds, regions, and advancement probabilities.

    Args:
        limit: Max teams to return (default 68 for full tournament field).
    """
    params = (request_data or {}).get("params", {})
    limit = params.get("limit", 68)

    # Fetch enough pages to cover the tournament field
    all_teams = []
    page = 1
    page_size = min(limit, 50)
    while len(all_teams) < limit:
        espn_params = {
            "region": "us",
            "lang": "en",
            "contentorigin": "espn",
            "limit": page_size,
            "page": page,
        }
        data = espn_fitt_request(SPORT_PATH, "powerindex", espn_params)
        if data.get("error"):
            if not all_teams:
                return data
            break

        batch = data.get("teams", [])
        if not batch:
            break

        for entry in batch:
            team = _normalize_bpi_team(entry)
            # Only include teams with tournament data (projected seed)
            if team.get("tournament") or team.get("resume", {}).get("proj_seed"):
                all_teams.append(team)

        pagination = data.get("pagination", {})
        page_count = pagination.get("pageCount", 1)
        if page >= page_count:
            break
        page += 1

    # Sort by projected seed (resume.proj_seed), then by BPI rank
    def sort_key(t):
        seed = t.get("resume", {}).get("proj_seed")
        bpi_rank = t.get("bpi", {}).get("bpi_rank")
        if seed is not None:
            try:
                return (0, float(seed), float(bpi_rank or 999))
            except (ValueError, TypeError):
                pass
        return (1, 999, float(bpi_rank or 999))

    all_teams.sort(key=sort_key)
    all_teams = all_teams[:limit]

    # Group by region
    regions = {}
    for team in all_teams:
        region = team.get("tournament", {}).get("region", "Unknown")
        if region not in regions:
            regions[region] = []
        regions[region].append(team)

    return {
        "teams": all_teams,
        "regions": regions,
        "count": len(all_teams),
    }


def compare_teams(request_data):
    """Compare two college basketball teams using BPI ratings and season stats.

    Args:
        team_a_id: ESPN team ID for team A.
        team_b_id: ESPN team ID for team B.
    """
    params = request_data.get("params", {})
    team_a_id = params.get("team_a_id")
    team_b_id = params.get("team_b_id")

    if not team_a_id or not team_b_id:
        return {"error": True, "message": "team_a_id and team_b_id are required"}

    # Fetch BPI for both teams
    bpi_a = get_power_index({"params": {"team_id": team_a_id, "limit": 1}})
    bpi_b = get_power_index({"params": {"team_id": team_b_id, "limit": 1}})

    if bpi_a.get("error"):
        return {"error": True, "message": f"Failed to fetch BPI for team {team_a_id}: {bpi_a.get('message', '')}"}
    if bpi_b.get("error"):
        return {"error": True, "message": f"Failed to fetch BPI for team {team_b_id}: {bpi_b.get('message', '')}"}

    team_a = bpi_a.get("teams", [{}])[0] if bpi_a.get("teams") else {}
    team_b = bpi_b.get("teams", [{}])[0] if bpi_b.get("teams") else {}

    if not team_a:
        return {"error": True, "message": f"No BPI data found for team {team_a_id}"}
    if not team_b:
        return {"error": True, "message": f"No BPI data found for team {team_b_id}"}

    # Compute matchup probability using BPI difference
    bpi_val_a = team_a.get("bpi", {}).get("bpi", 0)
    bpi_val_b = team_b.get("bpi", {}).get("bpi", 0)

    if isinstance(bpi_val_a, (int, float)) and isinstance(bpi_val_b, (int, float)):
        bpi_diff = bpi_val_a - bpi_val_b
        # Logistic model calibrated to BPI scale
        import math
        win_prob_a = 1.0 / (1.0 + math.pow(10, -bpi_diff / 10.0))
        win_prob_b = 1.0 - win_prob_a
    else:
        bpi_diff = None
        win_prob_a = None
        win_prob_b = None

    # Fetch season stats for both teams
    stats_a = get_team_stats({"params": {"team_id": team_a_id}})
    stats_b = get_team_stats({"params": {"team_id": team_b_id}})

    comparison = {
        "team_a": team_a,
        "team_b": team_b,
        "matchup": {
            "bpi_diff": round(bpi_diff, 2) if bpi_diff is not None else None,
            "win_prob_a": round(win_prob_a, 4) if win_prob_a is not None else None,
            "win_prob_b": round(win_prob_b, 4) if win_prob_b is not None else None,
        },
    }

    if not stats_a.get("error"):
        comparison["stats_a"] = stats_a
    if not stats_b.get("error"):
        comparison["stats_b"] = stats_b

    return comparison


def find_upset_candidates(request_data=None):
    """Find potential upset candidates in the NCAA tournament based on BPI vs seed differential.

    Args:
        min_seed: Minimum seed to consider (default 10).
        max_seed: Maximum seed to consider (default 16).
    """
    params = (request_data or {}).get("params", {})
    min_seed = params.get("min_seed", 10)
    max_seed = params.get("max_seed", 16)

    # Fetch tournament projections
    projections = get_tournament_projections({"params": {"limit": 68}})
    if projections.get("error"):
        return projections

    candidates = []
    for team in projections.get("teams", []):
        resume = team.get("resume", {})
        bpi_data = team.get("bpi", {})

        proj_seed = resume.get("proj_seed")
        bpi_rank = bpi_data.get("bpi_rank")
        bpi_val = bpi_data.get("bpi")

        if proj_seed is None or bpi_rank is None:
            continue

        try:
            seed = int(proj_seed)
            rank = int(bpi_rank)
        except (ValueError, TypeError):
            continue

        if seed < min_seed or seed > max_seed:
            continue

        # Upset score: how much better the team is than their seed implies
        # A 12-seed with BPI rank 25 has a big differential (seed expects ~rank 45-48)
        # Expected rank for a seed: rough mapping where 1-seed ≈ rank 1-4, 16-seed ≈ rank 61-68
        expected_rank = seed * 4
        upset_score = expected_rank - rank

        tournament = team.get("tournament", {})

        candidates.append({
            "team": team.get("team", {}),
            "seed": seed,
            "bpi_rank": rank,
            "bpi": bpi_val,
            "expected_rank_for_seed": expected_rank,
            "upset_score": upset_score,
            "advancement": {
                "round_of_32_pct": tournament.get("round_of_32_pct"),
                "sweet_sixteen_pct": tournament.get("sweet_sixteen_pct"),
                "elite_eight_pct": tournament.get("elite_eight_pct"),
                "final_four_pct": tournament.get("final_four_pct"),
            },
            "resume": resume,
        })

    # Sort by upset score descending (higher = better upset candidate)
    candidates.sort(key=lambda c: c.get("upset_score", 0), reverse=True)

    return {
        "candidates": candidates,
        "count": len(candidates),
        "filters": {"min_seed": min_seed, "max_seed": max_seed},
    }
