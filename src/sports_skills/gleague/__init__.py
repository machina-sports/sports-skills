"""NBA G League data — scores, standings, rosters, schedules, game summaries, play-by-play, and news.

Three sources, never mixed within a command:
- ESPN public endpoints (``basketball/nba-development``): ESPN G League team and
  event ids, which overlap NBA ids and are never sent to an NBA path.
- NBA Stats (stats.nba.com) with ``LeagueID=20``: the ``find_nba_player`` and
  ``get_nbastats_*`` commands, NBA-shaped, with official G League ids.
- The G League live CDN (cdn-gleague.nba.com): ``get_live_boxscore`` and
  ``get_live_playbyplay``, NBA-shaped, with no fallback to ESPN.

No API keys required. Zero config.
"""

from __future__ import annotations

from sports_skills._response import wrap
from sports_skills.gleague._cdn import (
    get_live_boxscore as _get_live_boxscore,
)
from sports_skills.gleague._cdn import (
    get_live_playbyplay as _get_live_playbyplay,
)
from sports_skills.gleague._connector import (
    get_game_summary as _get_game_summary,
)
from sports_skills.gleague._connector import (
    get_news as _get_news,
)
from sports_skills.gleague._connector import (
    get_play_by_play as _get_play_by_play,
)
from sports_skills.gleague._connector import (
    get_schedule as _get_schedule,
)
from sports_skills.gleague._connector import (
    get_scoreboard as _get_scoreboard,
)
from sports_skills.gleague._connector import (
    get_standings as _get_standings,
)
from sports_skills.gleague._connector import (
    get_team_roster as _get_team_roster,
)
from sports_skills.gleague._connector import (
    get_team_schedule as _get_team_schedule,
)
from sports_skills.gleague._connector import (
    get_teams as _get_teams,
)
from sports_skills.gleague._stats import (
    find_nba_player as _find_nba_player,
)
from sports_skills.gleague._stats import (
    get_nbastats_advanced_boxscore as _get_nbastats_advanced_boxscore,
)
from sports_skills.gleague._stats import (
    get_nbastats_game_log as _get_nbastats_game_log,
)
from sports_skills.gleague._stats import (
    get_nbastats_leaders as _get_nbastats_leaders,
)
from sports_skills.gleague._stats import (
    get_nbastats_play_by_play as _get_nbastats_play_by_play,
)
from sports_skills.gleague._stats import (
    get_nbastats_player_career as _get_nbastats_player_career,
)
from sports_skills.gleague._stats import (
    get_nbastats_shot_chart as _get_nbastats_shot_chart,
)
from sports_skills.gleague._stats import (
    get_nbastats_team_stats as _get_nbastats_team_stats,
)


def _params(**kwargs):
    """Build params dict, filtering out None values."""
    return {"params": {k: v for k, v in kwargs.items() if v is not None}}


def get_scoreboard(*, date: str | None = None) -> dict:
    """Get G League scores for a date.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to ESPN's current game day.
    """
    return wrap(_get_scoreboard(_params(date=date)))


def get_schedule(*, date: str | None = None, season: int | None = None) -> dict:
    """Get G League games on a date.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to ESPN's current game day.
        season: Not a filter (ESPN's scoreboard has none); without a date it returns an error.
            Use get_team_schedule(team_id, season) for a season.
    """
    return wrap(_get_schedule(_params(date=date, season=season)))


def get_standings(*, season: int | None = None) -> dict:
    """Get G League standings by conference.

    Args:
        season: Season ending year (2025-26 is 2026). Defaults to the latest season with games.
    """
    return wrap(_get_standings(_params(season=season)))


def get_teams() -> dict:
    """Get all G League teams (ESPN G League ids, not NBA ids)."""
    return wrap(_get_teams(_params()))


def get_team_roster(*, team_id: str) -> dict:
    """Get a G League team's roster as ESPN currently returns it (no historical rosters here).

    Args:
        team_id: ESPN G League team ID (e.g. "2" for Austin Spurs).
    """
    return wrap(_get_team_roster(_params(team_id=team_id)))


