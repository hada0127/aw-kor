#!/usr/bin/env python3
"""Exploratory, cheat-tainted P2 EWRAM-program direct boot; no BIOS transfer."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from qa_visual_regions import raw_to_png

ROM = ROOT / "output/game_wars_korean_candidate_20261015_b35.gba"
CLIENT = ROOT / "temp/release_C/verify4/client_b35.bin"
HARNESS = ROOT / "temp/release_C/verify4/mgba_link_harness"
OUT = ROOT / "temp/release_C/verify4/direct_pair_map1"
EXPECT_SHA = "7e4a3a9e6602b3fe1b82853420ee6ff46ed43b5c6ef2f0d058b71b97eb1c0a36"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert sha(ROM) == EXPECT_SHA
    OUT.mkdir(parents=True, exist_ok=True)
    transcript = []
    shots = {}
    with (OUT / "stderr.log").open("w") as err:
        proc = subprocess.Popen([str(HARNESS), str(ROM), "-", str(OUT / "emulator.log")],
                                cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=err, text=True, bufsize=1)
        def cmd(line):
            proc.stdin.write(line + "\n"); proc.stdin.flush()
            answer = proc.stdout.readline().strip()
            if line == "sio":
                answer += " | " + proc.stdout.readline().strip()
            transcript.append({"command": line, "response": answer})
            print(answer, flush=True)
            if not answer.startswith("OK "):
                raise RuntimeError((line, answer))
            return answer
        def shot(name, player):
            raw = OUT / f"{name}_p{player}.raw"
            png = raw.with_suffix(".png")
            cmd(f"shot {player} {raw}")
            raw_to_png(raw, png)
            shots[f"{name}_p{player}"] = {"png": str(png.relative_to(ROOT)), "sha256": sha(png)}
        try:
            cmd(f"watchaddr 0 08804FC8 8 r {OUT / 'host_row_watch.log'}")
            cmd("watchaddr 0 02020308 4 r KEEP")
            cmd("watchaddr 0 02020EE0 4 r KEEP")
            cmd(f"injectbin 0 02000000 {CLIENT}")
            cmd("w32 0 0203BFFC 485153CD")
            cmd("setreg 0 pc 02000000")
            cmd(f"watchaddr 1 02020308 4 r {OUT / 'client_sheet_watch.log'}")
            cmd("watchaddr 1 02020EE0 4 r KEEP")
            cmd(f"loadmb {CLIENT}")
            cmd("frames 1")
            shot("frame1", 0); shot("frame1", 1)
            cmd("frames 30")
            shot("frame31", 0); shot("frame31", 1)
            cmd("frames 150")
            shot("frame181", 0); shot("frame181", 1)
            cmd("keys 0 1")
            cmd("frames 2")
            cmd("keys 0 0")
            cmd("frames 180")
            shot("after_map_a", 0); shot("after_map_a", 1)
            cmd("status"); cmd("sio"); cmd("regs 0"); cmd("regs 1")
            cmd(f"dumpmem 0 02000000 231296 {OUT / 'host_program.bin'}")
            cmd("quit")
        finally:
            if proc.poll() is None:
                proc.stdin.close()
            code=proc.wait(timeout=10)
    receipt = {"rom_sha256": EXPECT_SHA, "client_payload_sha256": sha(CLIENT),
               "host_injected_program_sha256": sha(OUT / "host_program.bin") if (OUT / "host_program.bin").exists() else None,
               "cheat_tainted": True, "native_multiboot_transfer": False,
               "emulator_exit_code": code, "screens": shots, "transcript": transcript}
    (OUT / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("EXIT", code, flush=True)

if __name__ == "__main__":
    main()
