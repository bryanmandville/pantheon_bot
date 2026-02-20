#!/bin/bash
# Helper script to run APEX with the correct virtual environment

# Get the directory where this script is located
SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Check if .venv exists
if [ -f ".venv/bin/python" ]; then
    echo "Starting APEX (Gemini 2.5 Pro)..."
    exec .venv/bin/python -m pantheon.main --mode cli "$@"
else
    echo "Error: Virtual environment not found in .venv/"
    echo "Please run: python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
    exit 1
fi
