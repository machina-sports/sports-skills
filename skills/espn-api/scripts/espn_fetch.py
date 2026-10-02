#!/usr/bin/env python3
"""ESPN API fetch helper.

Lightweight utility for querying ESPN's public APIs. No dependencies beyond
the Python standard library; uses certifi's CA bundle if it is installed.

Prints raw, provider-native ESPN JSON. Makes live requests and does not
participate in SPORTS_SKILLS_REPLAY: when that variable is set to any mode
other than "off" it refuses to run, before any network access, so it cannot
bypass an offline or replay evaluation.

Usage:
    python espn_fetch.py scoreboard basketball nba
    python espn_fetch.py scoreboard basketball nba --date 20250315
    python espn_fetch.py standings basketball nba
    python espn_fetch.py teams football nfl
    python espn_fetch.py roster basketball nba 9
    python espn_fetch.py summary basketball nba 401811026
    python espn_fetch.py athlete-stats basketball nba 3975
    python espn_fetch.py athlete-gamelog basketball nba 3975
    python espn_fetch.py injuries football nfl
    python espn_fetch.py news basketball nba
    python espn_fetch.py odds basketball nba 401811026
    python espn_fetch.py cdn-game nba 401811026
    python espn_fetch.py search "Stephen Curry" --sport basketball
"""

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

SITE_API = "https://site.api.espn.com"
CORE_API = "https://sports.core.api.espn.com"
WEB_API = "https://site.web.api.espn.com"
CDN_API = "https://cdn.espn.com"
NOW_API = "https://now.core.api.espn.com"


_CERT_HELP = (
    "Install certifi (python -m pip install --user certifi) or, on macOS with python.org Python, "
    "run 'Install Certificates.command'. Certificate verification is never disabled."
)


def _fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)


# Always a verifying context: certifi's bundle when installed, else the system store.
def _ssl_context():
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    try:
        return ssl.create_default_context(cafile=certifi.where())
    except OSError as e:
        _fail(f"Could not load certifi CA bundle: {e}. Reinstall certifi or uninstall it to use the system store.")


def _refuse_under_replay():
    mode = (os.environ.get("SPORTS_SKILLS_REPLAY") or "off").strip().lower()
    if mode != "off":
        _fail(
            f"SPORTS_SKILLS_REPLAY={mode}: this raw ESPN helper is not record/replay-backed and would "
            "reach the network. Use the supported package runtime instead "
            "(e.g. `sports-skills nba get_scoreboard`), or unset SPORTS_SKILLS_REPLAY for live raw requests."
        )


def fetch(url, params=None):
    """Fetch JSON from a URL with optional query parameters."""
    _refuse_under_replay()
    if params:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{url}?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "espn-api/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        _fail(f"HTTP {e.code}: {e.reason} — {url}")
    except urllib.error.URLError as e:
        if isinstance(e.reason, ssl.SSLCertVerificationError):
            _fail(f"TLS certificate verification failed: {e.reason} — {url}. {_CERT_HELP}")
        _fail(f"Connection error: {e.reason} — {url}")
    except json.JSONDecodeError as e:
        _fail(f"Response was not JSON ({e}) — {url}")


def cmd_scoreboard(args):
    url = f"{SITE_API}/apis/site/v2/sports/{args.sport}/{args.league}/scoreboard"
    params = {}
    if args.date:
        params["dates"] = args.date
    return fetch(url, params)


def cmd_standings(args):
    url = f"{SITE_API}/apis/v2/sports/{args.sport}/{args.league}/standings"
    params = {}
    if args.season:
        params["season"] = args.season
    return fetch(url, params)


def cmd_teams(args):
    url = f"{SITE_API}/apis/site/v2/sports/{args.sport}/{args.league}/teams"
    return fetch(url)


def cmd_roster(args):
    url = f"{SITE_API}/apis/site/v2/sports/{args.sport}/{args.league}/teams/{args.team_id}/roster"
    return fetch(url)


def cmd_summary(args):
    url = f"{SITE_API}/apis/site/v2/sports/{args.sport}/{args.league}/summary"
    return fetch(url, {"event": args.event_id})


def cmd_athlete_stats(args):
    url = f"{WEB_API}/apis/common/v3/sports/{args.sport}/{args.league}/athletes/{args.athlete_id}/stats"
    params = {}
    if args.season:
        params["season"] = args.season
    return fetch(url, params)


