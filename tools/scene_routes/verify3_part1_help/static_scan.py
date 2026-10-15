"""Bound the Part 1 compact-help menu graph in the fixed b32r5 ROM."""
import hashlib
import json
import struct
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROM = ROOT / "output/game_wars_korean_full.gba"
OUT = ROOT / "temp/release_C/verify3/help_menu_graph.json"
EXPECTED = "7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a"
BASE = 0x08000000
ROOT_TABLE = 0x08DEFFC4
DETACHED = 0x08DF01A4
TARGET_CODES = {0, 5, 6, 16, 17, 18, 19}

blob = ROM.read_bytes()
assert hashlib.sha256(blob).hexdigest() == EXPECTED


def word(off):
    return struct.unpack_from("<I", blob, off)[0]


def table(addr):
    assert 0x08DEFFC4 <= addr < 0x08DF02A8, hex(addr)
    entries = []
    for n in range(40):
        off = addr - BASE + n * 20
        code = blob[off]
        if code == 0xFF:
            return entries
        assert blob[off + 1:off + 4] == b"\0\0\0", hex(off)
        cb = word(off + 4)
        assert 0x08B3E700 <= cb < 0x08B3EC00 and cb & 1, (hex(off), hex(cb))
        entries.append({"address": f"0x{BASE + off:08X}", "code": code,
                        "callback": f"0x{cb:08X}",
                        "child": f"0x{word(off + 12):08X}" if word(off + 12) else None,
                        "back": f"0x{word(off + 16):08X}" if word(off + 16) else None})
    raise AssertionError("missing table sentinel")


queue = deque([ROOT_TABLE])
seen = {}
while queue:
    addr = queue.popleft()
    if addr in seen:
        continue
    seen[addr] = table(addr)
    for entry in seen[addr]:
        for field in ("child", "back"):
            ptr = entry[field]
            if ptr:
                queue.append(int(ptr, 16))

reachable = sorted({e["code"] for rows in seen.values() for e in rows})
detached = table(DETACHED)
ptr = struct.pack("<I", DETACHED)
exact_refs = []
start = 0
while (at := blob.find(ptr, start)) != -1:
    exact_refs.append(f"0x{BASE + at:08X}")
    start = at + 1

target_node_candidates = {str(code): [] for code in sorted(TARGET_CODES)}
for off in range(0, len(blob) - 20, 4):
    code = blob[off]
    if code not in TARGET_CODES or blob[off + 1:off + 4] != b"\0\0\0":
        continue
    cb = word(off + 4)
    if 0x08B3E700 <= cb < 0x08B3EC00 and cb & 1:
        target_node_candidates[str(code)].append(f"0x{BASE + off:08X}")

report = {
    "rom_sha256": EXPECTED,
    "root": f"0x{ROOT_TABLE:08X}",
    "reachable_codes": reachable,
    "target_codes_absent_from_root_graph": sorted(TARGET_CODES - set(reachable)),
    "reachable_tables": {f"0x{k:08X}": v for k, v in sorted(seen.items())},
    "detached_table": {"address": f"0x{DETACHED:08X}", "entries": detached,
                       "exact_pointer_references_in_rom": exact_refs},
    "full_rom_target_node_candidates": target_node_candidates,
    "scope": "Static ROM menu-node graph from root and +12/+16 edges; cannot rule out dynamic RAM construction.",
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"table_count": len(seen), "reachable_codes": reachable,
                  "target_codes_absent": sorted(TARGET_CODES - set(reachable)),
                  "detached_refs": exact_refs,
                  "target_node_candidates": target_node_candidates}))
