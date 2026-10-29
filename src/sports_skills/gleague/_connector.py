"""NBA G League data connector — ESPN public API (``basketball/nba-development``).

G League team ids overlap NBA team ids (id 2 is the Austin Spurs here and the
Boston Celtics in the NBA), so nothing in this module falls back to ESPN's NBA
path, the NBA live CDN, or stats.nba.com. The NBA response shapes are shared,
so the pure NBA normalizers are reused and only the G League differences are
handled here.
"""

import datetime
import re

from sports_skills._espn_base import (
    default_standings_season,
    epoch_seconds,
    espn_request,
    espn_summary,
    espn_team_schedule,
    espn_web_request,
    event_season_type,
    standings_fields,
)
from sports_skills.nba._connector import _normalize_event as _nba_normalize_event
from sports_skills.nba._connector import _normalize_game_summary as _nba_normalize_game_summary
from sports_skills.nba._connector import (
    _normalize_news,
    _normalize_plays,
    _normalize_roster,
    _normalize_standings_entries,
    _normalize_team,
)

SPORT_PATH = "basketball/nba-development"

#: ``season_type`` values accepted by get_team_schedule -> ESPN ``seasontype`` code.
#: ESPN type 5 is the G League Tip-Off Tournament (Winter Showcase), not the NBA play-in.
_SCHEDULE_TYPES = {
    "regular": "2",
    "2": "2",
    "postseason": "3",
    "playoffs": "3",
    "3": "3",
    "tournament": "5",
    "showcase": "5",
    "5": "5",
    "all": "all",
}

_NEWS_CAVEAT = (
    "ESPN's G League news feed also carries stories tagged to other leagues (NBA, NBL, college); "
    "check an article's subject before attributing it to the G League."
)


def _id_error(name, value):
    """Error dict for a missing or malformed ESPN id, or None when it is ASCII digits.

    Ids are interpolated into URL paths and queries, so anything else ("../nba", "2?x", True)
    is refused rather than repaired.
    """
    if value is None or value == "":
        return {"error": True, "message": f"{name} is required"}
    text = str(value) if isinstance(value, (str, int)) and not isinstance(value, bool) else ""
    if not (text.isascii() and text.isdigit()):
        return {"error": True, "message": f"{name} must be a numeric ESPN G League id, got {value!r}"}
    return None


