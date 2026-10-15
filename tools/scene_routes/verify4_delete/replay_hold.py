#!/usr/bin/env python3
"""Keep the documented delete chord through game selection's transition."""
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
SOURCE = ROOT / "temp/release_C/rebind1/help/F_help_sweep/game.sav"
OUT = ROOT / "temp/release_C/verify4/delete_hold"
HARNESS = ROOT / "temp/mgbah_linux"
CHORD = KEYS["L"] | KEYS["RIGHT"] | KEYS["SELECT"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(part):
    out=OUT / part; out.mkdir(parents=True,exist_ok=True)
    private=out / "game.sav"; shutil.copyfile(SOURCE,private)
    before=sha(private)
    os.environ["AW_KOR_TEMP_DIR"]=str(out)
    d=MGBADriver(ROM,out,HARNESS,private)
    watch=out / "watch.log"
    shots=[]

    def capture(name):
        d.shot(name)
        shots.append({"name":name,"frame":d.cmd("framecounter"),
                      "png_sha256":sha(out / f"{name}.png"),
                      "watch_lines":len(watch.read_text().splitlines())})

    try:
        d.cmd(f"watchaddr 08804FC8 8 r {watch}")
        control=0x08DF29AA if part=="part1" else 0x08A34C2E
        d.cmd(f"watchaddr {control:08X} 2 r KEEP")
        d.frames(600)
        d.cmd(f"keys {KEYS['A']}");d.frames(2)
        d.cmd("keys 0");d.frames(120)
        capture("selection")
        if part=="part2":
            d.cmd(f"keys {KEYS['DOWN']}");d.frames(2)
            d.cmd("keys 0");d.frames(30)
            capture("part2_focus")
        d.cmd("keys 0");d.frames(30)
        d.cmd(f"keys {CHORD}");d.frames(2)
        d.cmd(f"keys {CHORD|KEYS['A']}");d.frames(2)
        d.cmd(f"dumpmem 04000130 2 {out / 'keyinput_held.bin'}")
        capture("chord_a")
        d.cmd(f"keys {CHORD}")
        for i,count in enumerate((20,40,60,60),1):
            d.frames(count)
            capture(f"held_{i}")
        d.cmd("keys 0");d.frames(180)
        capture("settled")
    finally:
        d.close()
    rows=watch.read_text().splitlines()
    result={"part":part,"rom_sha256":sha(ROM),"source_save_sha256":sha(SOURCE),
            "private_save_before_sha256":before,"private_save_after_sha256":sha(private),
            "cheat_tainted":True,"keyinput_held_hex":(out / "keyinput_held.bin").read_bytes().hex(),
            "target_reads":sum(any(f"addr={a:08X}" in line for a in range(0x08804FC8,0x08804FD0)) for line in rows),
            "control_reads":sum(any(f"addr={a:08X}" in line for a in (control,control+1)) for line in rows),
            "emulator_exit_code":d.proc.returncode,"shots":shots}
    (out / "receipt.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result),flush=True)


if __name__=="__main__":
    assert sha(ROM)=="7e4a3a9e6602b3fe1b82853420ee6ff46ed43b5c6ef2f0d058b71b97eb1c0a36"
    assert sha(SOURCE)=="d1210b1d8fe444a3cc84eb8ae272c0076375107f93ce97b37d786f0efc2e9d51"
    for part in ("part1","part2"):
        run(part)
