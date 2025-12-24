#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# 1. Running the Hypertension folder
echo ">>> Starting HyperTensioN Energy Profiling..."
sudo "$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/hypertension-runners/hype-runner.py" --config "$SCRIPT_DIR/hypertension-runners/config-hype.json"

echo ">>> ALL RUNS COMPLETE. Files saved to output folders."