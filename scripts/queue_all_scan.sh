#!/usr/bin/env bash
# Wait for a running scan process to finish, then run --type all.
# Usage: ./queue_all_scan.sh <PID>
#   e.g. ./queue_all_scan.sh 73347
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <PID>"
    echo "  Waits for the given PID to finish, then runs full_scan.py --type all."
    exit 1
fi

WAIT_PID="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"
FULL_SCAN="$SCRIPT_DIR/full_scan.py"

echo "$(date): Waiting for PID $WAIT_PID to finish..."

while kill -0 "$WAIT_PID" 2>/dev/null; do
    sleep 30
done

echo "$(date): PID $WAIT_PID finished. Starting --type all scan..."
echo ""
$PYTHON "$FULL_SCAN" --type all
echo ""
echo "$(date): All-types scan complete."
