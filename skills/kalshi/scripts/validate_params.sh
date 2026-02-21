#!/bin/bash
# Validates kalshi parameters
COMMAND="${1:-}"

# Ticker format hints
if [[ "$*" == *"--series_ticker="* ]]; then
  TICKER=$(echo "$*" | grep -o '\-\-series_ticker=[^ ]*' | cut -d= -f2)
  if [[ ! "$TICKER" =~ ^KX ]]; then
    echo "WARNING: Kalshi series tickers typically start with 'KX' (e.g., KXNBA, KXNFL). Got: $TICKER"
  fi
fi

# Timestamp check for candlesticks
if [[ "$COMMAND" == "get_market_candlesticks" ]]; then
  if [[ "$*" != *"--start_ts="* || "$*" != *"--end_ts="* ]]; then
    echo "ERROR: get_market_candlesticks requires --start_ts and --end_ts (Unix timestamps)."
    exit 1
  fi
fi
echo "OK"