def get_team_schedule(*, team_id: str, season: int | None = None, season_type: str | None = None) -> dict:
    """Get schedule for a specific G League team.

    Args:
        team_id: ESPN G League team ID.
        season: Season ending year (2025-26 is 2026). Defaults to the season ESPN selects.
        season_type: "regular", "postseason" (alias "playoffs"), "tournament" (alias "showcase";
            the Tip-Off Tournament, ESPN type 5), or "all" (tournament + regular + postseason).
            ESPN codes 2, 3, 5 also work. Omitted, ESPN's default rows are returned.
    """
    return wrap(_get_team_schedule(_params(team_id=team_id, season=season, season_type=season_type)))


def get_game_summary(*, event_id: str) -> dict:
    """Get detailed G League game summary with box score and scoring plays.

    Args:
        event_id: ESPN event ID.
    """
    return wrap(_get_game_summary(_params(event_id=event_id)))


def get_play_by_play(*, event_id: str) -> dict:
    """Get full play-by-play log for a G League game.

    Args:
        event_id: ESPN event ID.
    """
    return wrap(_get_play_by_play(_params(event_id=event_id)))


def get_news(*, limit: int | None = None) -> dict:
    """Get G League news articles (ESPN's feed also carries other leagues' stories).

    Args:
        limit: Max number of articles. Defaults to all ESPN returns.
    """
    return wrap(_get_news(_params(limit=limit)))


# ============================================================
# G League live CDN (cdn-gleague.nba.com)
# ============================================================


def get_live_boxscore(*, game_id: str) -> dict:
    """Get a G League box score from the official G League CDN (cdn-gleague.nba.com).

    Same shape as the NBA get_live_boxscore, plus provider "nba-cdn" and league_id "20".
    No ESPN fallback: a CDN refusal (e.g. HTTP 403/429) is returned as an error.

    Args:
        game_id: 10-digit official G League game id starting with 20 (e.g. "2052500034").
            Not an ESPN event id.
    """
    return wrap(_get_live_boxscore(_params(game_id=game_id)))


def get_live_playbyplay(*, game_id: str, limit: int = 25, scoring_only: bool = False) -> dict:
    """Get G League play-by-play from the official G League CDN, most recent plays first.

    Same shape as the NBA get_live_playbyplay, plus provider "nba-cdn" and league_id "20".
    No ESPN fallback: a CDN refusal (e.g. HTTP 403/429) is returned as an error.

    Args:
        game_id: 10-digit official G League game id starting with 20 (e.g. "2052500034").
        limit: Maximum plays to return (default 25).
        scoring_only: Only return scoring plays (default False).
    """
    return wrap(_get_live_playbyplay(_params(game_id=game_id, limit=limit, scoring_only=scoring_only)))


# ============================================================
# NBA Stats backend (stats.nba.com, LeagueID 20)
# ============================================================


def find_nba_player(*, name: str) -> dict:
    """Search the NBA Stats G League player registry (LeagueID 20) by name.

    Returns NBA.com person ids, which the get_nbastats_* functions take as
    ``player_id``. These are unrelated to ESPN athlete ids.

    Args:
        name: Full or partial player name (e.g. "McClung").
    """
    return wrap(_find_nba_player(_params(name=name)))


