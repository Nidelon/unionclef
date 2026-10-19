#!/usr/bin/env bash
# Fast iteration loop: run javac directly with structured diagnostics.
#
# Gradle takes 25-40s per compile and prints errors as text that has to be
# re-parsed (wrapped paths, a compact indented style mid-report, a caret column
# instead of a real range). This runs javac through scripts/port/diag/DumpDiagnostics
# in ~12s and emits one JSON object per error with exact source offsets.
#
#   scripts/port/diag/run.sh            # -> port26/build/diag.jsonl
#   scripts/port/diag/run.sh --count    # just the totals
set -euo pipefail
cd "$(dirname "$0")/../../.."

JDK="${JDK:-$HOME/.local/jdk/jdk-25.0.4.1+1}"
OUT=port26/build/diag.jsonl

if [ ! -f port26/build/classpath.txt ] || [ ! -f port26/build/sources.txt ]; then
    echo "classpath not dumped yet, run: gradle dumpClasspath" >&2
    exit 1
fi

mkdir -p port26/build/diag port26/build/diag-out
if [ ! -f port26/build/diag/DumpDiagnostics.class ]; then
    "$JDK/bin/javac" -d port26/build/diag scripts/port/diag/DumpDiagnostics.java
fi

"$JDK/bin/java" -cp port26/build/diag DumpDiagnostics \
    @port26/build/sources.txt \
    -cp "$(cat port26/build/classpath.txt)" \
    -d port26/build/diag-out > "$OUT" 2>port26/build/diag.err

python3 - "$OUT" <<'PY'
import json, sys, collections
entries = [json.loads(l) for l in open(sys.argv[1])]
lines = {(e["file"], e["line"]) for e in entries}
files = {e["file"] for e in entries}
print(f"diagnostics : {len(entries)}")
print(f"lines       : {len(lines)}")
print(f"files       : {len(files)}")
codes = collections.Counter(e["code"] for e in entries)
for k, v in codes.most_common(8):
    print(f"  {v:5d}  {k}")
PY
