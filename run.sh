#!/bin/bash
# Script to start the Arborizer project
set -e
cd "$(dirname "$0")"

# (Re)create venv if missing or broken (e.g. after a system Python upgrade)
if [ ! -d "venv" ] || ! venv/bin/python -m pip --version >/dev/null 2>&1; then
    echo "Creating virtual environment..."
    rm -rf venv
    python3 -m venv venv
fi

# Activate venv and install requirements if needed
source venv/bin/activate
python -m pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
    echo "Missing .env file: copy .env.example to .env and fill in the values." >&2
    exit 1
fi

# Run the application
echo "Starting Arborizer on http://127.0.0.1:5050"
python app.py
