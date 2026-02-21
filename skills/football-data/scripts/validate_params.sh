#!/bin/bash
# Validates football-data parameters
COMMAND="${1:-}"

# Season ID format check
if [[ "$*" == *"--season_id="* ]]; then
  SID=$(echo "$*" | grep -o '\-\-season_id=[^ ]*' | cut -d= -f2)
  if [[ ! "$SID" =~ ^[a-z-]+-[0-9]{4}$ ]]; then
    echo "ERROR: season_id must be {league-slug}-{year} format (e.g., premier-league-2025). Got: $SID"
    exit 1
  fi
fi

# League coverage warnings
case "$COMMAND" in
  get_season_leaders|get_missing_players)
    if [[ "$*" != *"premier-league"* ]]; then
      echo "WARNING: $COMMAND only works for Premier League. Will return empty for other leagues."
    fi
    ;;
  get_event_xg)
    echo "INFO: xG data only available for top 5 leagues (EPL, La Liga, Bundesliga, Serie A, Ligue 1)."
    ;;
esac
echo "OK"
