#!/usr/bin/env python3
"""Static code-context scan for E12 compact display xrefs.

`analyze_compact_display_xrefs.py` proves that compact display targets have
ROM pointer references. This helper asks the next question: which nearby
Thumb/ARM instructions load those pointer tables or table slots?

The result is still only a reachability lead. It should feed breakpoint/watch
probes, not be counted as visual evidence by itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import capstone
from capstone.arm_const import ARM_OP_MEM, ARM_REG_PC

ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "output" / "game_wars_korean_full.gba"
XREF_JSON = ROOT / "data" / "compact_display_xref_analysis.json"
OUT_JSON = ROOT / "data" / "compact_display_code_context.json"

GBA_BASE = 0x08000000
THUMB_WINDOW_BEFORE = 0x80
ARM_WINDOW_BEFORE = 0x100
WINDOW_AFTER = 0x20

KNOWN_DICTIONARY_LITERAL_OFFSETS = [
    0x003806FC,
    0x00381300,
    0x00B3C1F8,
]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def parse_hex(value: str) -> int:
    return int(value, 16)


def gba_addr(offset: int) -> int:
    return GBA_BASE + offset


def rom_offset(addr: int) -> int:
    if GBA_BASE <= addr < 0x0A000000:
        return addr - GBA_BASE
    return addr


def read_word(rom: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 4 > len(rom):
        return None
    return int.from_bytes(rom[offset:offset + 4], "little")


def iter_refs(rom: bytes, value: int) -> list[int]:
    pat = value.to_bytes(4, "little")
    refs: list[int] = []
    pos = rom.find(pat)
    while pos != -1:
        refs.append(pos)
        pos = rom.find(pat, pos + 1)
    return refs


def literal_addr_for(insn, mode: str) -> int | None:
    if insn.mnemonic != "ldr":
        return None
    for op in insn.operands:
        if op.type != ARM_OP_MEM or op.mem.base != ARM_REG_PC:
            continue
        if mode == "thumb":
            return ((insn.address + 4) & ~3) + op.mem.disp
        return insn.address + 8 + op.mem.disp
    return None


def disasm_window(rom: bytes, literal_offset: int, mode: str) -> list:
    if mode == "thumb":
        before = THUMB_WINDOW_BEFORE
        cs_mode = capstone.CS_MODE_THUMB
        align = 2
    else:
        before = ARM_WINDOW_BEFORE
        cs_mode = capstone.CS_MODE_ARM
        align = 4
    start = max(0, literal_offset - before)
    start -= start % align
    end = min(len(rom), literal_offset + WINDOW_AFTER)
    md = capstone.Cs(capstone.CS_ARCH_ARM, cs_mode)
    md.detail = True
    return list(md.disasm(rom[start:end], gba_addr(start)))


def find_literal_loads(rom: bytes, literal_offset: int) -> list[dict]:
    literal_gba = gba_addr(literal_offset)
    out: list[dict] = []
    for mode in ("thumb", "arm"):
        for insn in disasm_window(rom, literal_offset, mode):
            target = literal_addr_for(insn, mode)
            if target != literal_gba:
                continue
            out.append({
                "mode": mode,
                "pc": f"0x{insn.address:08X}",
                "offset": f"0x{rom_offset(insn.address):08X}",
                "mnemonic": insn.mnemonic,
                "op_str": insn.op_str,
                "literal_offset": f"0x{literal_offset:08X}",
                "literal_address": f"0x{literal_gba:08X}",
            })
    return out


def find_thumb_function_start(rom: bytes, insn_offset: int) -> int | None:
    start = max(0, insn_offset - 0x180)
    start -= start % 2
    for off in range(insn_offset & ~1, start - 1, -2):
        half = int.from_bytes(rom[off:off + 2], "little")
        # push {..., lr}; common Thumb function prologue.
        if (half & 0xFF00) == 0xB500:
            return off
    return None


def collect_literal_entries(xref: dict, rom: bytes) -> list[dict]:
    entries_by_key: dict[tuple[str, int, int | None], dict] = {}

    def add(group_id: str, target_addr: int | None, ref_offset: int, ref_kind: str, target_text: str = "") -> None:
        key = (group_id, ref_offset, target_addr)
        word = read_word(rom, ref_offset)
        row = entries_by_key.setdefault(key, {
            "group_id": group_id,
            "target_address": f"0x{target_addr:08X}" if target_addr is not None else None,
            "target_text": target_text,
            "ref_offset": f"0x{ref_offset:08X}",
            "ref_address": f"0x{gba_addr(ref_offset):08X}",
            "ref_kind": ref_kind,
            "word": f"0x{word:08X}" if word is not None else None,
            "word_rom_offset": f"0x{rom_offset(word):08X}" if word is not None and GBA_BASE <= word < 0x0A000000 else None,
            "source_count": 0,
        })
        row["source_count"] += 1

    for group in xref.get("groups", []):
        group_id = group.get("id") or "unknown"
        for target in group.get("targets", []):
            target_addr = parse_hex(target["address"])
            text = target.get("ko") or target.get("ja") or ""
            for value in target.get("external_pointer_refs", []):
                add(group_id, target_addr, parse_hex(value), "target_pointer_ref", text)
            for value in target.get("second_level_refs", []):
                add(group_id, target_addr, parse_hex(value), "second_level_ref", text)

    for off in KNOWN_DICTIONARY_LITERAL_OFFSETS:
        add("known_compact_dictionary_literals", None, off, "known_dictionary_literal")

    return sorted(entries_by_key.values(), key=lambda row: (row["group_id"], row["ref_offset"], row["target_address"] or ""))


def enrich_entry(rom: bytes, entry: dict) -> dict:
    ref_offset = parse_hex(entry["ref_offset"])
    loads = find_literal_loads(rom, ref_offset)
    for load in loads:
        insn_off = parse_hex(load["offset"])
        fn = find_thumb_function_start(rom, insn_off) if load["mode"] == "thumb" else None
        load["function_start"] = f"0x{gba_addr(fn):08X}" if fn is not None else None
        load["function_start_offset"] = f"0x{fn:08X}" if fn is not None else None
    entry["literal_loads"] = loads
    return entry


def likely_table_heads(entries: list[dict], rom: bytes) -> list[dict]:
    """Find table starts that themselves have pointer references nearby."""
    heads: dict[int, dict] = {}
    for entry in entries:
        word = entry.get("word")
        if not word:
            continue
        value = int(word, 16)
        off = rom_offset(value)
        if not (0 <= off < len(rom)):
            continue
        # If this literal points to a compact table, search direct refs to that
        # table head. This catches B84's 0x08DF2B54 table.
        for ref in iter_refs(rom, value):
            heads.setdefault(ref, {
                "table_head_value": f"0x{value:08X}",
                "table_head_offset": f"0x{off:08X}",
                "ref_offset": f"0x{ref:08X}",
                "ref_address": f"0x{gba_addr(ref):08X}",
                "word": f"0x{read_word(rom, ref):08X}",
                "source_count": 0,
            })["source_count"] += 1
    out = []
    for row in sorted(heads.values(), key=lambda item: item["ref_offset"]):
        out.append(enrich_entry(rom, {
            "group_id": "derived_table_head_refs",
            "target_address": None,
            "target_text": "",
            "ref_kind": "derived_table_head_ref",
            **row,
        }))
    return out


def summarize(entries: list[dict], derived: list[dict]) -> dict:
    by_group = Counter(row["group_id"] for row in entries)
    load_by_group = Counter(
        row["group_id"]
        for row in entries
        if row.get("literal_loads")
    )
    breakpoint_pcs = {}
    for row in entries + derived:
        for load in row.get("literal_loads", []):
            pc = load["pc"]
            if pc not in breakpoint_pcs:
                breakpoint_pcs[pc] = {
                    "pc": pc,
                    "mode": load["mode"],
                    "function_start": load.get("function_start"),
                    "sources": [],
                }
            breakpoint_pcs[pc]["sources"].append({
                "group_id": row["group_id"],
                "ref_offset": row["ref_offset"],
                "ref_kind": row["ref_kind"],
                "target_address": row.get("target_address"),
                "target_text": row.get("target_text"),
                "word": row.get("word"),
            })
    functions = defaultdict(set)
    for bp in breakpoint_pcs.values():
        if bp.get("function_start"):
            functions[bp["function_start"]].add(bp["pc"])
    return {
        "literal_entry_count": len(entries),
        "derived_table_head_ref_count": len(derived),
        "literal_entries_by_group": dict(sorted(by_group.items())),
        "literal_entries_with_loads_by_group": dict(sorted(load_by_group.items())),
        "breakpoint_candidate_count": len(breakpoint_pcs),
        "breakpoint_candidates": [
            {**row, "source_count": len(row["sources"])}
            for row in sorted(breakpoint_pcs.values(), key=lambda item: item["pc"])
        ],
        "function_candidates": [
            {"function_start": fn, "breakpoint_pcs": sorted(pcs)}
            for fn, pcs in sorted(functions.items())
        ],
    }


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=str(ROM))
    ap.add_argument("--xref-json", default=str(XREF_JSON))
    ap.add_argument("--out-json", default=str(OUT_JSON))
    args = ap.parse_args()

    rom_path = resolve(args.rom)
    xref_path = resolve(args.xref_json)
    out_json = resolve(args.out_json)
    if not rom_path.exists():
        raise SystemExit(f"ROM 없음: {rom_path}")
    if not xref_path.exists():
        raise SystemExit(f"xref JSON 없음: {xref_path}")

    rom = rom_path.read_bytes()
    xref = load(xref_path)
    entries = [enrich_entry(rom, entry) for entry in collect_literal_entries(xref, rom)]
    derived = likely_table_heads(entries, rom)
    report = {
        "tool": "tools/analyze_compact_display_code_context.py",
        "rom": rel(rom_path),
        "rom_sha256": sha256(rom_path),
        "git_commit": git_commit(),
        "source": rel(xref_path),
        "summary": summarize(entries, derived),
        "literal_entries": entries,
        "derived_table_head_refs": derived,
        "strict_note": (
            "This is static code-context evidence only. A candidate breakpoint "
            "must still hit on a real route and expose target addresses or "
            "source reads before it counts toward E12 visual evidence."
        ),
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({
        "out_json": rel(out_json),
        "rom_sha256": report["rom_sha256"],
        "literal_entry_count": report["summary"]["literal_entry_count"],
        "derived_table_head_ref_count": report["summary"]["derived_table_head_ref_count"],
        "breakpoint_candidate_count": report["summary"]["breakpoint_candidate_count"],
        "function_candidate_count": len(report["summary"]["function_candidates"]),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
