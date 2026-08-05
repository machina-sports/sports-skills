"""NFLverse-backed NFL data provider.

Prefers ``nflreadpy`` when available and falls back to ``nfl_data_py`` for
compatibility. Returns plain normalized dicts that are wrapped by
``sports_skills._response.wrap`` in the public module.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

logger = logging.getLogger("sports_skills.nfl._nflverse")


# Summary levels accepted by nflreadpy's stat loaders. "week" yields one row per
# game (and carries a `week` column); the rest are season aggregates.
_SUMMARY_LEVELS = ("week", "reg", "post", "reg+post")
_DEFAULT_SUMMARY_LEVEL = "reg"

# ESPN spells two clubs differently from nflverse. Only these two are safe to
# translate: nflverse never uses "LAR" or "WSH" in any season. Relocations
# (OAK/LV, SD/LAC, STL/LA) are deliberately absent — nflverse uses the
# era-correct abbreviation, so mapping them would corrupt historical queries.
_TEAM_ALIASES = {"LAR": "LA", "WSH": "WAS"}


def _current_season() -> int:
    now = datetime.now()
    return now.year if now.month >= 3 else now.year - 1


def _normalize_team(team: Any) -> str | None:
    """Translate an ESPN-style team abbreviation to its nflverse spelling."""
    if team is None:
        return None
    value = str(team).strip().upper()
    return _TEAM_ALIASES.get(value, value)


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


def _as_id(value: Any) -> str | None:
    """Render an upstream identifier as a plain string.

    Numeric id columns arrive as floats from some backends, so a straight str()
    would yield "401671789.0" and never match the ESPN id it is meant to join to.
    """
    value = _clean_scalar(value)
    if value is None or value == "":
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    return str(value)


def _pick(row: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            val = _clean_scalar(row[key])
            if val is not None:
                return val
    return default


class _NflverseUnavailable(Exception):
    """A requested table cannot be served by the installed backend."""


def _guard(fn):
    """Return connector errors as data instead of raising.

    These functions are called by autonomous agents, so a missing optional
    dependency or an upstream failure has to arrive as a readable message rather
    than an unhandled traceback.
    """

    @functools.wraps(fn)
    def wrapper(request_data: dict[str, Any]) -> dict[str, Any]:
        try:
            return fn(request_data)
        except _NflverseUnavailable as exc:
            return {"error": True, "message": str(exc)}
        except ImportError as exc:
            return {"error": True, "message": str(exc)}
        except Exception as exc:  # noqa: BLE001 — surface, never crash the agent
            logger.debug("nflverse call failed", exc_info=True)
            return {
                "error": True,
                "message": f"nflverse backend error ({type(exc).__name__}): {exc}",
            }

    return wrapper


def _resolve_summary_level(params: Mapping[str, Any]) -> str:
    """Pick the stat summary level, defaulting to regular-season aggregates.

    An explicit ``week`` filter only exists in the weekly table, so asking for a
    week implies weekly rows.
    """
    requested = params.get("summary_level")
    if requested is None:
        return "week" if params.get("week") is not None else _DEFAULT_SUMMARY_LEVEL
    level = str(requested).strip().lower()
    if level not in _SUMMARY_LEVELS:
        raise _NflverseUnavailable(
            f"Invalid summary_level {requested!r}. Valid values: {', '.join(_SUMMARY_LEVELS)}"
        )
    if params.get("week") is not None and level != "week":
        raise _NflverseUnavailable(
            f"summary_level={level!r} has no week column; omit week or use summary_level='week'"
        )
    return level


def _resolve_season(params: Mapping[str, Any]) -> tuple[int, bool]:
    """Return ``(season, was_explicit)``.

    The distinction matters for the fallback below: an implied season may be
    adjusted, an explicitly requested one never is.
    """
    requested = params.get("season")
    if requested is None:
        return _current_season(), False
    return int(requested), True


def _load_with_season_fallback(loader, season: int, explicit: bool):
    """Load a season, stepping back one year when the default is too new.

    nflverse publishes the upcoming season's schedule months before the derived
    tables (rosters, stats, play-by-play) exist for it, so between March and the
    season opener ``_current_season()`` names a year those tables cannot serve.
    An implied season steps back and reports the substitution; an explicit one
    surfaces the backend's own error instead of quietly answering about a
    different year.
    """
    try:
        return loader(season), season, None
    except Exception as exc:
        if explicit:
            raise
        prior = season - 1
        try:
            frame = loader(prior)
        except Exception:
            raise exc from None
        note = (
            f"season {season} is not in this nflverse table yet; returned {prior}. "
            f"Pass season={season} explicitly to see the upstream error."
        )
        logger.debug("nflverse season %s unavailable; fell back to %s", season, prior)
        return frame, prior, note


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


def _load_player_stats(provider_name: str, provider: Any, season: int, summary_level: str):
    if provider_name == "nflreadpy":
        try:
            return _coerce_frame(
                provider.load_player_stats([season], summary_level=summary_level)
            )
        except TypeError:
            # Older/newer nflreadpy without the keyword — falls back to its
            # default (weekly) rows rather than failing the call.
            return _coerce_frame(provider.load_player_stats([season]))
    if summary_level == "week":
        return _coerce_frame(provider.import_weekly_data([season]))
    df = _coerce_frame(provider.import_seasonal_data([season]))
    # import_seasonal_data only has player_id — enrich with roster data
    try:
        roster = _coerce_frame(provider.import_seasonal_rosters([season]))
        roster_cols = roster[["player_id", "player_name", "position", "team"]].drop_duplicates(subset=["player_id"])
        df = df.merge(roster_cols, on="player_id", how="left")
    except Exception:
        pass
    return df


def _load_team_stats(provider_name: str, provider: Any, season: int, summary_level: str):
    if provider_name == "nflreadpy":
        try:
            return _coerce_frame(
                provider.load_team_stats([season], summary_level=summary_level)
            )
        except TypeError:
            return _coerce_frame(provider.load_team_stats([season]))
    # nfl_data_py exposes no team-stat table. It previously returned the schedule
    # here, which normalized into rows of game metadata labelled as team stats.
    raise _NflverseUnavailable(
        "Team stats require the nflreadpy backend, which needs Python 3.10+. "
        "The installed nfl_data_py backend does not provide a team-stat table."
    )


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
        # `total` is the combined points actually scored; `total_line` is the
        # betting over/under. Keeping both prevents the result total being
        # mistaken for the market number.
        "total": _pick(row, "total"),
        "total_line": _pick(row, "total_line"),
        "spread_line": _pick(row, "spread_line", "spread"),
        "home_moneyline": _pick(row, "home_moneyline"),
        "away_moneyline": _pick(row, "away_moneyline"),
        # Cross-provider identifiers. `espn_event_id` is the ESPN event ID, which
        # is what joins these rows to the ESPN-backed functions in this module.
        "espn_event_id": _as_id(_pick(row, "espn")),
        "pfr_game_id": _pick(row, "pfr"),
        "gsis_game_id": _as_id(_pick(row, "gsis")),
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


def _filter_team(df, team: str | None, *columns: str):
    """Filter to a team across whichever of ``columns`` the frame actually has.

    Returns ``(frame, matched_column)``; ``matched_column`` is None when the
    frame exposes none of them, so callers can tell "filter did not apply" apart
    from "filter matched nothing".
    """
    if team is None:
        return df, None
    for col in columns:
        if col in df.columns:
            return df[df[col].astype(str).str.upper() == team], col
    return df, None


def _team_warnings(team: str | None, raw_team: Any, matched_column: str | None, count: int):
    """Explain an empty team filter rather than returning a bare empty list."""
    if team is None or count:
        return []
    if matched_column is None:
        return [f"team filter {raw_team!r} was not applied — no team column in this table"]
    note = f"team {team!r} matched no rows"
    if str(raw_team).strip().upper() != team:
        note += f" (normalized from {str(raw_team).strip().upper()!r})"
    return [note]


@_guard
def get_nflverse_schedule(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    season, explicit = _resolve_season(params)
    week = int(params["week"]) if params.get("week") is not None else None

    provider_name, provider = _load_provider()
    df, season, note = _load_with_season_fallback(
        lambda yr: _load_schedules(provider_name, provider, yr), season, explicit
    )
    if week is not None and "week" in df.columns:
        df = df[df["week"] == week]

    events = [_normalize_schedule_row(row) for row in _records(df)]
    result = {
        "provider": "nflverse",
        "provider_impl": provider_name,
        "season": season,
        "week": week,
        "events": events,
        "count": len(events),
    }
    if note:
        result["warnings"] = [note]
    return result


@_guard
def get_nflverse_weekly_rosters(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    season, explicit = _resolve_season(params)
    week = int(params["week"]) if params.get("week") is not None else None
    raw_team = params.get("team")
    team = _normalize_team(raw_team)

    provider_name, provider = _load_provider()
    df, season, note = _load_with_season_fallback(
        lambda yr: _load_weekly_rosters(provider_name, provider, yr), season, explicit
    )

    if week is not None and "week" in df.columns:
        df = df[df["week"] == week]
    df, matched = _filter_team(df, team, "team", "recent_team", "team_abbr")

    rosters = [_normalize_roster_row(row) for row in _records(df)]
    result = {
        "provider": "nflverse",
        "provider_impl": provider_name,
        "season": season,
        "week": week,
        "team": team,
        "players": rosters,
        "count": len(rosters),
    }
    warnings = ([note] if note else []) + _team_warnings(team, raw_team, matched, len(rosters))
    if warnings:
        result["warnings"] = warnings
    return result


@_guard
def get_nflverse_player_stats(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    season, explicit = _resolve_season(params)
    player_id = params.get("player_id")
    raw_team = params.get("team")
    team = _normalize_team(raw_team)
    position = params.get("position")
    week = int(params["week"]) if params.get("week") is not None else None
    summary_level = _resolve_summary_level(params)

    provider_name, provider = _load_provider()
    df, season, note = _load_with_season_fallback(
        lambda yr: _load_player_stats(provider_name, provider, yr, summary_level),
        season,
        explicit,
    )

    if week is not None and "week" in df.columns:
        df = df[df["week"] == week]
    if player_id is not None:
        for col in ("player_id", "gsis_id"):
            if col in df.columns:
                df = df[df[col].astype(str) == str(player_id)]
                break
    df, matched = _filter_team(df, team, "recent_team", "team", "team_abbr")
    if position is not None and "position" in df.columns:
        df = df[df["position"].astype(str).str.upper() == str(position).upper()]

    stats = [_normalize_player_stats_row(row) for row in _records(df)]
    result = {
        "provider": "nflverse",
        "provider_impl": provider_name,
        "season": season,
        "summary_level": summary_level,
        "week": week,
        "player_id": player_id,
        "team": team,
        "position": position,
        "players": stats,
        "count": len(stats),
    }
    warnings = ([note] if note else []) + _team_warnings(team, raw_team, matched, len(stats))
    if warnings:
        result["warnings"] = warnings
    return result


@_guard
def get_nflverse_team_stats(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    season, explicit = _resolve_season(params)
    raw_team = params.get("team")
    team = _normalize_team(raw_team)
    week = int(params["week"]) if params.get("week") is not None else None
    summary_level = _resolve_summary_level(params)

    provider_name, provider = _load_provider()
    df, season, note = _load_with_season_fallback(
        lambda yr: _load_team_stats(provider_name, provider, yr, summary_level),
        season,
        explicit,
    )

    df, matched = _filter_team(df, team, "team", "team_abbr", "recent_team")
    if week is not None and "week" in df.columns:
        df = df[df["week"] == week]

    teams = [_normalize_team_stats_row(row) for row in _records(df)]
    result = {
        "provider": "nflverse",
        "provider_impl": provider_name,
        "season": season,
        "summary_level": summary_level,
        "team": team,
        "week": week,
        "teams": teams,
        "count": len(teams),
    }
    warnings = ([note] if note else []) + _team_warnings(team, raw_team, matched, len(teams))
    if warnings:
        result["warnings"] = warnings
    return result


@_guard
def get_nflverse_play_by_play(request_data: dict[str, Any]) -> dict[str, Any]:
    params = request_data.get("params", {})
    season, explicit = _resolve_season(params)
    week = int(params["week"]) if params.get("week") is not None else None
    raw_team = params.get("team")
    team = _normalize_team(raw_team)
    game_id = params.get("game_id")
    limit = params.get("limit")

    provider_name, provider = _load_provider()
    df, season, note = _load_with_season_fallback(
        lambda yr: _load_pbp(provider_name, provider, yr), season, explicit
    )

    if week is not None and "week" in df.columns:
        df = df[df["week"] == week]
    matched = None
    if team is not None:
        mask = None
        for col in ("posteam", "home_team", "away_team", "defteam"):
            if col in df.columns:
                col_mask = df[col].astype(str).str.upper() == team
                mask = col_mask if mask is None else (mask | col_mask)
                matched = col
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
    result = {
        "provider": "nflverse",
        "provider_impl": provider_name,
        "season": season,
        "week": week,
        "team": team,
        "game_id": game_id,
        "plays": plays,
        "count": len(plays),
    }
    # `limit` truncates silently otherwise — say so rather than implying the game
    # only had this many plays.
    if note:
        result["warnings"] = [note]
    if limit is not None and len(plays) >= int(limit):
        result["truncated"] = True
        result.setdefault("warnings", []).append(f"results truncated to limit={int(limit)}")
    warnings = _team_warnings(team, raw_team, matched, len(plays))
    if warnings:
        result.setdefault("warnings", []).extend(warnings)
    return result
