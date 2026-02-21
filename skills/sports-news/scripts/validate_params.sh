#!/bin/bash
# Validates sports-news parameters
if [[ "$*" == *"--google_news"* && "$*" != *"--query="* ]]; then
  echo "ERROR: google_news=True requires a --query parameter."
  exit 1
fi
if [[ "$*" == *"--url="* && "$*" == *"--google_news"* ]]; then
  echo "ERROR: --url and --google_news are mutually exclusive."
  exit 1
fi
echo "OK"
