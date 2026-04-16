#!/bin/bash

exec > RESULTS.md 2>&1

echo "========================================"
echo "1. machina version < /dev/null"
echo "========================================"
machina version < /dev/null

echo ""
echo "========================================"
echo "2. machina config list < /dev/null"
echo "========================================"
machina config list < /dev/null

echo ""
echo "========================================"
echo "3. cat ~/.machina/credentials.json"
echo "========================================"
cat ~/.machina/credentials.json

echo ""
echo "========================================"
echo "4. machina agent list < /dev/null"
echo "========================================"
machina agent list < /dev/null

echo ""
echo "========================================"
echo "5. machina agent run podcast-digest-agent query=\"Brasileirao\" --sync --json < /dev/null"
echo "========================================"
machina agent run podcast-digest-agent query="Brasileirao" --sync --json < /dev/null