def get_nbastats_game_log(
    *,
    season: int | str | None = None,
    team: str | None = None,
    season_type: str | None = None,
    player_or_team: str | None = None,
    player: str | None = None,
    sort_by: str | None = None,
    descending: bool | None = None,
    limit: int | None = None,
    fields: str | None = None,
) -> dict:
    """Get the G League game log via NBA Stats (LeagueID 20).

    One row per team per game (or one player's games with player), with the
    10-digit official G League game ids ("20...") the other get_nbastats_* and
    get_live_* functions take. matchup names the opponent and home/away
    ("STO @ AUS" away, "MHU vs. CLC" home). Team abbreviations are NBA.com's G
    League tricodes; no ESPN spelling is attached.

    Args:
        season: Season starting year (2025 for 2025-26) or "2025-26". Defaults to the
            current season. ESPN-backed commands use the ending year instead.
        team: Optional G League team abbreviation filter (e.g. "STO"). NBA spellings are not translated.
        season_type: "regular" (default), "playoffs", or "preseason". Also accepts
            stats.nba.com spellings and 2/4/1, plus showcase/tournament. There is no play-in.
        player_or_team: "team" (default), or "player" for league-wide or selected-player rows.
        player: Player name or NBA.com person id (e.g. "Mac McClung" or "1630644"): that
            player's games only. Implies player_or_team="player". Omit for league-wide player rows.
        sort_by: Optional column to sort rows by, e.g. pts. Numeric-aware;
            missing values sort last.
        descending: Sort direction when sort_by is given. Defaults to true.
        limit: Optional max rows to return, applied after sort_by.
        fields: Optional comma-separated columns to keep, e.g. "game_date,matchup,wl,pts".
            Always keeps game_id, game_date, team_abbreviation, matchup (and player_id for
            player rows). Unknown names return the valid columns.
    """
    return wrap(
        _get_nbastats_game_log(
            _params(
                season=season,
                team=team,
                season_type=season_type,
                player_or_team=player_or_team,
                player=player,
                sort_by=sort_by,
                descending=descending,
                limit=limit,
                fields=fields,
            )
        )
    )


def get_nbastats_player_career(
    *,
    player_id: str | None = None,
    player: str | None = None,
    per_mode: str | None = None,
) -> dict:
    """Get a player's G League regular-season career, season by season, via NBA Stats.

    Only the G League regular-season tables are returned; college, Showcase and
    playoff tables in the same response are not.

    Args:
        player_id: NBA.com person id (e.g. "1630644"). Find it with find_nba_player.
        player: Player name to resolve instead of player_id. Must match exactly
            one G League player; ambiguous names return the candidates.
        per_mode: "totals" (default), "per_game", or "per_36".
    """
    return wrap(_get_nbastats_player_career(_params(player_id=player_id, player=player, per_mode=per_mode)))


def get_nbastats_team_stats(
    *,
    season: int | str | None = None,
    team: str | None = None,
    measure: str | None = None,
    per_mode: str | None = None,
    season_type: str | None = None,
    sort_by: str | None = None,
    descending: bool | None = None,
    limit: int | None = None,
    fields: str | None = None,
) -> dict:
    """Get league-wide G League team stats via NBA Stats (LeagueID 20).

    team_abbreviation comes from the same season's G League game log (one extra,
    cached request); a team without game-log rows has a null abbreviation.

    Args:
        season: Season starting year (2025 for 2025-26) or "2025-26". Defaults to the current season.
        team: Optional filter: G League abbreviation (e.g. "AUS"), official team name
            ("Austin Spurs"), or NBA.com team id. NBA spellings are not translated.
        measure: "base" (default), "advanced", "four_factors", "misc",
            "scoring", "opponent", or "defense".
        per_mode: "totals" (default), "per_game", or "per_36".
        season_type: "regular" (default), "playoffs", or "preseason". No play-in;
            showcase/tournament maps to the verified upstream value Showcase.
        sort_by: Optional column to sort rows by, e.g. pts. Numeric-aware;
            missing values sort last.
        descending: Sort direction when sort_by is given. Defaults to true.
        limit: Optional max rows to return, applied after sort_by.
        fields: Optional comma-separated columns to keep, e.g. "w,l,pts".
            Always keeps team_id, team_name, team_abbreviation. Unknown names return the valid columns.
    """
    return wrap(
        _get_nbastats_team_stats(
            _params(
                season=season,
                team=team,
                measure=measure,
                per_mode=per_mode,
                season_type=season_type,
                sort_by=sort_by,
                descending=descending,
                limit=limit,
                fields=fields,
            )
        )
    )


