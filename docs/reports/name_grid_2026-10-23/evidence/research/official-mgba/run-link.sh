#!/bin/sh
set -eu
R=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export TMPDIR="$R/tmp/"
export AW_KOR_TEMP_DIR="$R/runtime"
export DYLD_LIBRARY_PATH="$R/build"
mkdir -p "$TMPDIR" "$R/runtime/temp/release_C/verify4b"
cd "$R/runtime"
# Input ROM/BIOS/save/log arguments must use absolute paths; stdin output paths are relative to runtime/.
# LOG_FILE is mandatory in the existing link harness CLI.
exec "$R/mgba_link_harness" "$@"
