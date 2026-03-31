"""CLI entry point for sports-skills.

Usage:
    sports-skills <module> <command> [--param=value ...]

Examples:
    sports-skills football get_season_standings --season_id=premier-league-2025
    sports-skills polymarket get_sports_markets --limit=20
    sports-skills kalshi get_markets --series_ticker=KXNBA
    sports-skills news fetch_items --query="Arsenal" --limit=5
    sports-skills f1 get_race_schedule --year=2025
    sports-skills nfl get_scoreboard
    sports-skills nfl get_standings --season=2025
    sports-skills golf get_leaderboard --tour=pga
"""

import argparse
import json
import sys

# Registry of modules → commands → functions (lazy-loaded)
_REGISTRY = {
    "football": {
        "get_current_season": {"required": ["competition_id"]},
        "get_competitions": {},
        "get_competition_seasons": {"required": ["competition_id"]},
        "get_season_schedule": {"required": ["season_id"]},
        "get_season_standings": {"required": ["season_id"]},
        "get_season_leaders": {"required": ["season_id"]},
        "get_season_teams": {"required": ["season_id"]},
        "search_player": {"required": ["query"]},
        "search_team": {"required": ["query"], "optional": ["competition_id"]},
        "get_team_profile": {"required": ["team_id"], "optional": ["league_slug"]},
        "get_daily_schedule": {"optional": ["date"]},
        "get_event_summary": {"required": ["event_id"]},
        "get_event_lineups": {"required": ["event_id"]},
        "get_event_statistics": {"required": ["event_id"]},
        "get_event_timeline": {"required": ["event_id"]},
        "get_team_schedule": {
            "required": ["team_id"],
            "optional": ["league_slug", "season_year", "competition_id"],
        },
        "get_head_to_head": {"required": ["team_id", "team_id_2"]},
        "get_event_xg": {"required": ["event_id"]},
        "get_event_players_statistics": {"required": ["event_id"]},
        "get_missing_players": {"required": ["season_id"]},
        "get_season_transfers": {
            "required": ["season_id"],
            "optional": ["tm_player_ids"],
        },
        "get_player_profile": {"optional": ["player_id", "fpl_id", "tm_player_id"]},
        "get_player_season_stats": {"required": ["player_id"], "optional": ["league_slug"]},
    },
    "polymarket": {
        "get_sports_markets": {
            "optional": [
                "limit",
                "offset",
                "sports_market_types",
                "game_id",
                "active",
                "closed",
                "order",
                "ascending",
            ]
        },
        "get_sports_events": {
            "optional": [
                "limit",
                "offset",
                "active",
                "closed",
                "order",
                "ascending",
                "series_id",
            ]
        },
        "get_series": {"optional": ["limit", "offset"]},
        "get_market_details": {"optional": ["market_id", "slug"]},
        "get_event_details": {"optional": ["event_id", "slug"]},
        "get_market_prices": {"optional": ["token_id", "token_ids"]},
        "get_order_book": {"required": ["token_id"]},
        "get_sports_market_types": {},
        "get_sports_config": {},
        "get_todays_events": {
            "required": ["sport"],
            "optional": ["limit"],
        },
        "search_markets": {
            "optional": ["query", "sport", "sports_market_types", "tag_id", "limit"]
        },
        "get_price_history": {
            "required": ["token_id"],
            "optional": ["interval", "fidelity"],
        },
        "get_last_trade_price": {"required": ["token_id"]},
        # Wallet configuration
        "configure": {"optional": ["private_key", "signature_type"]},
        # Trading (authenticated — requires wallet)
        "create_order": {
            "required": ["token_id", "side", "price", "size"],
            "optional": ["order_type"],
        },
        "market_order": {"required": ["token_id", "side", "amount"]},
        "cancel_order": {"required": ["order_id"]},
        "cancel_all_orders": {},
        "get_orders": {"optional": ["market"]},
        "get_user_trades": {},
    },
    "kalshi": {
        "get_exchange_status": {},
        "get_exchange_schedule": {},
        "get_series_list": {"optional": ["category", "tags"]},
        "get_series": {"required": ["series_ticker"]},
        "get_events": {
            "optional": [
                "limit",
                "cursor",
                "status",
                "series_ticker",
                "with_nested_markets",
            ]
        },
        "get_event": {
            "required": ["event_ticker"],
            "optional": ["with_nested_markets"],
        },
        "get_markets": {
            "optional": [
                "limit",
                "cursor",
                "event_ticker",
                "series_ticker",
                "status",
                "tickers",
            ]
        },
        "get_market": {"required": ["ticker"]},
        "get_trades": {"optional": ["limit", "cursor", "ticker", "min_ts", "max_ts"]},
        "get_market_candlesticks": {
            "required": [
                "series_ticker",
                "ticker",
                "start_ts",
                "end_ts",
                "period_interval",
            ]
        },
        "get_sports_filters": {},
        "get_sports_config": {},
        "get_todays_events": {
            "required": ["sport"],
            "optional": ["limit"],
        },
        "search_markets": {
            "optional": ["sport", "query", "status", "limit"],
        },
    },
    "betting": {
        "convert_odds": {"required": ["odds", "from_format"]},
        "devig": {"required": ["odds"], "optional": ["format"]},
        "find_edge": {"required": ["fair_prob", "market_prob"]},
        "kelly_criterion": {"required": ["fair_prob", "market_prob"]},
        "evaluate_bet": {
            "required": ["book_odds", "market_prob"],
            "optional": ["book_format", "outcome"],
        },
        "find_arbitrage": {"required": ["market_probs"], "optional": ["labels"]},
        "parlay_analysis": {
            "required": ["legs", "parlay_odds"],
            "optional": ["odds_format", "correlation"],
        },
        "line_movement": {
            "optional": [
                "open_odds",
                "close_odds",
                "open_line",
                "close_line",
                "market_type",
            ],
        },
        "matchup_probability": {"required": ["bpi_a", "bpi_b"]},
    },
    "markets": {
        "get_todays_markets": {"optional": ["sport", "date"]},
        "search_entity": {"required": ["query"], "optional": ["sport"]},
        "compare_odds": {"required": ["sport", "event_id"]},
        "get_sport_markets": {"required": ["sport"], "optional": ["status", "limit"]},
        "get_sport_schedule": {"optional": ["sport", "date"]},
        "normalize_price": {"required": ["price", "source"]},
        "evaluate_market": {
            "required": ["sport", "event_id"],
            "optional": ["token_id", "kalshi_ticker", "outcome"],
        },
    },
    "metadata": {
        "get_team_logo": {"required": ["team_name"], "optional": ["sport"]},
        "get_team_info": {"required": ["team_name"]},
        "get_player_photo": {"required": ["player_name"]},
        "search_teams": {"required": ["query"]},
        "search_players": {"required": ["query"]},
    },
    "news": {
        "fetch_feed": {
            "optional": [
                "google_news",
                "query",
                "url",
                "language",
                "country",
                "after",
                "before",
                "sort_by_date",
            ]
        },
        "fetch_items": {
            "optional": [
                "google_news",
                "query",
                "url",
                "limit",
                "language",
                "country",
                "after",
                "before",
                "sort_by_date",
            ]
        },
    },
    "f1": {
        "get_session_data": {
            "required": ["session_year", "session_name"],
            "optional": ["session_type"],
        },
        "get_driver_info": {"required": ["year"], "optional": ["driver"]},
        "get_team_info": {"required": ["year"], "optional": ["team"]},
        "get_race_schedule": {"required": ["year"]},
        "get_lap_data": {
            "required": ["year", "event"],
            "optional": ["session_type", "driver"],
        },
        "get_race_results": {"required": ["year", "event"]},
        "get_pit_stops": {"required": ["year"], "optional": ["event", "driver"]},
        "get_speed_data": {"required": ["year"], "optional": ["event", "driver"]},
        "get_championship_standings": {"required": ["year"]},
        "get_season_stats": {"required": ["year"]},
        "get_team_comparison": {
            "required": ["year", "team1", "team2"],
            "optional": ["event"],
        },
        "get_driver_comparison": {
            "required": ["year", "driver1", "driver2"],
            "optional": ["event"],
        },
        "get_tire_analysis": {"required": ["year"], "optional": ["event", "driver"]},
    },
    "nfl": {
        "get_scoreboard": {"optional": ["date", "week"]},
        "get_standings": {"optional": ["season"]},
        "get_teams": {},
        "get_team_roster": {"required": ["team_id"]},
        "get_team_schedule": {"required": ["team_id"], "optional": ["season"]},
        "get_game_summary": {"required": ["event_id"]},
        "get_play_by_play": {"required": ["event_id"]},
        "get_win_probability": {"required": ["event_id"]},
        "get_leaders": {"optional": ["season"]},
        "get_news": {"optional": ["team_id"]},
        "get_schedule": {"optional": ["season", "week"]},
        "get_injuries": {},
        "get_transactions": {"optional": ["limit"]},
        "get_futures": {"optional": ["limit", "season_year"]},
        "get_depth_chart": {"required": ["team_id"]},
        "get_team_stats": {"required": ["team_id"], "optional": ["season_year", "season_type"]},
        "get_player_stats": {"required": ["player_id"], "optional": ["season_year", "season_type"]},
    },
    "nba": {
        "get_scoreboard": {"optional": ["date"]},
        "get_standings": {"optional": ["season"]},
        "get_teams": {},
        "get_team_roster": {"required": ["team_id"]},
        "get_team_schedule": {"required": ["team_id"], "optional": ["season"]},
        "get_game_summary": {"required": ["event_id"]},
        "get_play_by_play": {"required": ["event_id"]},
        "get_win_probability": {"required": ["event_id"]},
        "get_leaders": {"optional": ["season"]},
        "get_news": {"optional": ["team_id"]},
        "get_schedule": {"optional": ["date", "season"]},
        "get_injuries": {},
        "get_transactions": {"optional": ["limit"]},
        "get_futures": {"optional": ["limit", "season_year"]},
        "get_depth_chart": {"required": ["team_id"]},
        "get_team_stats": {"required": ["team_id"], "optional": ["season_year", "season_type"]},
        "get_player_stats": {"required": ["player_id"], "optional": ["season_year", "season_type"]},
        "get_live_scoreboard": {},
        "get_live_boxscore": {"required": ["game_id"]},
        "get_live_playbyplay": {"required": ["game_id"], "optional": ["limit", "scoring_only"]},
        "get_player_live_stats": {"required": ["player_name"]},
    },
    "wnba": {
        "get_scoreboard": {"optional": ["date"]},
        "get_standings": {"optional": ["season"]},
        "get_teams": {},
        "get_team_roster": {"required": ["team_id"]},
        "get_team_schedule": {"required": ["team_id"], "optional": ["season"]},
        "get_game_summary": {"required": ["event_id"]},
        "get_play_by_play": {"required": ["event_id"]},
        "get_win_probability": {"required": ["event_id"]},
        "get_leaders": {"optional": ["season"]},
        "get_news": {"optional": ["team_id"]},
        "get_schedule": {"optional": ["date", "season"]},
        "get_injuries": {},
        "get_transactions": {"optional": ["limit"]},
        "get_futures": {"optional": ["limit", "season_year"]},
        "get_team_stats": {"required": ["team_id"], "optional": ["season_year", "season_type"]},
        "get_player_stats": {"required": ["player_id"], "optional": ["season_year", "season_type"]},
    },
    "nhl": {
        "get_scoreboard": {"optional": ["date"]},
        "get_standings": {"optional": ["season"]},
        "get_teams": {},
        "get_team_roster": {"required": ["team_id"]},
        "get_team_schedule": {"required": ["team_id"], "optional": ["season"]},
        "get_game_summary": {"required": ["event_id"]},
        "get_play_by_play": {"required": ["event_id"]},
        "get_leaders": {"optional": ["season"]},
        "get_news": {"optional": ["team_id"]},
        "get_schedule": {"optional": ["date", "season"]},
        "get_injuries": {},
        "get_transactions": {"optional": ["limit"]},
        "get_futures": {"optional": ["limit", "season_year"]},
        "get_team_stats": {"required": ["team_id"], "optional": ["season_year", "season_type"]},
        "get_player_stats": {"required": ["player_id"], "optional": ["season_year", "season_type"]},
    },
    "mlb": {
        "get_scoreboard": {"optional": ["date"]},
        "get_standings": {"optional": ["season"]},
        "get_teams": {},
        "get_team_roster": {"required": ["team_id"]},
        "get_team_schedule": {"required": ["team_id"], "optional": ["season"]},
        "get_game_summary": {"required": ["event_id"]},
        "get_play_by_play": {"required": ["event_id"]},
        "get_win_probability": {"required": ["event_id"]},
        "get_leaders": {"optional": ["season"]},
        "get_news": {"optional": ["team_id"]},
        "get_schedule": {"optional": ["date", "season"]},
        "get_injuries": {},
        "get_transactions": {"optional": ["limit"]},
        "get_depth_chart": {"required": ["team_id"]},
        "get_team_stats": {"required": ["team_id"], "optional": ["season_year", "season_type"]},
        "get_player_stats": {"required": ["player_id"], "optional": ["season_year", "season_type"]},
    },
    "tennis": {
        "get_scoreboard": {"optional": ["tour", "date"]},
        "get_calendar": {"required": ["tour"], "optional": ["year"]},
        "get_rankings": {"required": ["tour"], "optional": ["limit"]},
        "get_player_info": {"required": ["player_id"]},
        "get_news": {"required": ["tour"]},
    },
    "cfb": {
        "get_scoreboard": {"optional": ["date", "week", "group", "limit"]},
        "get_standings": {"optional": ["season", "group"]},
        "get_teams": {},
        "get_team_roster": {"required": ["team_id"]},
        "get_team_schedule": {"required": ["team_id"], "optional": ["season"]},
        "get_game_summary": {"required": ["event_id"]},
        "get_play_by_play": {"required": ["event_id"]},
        "get_rankings": {"optional": ["season", "week"]},
        "get_news": {"optional": ["team_id"]},
        "get_schedule": {"optional": ["season", "week", "group"]},
        "get_injuries": {},
        "get_futures": {"optional": ["limit", "season_year"]},
        "get_team_stats": {"required": ["team_id"], "optional": ["season_year", "season_type"]},
        "get_player_stats": {"required": ["player_id"], "optional": ["season_year", "season_type"]},
    },
    "cbb": {
        "get_scoreboard": {"optional": ["date", "group", "limit"]},
        "get_standings": {"optional": ["season", "group"]},
        "get_teams": {},
        "get_team_roster": {"required": ["team_id"]},
        "get_team_schedule": {"required": ["team_id"], "optional": ["season"]},
        "get_game_summary": {"required": ["event_id"]},
        "get_play_by_play": {"required": ["event_id"]},
        "get_win_probability": {"required": ["event_id"]},
        "get_rankings": {"optional": ["season", "week"]},
        "get_news": {"optional": ["team_id"]},
        "get_schedule": {"optional": ["date", "season", "group"]},
        "get_futures": {"optional": ["limit", "season_year"]},
        "get_team_stats": {"required": ["team_id"], "optional": ["season_year", "season_type"]},
        "get_player_stats": {"required": ["player_id"], "optional": ["season_year", "season_type"]},
        "get_power_index": {"optional": ["team_id", "limit", "page"]},
        "get_tournament_projections": {"optional": ["limit"]},
        "compare_teams": {"required": ["team_a_id", "team_b_id"]},
        "find_upset_candidates": {"optional": ["min_seed", "max_seed"]},
    },
    "golf": {
        "get_leaderboard": {"required": ["tour"]},
        "get_schedule": {"required": ["tour"], "optional": ["year"]},
        "get_player_info": {"required": ["player_id"], "optional": ["tour"]},
        "get_player_overview": {"required": ["player_id"], "optional": ["tour"]},
        "get_scorecard": {"required": ["tour", "player_id"]},
        "get_news": {"required": ["tour"]},
    },
    "volleyball": {
        "get_competitions": {},
        "get_standings": {"required": ["competition_id"]},
        "get_schedule": {"required": ["competition_id"]},
        "get_results": {"required": ["competition_id"]},
        "get_clubs": {"optional": ["competition_id", "limit"]},
        "get_club_schedule": {"required": ["club_id"]},
        "get_club_results": {"required": ["club_id"]},
        "get_poules": {"optional": ["competition_id", "regio", "limit"]},
        "get_tournaments": {"optional": ["limit"]},
        "get_news": {"optional": ["limit"]},
    },
}

