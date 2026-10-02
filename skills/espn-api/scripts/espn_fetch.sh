#!/usr/bin/env bash
# ESPN API fetch helper (bash/curl version)
#
# Usage:
#   ./espn_fetch.sh scoreboard basketball nba
#   ./espn_fetch.sh scoreboard basketball nba 20250315
#   ./espn_fetch.sh standings basketball nba
#   ./espn_fetch.sh teams football nfl
#   ./espn_fetch.sh roster basketball nba 9
#   ./espn_fetch.sh summary basketball nba 401811026
#   ./espn_fetch.sh athlete-stats basketball nba 3975
#   ./espn_fetch.sh athlete-gamelog basketball nba 3975
#   ./espn_fetch.sh injuries football nfl
#   ./espn_fetch.sh news basketball nba
#   ./espn_fetch.sh odds basketball nba 401811026
#   ./espn_fetch.sh cdn-game nba 401811026
#   ./espn_fetch.sh search "Stephen Curry"
#
# Pipe to jq for pretty output: ./espn_fetch.sh scoreboard basketball nba | jq .
#
# Prints raw, provider-native ESPN JSON. Makes live requests and does not
# participate in SPORTS_SKILLS_REPLAY: when that variable is set to any mode
# other than "off" it refuses to run, before any network access.

set -euo pipefail

REPLAY_MODE="$(printf '%s' "${SPORTS_SKILLS_REPLAY:-off}" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')"
if [[ -n "$REPLAY_MODE" && "$REPLAY_MODE" != "off" ]]; then
    echo "SPORTS_SKILLS_REPLAY=${REPLAY_MODE}: this raw ESPN helper is not record/replay-backed and would reach the network." >&2
    echo "Use the supported package runtime instead (e.g. sports-skills nba get_scoreboard), or unset SPORTS_SKILLS_REPLAY for live raw requests." >&2
    exit 1
fi

SITE_API="https://site.api.espn.com"
CORE_API="https://sports.core.api.espn.com"
WEB_API="https://site.web.api.espn.com"
CDN_API="https://cdn.espn.com"
NOW_API="https://now.core.api.espn.com"

# -sS: no progress bar, but errors still go to stderr. -f: fail on HTTP errors.
fetch() {
    curl -sS -f --connect-timeout 10 --max-time 30 \
        -H "User-Agent: espn-api/1.0" -H "Accept: application/json" "$@"
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
        # curl URL-encodes the query as data; it is never interpolated into code.
        fetch -G --data-urlencode "query=$1" --data "limit=10" "${WEB_API}/apis/search/v2"
        ;;
    *)
        echo "Unknown command: $CMD"
        usage
        ;;
esac
