#!/bin/bash
# Validates fastf1 parameters
MONTH=$(date +%m)
YEAR=$(date +%Y)

# Season timing check
if [[ $MONTH -le 2 ]]; then
  echo "INFO: F1 season hasn't started yet. Use year=$((YEAR - 1)) for most recent completed season."
fi

# Year parameter check
if [[ "$*" == *"--year="* ]]; then
  Y=$(echo "$*" | grep -o '\-\-year=[^ ]*' | cut -d= -f2)
  if [[ $Y -gt $YEAR ]]; then
    echo "WARNING: Year $Y is in the future. No data will be available."
  fi
fi
echo "OK"
