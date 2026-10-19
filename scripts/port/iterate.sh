#!/usr/bin/env bash
# Iterate the automated fixers until the diagnostic count stops dropping.
#
# Each round: structured diagnostics -> deterministic fixers -> rule/member
# autofix. Everything here is idempotent, so the loop is safe to re-run.
#
#   scripts/port/iterate.sh [rounds]
set -uo pipefail
cd "$(dirname "$0")/../.."

ROUNDS="${1:-4}"
MAPS=scripts/port/maps

for i in $(seq 1 "$ROUNDS"); do
    echo "=== round $i ==="
    # text-changing passes run BEFORE the compile: javac offsets are only valid
    # for the exact bytes it read, so anything that edits the tree afterwards
    # invalidates every span in the diagnostics
    python3 scripts/port/fixups.py port26/src/main/java >/dev/null 2>&1 || true
    python3 "$MAPS/fix_color_collections.py" port26/src/main/java --apply >/dev/null 2>&1 || true

    bash scripts/port/diag/run.sh | head -3

    python3 "$MAPS/autofix.py" --apply 2>&1 | grep -E '^applied|fixes over' || true
done

echo "=== final ==="
bash scripts/port/diag/run.sh | head -4
