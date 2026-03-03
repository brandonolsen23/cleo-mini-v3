#!/usr/bin/env bash
# Overnight full scan: runs remaining property types sequentially.
# Each type picks up where it left off (checks seen_rt_ids.json).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"
FULL_SCAN="$SCRIPT_DIR/full_scan.py"

for TYPE in comm-ind-land industrial res-land all; do
    echo ""
    echo "============================================"
    echo "$(date): Starting full scan for $TYPE"
    echo "============================================"
    $PYTHON "$FULL_SCAN" --type "$TYPE" || echo "$(date): $TYPE exited with error (continuing)"
    echo "$(date): Finished $TYPE"
done

echo ""
echo "$(date): All scans complete."
