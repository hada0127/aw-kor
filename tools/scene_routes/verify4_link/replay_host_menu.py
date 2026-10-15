#!/usr/bin/env python3
"""Replay the existing cold Part 2 menu route on b35's host core.

The client core has no cartridge and is not run before the selected link menu.
This navigates to the single-pak submenu, then stops before initiating a send.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from qa_visual_regions import KEYS, raw_to_png

ROM = ROOT / "output/game_wars_korean_candidate_20261015_b35.gba"
ROM_SHA = "7e4a3a9e6602b3fe1b82853420ee6ff46ed43b5c6ef2f0d058b71b97eb1c0a36"
HARNESS = ROOT / "temp/release_C/verify4/mgba_link_harness"
OUT = ROOT / "temp/release_C/verify4/host_menu"
INPUT = ROOT / "temp/release_C/inputs/B/B23_p2menu.txt"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(proc, line):
    proc.stdin.write(line + "\n")
    proc.stdin.flush()
    reply = proc.stdout.readline().strip()
    if not reply.startswith("OK "):
        raise RuntimeError(f"{line!r} -> {reply!r}; exit={proc.poll()}")
    return reply


def main():
    assert sha(ROM) == ROM_SHA
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "stderr.log").open("w") as stderr:
        proc = subprocess.Popen([str(HARNESS), str(ROM), "-", str(OUT / "emulator.log")],
                                cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=stderr, text=True, bufsize=1)
        events = []
        try:
            # Stop at the first entry into the Part 2 link submenu. The
            # existing route's earlier, independently reviewed inputs are reused.
            for line_number, raw in enumerate(INPUT.read_text().splitlines(), 1):
                fields = raw.split()
                if not fields or fields[0] == "note":
                    continue
                key = fields[0]
                if key not in KEYS and key != "NONE":
                    raise ValueError(f"unknown key on line {line_number}: {key}")
                if line_number == 14:
                    # On b35 the carried route lands on Trial after the
                    # three DOWNs. Communication is one more row below.
                    command(proc, f"keys 0 {KEYS['DOWN']}")
                    command(proc, "frames1 0 90")
                    command(proc, "keys 0 0")
                    command(proc, "frames1 0 6")
                    raw_path=OUT / "extra_down_link_focus.raw"
                    png_path=raw_path.with_suffix(".png")
                    command(proc,f"shot 0 {raw_path}")
                    raw_to_png(raw_path,png_path)
                    events.append({"line": "extra_down", "key": "DOWN", "hold": 90,
                                   "release": 6, "frame": command(proc,"status"),
                                   "png": str(png_path.relative_to(ROOT)), "png_sha256": sha(png_path)})
                    print(json.dumps(events[-1]), flush=True)
                hold = int(fields[1]); release = int(fields[2]) if len(fields)>2 else 0
                if key != "NONE":
                    command(proc, f"keys 0 {KEYS[key]}")
                    command(proc, f"frames1 0 {hold}")
                else:
                    command(proc, f"frames1 0 {hold}")
                command(proc, "keys 0 0")
                if release:
                    command(proc, f"frames1 0 {release}")
                raw_path = OUT / f"line{line_number:02}_{key}.raw"
                png_path = raw_path.with_suffix(".png")
                command(proc, f"shot 0 {raw_path}")
                raw_to_png(raw_path,png_path)
                events.append({"line": line_number, "key": key, "hold": hold,
                               "release": release, "frame": command(proc,"status"),
                               "png": str(png_path.relative_to(ROOT)), "png_sha256": sha(png_path)})
                print(json.dumps(events[-1]), flush=True)
                if key == "A" and line_number > 10:
                    # First A after the three DOWNs is the link submenu.
                    break
            state = OUT / "host_menu.ss0"
            command(proc,f"savestate 0 {state}")
            command(proc,"quit")
        finally:
            if proc.poll() is None:
                proc.stdin.close()
            exit_code = proc.wait(timeout=15)
    result = {"rom_sha256": ROM_SHA, "input_route": str(INPUT.relative_to(ROOT)),
              "client_state": "no cartridge; core not stepped", "emulator_exit_code": exit_code,
              "host_menu_state": str(state.relative_to(ROOT)),
              "host_menu_state_sha256": sha(state), "events": events}
    (OUT / "receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    print("EXIT",exit_code,"EVENTS",len(events))


if __name__ == "__main__":
    main()
