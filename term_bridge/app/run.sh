#!/bin/sh
set -eu

echo "Starting TERM Bridge runner"

while true; do
    echo "Launching /app/main.py"
    if python3 -u /app/main.py; then
        exit_code=0
    else
        exit_code=$?
    fi

    echo "main.py exited with code ${exit_code}, restarting in 5 seconds..."
    sleep 5
done
