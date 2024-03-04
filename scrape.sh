#!/bin/bash

script_dir=$(dirname "$(readlink -f "$0")")
cd $script_dir

PYTHON_PROGRAM="./main.py"
LAST_EXECUTION_FILE="./last_execution_time.txt"

# Check if the last execution time file exists
if [ ! -f "$LAST_EXECUTION_FILE" ]; then
    touch "$LAST_EXECUTION_FILE"
fi

# Get the last execution time
last_execution_time=$(cat "$LAST_EXECUTION_FILE")

# Get the current time
current_time=$(date +%s)

# Calculate the difference in seconds between the last execution time and the current time
time_difference=$((current_time - last_execution_time))

# Check if the time difference is greater than 24.5 hours (88200 seconds)
if [ "$time_difference" -gt 88200 ]; then
    # Run the Python program
    python "$PYTHON_PROGRAM"

    # Update the last execution time if successful
    if [ "$?" -eq 0 ]; then
        date +%s > "$LAST_EXECUTION_FILE"
    else
        echo "$PYTHON_PROGRAM failed with exit code $?"
    fi
else
    echo "Not enough time has elapsed since last execution ($time_difference seconds elapsed)"
fi