# Params that should be parsed as boolean
_BOOL_PARAMS = {
    "google_news",
    "sort_by_date",
    "active",
    "closed",
    "ascending",
    "with_nested_markets",
}

# Params that should be parsed as int
_INT_PARAMS = {
    "limit",
    "offset",
    "year",
    "session_year",
    "tag_id",
    "fidelity",
    "start_ts",
    "end_ts",
    "period_interval",
    "min_ts",
    "max_ts",
    "season",
    "season_year",
    "season_type",
    "week",
    "group",
    "outcome",
    "page",
    "min_seed",
    "max_seed",
}

# Params that should be parsed as float
_FLOAT_PARAMS = {
    "odds",
    "fair_prob",
    "market_prob",
    "parlay_odds",
    "open_odds",
    "close_odds",
    "open_line",
    "close_line",
    "correlation",
    "price",
    "bpi_a",
    "bpi_b",
}

# Params that should be parsed as list (comma-separated)
_LIST_PARAMS = {"tm_player_ids", "token_ids"}


class OptionalDependencyError(ImportError):
    """Structured error for missing optional dependencies."""

    def __init__(self, message: str, *, dependency: str, extra: str, hint: str):
        super().__init__(message)
        self.dependency = dependency
        self.extra = extra
        self.hint = hint


