#!/bin/bash
# Validates polymarket read-only parameters
COMMAND="${1:-}"

TRADING_COMMANDS="configure create_order market_order cancel_order cancel_all_orders get_orders get_user_trades"
if echo "$TRADING_COMMANDS" | grep -qw "$COMMAND"; then
  echo "ERROR: $COMMAND is a financial-execution command and is not part of the read-only polymarket skill. Use polymarket-trading only after explicit user approval."
  exit 1
fi

# token_id vs market_id warning
if [[ "$COMMAND" == "get_market_prices" || "$COMMAND" == "get_order_book" || "$COMMAND" == "get_price_history" || "$COMMAND" == "get_last_trade_price" ]]; then
  if [[ "$*" != *"--token_id="* ]]; then
    echo "ERROR: $COMMAND requires --token_id (CLOB token ID), not market_id. Get it from get_market_details."
    exit 1
  fi
fi

# Search tips
if [[ "$COMMAND" == "search_markets" ]]; then
  echo "TIP: search_markets matches event titles. Use the sport parameter (e.g. --sport=epl) for single-game markets. Without it, only high-volume futures are returned."
fi
echo "OK"
