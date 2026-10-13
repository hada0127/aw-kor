#!/usr/bin/env bash
# Ghidra headless decompile helper for the GBA ROM (static aid only; confirm at runtime).
# Usage: tools/ghidra/decomp.sh [--rom PATH] ADDR[:t|:a] [more specs...] [xref=0xVALUE]
#   default mode Thumb (:t). Output: $GHIDRA_OUT/<ADDR>.c (C + disasm)
# Env: GHIDRA_HOME (default ~/.local/opt/ghidra_12.1.4_PUBLIC)
#      JAVA_HOME   (default ~/.local/opt/jdk-21.0.12.1+1)
#      GHIDRA_PROJ (default <repo>/temp/decomp/ghidra/proj)
#      GHIDRA_OUT  (default <repo>/temp/decomp/ghidra/out)
set -euo pipefail
D=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$D/../.." && pwd)
ROM="$REPO/original/Game Boy Wars Advance 1+2 (Japan).gba"
ORIG_ROM="$ROM"
specs=()
while [ $# -gt 0 ]; do
  case $1 in
    --rom) ROM=$(realpath "$2"); shift 2;;
    --rom=*) ROM=$(realpath "${1#--rom=}"); shift;;
    -h|--help) sed -n 2,8p "$0"; exit 0;;
    *:a|*:t|xref=*) specs+=("$1"); shift;;
    *) specs+=("$1:t"); shift;;
  esac
done
[ ${#specs[@]} -gt 0 ] || { echo "error: no address specs (see --help)" >&2; exit 2; }
GH=${GHIDRA_HOME:-$HOME/.local/opt/ghidra_12.1.4_PUBLIC}
export JAVA_HOME=${JAVA_HOME:-$HOME/.local/opt/jdk-21.0.12.1+1}
[ -x "$GH/support/analyzeHeadless" ] || { echo "error: Ghidra not found at $GH (set GHIDRA_HOME; see docs/GHIDRA.md)" >&2; exit 3; }
[ -x "$JAVA_HOME/bin/java" ] || { echo "error: JDK 21 not found at $JAVA_HOME (set JAVA_HOME; see docs/GHIDRA.md)" >&2; exit 3; }
[ -f "$ROM" ] || { echo "error: ROM not found: $ROM" >&2; exit 4; }
command -v memcap >/dev/null || { echo "error: memcap not found" >&2; exit 5; }
PROJ=${GHIDRA_PROJ:-$REPO/temp/decomp/ghidra/proj}
OUT=${GHIDRA_OUT:-$REPO/temp/decomp/ghidra/out}
NAME=gbwa
if [ "$ROM" != "$ORIG_ROM" ]; then
  SHA=$(sha256sum "$ROM" | cut -c1-12)
  NAME="gbwa_$SHA"
  [ -n "${GHIDRA_OUT:-}" ] || OUT="$OUT/$SHA"
fi
export MAXMEM=6G
export JAVA_TOOL_OPTIONS="-XX:ActiveProcessorCount=4"
mkdir -p "$PROJ" "$OUT"
if [ ! -d "$PROJ/$NAME.rep" ]; then
  IMP=(-import "$ROM" -loader BinaryLoader -loader-baseAddr 0x08000000 -processor ARM:LE:32:v4t -noanalysis)
else
  IMP=(-process "$(basename "$ROM")" -noanalysis)
fi
exec memcap -n ghidra-decomp -m 8G -- python3 -I "$D/scripts/peakrss.py" "$OUT/metrics.log" nice -n 15 "$GH/support/analyzeHeadless" "$PROJ" "$NAME" "${IMP[@]}" \
  -scriptPath "$D/scripts" -postScript GbaDecomp.java "$OUT" "${specs[@]}"