def _cli_error(
    message,
    *,
    error_code=None,
    hint=None,
    dependency=None,
    extra=None,
):
    """Print error as JSON to stdout (for agents) and plain text to stderr (for humans), then exit."""
    payload = {"status": False, "data": None, "message": message}
    if error_code:
        payload["error_code"] = error_code
    if hint:
        payload["hint"] = hint
    if dependency:
        payload["dependency"] = dependency
    if extra:
        payload["extra"] = extra
    print(json.dumps(payload, indent=2))
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(1)


def _load_module(name):
    """Lazy-import a sports_skills module."""
    if name == "football":
        from sports_skills import football

        return football
    elif name == "polymarket":
        from sports_skills import polymarket

        return polymarket
    elif name == "kalshi":
        from sports_skills import kalshi

        return kalshi
    elif name == "betting":
        from sports_skills import betting

        return betting
    elif name == "markets":
        from sports_skills import markets

        return markets
    elif name == "metadata":
        from sports_skills import metadata

        return metadata
    elif name == "news":
        from sports_skills import news

        return news
    elif name == "f1":
        err_msg = (
            "F1 module dependencies are unavailable in this environment."
        )
        hint = "python3 -m pip install --upgrade sports-skills"
        try:
            from sports_skills import f1

            if f1 is None:
                raise OptionalDependencyError(
                    err_msg,
                    dependency="fastf1",
                    extra="f1",
                    hint=hint,
                )
            return f1
        except OptionalDependencyError:
            raise
        except ImportError as e:
            raise OptionalDependencyError(
                err_msg,
                dependency="fastf1",
                extra="f1",
                hint=hint,
            ) from e
    elif name == "nfl":
        from sports_skills import nfl

        return nfl
    elif name == "nba":
        from sports_skills import nba

        return nba
    elif name == "wnba":
        from sports_skills import wnba

        return wnba
    elif name == "nhl":
        from sports_skills import nhl

        return nhl
    elif name == "mlb":
        from sports_skills import mlb

        return mlb
    elif name == "tennis":
        from sports_skills import tennis

        return tennis
    elif name == "cfb":
        from sports_skills import cfb
        return cfb
    elif name == "cbb":
        from sports_skills import cbb
        return cbb
    elif name == "golf":
        from sports_skills import golf
        return golf
    elif name == "volleyball":
        from sports_skills import volleyball
        return volleyball
    else:
        raise ValueError(f"Unknown module '{name}'. Available: {', '.join(_REGISTRY.keys())}")


