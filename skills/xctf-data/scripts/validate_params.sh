#!/bin/bash
# Validates parameters before executing xctf-data commands

if ! command -v sports-skills &>/dev/null; then
  echo "ERROR: sports-skills CLI not found. Run: pip install sports-skills"
  exit 1
fi

if [[ "$*" == *"get_athlete_profile"* ]]; then
  if [[ "$*" != *"--athlete_id="* ]]; then
    echo "ERROR: get_athlete_profile requires --athlete_id"
    exit 1
  fi
  if [[ "$*" != *"--school="* ]]; then
    echo "ERROR: get_athlete_profile requires --school"
    exit 1
  fi
  if [[ "$*" != *"--name="* ]]; then
    echo "ERROR: get_athlete_profile requires --name"
    exit 1
  fi
fi

if [[ "$*" == *"search_athlete"* ]]; then
  if [[ "$*" != *"--name="* ]]; then
    echo "ERROR: search_athlete requires --name"
    exit 1
  fi
  if [[ "$*" != *"--school="* ]]; then
    echo "ERROR: search_athlete requires --school"
    exit 1
  fi
fi

if [[ "$*" == *"get_meet_results"* ]]; then
  if [[ "$*" != *"--meet_id="* ]]; then
    echo "ERROR: get_meet_results requires --meet_id"
    exit 1
  fi
  if [[ "$*" != *"--slug="* ]]; then
    echo "ERROR: get_meet_results requires --slug"
    exit 1
  fi
fi

if [[ "$*" == *"get_team_roster"* ]]; then
  if [[ "$*" != *"--school="* ]]; then
    echo "ERROR: get_team_roster requires --school"
    exit 1
  fi
fi

echo "OK"
