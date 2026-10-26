#!/bin/bash
# Script to start the Arborizer project

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv and install requirements if needed
source venv/bin/activate
pip install -r requirements.txt

# Run the application
echo "Starting Arborizer on http://127.0.0.1:5050"
python3 app.py
