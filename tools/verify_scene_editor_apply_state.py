#!/usr/bin/env python3
"""Verify scene editor apply-needed and output SHA state.

The check is intentionally small and non-content-mutating:
1. The live :8782 server must report output full/final/title_test SHA sync.
2. A clean tree should report apply_needed=false.
3. Temporarily moving an override file mtime past output ROM must make
   apply_needed=true, then restoring mtime must return to clean.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROM = ROOT / "output" / "game_wars_korean_full.gba"
OVERRIDES = ROOT / "data" / "dialogue_overrides.json"


def api_json(base_url: str, path: str) -> dict:
    with urllib.request.urlopen(base_url.rstrip("/") + path, timeout=10) as res:
        return json.loads(res.read().decode("utf-8"))


def wait_state(base_url: str, expected_apply_needed: bool, timeout_s: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout_s
    last = None
    while time.monotonic() < deadline:
        last = api_json(base_url, "/api/state")
        if bool(last.get("apply_needed")) == expected_apply_needed:
            return last
        time.sleep(0.1)
    raise AssertionError(
        "apply_needed did not become %s; last state=%s" %
        (expected_apply_needed, json.dumps(last, ensure_ascii=False))
    )


def stat_ns(path: Path) -> tuple[int, int]:
    st = path.stat()
    return st.st_atime_ns, st.st_mtime_ns


def require(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://127.0.0.1:8782")
    args = ap.parse_args()

    require(OUTPUT_ROM.exists(), f"missing output ROM: {OUTPUT_ROM}")
    require(OVERRIDES.exists(), f"missing overrides: {OVERRIDES}")

    old_times = stat_ns(OVERRIDES)
    future_ns = None
    restored_by_script = False
    try:
        clean = wait_state(args.server, False)
        require(clean.get("output_sync", {}).get("ok"), "output SHA sync is not OK")
        require(not clean.get("apply_needed"), "initial state unexpectedly requires apply")

        future_ns = max(time.time_ns(), OUTPUT_ROM.stat().st_mtime_ns) + 5_000_000_000
        os.utime(OVERRIDES, ns=(old_times[0], future_ns))
        dirty = wait_state(args.server, True)
        require(dirty.get("apply_needed"), "override mtime newer than ROM did not require apply")
        require(dirty.get("dirty", {}).get("apply_needed"), "dirty.apply_needed was not set")

    finally:
        if future_ns is not None:
            current_times = stat_ns(OVERRIDES)
            if current_times[1] == future_ns:
                os.utime(OVERRIDES, ns=old_times)
                restored_by_script = True

    require(restored_by_script, "override mtime changed during verification; not restoring over concurrent edit")
    restored = wait_state(args.server, False)
    require(restored.get("output_sync", {}).get("ok"), "output SHA sync failed after restore")
    require(not restored.get("apply_needed"), "apply_needed did not clear after mtime restore")

    print(json.dumps({
        "ok": True,
        "rom_sha256": restored.get("rom", {}).get("full_sha256"),
        "output_sha256": restored.get("output_sync", {}).get("full_sha256"),
        "apply_needed_probe": "passed",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
