#!/usr/bin/env python3
"""VERIFY-4b step 1: cold b35 host -> Part 2 LINK MODE -> one-pak, client receives via real BIOS."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from biolink import Link, ROOT  # noqa: E402

OUT = ROOT / "temp/release_C/verify4b/onepak"


def main():
    L = Link(OUT)
    extra = {"cheat_tainted": False}
    try:
        L.cmd(f"siotrace {OUT / 'sio_trace.log'}")
        L.cmd(f"watchaddr 0 08804FC8 8 r {OUT / 'host_row_watch.log'}")
        L.cmd("frames 480")
        for key, hold in [("A", 200), ("START", 200), ("DOWN", 120), ("A", 240),
                          ("START", 240), ("A", 200), ("DOWN", 60), ("DOWN", 60),
                          ("DOWN", 90), ("DOWN", 90), ("A", 120)]:
            L.press(key, 2, hold)
        L.capture("mode_select", 0)
        L.press("A", 2, 180)
        L.capture("link_mode", 0)
        L.capture("client_before", 1, sync=True)
        L.press("UP", 2, 90)
        L.press("A", 2, 150)
        L.capture("onepak_focus", 0)
        L.press("A", 2, 150)
        L.capture("onepak_setup", 0)
        L.cmd("sio")
        L.cmd("status")
        for i in range(12):
            L.cmd("frames 100")
            L.capture(f"host_{i:02d}", 0)
            L.capture(f"client_{i:02d}", 1, sync=True)
            L.cmd("sio")
            L.cmd("regs 1")
        L.cmd("status")
    finally:
        L.finish(extra)


if __name__ == "__main__":
    main()