def _parse_value(key, value):
    """Convert CLI string values to appropriate Python types."""
    if key in _BOOL_PARAMS:
        if isinstance(value, bool):
            return value
        return value.lower() in ("true", "1", "yes", "")
    if key in _INT_PARAMS:
        return int(value)
    if key in _FLOAT_PARAMS:
        return float(value)
    if key in _LIST_PARAMS:
        return [v.strip() for v in value.split(",")]
    return value


def _parse_docstring_args(docstring):
    """Parse Google-style docstring Args section into a dict of {param: description}."""
    if not docstring:
        return {}
    lines = docstring.strip().split("\n")
    args = {}
    in_args = False
    current_param = None
    current_desc = []

    for line in lines:
        stripped = line.strip()
        # Detect start of Args section
        if stripped == "Args:":
            in_args = True
            continue
        if not in_args:
            continue
        # End of Args section: a new section header (word followed by colon at base indent)
        if stripped and not stripped.startswith(" ") and stripped.endswith(":") and stripped != "Args:":
            break
        # Empty line inside Args can end the section if we already have params
        if not stripped:
            if current_param:
                args[current_param] = " ".join(current_desc).strip()
                current_param = None
                current_desc = []
            continue
        # New parameter line: "param_name: description" or "param_name (type): description"
        if ":" in stripped and not stripped[0].isspace():
            # Save previous param
            if current_param:
                args[current_param] = " ".join(current_desc).strip()
            param_part, _, desc_part = stripped.partition(":")
            # Handle "param_name (type)" format
            param_name = param_part.split("(")[0].strip()
            current_param = param_name
            current_desc = [desc_part.strip()] if desc_part.strip() else []
        elif current_param:
            # Continuation line for current parameter
            current_desc.append(stripped)

    # Save last param
    if current_param:
        args[current_param] = " ".join(current_desc).strip()

    return args