def get_nbastats_shot_chart(
    *,
    player_id: str | None = None,
    player: str | None = None,
    season: int | str | None = None,
    season_type: str | None = None,
    sort_by: str | None = None,
    descending: bool | None = None,
    limit: int | None = None,
    fields: str | None = None,
) -> dict:
    """Get a G League player's shot chart (court x/y per attempt) via NBA Stats.

    Coordinates are in tenths of feet from the basket (loc_x lateral,
    loc_y toward half court).

    Args:
        player_id: NBA.com person id. Find it with find_nba_player.
        player: Player name to resolve instead of player_id.
        season: Season starting year (2025 for 2025-26) or "2025-26". Defaults to the current season.
        season_type: "regular" (default), "playoffs", or "preseason".
        sort_by: Optional column to sort rows by, e.g. shot_distance. Numeric-aware;
            missing values sort last.
        descending: Sort direction when sort_by is given. Defaults to true.
        limit: Maximum shots to return, applied after sort_by; truncation is flagged in the response.
        fields: Optional comma-separated columns to keep, e.g. "shot_distance,made".
            Always keeps game_id, game_date, period. Unknown names return the valid columns.
    """
    return wrap(
        _get_nbastats_shot_chart(
            _params(
                player_id=player_id,
                player=player,
                season=season,
                season_type=season_type,
                sort_by=sort_by,
                descending=descending,
                limit=limit,
                fields=fields,
            )
        )
    )


def get_nbastats_play_by_play(*, game_id: str, limit: int | None = None) -> dict:
    """Get G League play-by-play with court coordinates via NBA Stats.

    Args:
        game_id: 10-digit official G League game id from get_nbastats_game_log
            (e.g. "2022500001"). Not an ESPN event id.
        limit: Maximum actions to return; truncation is flagged in the response.
    """
    return wrap(_get_nbastats_play_by_play(_params(game_id=game_id, limit=limit)))


def get_nbastats_advanced_boxscore(*, game_id: str) -> dict:
    """Get a G League advanced box score (ratings, pace, usage) via NBA Stats.

    Args:
        game_id: 10-digit official G League game id from get_nbastats_game_log
            (e.g. "2022500001"). Not an ESPN event id.
    """
    return wrap(_get_nbastats_advanced_boxscore(_params(game_id=game_id)))


def get_nbastats_leaders(
    *,
    season: int | str | None = None,
    season_type: str | None = None,
    per_mode: str | None = None,
    stat_category: str | None = None,
    sort_by: str | None = None,
    descending: bool | None = None,
    limit: int | None = None,
    fields: str | None = None,
) -> dict:
    """Get G League player leaders via NBA Stats leagueleaders (LeagueID 20).

    Rows keep the NBA Stats columns (player_id, rank, player, team, gp, pts, ...).

    Args:
        season: Season starting year (2025 for 2025-26) or "2025-26". Defaults to the current season.
        season_type: "regular" (default), "playoffs", or "preseason".
        per_mode: "per_game" (default), "totals", or "per_36".
        stat_category: Ranking stat, e.g. "PTS" (default), "REB", "AST", "STL", "BLK", "FG_PCT", "EFF".
        sort_by: Optional column to re-sort rows by. Numeric-aware; missing values sort last.
        descending: Sort direction when sort_by is given. Defaults to true.
        limit: Optional max rows to return, applied after sort_by.
        fields: Optional comma-separated columns to keep, e.g. "gp,pts".
            Always keeps player_id, rank, player, team. Unknown names return the valid columns.
    """
    return wrap(
        _get_nbastats_leaders(
            _params(
                season=season,
                season_type=season_type,
                per_mode=per_mode,
                stat_category=stat_category,
                sort_by=sort_by,
                descending=descending,
                limit=limit,
                fields=fields,
            )
        )
    )
