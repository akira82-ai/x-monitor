#!/usr/bin/env bash
# Quick demo launcher

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found"
    echo "Run: ./run.sh to set up"
    exit 1
fi

# Activate and run
source .venv/bin/activate
python3 demo.py
