#!/bin/bash
# Absolute path to your HyperTensioN folder
DIR="/home/rahul/Desktop/HyperTensioN"
cd "$DIR"

# Run the solver 50 times to give perf time to capture samples
for i in {1..50}
do
   # Using 'Hype.rb' since that is usually the runner for this planner
   ruby ./Hype.rb "$@" > /dev/null
done