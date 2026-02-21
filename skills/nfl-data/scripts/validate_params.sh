#!/bin/bash
SPORT="${1:-nfl}"  # nfl, nhl, or golf
MONTH=$(date +%m)

case "$SPORT" in
  nfl)
    if [[ $MONTH -ge 3 && $MONTH -le 8 ]]; then
      echo "WARNING: NFL is in off-season (Sep-Feb). Scoreboard may be empty."
      echo "SUGGESTION: Use get_news or get_standings with a prior season."
    fi
    ;;
  nhl)
    if [[ $MONTH -ge 7 && $MONTH -le 9 ]]; then
      echo "WARNING: NHL is in off-season (Oct-Jun). Scoreboard may be empty."
      echo "SUGGESTION: Use get_news or get_standings with a prior season."
    fi
    ;;
  golf)
    DOW=$(date +%u)
    if [[ $DOW -le 3 ]]; then
      echo "INFO: Golf tournaments run Thu-Sun. Leaderboard may show last week's results."
    fi
    ;;
esac
echo "OK"
