"""NFLverse-backed NFL data provider.

Prefers ``nflreadpy`` when available and falls back to ``nfl_data_py`` for
compatibility. Returns plain normalized dicts that are wrapped by
``sports_skills._response.wrap`` in the public module.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any


def _current_season() -> int:
    now = datetime.now()
    return now.year if now.month >= 3 else now.year - 1


def _coerce_frame(obj: Any):
    """Return a pandas-like DataFrame from nflverse loaders."""
    if hasattr(obj, "to_pandas"):
        return obj.to_pandas()
    return obj


def _is_missing(value: Any) -> bool:
    try:
        return bool(value != value)
    except Exception:
        return False


def _clean_scalar(value: Any) -> Any:
    if value is None or _is_missing(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _normalize_value(value: Any) -> Any:
    value = _clean_scalar(value)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat") and not isinstance(value, str):
        try:
            return value.isoformat()
        except Exception:
            pass
    if isinstance(value, Mapping):
        return {str(k): _normalize_value(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize_value(v) for v in value]
    return value


def _records(df) -> list[dict]:
    if df is None:
        return []
    df = _coerce_frame(df)
    if getattr(df, "empty", False):
        return []
    return [_normalize_value(row) for row in df.to_dict(orient="records")]


def _pick(row: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            val = _clean_scalar(row[key])
            if val is not None:
                return val
    return default


def _load_provider():
    try:
        import nflreadpy as provider  # type: ignore

        return "nflreadpy", provider
    except ImportError:
        pass

    try:
        import nfl_data_py as provider  # type: ignore

        return "nfl_data_py", provider
    except ImportError as exc:
        raise ImportError(
            "NFLverse backend dependencies are unavailable. Install with: pip install sports-skills[nfl]"
        ) from exc


def _load_schedules(provider_name: str, provider: Any, season: int):
    if provider_name == "nflreadpy":
        return _coerce_frame(provider.load_schedules([season]))
    return _coerce_frame(provider.import_schedules([season]))


def _load_weekly_rosters(provider_name: str, provider: Any, season: int):
    if provider_name == "nflreadpy":
        return _coerce_frame(provider.load_rosters_weekly([season]))
    return _coerce_frame(provider.import_weekly_rosters([season]))


def _load_player_stats(provider_name: str, provider: Any, season: int):
    if provider_name == "nflreadpy":
        try:
            return _coerce_frame(provider.load_player_stats([season], stat_type="season"))
        except TypeError:
            return _coerce_frame(provider.load_player_stats([season]))
    df = _coerce_frame(provider.import_seasonal_data([season]))
    # import_seasonal_data only has player_id — enrich with roster data
    try:
        roster = _coerce_frame(provider.import_seasonal_rosters([season]))
        roster_cols = roster[["player_id", "player_name", "position", "team"]].drop_duplicates(subset=["player_id"])
        df = df.merge(roster_cols, on="player_id", how="left")
    except Exception:
        pass
    return df


def _load_team_stats(provider_name: str, provider: Any, season: int):
    if provider_name == "nflreadpy":
        try:
            return _coerce_frame(provider.load_team_stats([season], stat_type="season"))
        except TypeError:
            return _coerce_frame(provider.load_team_stats([season]))
    return _coerce_frame(provider.import_schedules([season]))


def _load_pbp(provider_name: str, provider: Any, season: int):
    if provider_name == "nflreadpy":
        return _coerce_frame(provider.load_pbp([season]))
    return _coerce_frame(provider.import_pbp_data([season], downcast=True))


def _normalize_schedule_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "game_id": str(_pick(row, "game_id", "old_game_id", "gsis_id", default="")),
        "season": _pick(row, "season"),
        "week": _pick(row, "week"),
        "game_type": _pick(row, "game_type", "season_type"),
        "gameday": _pick(row, "gameday", "game_date"),
        "gametime": _pick(row, "gametime"),
        "weekday": _pick(row, "weekday"),
        "away_team": _pick(row, "away_team", "visitor_team_abbr"),
        "home_team": _pick(row, "home_team", "home_team_abbr"),
        "away_score": _pick(row, "away_score", "vis_score"),
        "home_score": _pick(row, "home_score", "home_score_total"),
        "location": _pick(row, "location", "stadium"),
        "result": _pick(row, "result", "game_result"),
        "total": _pick(row, "total"),
        "spread_line": _pick(row, "spread_line", "spread"),
        "home_moneyline": _pick(row, "home_moneyline"),
        "away_moneyline": _pick(row, "away_moneyline"),
    }


def _normalize_roster_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "season": _pick(row, "season"),
        "week": _pick(row, "week"),
        "team": _pick(row, "team", "recent_team", "team_abbr"),
        "player_id": str(_pick(row, "gsis_id", "player_id", "player_gsis_id", default="")),
        "player_name": _pick(row, "player_name", "full_name", "display_name"),
        "position": _pick(row, "position"),
        "jersey_number": _pick(row, "jersey_number", "number"),
        "status": _pick(row, "status"),
        "height": _pick(row, "height"),
        "weight": _pick(row, "weight"),
        "birth_date": _pick(row, "birth_date"),
        "college": _pick(row, "college_name", "college"),
        "years_exp": _pick(row, "years_exp", "entry_year"),
        "headshot_url": _pick(row, "headshot", "headshot_url"),
    }


def _normalize_player_stats_row(row: Mapping[str, Any]) -> dict[str, Any]:
    base = {
        "player_id": str(_pick(row, "player_id", "gsis_id", default="")),
        "player_name": _pick(row, "player_name", "player_display_name", "full_name"),
        "position": _pick(row, "position"),
        "team": _pick(row, "recent_team", "team", "team_abbr"),
        "season": _pick(row, "season"),
        "season_type": _pick(row, "season_type", default="REG"),
    }
    stats = {}
    for key, value in row.items():
        if key in base or key in {
            "player_id",
            "gsis_id",
            "player_name",
            "player_display_name",
            "full_name",
            "position",
            "recent_team",
            "team",
            "team_abbr",
            "season",
            "season_type",
        }:
            continue
        normalized = _normalize_value(value)
        if normalized is not None:
            stats[str(key)] = normalized
    base["stats"] = stats
    return base


def _normalize_team_stats_row(row: Mapping[str, Any]) -> dict[str, Any]:
    base = {
        "team": _pick(row, "team", "team_abbr", "recent_team", "home_team"),
        "season": _pick(row, "season"),
        "season_type": _pick(row, "season_type", "game_type", default="REG"),
        "week": _pick(row, "week"),
        "game_id": _pick(row, "game_id", "old_game_id"),
    }
    skip_keys = {
        "team", "team_abbr", "recent_team", "home_team", "season",
        "season_type", "game_type", "week", "game_id", "old_game_id",
    }
    stats = {}
    for key, value in row.items():
        if key in base or key in skip_keys:
            continue
        normalized = _normalize_value(value)
        if normalized is not None:
            stats[str(key)] = normalized
    base["stats"] = stats
    return base


def _normalize_pbp_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "play_id": str(_pick(row, "play_id", default="")),
        "game_id": str(_pick(row, "game_id", "old_game_id", default="")),
        "season": _pick(row, "season"),
        "week": _pick(row, "week"),
        "quarter": _pick(row, "qtr", "quarter"),
        "clock": _pick(row, "time", "game_seconds_remaining"),
        "posteam": _pick(row, "posteam"),
        "defteam": _pick(row, "defteam"),
        "yardline_100": _pick(row, "yardline_100"),
        "down": _pick(row, "down"),
        "ydstogo": _pick(row, "ydstogo"),
        "play_type": _pick(row, "play_type", "play_type_nfl"),
        "desc": _pick(row, "desc"),
        "yards_gained": _pick(row, "yards_gained"),
        "epa": _pick(row, "epa"),
        "wp": _pick(row, "wp"),
        "wpa": _pick(row, "wpa"),
        "home_team": _pick(row, "home_team"),
        "away_team": _pick(row, "away_team"),
        "total_home_score": _pick(row, "total_home_score", "home_score"),
        "total_away_score": _pick(row, "total_away_score", "away_score"),
    }


def get_nflverse_schedule(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    season = int(params.get("season") or _current_season())
    week = int(params["week"]) if params.get("week") is not None else None

    provider_name, provider = _load_provider()
    df = _load_schedules(provider_name, provider, season)
    if week is not None and "week" in df.columns:
        df = df[df["week"] == week]

    events = [_normalize_schedule_row(row) for row in _records(df)]
    return {
        "provider": "nflverse",
        "provider_impl": provider_name,
        "season": season,
        "week": week,
        "events": events,
        "count": len(events),
    }


def get_nflverse_weekly_rosters(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    season = int(params.get("season") or _current_season())
    week = int(params["week"]) if params.get("week") is not None else None
    team = params.get("team")

    provider_name, provider = _load_provider()
    df = _load_weekly_rosters(provider_name, provider, season)

    if week is not None and "week" in df.columns:
        df = df[df["week"] == week]
    if team is not None:
        team_upper = str(team).upper()
        for col in ("team", "recent_team", "team_abbr"):
            if col in df.columns:
                df = df[df[col].astype(str).str.upper() == team_upper]
                break

    rosters = [_normalize_roster_row(row) for row in _records(df)]
    return {
        "provider": "nflverse",
        "provider_impl": provider_name,
        "season": season,
        "week": week,
        "team": team,
        "players": rosters,
        "count": len(rosters),
    }


def get_nflverse_player_stats(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    season = int(params.get("season") or _current_season())
    player_id = params.get("player_id")
    team = params.get("team")
    position = params.get("position")

    provider_name, provider = _load_provider()
    df = _load_player_stats(provider_name, provider, season)

    if player_id is not None:
        for col in ("player_id", "gsis_id"):
            if col in df.columns:
                df = df[df[col].astype(str) == str(player_id)]
                break
    if team is not None:
        team_upper = str(team).upper()
        for col in ("recent_team", "team", "team_abbr"):
            if col in df.columns:
                df = df[df[col].astype(str).str.upper() == team_upper]
                break
    if position is not None and "position" in df.columns:
        df = df[df["position"].astype(str).str.upper() == str(position).upper()]

    stats = [_normalize_player_stats_row(row) for row in _records(df)]
    return {
        "provider": "nflverse",
        "provider_impl": provider_name,
        "season": season,
        "player_id": player_id,
        "team": team,
        "position": position,
        "players": stats,
        "count": len(stats),
    }


def get_nflverse_team_stats(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    season = int(params.get("season") or _current_season())
    team = params.get("team")
    week = int(params["week"]) if params.get("week") is not None else None

    provider_name, provider = _load_provider()
    df = _load_team_stats(provider_name, provider, season)

    if team is not None:
        team_upper = str(team).upper()
        matched = False
        for col in ("team", "team_abbr", "recent_team"):
            if col in df.columns:
                df = df[df[col].astype(str).str.upper() == team_upper]
                matched = True
                break
        if not matched:
            # schedule-based fallback: filter where team is home or away
            mask = None
            for col in ("home_team", "away_team"):
                if col in df.columns:
                    col_mask = df[col].astype(str).str.upper() == team_upper
                    mask = col_mask if mask is None else (mask | col_mask)
            if mask is not None:
                df = df[mask]
    if week is not None and "week" in df.columns:
        df = df[df["week"] == week]

    teams = [_normalize_team_stats_row(row) for row in _records(df)]
    return {
        "provider": "nflverse",
        "provider_impl": provider_name,
        "season": season,
        "team": team,
        "week": week,
        "teams": teams,
        "count": len(teams),
    }


def get_nflverse_play_by_play(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    season = int(params.get("season") or _current_season())
    week = int(params["week"]) if params.get("week") is not None else None
    team = params.get("team")
    game_id = params.get("game_id")
    limit = params.get("limit")

    provider_name, provider = _load_provider()
    df = _load_pbp(provider_name, provider, season)

    if week is not None and "week" in df.columns:
        df = df[df["week"] == week]
    if team is not None:
        team_upper = str(team).upper()
        mask = None
        for col in ("posteam", "home_team", "away_team", "defteam"):
            if col in df.columns:
                col_mask = df[col].astype(str).str.upper() == team_upper
                mask = col_mask if mask is None else (mask | col_mask)
        if mask is not None:
            df = df[mask]
    if game_id is not None:
        for col in ("game_id", "old_game_id"):
            if col in df.columns:
                df = df[df[col].astype(str) == str(game_id)]
                break
    if limit is not None:
        df = df.head(int(limit))

    plays = [_normalize_pbp_row(row) for row in _records(df)]
    return {
        "provider": "nflverse",
        "provider_impl": provider_name,
        "season": season,
        "week": week,
        "team": team,
        "game_id": game_id,
        "plays": plays,
        "count": len(plays),
    }
