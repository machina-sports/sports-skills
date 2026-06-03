#!/bin/bash
# Validates cricket-data parameters
VALID_COMPETITIONS="tests odis t20s ipl bbl psl cpl hnd ntb cch sat msl lpl ilt wbb wpl"

if [[ "$*" == *"--competition="* ]]; then
  COMP=$(echo "$*" | grep -o '\-\-competition=[^ ]*' | cut -d= -f2)
  if [[ " $VALID_COMPETITIONS " != *" $COMP "* ]]; then
    echo "ERROR: --competition must be one of: $VALID_COMPETITIONS. Got: $COMP"
    exit 1
  fi
fi

if [[ "$*" == *"--series_id="* ]]; then
  SID=$(echo "$*" | grep -o '\-\-series_id=[^ ]*' | cut -d= -f2)
  if [[ ! "$SID" =~ ^[0-9]+$ ]]; then
    echo "ERROR: --series_id must be numeric (discover with get_series). Got: $SID"
    exit 1
  fi
fi

if [[ "$*" == *"--date="* ]]; then
  DATE=$(echo "$*" | grep -o '\-\-date=[^ ]*' | cut -d= -f2)
  if [[ ! "$DATE" =~ ^[0-9]{8}$ && ! "$DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    echo "ERROR: --date must be YYYYMMDD or YYYY-MM-DD. Got: $DATE"
    exit 1
  fi
fi

echo "OK"
