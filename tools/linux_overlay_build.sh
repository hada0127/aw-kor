#!/usr/bin/env bash
# Linux screen-QA candidate build without the macOS fonts (OkDanDan, AppleSDGothicNeo,
# NanumGothic). Never a release build: release needs a Mac real-font rebuild that is
# byte-compared to the candidate.
#
# Method (docs/success.md "Linux font-stub overlay build"):
#   A = stub build of BASE_REF (the commit whose real-font build is REFERENCE_ROM)
#   B = stub build of the current working tree
#   candidate = REFERENCE_ROM + bytes where A != B
# Both builds run tools/linux_fontstub/fontstub_build.py (missing fonts -> Galmuri11-Bold,
# font hash guards relaxed) with write tracing (AW_TRACE_OUT). overlay_check.py must PASS:
# A != reference only inside font-using writer spans, no untraced writes, identical font
# spans in A and B, and no A != B byte inside a font span.
#
# usage: tools/linux_overlay_build.sh [--base-ref REF] [--reference ROM] [--name NAME]
#                                     [--work DIR] [--no-publish]
#   defaults: --base-ref 1761a95 (source of candidate e4963765)
#             --reference output/game_wars_korean_candidate_e4963765.gba
#             --name <sha8>  -> output/game_wars_korean_candidate_<name>.gba (never overwritten)
#             --work temp/linux_overlay
# A is cached per base commit + stub script hash in WORK/A_<commit>_<stub8>.
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"
BASE_REF=1761a95
REFERENCE=output/game_wars_korean_candidate_e4963765.gba
NAME=""
WORK=temp/linux_overlay
PUBLISH=1
while [ $# -gt 0 ]; do
  case "$1" in
    --base-ref) BASE_REF=$2; shift 2;;
    --reference) REFERENCE=$2; shift 2;;
    --name) NAME=$2; shift 2;;
    --work) WORK=$2; shift 2;;
    --no-publish) PUBLISH=0; shift;;
    -h|--help) sed -n '2,25p' "$0"; exit 0;;
    *) echo "unknown argument: $1" >&2; exit 64;;
  esac
done

STUB="$ROOT/tools/linux_fontstub"
ORIGINAL="$ROOT/original/Game Boy Wars Advance 1+2 (Japan).gba"
[ -f "$ORIGINAL" ] || { echo "original ROM missing: $ORIGINAL" >&2; exit 2; }
[ -f "$REFERENCE" ] || { echo "reference ROM missing: $REFERENCE" >&2; exit 2; }
if pgrep -f '^python3?[^ ]* [^ ]*(build_korean_full|fontstub_build)\.py' >/dev/null; then
  echo "another build_korean_full.py is running; builds are serialized" >&2; exit 3
fi
COMMIT=$(git rev-parse "$BASE_REF")
STUB_SHA=$(cat "$STUB/fontstub_build.py" | sha256sum | cut -c1-8)
mkdir -p "$WORK"
WORK=$(cd "$WORK" && pwd)
A_DIR="$WORK/A_${COMMIT:0:12}_$STUB_SHA"

# Gitignored build inputs that a clean worktree lacks.
IGNORED_INPUTS="data/sprite_edits data/sprite_layouts.json data/sprites_index.json data/dialogue_groups.json data/dialogue_map.json"

if [ ! -f "$A_DIR/build_A.gba" ] || [ ! -f "$A_DIR/trace_A.json" ]; then
  echo "== building A from $COMMIT"
  rm -rf "$A_DIR"; mkdir -p "$A_DIR"
  WT="$WORK/wt_${COMMIT:0:12}"
  git worktree remove --force "$WT" 2>/dev/null || true
  git worktree add --detach "$WT" "$COMMIT" >/dev/null
  ln -s "$ROOT/original" "$WT/original"
  for f in $IGNORED_INPUTS; do [ -e "$f" ] && cp -a "$f" "$WT/$f"; done
  mkdir -p "$WT/temp"
  AW_TRACE_OUT="$A_DIR/trace_A.json" nice -n 15 python3 "$STUB/fontstub_build.py" "$WT" \
      --out "$A_DIR/build_A.gba" --no-sync-outputs > "$A_DIR/build_A.log" 2>&1 \
      || { echo "A build failed; see $A_DIR/build_A.log" >&2; exit 4; }
  cp "$WT/temp/integrity_map.json" "$A_DIR/integrity_map.json"
  git worktree remove --force "$WT"
fi

RUN="$WORK/run_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RUN"
echo "== building B from working tree ($(git rev-parse --short HEAD)$(git diff --quiet || echo ' + local changes'))"
AW_TRACE_OUT="$RUN/trace_B.json" nice -n 15 python3 "$STUB/fontstub_build.py" "$ROOT" \
    --out "$RUN/build_B.gba" --no-sync-outputs > "$RUN/build_B.log" 2>&1 \
    || { echo "B build failed; see $RUN/build_B.log" >&2; exit 5; }

python3 "$STUB/overlay_check.py" "$A_DIR/build_A.gba" "$RUN/build_B.gba" "$REFERENCE" "$ORIGINAL" \
    "$A_DIR/trace_A.json" "$RUN/trace_B.json" "$RUN/overlay_check.json" > "$RUN/overlay_check.log" \
    || { echo "overlay check FAILED; see $RUN/overlay_check.json" >&2; exit 6; }
python3 "$STUB/overlay.py" "$A_DIR/build_A.gba" "$RUN/build_B.gba" "$REFERENCE" "$RUN/candidate.gba" \
    > "$RUN/overlay.log" || { echo "overlay failed; see $RUN/overlay.log" >&2; exit 7; }
SHA=$(sha256sum "$RUN/candidate.gba" | cut -d' ' -f1)
echo "build B: $RUN/build_B.gba (integrity map: temp/integrity_map.json, manifest: temp/repoint_manifest.json)"
if [ "$PUBLISH" = 1 ]; then
  DEST="output/game_wars_korean_candidate_${NAME:-${SHA:0:8}}.gba"
  if [ -e "$DEST" ]; then
    if cmp -s "$DEST" "$RUN/candidate.gba"; then echo "already published (identical): $DEST"
    else echo "refusing to overwrite different $DEST" >&2; exit 8; fi
  else
    cp "$RUN/candidate.gba" "$DEST"
  fi
  echo "candidate: $ROOT/$DEST"
else
  echo "candidate: $RUN/candidate.gba"
fi
echo "sha256: $SHA"
