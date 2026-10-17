#!/usr/bin/env python3
"""SHA-pinned b39 two-core step driver. Tokens match verify4 bios_nav plus w16/w32."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/scene_routes/verify4_link"))
import biolink as b  # noqa: E402

b.ROM = ROOT / "output/game_wars_korean_candidate_20261017_b39.gba"
b.ROM_SHA = "7e00df656ffe7b1b0b8b236c24e30c178467860f8ff92e2072071a0497c7f217"


def run(out, tokens):
    out = Path(out).resolve()
    link = b.Link(out)
    try:
        for token in tokens:
            op, _, arg = token.partition(":")
            if op == "link":
                link.cmd(f"link {arg}")
            elif op in ("load", "loadc", "save", "savec"):
                player = int(op.endswith("c"))
                verb = "loadstate" if op.startswith("load") else "savestate"
                path = Path(arg)
                link.cmd(f"{verb} {player} {path if path.is_absolute() else ROOT / path}")
            elif op == "wait":
                link.cmd(f"frames {int(arg)}")
            elif op == "shot":
                link.capture(arg, 0)
            elif op == "cshot":
                link.capture(arg, 1, sync=True)
            elif op in ("w16", "w32"):
                player, addr, value = arg.split(":")
                link.cmd(f"{op} {player} {addr} {value}")
            elif op == "dump":
                player, addr, length, name = arg.split(":")
                link.cmd(f"dumpmem {player} {addr} {length} {out / name}")
            elif op == "ckey":
                key, hold, release = arg.split(":")
                link.press(key, int(hold), int(release), player=1)
            else:
                hold, release = arg.split(":")
                link.press(op, int(hold), int(release))
        link.cmd("status")
        link.cmd("sio")
    finally:
        b.finish_checked(link, {"route": "VERIFY-5 b39 paired step", "tokens": tokens,
                                "cheat_tainted": False})


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2:])
