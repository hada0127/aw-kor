#!/usr/bin/env python3
"""Identify which embedded b35 MultiBoot payload a client EWRAM dump holds.

Usage: payload_id.py CLIENT_EWRAM.bin [OUT.json]
Compares the dump (loaded at 0x02000000) against the stage-one image and the
four embedded P2 payloads, and reports exact-match lengths plus the client
EWRAM addresses of the day-banner sheets for the matching payload.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROM = ROOT / "output/game_wars_korean_candidate_20261015_b35.gba"
REGIONS = {
    "stage1": (0x8FED9C, 0x902A8C),
    "payload0": (0x90DC7C, 0x9463FC),
    "payload1": (0x9463FC, 0x9463FC + 0x388A4),
    "payload2": (0x97ECA0, 0x97ECA0 + 0x388A4),
    "payload3": (0x9B7544, 0x9B7544 + 0x388A4),
}
SHEETS = {"payload0": (0x92DF84, 0x92EB5C), "payload1": (0x966C0C, 0x9677E4),
          "payload2": (0x99F4B0, 0x9A0088), "payload3": (0x9D7D54, 0x9D892C)}


def main():
    rom = ROM.read_bytes()
    dump = Path(sys.argv[1]).read_bytes()
    result = {"dump": sys.argv[1], "dump_sha256": hashlib.sha256(dump).hexdigest(), "regions": {}}
    for name, (a, b) in REGIONS.items():
        img = rom[a:b]
        n = min(len(img), len(dump))
        same = sum(1 for i in range(n) if img[i] == dump[i])
        prefix = 0
        while prefix < n and img[prefix] == dump[prefix]:
            prefix += 1
        entry = {"rom_range": [hex(a), hex(b)], "length": len(img), "equal_bytes": same,
                 "exact_prefix": prefix, "full_match": dump[:len(img)] == img}
        probe = img[0x100:0x140]
        found = dump.find(probe)
        entry["probe_0x100_found_at"] = hex(0x02000000 + found - 0x100) if found >= 0 else None
        if name in SHEETS:
            entry["client_sheet_addrs"] = [hex(0x02000000 + s - a) for s in SHEETS[name]]
            entry["rom_sheets"] = [hex(s) for s in SHEETS[name]]
        result["regions"][name] = entry
    text = json.dumps(result, indent=2)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
