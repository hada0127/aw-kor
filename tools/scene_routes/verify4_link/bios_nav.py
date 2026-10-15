#!/usr/bin/env python3
"""Step-wise host/linked navigation for the BIOS-linked harness.

Usage: bios_nav.py OUTDIR TOKEN...
Tokens (executed in order):
  link:on|off             schedule client with host (off = host only)
  load:FILE / save:FILE   host savestate (player 0)
  loadc:FILE / savec:FILE client savestate (player 1)
  KEY[+KEY]:HOLD:REL      host key press (KEY from A,B,START,SELECT,UP,DOWN,LEFT,RIGHT,L,R)
  ckey:KEY:HOLD:REL       client key press
  wait:N                  advance N host frames
  shot:NAME / cshot:NAME  capture host / client (client capture is frame-synced)
  watch:P:ADDR:LEN:r|w|a:FILE   read/write watch on player P
  siotrace:FILE
  dump:P:ADDR:LEN:NAME    dump player memory to OUTDIR/NAME
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from biolink import Link, ROOT  # noqa: E402


def main():
    out = Path(sys.argv[1])
    if not out.is_absolute():
        out = ROOT / out
    tokens = sys.argv[2:]
    L = Link(out)
    extra = {"tokens": tokens, "cheat_tainted": False, "route_completed": False}
    try:
        for tok in tokens:
            kind, _, rest = tok.partition(":")
            if kind == "link":
                L.cmd(f"link {rest}")
            elif kind in ("load", "save", "loadc", "savec"):
                player = 1 if kind.endswith("c") else 0
                verb = "loadstate" if kind.startswith("load") else "savestate"
                path = Path(rest) if Path(rest).is_absolute() else ROOT / rest
                L.cmd(f"{verb} {player} {path}")
            elif kind == "wait":
                L.cmd(f"frames {int(rest)}")
            elif kind == "shot":
                L.capture(rest, 0)
            elif kind == "cshot":
                L.capture(rest, 1, sync=True)
            elif kind == "watch":
                p, addr, ln, mode, path = rest.split(":")
                path = Path(path) if Path(path).is_absolute() else (out / path if path != "KEEP" else path)
                L.cmd(f"watchaddr {p} {addr} {ln} {mode} {path}")
            elif kind == "siotrace":
                L.cmd(f"siotrace {out / rest}")
            elif kind == "dump":
                p, addr, ln, path = rest.split(":")
                L.cmd(f"dumpmem {p} {addr} {ln} {out / path}")
            elif kind == "cmd":
                raise ValueError("raw harness commands are unavailable in the clean navigation driver")
            elif kind == "ckey":
                key, hold, rel = rest.split(":")
                L.press(key, int(hold), int(rel), player=1)
            else:
                hold, _, rel = rest.partition(":")
                L.press(kind, int(hold or 2), int(rel or 6))
        L.cmd("status")
        L.cmd("sio")
        extra['route_completed'] = True
    finally:
        L.finish(extra)


if __name__ == "__main__":
    main()
