"""Cricket data — live-ish scores via ESPN public API, historical ball-by-ball via Cricsheet.org.

ESPN backend (no API keys): active series, scoreboards, standings, match
summaries, news. Cricket has no single league on ESPN — discover numeric
series IDs with get_series().

Cricsheet backend (ODC-BY 1.0, attribution included in responses):
completed-match ball-by-ball data, player stats aggregation, and the
player registry with ESPNcricinfo ID mappings.
"""

from __future__ import annotations

from sports_skills._response import wrap
from sports_skills.cricket import _cricsheet, _espn


def _params(**kwargs):
    """Build params dict, filtering out None values."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


# ── ESPN backend (live-ish) ─────────────────────────────────


def get_series() -> dict:
    """List currently-active cricket series with ESPN series IDs and live events."""
    return wrap(_espn.get_series({}))


def get_scoreboard(*, series_id: str, date: str | None = None) -> dict:
    """Get scoreboard (matches + scores + status) for a series.

    Args:
        series_id: ESPN series ID (e.g. "8048" for IPL). Discover via get_series.
        date: Date in YYYYMMDD or YYYY-MM-DD format. Defaults to current window.
    """
    return wrap(_espn.get_scoreboard(_params(series_id=series_id, date=date)))


def get_standings(*, series_id: str) -> dict:
    """Get the points table for a series. Empty for most bilateral tours.

    Args:
        series_id: ESPN series ID (e.g. "8048" for IPL). Discover via get_series.
    """
    return wrap(_espn.get_standings(_params(series_id=series_id)))


def get_game_summary(*, series_id: str, event_id: str) -> dict:
    """Get match detail: rosters, leaders, matchcards, venue info.

    Args:
        series_id: ESPN series ID. Discover via get_series.
        event_id: ESPN event ID from get_scoreboard or get_series.
    """
    return wrap(_espn.get_game_summary(_params(series_id=series_id, event_id=event_id)))


def get_news(*, series_id: str) -> dict:
    """Get news articles for a series.

    Args:
        series_id: ESPN series ID (e.g. "8048" for IPL). Discover via get_series.
    """
    return wrap(_espn.get_news(_params(series_id=series_id)))


# ── Cricsheet backend (historical, ODC-BY 1.0) ──────────────


def get_competitions() -> dict:
    """List Cricsheet competition codes usable with the historical commands."""
    return wrap(_cricsheet.get_competitions({}))


def get_matches(*, competition: str, season: int | None = None) -> dict:
    """List completed matches for a competition, newest first.

    Args:
        competition: Cricsheet code (e.g. "ipl", "tests"). See get_competitions.
        season: Season start year (e.g. 2024; 2020 matches "2020/21").
    """
    return wrap(_cricsheet.get_matches(_params(competition=competition, season=season)))


def get_match_deliveries(*, competition: str, match_id: str, innings: int | None = None) -> dict:
    """Get ball-by-ball deliveries for a completed match.

    Args:
        competition: Cricsheet code (e.g. "ipl"). See get_competitions.
        match_id: Cricsheet match ID from get_matches (equals the ESPNcricinfo match ID).
        innings: Restrict to one innings (1-4).
    """
    return wrap(_cricsheet.get_match_deliveries(
        _params(competition=competition, match_id=match_id, innings=innings)
    ))


def get_player_stats(*, competition: str, player: str, season: int | None = None) -> dict:
    """Aggregate batting and bowling stats for a player across a competition.

    Args:
        competition: Cricsheet code (e.g. "ipl"). See get_competitions.
        player: Exact player name as it appears in Cricsheet (see find_player).
        season: Season start year to filter by.
    """
    return wrap(_cricsheet.get_player_stats(
        _params(competition=competition, player=player, season=season)
    ))


def find_player(*, name: str) -> dict:
    """Search the Cricsheet player registry; returns ESPNcricinfo ID mappings.

    Args:
        name: Player name substring, case-insensitive (e.g. "kohli").
    """
    return wrap(_cricsheet.find_player(_params(name=name)))
