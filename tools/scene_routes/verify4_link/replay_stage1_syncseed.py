#!/usr/bin/env python3
"""Cold b35 one-pak route, then a bounded extracted-client lockstep probe."""
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
CLIENT = ROOT / "temp/release_C/verify4/stage1_b35.bin"
HARNESS = ROOT / "temp/release_C/verify4/mgba_link_harness"
OUT = ROOT / "temp/release_C/verify4/cold_pair_stage1_syncseed"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert sha(ROM) == ROM_SHA
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "stderr.log").open("w") as stderr:
        proc = subprocess.Popen([str(HARNESS), str(ROM), "-", str(OUT / "emulator.log")],
                                cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=stderr, text=True, bufsize=1)
        transcript = []

        def cmd(line):
            proc.stdin.write(line + "\n"); proc.stdin.flush()
            response=proc.stdout.readline().strip()
            if line == "sio":
                response += " | " + proc.stdout.readline().strip()
            transcript.append({"command": line, "response": response})
            print(response, flush=True)
            if not response.startswith("OK "):
                raise RuntimeError(f"{line!r}: {response!r}")
            return response

        def press(key, hold=2, release=6):
            cmd(f"keys 0 {KEYS[key]}")
            cmd(f"frames1 0 {hold}")
            cmd("keys 0 0")
            if release: cmd(f"frames1 0 {release}")

        def capture(name, player):
            raw=OUT / f"{name}_p{player}.raw"
            png=raw.with_suffix(".png")
            cmd(f"shot {player} {raw}")
            raw_to_png(raw,png)
            return {"path": str(png.relative_to(ROOT)), "sha256": sha(png)}

        screens={}
        try:
            cmd(f"watchaddr 0 08804FC8 8 r {OUT / 'host_row_watch.log'}")
            cmd("frames1 0 480")
            for key,hold in [("A",200),("START",200),("DOWN",120),("A",240),
                             ("START",240),("A",200),("DOWN",60),("DOWN",60),
                             ("DOWN",90),("DOWN",90),("A",120)]:
                press(key,hold)
            press("A",2,180)       # enter LINK MODE
            screens["link_mode"] = capture("link_mode",0)
            press("UP",2,90)       # one-pak row
            press("A",2,150)      # focus one-pak
            press("A",2,150)      # enter one-pak setup
            screens["onepak_setup"] = capture("onepak_setup",0)
            cmd("sio")
            cmd(f"dumpmem 0 02000000 231296 {OUT / 'preload_host_buffer.bin'}")
            cmd(f"watchaddr 1 02020308 4 r {OUT / 'client_sheet_watch.log'}")
            cmd("watchaddr 1 02020EE0 4 r KEEP")
            cmd(f"loadmb {CLIENT}")
            cmd("w16 1 04000134 0000")
            cmd("w16 1 04000128 6003")
            cmd("sio")
            cmd("frames 1")
            screens["client_frame1"] = capture("client_frame1",1)
            cmd("frames 200")
            screens["host_after6"] = capture("host_after6",0)
            screens["client_after6"] = capture("client_after6",1)
            cmd("status")
            cmd("sio")
            cmd("regs 0")
            cmd("regs 1")
            cmd(f"dumpmem 0 02000000 231296 {OUT / 'after_host_buffer.bin'}")
            cmd("quit")
        finally:
            if proc.poll() is None:
                proc.stdin.close()
            exit_code=proc.wait(timeout=10)
    result={"rom_sha256": ROM_SHA, "client_payload_sha256": sha(CLIENT),
            "client_provenance": "extracted from b35 ROM; HLE BIOS transfer bypassed",
            "cheat_tainted": True, "emulator_exit_code": exit_code,
            "screens": screens, "transcript": transcript}
    (OUT / "receipt.json").write_text(json.dumps(result,indent=2) + "\n")
    print("EXIT",exit_code,flush=True)


if __name__ == "__main__":
    main()
