#!/usr/bin/env python3
"""Cold b35 Part 1/2 delete-confirmation probes with private copied SRAM."""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from qa_visual_regions import MGBADriver, KEYS

ROM = ROOT / "output/game_wars_korean_candidate_20261015_b35.gba"
ROM_SHA = "7e4a3a9e6602b3fe1b82853420ee6ff46ed43b5c6ef2f0d058b71b97eb1c0a36"
SAVE_SOURCE = ROOT / "temp/release_C/rebind1/help/F_help_sweep/game.sav"
SAVE_SHA = "d1210b1d8fe444a3cc84eb8ae272c0076375107f93ce97b37d786f0efc2e9d51"
OUT = ROOT / "temp/release_C/verify4/delete"
HARNESS = ROOT / "temp/mgbah_linux"
CHORD = KEYS["L"] | KEYS["RIGHT"] | KEYS["SELECT"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hold(driver, mask, count):
    driver.cmd(f"keys {mask}")
    driver.frames(count)
    driver.cmd("keys 0")


def run(part):
    out = OUT / part
    out.mkdir(parents=True, exist_ok=True)
    save = out / "game.sav"
    shutil.copyfile(SAVE_SOURCE, save)
    assert sha(save) == SAVE_SHA
    os.environ["AW_KOR_TEMP_DIR"] = str(out)
    driver = MGBADriver(ROM, out, HARNESS, save)
    watch = out / "watch.log"
    events = []

    def capture(label):
        driver.shot(label)
        events.append({"label": label, "core_frame": driver.cmd("framecounter"),
                       "png": str((out / f"{label}.png").relative_to(ROOT)),
                       "png_sha256": sha(out / f"{label}.png"),
                       "watch_lines": len(watch.read_text().splitlines())})

    try:
        assert driver.cmd(f"watchaddr 08804FC8 8 r {watch}").endswith("set=8")
        # Distinct prompt text supplies a positive control for each game's
        # delete screen. This does not assume the target compact row is live.
        control = 0x08DF29AA if part == "part1" else 0x08A34C2E
        assert driver.cmd(f"watchaddr {control:08X} 2 r KEEP").endswith("set=2")
        driver.frames(600)
        capture("common_title")
        hold(driver, KEYS["A"], 2)
        driver.frames(120)
        capture("game_selection")
        if part == "part2":
            hold(driver, KEYS["DOWN"], 2)
            driver.frames(30)
            capture("part2_selected")
        # Release all buttons at selection, then make a fresh chord+A press.
        driver.cmd("keys 0")
        driver.frames(30)
        driver.cmd(f"keys {CHORD}")
        driver.frames(2)
        driver.cmd(f"keys {CHORD | KEYS['A']}")
        driver.frames(2)
        capture("chord_a_held")
        driver.cmd("keys 0")
        driver.frames(180)
        capture("after_chord")
        driver.frames(180)
        capture("settled")
    finally:
        driver.close()
    rows = watch.read_text().splitlines()
    target_count = sum(any(f"addr={a:08X}" in row for a in range(0x08804FC8,0x08804FD0)) for row in rows)
    control_count = sum(any(f"addr={a:08X}" in row for a in (control,control+1)) for row in rows)
    receipt = {"rom_sha256": ROM_SHA, "part": part,
               "save_source_sha256": SAVE_SHA, "private_save_sha256_after": sha(save),
               "cheat_tainted": True, "target_range": "0x08804FC8..0x08804FCF",
               "control_range": f"0x{control:08X}..0x{control+1:08X}",
               "target_reads": target_count, "control_reads": control_count,
               "emulator_exit_code": driver.proc.returncode, "events": events}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt), flush=True)


def main():
    assert sha(ROM) == ROM_SHA
    assert sha(SAVE_SOURCE) == SAVE_SHA
    OUT.mkdir(parents=True, exist_ok=True)
    for part in ("part1", "part2"):
        run(part)


if __name__ == "__main__":
    main()
