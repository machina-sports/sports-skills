#!/bin/bash
# Validates polymarket parameters
COMMAND="${1:-}"

# token_id vs market_id warning
if [[ "$COMMAND" == "get_market_prices" || "$COMMAND" == "get_order_book" || "$COMMAND" == "get_price_history" || "$COMMAND" == "get_last_trade_price" ]]; then
  if [[ "$*" != *"--token_id="* ]]; then
    echo "ERROR: $COMMAND requires --token_id (CLOB token ID), not market_id. Get it from get_market_details."
    exit 1
  fi
fi

# Search tips
if [[ "$COMMAND" == "search_markets" ]]; then
  echo "TIP: search_markets matches event titles. Use league names (e.g., 'Premier League', 'NBA Finals'), not generic terms like 'soccer'."
fi
echo "OK"
