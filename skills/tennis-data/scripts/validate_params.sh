#!/bin/bash
# Validates tennis-data parameters
if [[ "$*" == *"--tour="* ]]; then
  TOUR=$(echo "$*" | grep -o '\-\-tour=[^ ]*' | cut -d= -f2)
  if [[ "$TOUR" != "atp" && "$TOUR" != "wta" ]]; then
    echo "ERROR: --tour must be 'atp' or 'wta'. Got: $TOUR"
    exit 1
  fi
fi
echo "OK"
