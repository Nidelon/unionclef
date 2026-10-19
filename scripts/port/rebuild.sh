#!/usr/bin/env bash
# Full port rebuild, from the pristine yarn-named tree to a loadable jar.
#
#   scripts/port/rebuild.sh
#
# Steps: preprocess + rename + fixups (port.sh), refresh the compile classpath,
# iterate the error-driven fixers until they converge, verify mixin injection
# points against the 26.2 jar, then build.
set -euo pipefail
cd "$(dirname "$0")/../.."

JDK="${JDK:-$HOME/.local/jdk/jdk-25.0.4.1+1}"
GRADLE="${GRADLE:-$HOME/.local/gradle/gradle-9.8.0/bin/gradle}"

echo "== 1/5 regenerate the tree =="
bash scripts/port/port.sh

echo
echo "== 2/5 refresh the compile classpath =="
JAVA_HOME="$JDK" "$GRADLE" -p port26 dumpClasspath --console=plain --no-daemon >/dev/null

echo
echo "== 3/5 fix compile errors until they converge =="
bash scripts/port/iterate.sh 5 | tail -4

echo
echo "== 4/5 verify mixin injection points =="
python3 scripts/port/mixincheck.py | tail -3

echo
echo "== 5/5 build =="
JAVA_HOME="$JDK" "$GRADLE" -p port26 build --console=plain --no-daemon | tail -4

ls -la port26/build/libs/*.jar
