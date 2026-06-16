#!/usr/bin/env bash
# Render a Logisim .circ to PNG using Logisim-evolution's own drawing code.
#
#   ./render/render.sh in.circ out.png [scale]
#
# Requires a JDK and the Logisim-evolution "all" jar. Point LOGISIM_JAR at it,
# or install Logisim-evolution.app on macOS (the default path below is tried).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DL="https://github.com/logisim-evolution/logisim-evolution/releases"

die() { echo "error: $*" >&2; exit 1; }

# --- toolchain checks (clear messages instead of "command not found") -------
command -v java  >/dev/null 2>&1 || die $'`java` not found on PATH. Install a JDK:\n  macOS: brew install temurin   Linux: sudo apt install default-jdk'
command -v javac >/dev/null 2>&1 || die $'`javac` not found on PATH (need a JDK, not just a JRE).\n  macOS: brew install temurin   Linux: sudo apt install default-jdk'

# --- locate the Logisim jar -------------------------------------------------
JAR="${LOGISIM_JAR:-}"
if [[ -z "$JAR" ]]; then
  for c in \
    /Applications/Logisim-evolution.app/Contents/app/logisim-evolution-*-all.jar \
    "$HOME"/Downloads/logisim-evolution-*-all.jar; do
    if [[ -f "$c" ]]; then JAR="$c"; break; fi
  done
fi
if [[ -z "$JAR" || ! -f "$JAR" ]]; then
  die "Logisim jar not found.
  Set LOGISIM_JAR to the '…-all.jar', e.g.:
    export LOGISIM_JAR=/path/to/logisim-evolution-X.Y.Z-all.jar
  Download: $DL
  (On macOS, installing Logisim-evolution.app is auto-detected.)"
fi

# --- arguments --------------------------------------------------------------
IN="${1:-}"; OUT="${2:-}"; SCALE="${3:-4}"
[[ -n "$IN" && -n "$OUT" ]] || die "usage: render.sh in.circ out.png [scale]"
[[ -f "$IN" ]] || die "input circuit not found: $IN
  (generate it first, e.g. python3 -m examples.circuits, then render the *_fig.circ variant)"

# --- compile once, then render ----------------------------------------------
if [[ ! -f "$HERE/LogiRender.class" || "$HERE/LogiRender.java" -nt "$HERE/LogiRender.class" ]]; then
  javac -classpath "$JAR" -d "$HERE" "$HERE/LogiRender.java" \
    || die "failed to compile LogiRender.java against $JAR (is it the '…-all.jar'?)"
fi

java -Djava.awt.headless=true -classpath "$HERE:$JAR" LogiRender "$IN" "$OUT" "$SCALE"
