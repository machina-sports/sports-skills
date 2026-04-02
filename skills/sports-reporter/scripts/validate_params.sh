#!/bin/bash
# Validates sports-reporter parameters
# This skill orchestrates other skills — validate that sports-skills is installed

if ! command -v sports-skills &>/dev/null; then
  echo "ERROR: sports-skills CLI not found. Run: pip install sports-skills"
  exit 1
fi

echo "OK"
