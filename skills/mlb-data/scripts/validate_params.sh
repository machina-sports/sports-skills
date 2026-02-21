#!/bin/bash
# Validates parameters before executing sports-skills commands
SPORT="mlb"
MONTH=$(date +%m)

case "$SPORT" in
  mlb)
    if [[ $MONTH -ge 11 || $MONTH -le 2 ]]; then
      echo "WARNING: MLB is in off-season (late Mar–Oct). Scoreboard may be empty."
      echo "SUGGESTION: Use get_news or get_standings with a prior season."
    fi
    ;;
esac

if [[ "$*" == *"--date="* ]]; then
  DATE=$(echo "$*" | grep -o '\-\-date=[^ ]*' | cut -d= -f2)
  if [[ ! "$DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "ERROR: Date must be YYYY-MM-DD format. Got: $DATE"
    exit 1
  fi
fi

if [[ "$*" == *"--team_id="* ]]; then
  TEAM_ID=$(echo "$*" | grep -o '\-\-team_id=[^ ]*' | cut -d= -f2)
  if [[ -z "$TEAM_ID" ]]; then
    echo "ERROR: --team_id requires a value. Use get_teams to find valid IDs."
    exit 1
  fi
fi

echo "OK"
