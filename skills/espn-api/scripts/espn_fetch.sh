#!/usr/bin/env bash
# ESPN API fetch helper (bash/curl version)
#
# Usage:
#   ./espn_fetch.sh scoreboard basketball nba
#   ./espn_fetch.sh scoreboard basketball nba 20250315
#   ./espn_fetch.sh standings basketball nba
#   ./espn_fetch.sh teams football nfl
#   ./espn_fetch.sh roster basketball nba 13
#   ./espn_fetch.sh summary basketball nba 401811026
#   ./espn_fetch.sh athlete-stats basketball nba 3136776
#   ./espn_fetch.sh athlete-gamelog basketball nba 3136776
#   ./espn_fetch.sh injuries football nfl
#   ./espn_fetch.sh news basketball nba
#   ./espn_fetch.sh odds basketball nba 401811026
#   ./espn_fetch.sh cdn-game nba 401811026
#   ./espn_fetch.sh search "Stephen Curry"
#
# Pipe to jq for pretty output: ./espn_fetch.sh scoreboard basketball nba | jq .

set -euo pipefail

SITE_API="https://site.api.espn.com"
CORE_API="https://sports.core.api.espn.com"
WEB_API="https://site.web.api.espn.com"
CDN_API="https://cdn.espn.com"
NOW_API="https://now.core.api.espn.com"

fetch() {
    curl -s -f -H "User-Agent: espn-api/1.0" -H "Accept: application/json" "$1"
}

usage() {
    echo "Usage: $0 <command> [args...]"
    echo ""
    echo "Commands:"
    echo "  scoreboard <sport> <league> [date]       Get scores (date: YYYYMMDD)"
    echo "  standings  <sport> <league> [season]      Get standings"
    echo "  teams      <sport> <league>               Get all teams"
    echo "  roster     <sport> <league> <team_id>     Get team roster"
    echo "  summary    <sport> <league> <event_id>    Get game summary"
    echo "  athlete-stats   <sport> <league> <id>     Get player stats"
    echo "  athlete-gamelog <sport> <league> <id>      Get player game log"
    echo "  injuries   <sport> <league>               Get injury report"
    echo "  news       [sport] [league]               Get news"
    echo "  odds       <sport> <league> <event_id>    Get betting odds"
    echo "  cdn-game   <cdn_sport> <game_id>          Get CDN game package"
    echo "  search     <query>                        Search ESPN"
    exit 1
}

[[ $# -lt 1 ]] && usage

CMD="$1"; shift

case "$CMD" in
    scoreboard)
        [[ $# -lt 2 ]] && { echo "Usage: $0 scoreboard <sport> <league> [date]"; exit 1; }
        SPORT="$1"; LEAGUE="$2"; DATE="${3:-}"
        URL="${SITE_API}/apis/site/v2/sports/${SPORT}/${LEAGUE}/scoreboard"
        [[ -n "$DATE" ]] && URL="${URL}?dates=${DATE}"
        fetch "$URL"
        ;;
    standings)
        [[ $# -lt 2 ]] && { echo "Usage: $0 standings <sport> <league> [season]"; exit 1; }
        SPORT="$1"; LEAGUE="$2"; SEASON="${3:-}"
        URL="${SITE_API}/apis/v2/sports/${SPORT}/${LEAGUE}/standings"
        [[ -n "$SEASON" ]] && URL="${URL}?season=${SEASON}"
        fetch "$URL"
        ;;
    teams)
        [[ $# -lt 2 ]] && { echo "Usage: $0 teams <sport> <league>"; exit 1; }
        fetch "${SITE_API}/apis/site/v2/sports/$1/$2/teams"
        ;;
    roster)
        [[ $# -lt 3 ]] && { echo "Usage: $0 roster <sport> <league> <team_id>"; exit 1; }
        fetch "${SITE_API}/apis/site/v2/sports/$1/$2/teams/$3/roster"
        ;;
    summary)
        [[ $# -lt 3 ]] && { echo "Usage: $0 summary <sport> <league> <event_id>"; exit 1; }
        fetch "${SITE_API}/apis/site/v2/sports/$1/$2/summary?event=$3"
        ;;
    athlete-stats)
        [[ $# -lt 3 ]] && { echo "Usage: $0 athlete-stats <sport> <league> <athlete_id>"; exit 1; }
        fetch "${WEB_API}/apis/common/v3/sports/$1/$2/athletes/$3/stats"
        ;;
    athlete-gamelog)
        [[ $# -lt 3 ]] && { echo "Usage: $0 athlete-gamelog <sport> <league> <athlete_id>"; exit 1; }
        fetch "${WEB_API}/apis/common/v3/sports/$1/$2/athletes/$3/gamelog"
        ;;
    injuries)
        [[ $# -lt 2 ]] && { echo "Usage: $0 injuries <sport> <league>"; exit 1; }
        fetch "${SITE_API}/apis/site/v2/sports/$1/$2/injuries"
        ;;
    news)
        SPORT="${1:-}"; LEAGUE="${2:-}"
        if [[ -n "$SPORT" && -n "$LEAGUE" ]]; then
            URL="${SITE_API}/apis/site/v2/sports/${SPORT}/${LEAGUE}/news?limit=20"
        else
            URL="${NOW_API}/v1/sports/news?limit=20"
        fi
        fetch "$URL"
        ;;
    odds)
        [[ $# -lt 3 ]] && { echo "Usage: $0 odds <sport> <league> <event_id>"; exit 1; }
        fetch "${CORE_API}/v2/sports/$1/leagues/$2/events/$3/competitions/$3/odds"
        ;;
    cdn-game)
        [[ $# -lt 2 ]] && { echo "Usage: $0 cdn-game <cdn_sport> <game_id>"; exit 1; }
        fetch "${CDN_API}/core/$1/game?xhr=1&gameId=$2"
        ;;
    search)
        [[ $# -lt 1 ]] && { echo "Usage: $0 search <query>"; exit 1; }
        QUERY=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$1'))")
        fetch "${WEB_API}/apis/search/v2?query=${QUERY}&limit=10"
        ;;
    *)
        echo "Unknown command: $CMD"
        usage
        ;;
esac
