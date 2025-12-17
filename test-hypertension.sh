#!/bin/sh

# Set timeout in seconds (e.g., 300 = 5 minutes)
TIMEOUT=30

for i in $(seq -w 1 10)
do 
    echo "=========================================="
    echo "Running problem instance: ${i}.hddl"
    echo "=========================================="
    
    # Run with timeout
    timeout --signal=KILL $TIMEOUT ruby Hype.rb \
        benchmarks/domains/AssemblyHierachial/domain.hddl \
        benchmarks/domains/AssemblyHierachial/${i}.hddl run
    
    exit_code=$?
    
    if [ $exit_code -eq 124 ] || [ $exit_code -eq 137 ]; then
        echo "TIMEOUT: Problem ${i} exceeded ${TIMEOUT} seconds"
    elif [ $exit_code -ne 0 ]; then
        echo "ERROR: Problem ${i} failed with exit code $exit_code"
    else
        echo "SUCCESS: Problem ${i} completed"
    fi
    
    echo ""
done