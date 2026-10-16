#!/usr/bin/env python3
"""VERIFY-5: interrupt a cold-boot real-BIOS one-cart transfer on b37."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/scene_routes/verify4_link"))
import biolink as b  # noqa: E402

b.ROM = ROOT / "output/game_wars_korean_candidate_20261016_b37.gba"
b.ROM_SHA = "c8a9468cd0bb7673705f1d3a1532610ec32f17eb608fe25d0d586f4244dfa5e8"


def run(part: int, out: Path) -> None:
    link = b.Link(out)
    try:
        link.cmd("link off")
        link.cmd("frames 480")
        if part == 1:
            from qa_visual_regions import PART1_MENU_PRENAV, PART1_MENU_ADVANCE_A_PRESSES
            for key in PART1_MENU_PRENAV:
                link.press(key, 2, 120)
            for _ in range(PART1_MENU_ADVANCE_A_PRESSES):
                link.press("A", 2, 160)
            link.cmd("frames 10")
            link.press("UP", 2, 120)
            link.press("A", 2, 180)
            link.cmd("link on")
            link.press("UP", 2, 60)
            link.press("UP", 2, 60)
            link.press("A", 2, 400)
        else:
            for key, release in [("A", 200), ("START", 200), ("DOWN", 120),
                                 ("A", 240), ("START", 240), ("A", 200)]:
                link.press(key, 2, release)
            for _ in range(3):
                link.press("DOWN", 2, 40)
            link.press("A", 2, 180)
            link.cmd("link on")
            link.press("UP", 2, 60)
            link.press("A", 2, 400)
        link.capture("host_before", 0)
        link.capture("client_before", 1, sync=True)
        link.cmd(f"siotrace {out / 'sio_trace.log'}")
        link.press("START", 2, 10)
        transfer_frames = 250 if part == 1 else 500
        link.cmd(f"frames {transfer_frames}")
        link.capture("host_transfer", 0)
        link.capture("client_transfer", 1, sync=True)
        link.cmd("status")
        link.cmd("link off")
        for frames in (120, 360, 720, 1440):
            link.cmd(f"frames1 0 {frames}")
            link.capture(f"host_detached_{frames}", 0)
        for frames in (120, 360, 720, 1440):
            link.cmd(f"frames1 1 {frames}")
            link.capture(f"client_detached_{frames}", 1)
        link.cmd("status")
        link.cmd("sio")
    finally:
        b.finish_checked(link, {"route": f"VERIFY-5 Part {part} transfer interrupted by stopping opposite core",
                                "cheat_tainted": False, "client_detached_after_host_frames": transfer_frames,
                                "host_and_client_run_separately_after_detach": True})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("part", type=int, choices=(1, 2))
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    run(args.part, args.out.resolve())
