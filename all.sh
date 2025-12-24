#!/bin/bash
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# --- 1. Kernel Permissions (CRITICAL for Perf & pyRAPL) ---
echo ">>> Setting kernel permissions..."
sudo sysctl -w kernel.perf_event_paranoid=-1
sudo sysctl -w kernel.kptr_restrict=0

# --- 2. Ensure Wrapper Script is Executable ---
# If you are using the wrap_hype.sh we created, ensure it has +x permissions
if [ -f "$SCRIPT_DIR/wrap_hype.sh" ]; then
    chmod +x "$SCRIPT_DIR/wrap_hype.sh"
fi

# --- 3. Run HyperTensioN Energy Profiling ---
# We use the full path to the virtual environment and the config file
echo ">>> Starting HyperTensioN Energy Profiling using Perf..."

# Run the perf-based script
sudo "$SCRIPT_DIR/.venv/bin/python3" "$SCRIPT_DIR/hypertension-runners/hype-perf.py" \
    --config "$SCRIPT_DIR/hypertension-runners/config-hype.json"

echo ">>> ALL RUNS COMPLETE. Files saved to output folders."