#!/bin/bash
# Usage: scripts/validate_params.sh [command] [options]
# Validates parameters before executing sports-skills commands

SPORT="cfb"
COMMAND="${1:-}"

# Season check
MONTH=$(date +%m)
case "$SPORT" in
  cfb)
    if [[ $MONTH -ge 2 && $MONTH -le 7 ]]; then
      echo "WARNING: CFB is in off-season (Aug-Jan). Scoreboard/rankings may be empty."
      echo "SUGGESTION: Use get_news or get_standings with a specific season instead."
    fi
    ;;
esac

# Date format check
if [[ "$*" == *"--date="* ]]; then
  DATE=$(echo "$*" | grep -o '\-\-date=[^ ]*' | cut -d= -f2)
  if [[ ! "$DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "ERROR: Date must be in YYYY-MM-DD format. Got: $DATE"
    exit 1
  fi
fi

# Group ID check
if [[ "$*" == *"--group="* ]]; then
  GROUP=$(echo "$*" | grep -o '\-\-group=[^ ]*' | cut -d= -f2)
  if [[ ! "$GROUP" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Group ID must be a number. Got: $GROUP"
    exit 1
  fi
fi

# Team ID check
if [[ "$*" == *"--team_id="* ]]; then
  TEAM_ID=$(echo "$*" | grep -o '\-\-team_id=[^ ]*' | cut -d= -f2)
  if [[ ! "$TEAM_ID" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Team ID must be a number. Got: $TEAM_ID"
    exit 1
  fi
fi

# Week check
if [[ "$*" == *"--week="* ]]; then
  WEEK=$(echo "$*" | grep -o '\-\-week=[^ ]*' | cut -d= -f2)
  if [[ ! "$WEEK" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Week must be a number. Got: $WEEK"
    exit 1
  fi
fi

# Event ID check
if [[ "$*" == *"--event_id="* ]]; then
  EVENT_ID=$(echo "$*" | grep -o '\-\-event_id=[^ ]*' | cut -d= -f2)
  if [[ ! "$EVENT_ID" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Event ID must be a number. Got: $EVENT_ID"
    exit 1
  fi
fi

echo "OK"