def _param_type(name):
    """Return JSON Schema type string for a parameter based on known sets."""
    if name in _BOOL_PARAMS:
        return "boolean"
    if name in _INT_PARAMS:
        return "integer"
    if name in _LIST_PARAMS:
        return "array"
    return "string"


def _generate_schema(module_name):
    """Generate JSON Schema tool definitions for a module (Vercel AI SDK compatible).

    Reads the _REGISTRY for command definitions and attempts to load the
    module to extract docstrings from the actual functions.
    """
    commands = _REGISTRY[module_name]

    # Try loading the module to get function docstrings and param descriptions
    func_docs = {}
    param_docs = {}
    try:
        module = _load_module(module_name)
        for cmd_name in commands:
            func = getattr(module, cmd_name, None)
            if func and func.__doc__:
                # Use the first line of the docstring as description
                func_docs[cmd_name] = func.__doc__.strip().split("\n")[0]
                # Parse Args section for parameter descriptions
                param_docs[cmd_name] = _parse_docstring_args(func.__doc__)
    except ImportError:
        pass

    tools = []
    for cmd_name, cmd_info in commands.items():
        required = cmd_info.get("required", [])
        optional = cmd_info.get("optional", [])
        cmd_param_docs = param_docs.get(cmd_name, {})

        properties = {}
        for param in required + optional:
            ptype = _param_type(param)
            prop = {"type": ptype}
            if ptype == "array":
                prop["items"] = {"type": "string"}
            if param in cmd_param_docs:
                prop["description"] = cmd_param_docs[param]
            properties[param] = prop

        tool = {
            "name": f"{module_name}_{cmd_name}",
            "command": cmd_name,
            "description": func_docs.get(
                cmd_name, f"{cmd_name} command for {module_name}"
            ),
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }
        tools.append(tool)

    from sports_skills import __version__

    return {"sport": module_name, "version": __version__, "tools": tools}


