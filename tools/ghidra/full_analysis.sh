#!/usr/bin/env bash
# Whole-ROM Ghidra analysis + export (static aid only; confirm findings at runtime).
# Usage: tools/ghidra/full_analysis.sh [--rom PATH] [--out DIR] [--seeds TSV] [--overlays TSV]
#   default ROM = original; project temp/decomp/ghidra/proj_full (name gbwa_full[_<sha12>])
#   default out = temp/ghidra_audit_20261013/ghidra_export
#   Re-running on an existing project skips analysis and only re-exports.
# Env: GHIDRA_HOME, JAVA_HOME (see docs/GHIDRA.md), GHIDRA_FULL_PROJ, MAXMEM (default 6G)
set -euo pipefail
D=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$D/../.." && pwd)
ORIG_ROM="$REPO/original/Game Boy Wars Advance 1+2 (Japan).gba"
ROM="$ORIG_ROM"
A="$REPO/temp/ghidra_audit_20261013"
OUT="$A/ghidra_export"; SEEDS="$A/seeds_known.tsv"; OVL="$A/overlays.tsv"
while [ $# -gt 0 ]; do
  case $1 in
    --rom) ROM=$(realpath "$2"); shift 2;;
    --out) OUT=$(realpath -m "$2"); shift 2;;
    --seeds) SEEDS=$(realpath "$2"); shift 2;;
    --overlays) OVL=$(realpath "$2"); shift 2;;
    -h|--help) sed -n 2,8p "$0"; exit 0;;
    *) echo "unknown arg $1" >&2; exit 2;;
  esac
done
GH=${GHIDRA_HOME:-$HOME/.local/opt/ghidra_12.1.4_PUBLIC}
export JAVA_HOME=${JAVA_HOME:-$HOME/.local/opt/jdk-21.0.12.1+1}
[ -x "$GH/support/analyzeHeadless" ] || { echo "error: Ghidra not found at $GH" >&2; exit 3; }
[ -f "$ROM" ] || { echo "error: ROM not found: $ROM" >&2; exit 4; }
[ -f "$SEEDS" ] || { echo "error: seeds TSV not found: $SEEDS" >&2; exit 4; }
PROJ=${GHIDRA_FULL_PROJ:-$REPO/temp/decomp/ghidra/proj_full}
NAME=gbwa_full
[ "$ROM" = "$ORIG_ROM" ] || NAME="gbwa_full_$(sha256sum "$ROM" | cut -c1-12)"
export MAXMEM=${MAXMEM:-6G}
export JAVA_TOOL_OPTIONS="-XX:ActiveProcessorCount=4"
mkdir -p "$PROJ" "$OUT"
sha256sum "$ROM" > "$OUT/rom.sha256"
if [ ! -d "$PROJ/$NAME.rep" ]; then
  IMP=(-import "$ROM" -loader BinaryLoader -loader-baseAddr 0x08000000 -processor ARM:LE:32:v4t -noanalysis)
else
  IMP=(-process "$(basename "$ROM")" -noanalysis)
fi
exec memcap -n ghidra-full -m 8G -- python3 -I "$D/scripts/peakrss.py" "$OUT/metrics.log" nice -n 15 \
  "$GH/support/analyzeHeadless" "$PROJ" "$NAME" "${IMP[@]}" -max-cpu 4 -analysisTimeoutPerFile 7200 \
  -scriptPath "$D/scripts" -postScript GbaFullAnalysis.java "$OUT" "$SEEDS" "${OVL:-/dev/null}"
