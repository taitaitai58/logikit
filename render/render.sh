#!/usr/bin/env bash
# Render a Logisim .circ to PNG using Logisim-evolution's own drawing code.
#
#   ./render/render.sh in.circ out.png [scale]
#
# Requires a JDK and the Logisim-evolution "all" jar. Point LOGISIM_JAR at it,
# or install Logisim-evolution.app on macOS (the default path below is tried).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Locate the Logisim jar.
JAR="${LOGISIM_JAR:-}"
if [[ -z "$JAR" ]]; then
  for c in \
    /Applications/Logisim-evolution.app/Contents/app/logisim-evolution-*-all.jar \
    "$HOME"/Downloads/logisim-evolution-*-all.jar; do
    if [[ -f "$c" ]]; then JAR="$c"; break; fi
  done
fi
if [[ -z "$JAR" || ! -f "$JAR" ]]; then
  echo "error: Logisim jar not found. Set LOGISIM_JAR=/path/to/logisim-evolution-X.Y.Z-all.jar" >&2
  exit 1
fi

IN="${1:?usage: render.sh in.circ out.png [scale]}"
OUT="${2:?usage: render.sh in.circ out.png [scale]}"
SCALE="${3:-4}"

# Compile once (the .class lands next to the .java).
if [[ ! -f "$HERE/LogiRender.class" || "$HERE/LogiRender.java" -nt "$HERE/LogiRender.class" ]]; then
  javac -classpath "$JAR" -d "$HERE" "$HERE/LogiRender.java"
fi

java -Djava.awt.headless=true -classpath "$HERE:$JAR" LogiRender "$IN" "$OUT" "$SCALE"
