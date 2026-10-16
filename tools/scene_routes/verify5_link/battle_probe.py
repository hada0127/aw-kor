#!/usr/bin/env python3
"""VERIFY-5: continue b37's paired real-BIOS one-cart state into battle."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/scene_routes/verify4_link"))
import biolink as b  # noqa: E402

b.ROM = ROOT / "output/game_wars_korean_candidate_20261016_b37.gba"
b.ROM_SHA = "c8a9468cd0bb7673705f1d3a1532610ec32f17eb608fe25d0d586f4244dfa5e8"


def run(part: int, out: Path) -> None:
    src = ROOT / f"temp/release_C/rebind5/link/part{part}/transfer"
    link = b.Link(out)
    try:
        link.cmd("link off")
        link.cmd(f"loadstate 0 {src / 'host_end.ss0'}")
        link.cmd(f"loadstate 1 {src / 'client_end.ss0'}")
        link.cmd("link on")
        link.capture("host_select", 0)
        link.capture("client_select", 1, sync=True)
        if part == 1:
            link.press("START", 2, 30)
        else:
            link.press("A", 2, 30)
        for index, frames in enumerate((110, 120, 180, 300, 600)):
            link.cmd(f"frames {frames}")
            link.capture(f"host_{index:02d}", 0)
            link.capture(f"client_{index:02d}", 1, sync=True)
        link.cmd(f"savestate 0 {out / 'host_end.ss0'}")
        link.cmd(f"savestate 1 {out / 'client_end.ss0'}")
    finally:
        b.finish_checked(link, {"route": f"VERIFY-5 Part {part} link battle continuation",
                                "cheat_tainted": False})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("part", type=int, choices=(1, 2))
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    run(args.part, args.out.resolve())