def _date_error(date):
    """Error dict for a ``date`` that is not a real YYYY-MM-DD date, or None (also when omitted)."""
    if date is None or date == "":
        return None
    if isinstance(date, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        try:
            datetime.date.fromisoformat(date)
            return None
        except ValueError:
            pass
    return {"error": True, "message": f"date must be a real date in YYYY-MM-DD format, got {date!r}"}


def _summary(event_id):
    """``(summary, None)`` for an identifiable game, else ``(None, error dict)``.

    ``espn_summary`` stamps a retrieval time on every payload, so an ESPN error body
    (``{"error": ...}``) or ``{}`` is truthy; require a header naming this event and a
    non-empty competition before anything is normalized.
    """
    error = _id_error("event_id", event_id)
    if error:
        return None, error
    data = espn_summary(SPORT_PATH, event_id) or {}
    header = data.get("header")
    competitions = header.get("competitions") if isinstance(header, dict) else None
    comp = competitions[0] if isinstance(competitions, list) and competitions else None
    status = comp.get("status") if isinstance(comp, dict) else None
    status_type = status.get("type") if isinstance(status, dict) else None
    competitors = comp.get("competitors") if isinstance(comp, dict) else None
    if (
        data.get("error")
        or not isinstance(header, dict)
        or str(header.get("id", "")) != str(event_id)
        or not isinstance(comp, dict)
        or str(comp.get("id", event_id)) != str(event_id)
        or not isinstance(status_type, dict)
        or not status_type.get("name")
        or not isinstance(competitors, list)
        or len(competitors) != 2
        or any(
            not isinstance(c, dict) or not isinstance(c.get("team"), dict) or not c["team"].get("id")
            for c in competitors
        )
    ):
        return None, {"error": True, "message": f"No summary data found for event {event_id}"}
    return data, None


def _phase(label):
    """The shared helpers name ESPN type 5 for the NBA ("playin"); for the G League it is the tournament."""
    return "tournament" if label == "playin" else label


def _normalize_event(espn_event):
    row = _nba_normalize_event(espn_event)
    row["season_type"] = _phase(row["season_type"])
    return row


def _standings_entries(table):
    """NBA standings rows, plus the G League's "Last Ten Games" stat (the NBA calls it L10)."""
    entries = _normalize_standings_entries(table)
    for row, raw in zip(entries, table.get("entries", [])):
        if not row["last_ten"]:
            stats = {s.get("name"): s.get("displayValue", "") for s in raw.get("stats", []) if isinstance(s, dict)}
            row["last_ten"] = stats.get("Last Ten Games", "")
    return entries


def _normalize_standings(espn_data):
    """Every standings table: league-wide (root), per conference, and per group inside a conference."""
    groups = []

    def add(table, conference, division):
        entries = _standings_entries(table) if isinstance(table, dict) else []
        for entry in entries:
            entry["division"] = division
        if entries:
            groups.append({"conference": conference, "division": division, "entries": entries})

    add(espn_data.get("standings"), espn_data.get("name", ""), "")
    for conference in espn_data.get("children") or []:
        if not isinstance(conference, dict):
            continue
        name = conference.get("name", conference.get("abbreviation", ""))
        add(conference.get("standings"), name, "")
        for group in conference.get("children") or []:
            if isinstance(group, dict):
                add(group.get("standings"), name, group.get("name", ""))
    return groups


def _echo_season(requested, data):
    """The season the events describe: the requested one, else ESPN's ``requestedSeason``.

    ESPN's top-level ``season`` is its *current* season (2027 on a 2026 request).
    """
    if requested not in (None, ""):
        try:
            return int(requested)
        except (TypeError, ValueError):
            return requested
    return (data.get("requestedSeason") or {}).get("year") or (data.get("season") or {}).get("year", "")


def _scoreboard(date):
    error = _date_error(date)
    if error:
        return error
    data = espn_request(SPORT_PATH, "scoreboard", {"dates": date.replace("-", "")} if date else None)
    if data.get("error"):
        return data
    events = [_normalize_event(e) for e in data.get("events", [])]
    return {"events": events, "day": (data.get("day") or {}).get("date", ""), "count": len(events)}


# ============================================================
# Command Functions
# ============================================================


def get_scoreboard(request_data):
    """Get G League scores for a date (ESPN's default game day without one)."""
    return _scoreboard(request_data.get("params", {}).get("date"))


def get_schedule(request_data):
    """Get G League games on a date."""
    params = request_data.get("params", {})
    date = params.get("date")
    season = params.get("season")
    if season and not date:
        # ESPN's scoreboard ignores ``season`` and returns the next game day.
        return {
            "error": True,
            "message": (
                f"get_schedule cannot list season {season}: ESPN's scoreboard has no season filter. "
                "Pass date=YYYY-MM-DD for one day, or use get_team_schedule(team_id, season) "
                "for a team's season."
            ),
        }
    return _scoreboard(date)


def get_standings(request_data):
    """Get G League standings."""
    params = request_data.get("params", {})
    season = params.get("season")
    data = espn_web_request(SPORT_PATH, "standings", {"season": season} if season else None)
    if data.get("error"):
        return data
    data, defaulted_from = default_standings_season(
        data, season, lambda year: espn_web_request(SPORT_PATH, "standings", {"season": year})
    )
    fields = standings_fields(data, season, defaulted_from)
    fields["season_type"] = _phase(fields["season_type"])
    return {"groups": _normalize_standings(data), **fields}


def get_teams(request_data=None):
    """Get all G League teams."""
    data = espn_request(SPORT_PATH, "teams")
    if data.get("error"):
        return data
    teams = [
        _normalize_team(wrapper)
        for sport in data.get("sports", [])
        for league in sport.get("leagues", [])
        for wrapper in league.get("teams", [])
    ]
    return {"teams": teams, "count": len(teams)}


def get_team_roster(request_data):
    """Get a G League team's current roster."""
    team_id = request_data.get("params", {}).get("team_id")
    error = _id_error("team_id", team_id)
    if error:
        return error
    data = espn_request(SPORT_PATH, f"teams/{team_id}/roster")
    if data.get("error"):
        return data
    athletes = _normalize_roster(data)
    team_info = data.get("team") or {}
    return {
        "team": {
            "id": str(team_info.get("id", team_id)),
            "name": team_info.get("displayName", ""),
            "abbreviation": team_info.get("abbreviation", ""),
        },
        "season": (data.get("season") or {}).get("year", ""),
        "athletes": athletes,
        "count": len(athletes),
    }


def get_team_schedule(request_data):
    """Get a G League team's schedule."""
    params = request_data.get("params", {})
    team_id = params.get("team_id")
    season = params.get("season")
    season_type = params.get("season_type")
    error = _id_error("team_id", team_id)
    if error:
        return error
    code = None
    if season_type not in (None, ""):
        code = _SCHEDULE_TYPES.get(str(season_type).strip().lower())
        if code is None:
            return {
                "error": True,
                "message": (
                    f"Unknown season_type '{season_type}' for the G League. Use one of: regular, "
                    "postseason (alias playoffs), tournament (alias showcase; the Tip-Off Tournament, "
                    "ESPN type 5), all, or ESPN codes 2, 3, 5."
                ),
            }
    data = espn_team_schedule(SPORT_PATH, team_id, season, code, all_types=("5", "2", "3"))
    if data.get("error"):
        return data
    events = [_normalize_event(e) for e in data.get("events", [])]
    team_info = data.get("team") or {}
    return {
        "team": {
            "id": str(team_info.get("id", team_id)),
            "name": team_info.get("displayName", ""),
            "abbreviation": team_info.get("abbreviation", ""),
        },
        "events": events,
        "season": _echo_season(season, data),
        "count": len(events),
    }


def get_game_summary(request_data):
    """Get a G League game summary with box score and scoring plays."""
    data, error = _summary(request_data.get("params", {}).get("event_id"))
    if error:
        return error
    result = _nba_normalize_game_summary(data)
    game_info = result["game_info"]
    game_info["start_ts"] = epoch_seconds(game_info.get("start_time"))
    game_info["season_type"] = _phase(event_season_type(data.get("header") or {}))
    return result


def get_play_by_play(request_data):
    """Get a G League game's play-by-play."""
    data, error = _summary(request_data.get("params", {}).get("event_id"))
    if error:
        return error
    if not data.get("plays"):
        return {"plays": [], "count": 0}
    return _normalize_plays(data)


def get_news(request_data):
    """Get G League news articles."""
    limit = request_data.get("params", {}).get("limit")
    if limit is not None:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            return {"error": True, "message": f"limit must be a positive integer, got {limit!r}"}
        if limit < 1:
            return {"error": True, "message": f"limit must be a positive integer, got {limit}"}
    data = espn_request(SPORT_PATH, "news")
    if data.get("error"):
        return data
    articles = _normalize_news(data)[:limit]
    return {"articles": articles, "count": len(articles), "caveats": [_NEWS_CAVEAT]}