def cmd_athlete_gamelog(args):
    url = f"{WEB_API}/apis/common/v3/sports/{args.sport}/{args.league}/athletes/{args.athlete_id}/gamelog"
    params = {}
    if args.season:
        params["season"] = args.season
    return fetch(url, params)


def cmd_injuries(args):
    url = f"{SITE_API}/apis/site/v2/sports/{args.sport}/{args.league}/injuries"
    return fetch(url)


def cmd_news(args):
    # The Now API (now.core.api.espn.com) often returns empty feeds, so
    # we use the Site API which reliably returns articles.
    if args.sport and args.league:
        url = f"{SITE_API}/apis/site/v2/sports/{args.sport}/{args.league}/news"
    else:
        # Fallback to Now API for unfiltered global news
        url = f"{NOW_API}/v1/sports/news"
    params = {"limit": args.limit or 20}
    return fetch(url, params)


def cmd_odds(args):
    eid = args.event_id
    url = f"{CORE_API}/v2/sports/{args.sport}/leagues/{args.league}/events/{eid}/competitions/{eid}/odds"
    return fetch(url)


def cmd_cdn_game(args):
    url = f"{CDN_API}/core/{args.cdn_sport}/game"
    return fetch(url, {"xhr": 1, "gameId": args.game_id})


def cmd_search(args):
    url = f"{WEB_API}/apis/search/v2"
    params = {"query": args.query, "limit": args.limit or 10}
    if args.sport:
        params["sport"] = args.sport
    return fetch(url, params)


def main():
    parser = argparse.ArgumentParser(description="ESPN API fetch helper")
    parser.add_argument("--pretty", action="store_true", default=True, help="Pretty-print JSON output")
    sub = parser.add_subparsers(dest="command", required=True)

    # scoreboard
    p = sub.add_parser("scoreboard", help="Get scoreboard/scores")
    p.add_argument("sport")
    p.add_argument("league")
    p.add_argument("--date", help="Date in YYYYMMDD format")
    p.set_defaults(func=cmd_scoreboard)

    # standings
    p = sub.add_parser("standings", help="Get league standings")
    p.add_argument("sport")
    p.add_argument("league")
    p.add_argument("--season", help="Season year")
    p.set_defaults(func=cmd_standings)

    # teams
    p = sub.add_parser("teams", help="Get all teams")
    p.add_argument("sport")
    p.add_argument("league")
    p.set_defaults(func=cmd_teams)

    # roster
    p = sub.add_parser("roster", help="Get team roster")
    p.add_argument("sport")
    p.add_argument("league")
    p.add_argument("team_id")
    p.set_defaults(func=cmd_roster)

    # summary
    p = sub.add_parser("summary", help="Get game summary")
    p.add_argument("sport")
    p.add_argument("league")
    p.add_argument("event_id")
    p.set_defaults(func=cmd_summary)

    # athlete-stats
    p = sub.add_parser("athlete-stats", help="Get athlete season stats")
    p.add_argument("sport")
    p.add_argument("league")
    p.add_argument("athlete_id")
    p.add_argument("--season", help="Season year")
    p.set_defaults(func=cmd_athlete_stats)

    # athlete-gamelog
    p = sub.add_parser("athlete-gamelog", help="Get athlete game log")
    p.add_argument("sport")
    p.add_argument("league")
    p.add_argument("athlete_id")
    p.add_argument("--season", help="Season year")
    p.set_defaults(func=cmd_athlete_gamelog)

    # injuries
    p = sub.add_parser("injuries", help="Get league-wide injuries")
    p.add_argument("sport")
    p.add_argument("league")
    p.set_defaults(func=cmd_injuries)

    # news
    p = sub.add_parser("news", help="Get real-time news")
    p.add_argument("sport", nargs="?")
    p.add_argument("league", nargs="?")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_news)

    # odds
    p = sub.add_parser("odds", help="Get betting odds for a game")
    p.add_argument("sport")
    p.add_argument("league")
    p.add_argument("event_id")
    p.set_defaults(func=cmd_odds)

    # cdn-game
    p = sub.add_parser("cdn-game", help="Get full CDN game package")
    p.add_argument("cdn_sport", help="CDN sport slug (nba, nfl, mlb, etc.)")
    p.add_argument("game_id")
    p.set_defaults(func=cmd_cdn_game)

    # search
    p = sub.add_parser("search", help="Search ESPN")
    p.add_argument("query")
    p.add_argument("--sport")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_search)

    args = parser.parse_args()
    _refuse_under_replay()
    data = args.func(args)
    print(json.dumps(data, indent=2 if args.pretty else None))


if __name__ == "__main__":
    main()
