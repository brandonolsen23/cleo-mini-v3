#!/usr/bin/env bash
# Overnight full scan: runs remaining property types sequentially.
# Each type picks up where it left off (checks seen_rt_ids.json).
set -euo pipefail

PYTHON="/Users/brandonolsen23/cleo-mini-v3-venv/bin/python"
SCRIPT="/Users/brandonolsen23/cleo-mini-v3/scripts/full_scan.py"

for TYPE in comm-ind-land industrial res-land; do
    echo ""
    echo "============================================"
    echo "$(date): Starting full scan for $TYPE"
    echo "============================================"
    $PYTHON "$SCRIPT" --type "$TYPE" || echo "$(date): $TYPE exited with error (continuing)"
    echo "$(date): Finished $TYPE"
done

echo ""
echo "$(date): All scans complete."