def main():
    parser = argparse.ArgumentParser(
        prog="sports-skills",
        description="Lightweight CLI for sports data — football, F1, NFL, NBA, WNBA, NHL, MLB, tennis, CFB, CBB, golf, volleyball, prediction markets, betting analysis, metadata, and news.",
    )
    parser.add_argument(
        "module", nargs="?", help="Module name: football, f1, nfl, nba, wnba, nhl, mlb, tennis, cfb, cbb, golf, volleyball, polymarket, kalshi, betting, markets, metadata, news"
    )
    parser.add_argument(
        "command", nargs="?", help="Command name (e.g., get_season_standings)"
    )
    parser.add_argument("--version", action="store_true", help="Show version")

    # Parse known args, rest are --key=value params
    args, remaining = parser.parse_known_args()

    if args.version:
        from sports_skills import __version__

        print(f"sports-skills {__version__}")
        return

    if not args.module:
        parser.print_help()
        print("\nAvailable modules:")
        for mod_name, commands in _REGISTRY.items():
            print(f"  {mod_name}: {', '.join(commands.keys())}")
        return

    # Reserved "catalog" command: return all available modules
    if args.module == "catalog":
        from sports_skills import __version__

        catalog = {
            "version": __version__,
            "modules": list(_REGISTRY.keys()),
        }
        print(json.dumps(catalog, indent=2))
        return

    if not args.command:
        # Show commands for this module
        if args.module not in _REGISTRY:
            _cli_error(
                f"Unknown module '{args.module}'. Available: {', '.join(_REGISTRY.keys())}"
            )
        commands = _REGISTRY[args.module]
        print(f"Commands for '{args.module}':")
        for cmd_name, cmd_info in commands.items():
            required = cmd_info.get("required", [])
            optional = cmd_info.get("optional", [])
            parts = [f"--{p}=<value>" for p in required]
            parts += [f"[--{p}=<value>]" for p in optional]
            print(f"  {cmd_name} {' '.join(parts)}")
        return

    # Reserved "schema" command: generate JSON Schema tool definitions
    if args.command == "schema":
        if args.module not in _REGISTRY:
            _cli_error(
                f"Unknown module '{args.module}'. Available: {', '.join(_REGISTRY.keys())}"
            )
        schema = _generate_schema(args.module)
        print(json.dumps(schema, indent=2))
        return

    module_name = args.module
    command_name = args.command

    # Universal command aliases for cross-sport abstraction (e.g., used by sportsclaw)
    if command_name == "scores":
        if module_name == "football":
            command_name = "get_daily_schedule"
        elif "get_scoreboard" in _REGISTRY.get(module_name, {}):
            command_name = "get_scoreboard"
        elif "get_leaderboard" in _REGISTRY.get(module_name, {}):
            command_name = "get_leaderboard"

    if module_name not in _REGISTRY:
        _cli_error(
            f"Unknown module '{module_name}'. Available: {', '.join(_REGISTRY.keys())}"
        )

    if command_name not in _REGISTRY[module_name]:
        _cli_error(
            f"Unknown command '{command_name}' for module '{module_name}'. "
            f"Available: {', '.join(_REGISTRY[module_name].keys())}"
        )

    # Parse --key=value and --flag params
    kwargs = {}
    for arg in remaining:
        if arg.startswith("--"):
            arg = arg[2:]
            if "=" in arg:
                key, value = arg.split("=", 1)
                kwargs[key] = _parse_value(key, value)
            else:
                # Boolean flag (e.g., --google_news)
                kwargs[arg] = _parse_value(arg, True)

    # Check required params
    cmd_info = _REGISTRY[module_name][command_name]
    required = cmd_info.get("required", [])
    missing = [p for p in required if p not in kwargs]
    if missing:
        _cli_error(
            f"Missing required params: {', '.join('--' + p for p in missing)}. "
            f"Run 'sports-skills {module_name}' to see usage."
        )

    # Load module and call function
    try:
        module = _load_module(module_name)
    except OptionalDependencyError as e:
        _cli_error(
            str(e),
            error_code="MISSING_OPTIONAL_DEPENDENCY",
            hint=e.hint,
            dependency=e.dependency,
            extra=e.extra,
        )
    except (ImportError, ValueError) as e:
        _cli_error(str(e))
    func = getattr(module, command_name, None)
    if not func:
        _cli_error(f"Function '{command_name}' not found in module '{module_name}'")

    try:
        result = func(**kwargs)
        print(json.dumps(result, indent=2, default=str, ensure_ascii=False))
    except TypeError as e:
        _cli_error(
            f"{e}. Hint: check parameter names. Run 'sports-skills {module_name}' to see usage."
        )
    except Exception as e:
        print(json.dumps({"status": False, "data": None, "message": str(e)}, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
