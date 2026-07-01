#!/usr/bin/env python3
"""Part 1 operation-room dialogue bitmap safety gate.

The operation-room dialogue renderer is more fragile than the broad story
dialogue path: byte-fit alone can still leave a row exactly full, and ASCII
punctuation at the end of a full slot has produced a broken-looking glyph on
real mGBA screenshots.  Keep the known sensitive tutorial pair short,
level-0, and with enough tail padding in the shipped ROM bytes.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_korean_full import ADDRESS_TEXT_OVERRIDES, SYLCODE, encode_fit, load_slots  # noqa: E402

ROM = ROOT / "output" / "game_wars_korean_full.gba"
OUT = ROOT / "temp" / "part1_operation_dialogue_qa.json"

TARGETS = {
    0x00DF68F6: {
        "label": "operation-room final test line 1",
        "max_encoded_len": 28,
        "max_half_cells": 24,
    },
    0x00DF691D: {
        "label": "operation-room final test line 2",
        "max_encoded_len": 26,
        "max_half_cells": 24,
    },
}
FORBIDDEN_SOURCE_CHARS = set(",.!?:;()[]{}\"'")
ALLOWED_TAIL_BYTES = {0x00, 0x20}


def encoded_half_cells(raw: bytes) -> int:
    i = 0
    cur = 0
    best = 0
    while i < len(raw):
        b = raw[i]
        if b in (0x00, 0x0A):
            best = max(best, cur)
            cur = 0
            i += 1
        elif 0x81 <= b <= 0xE2 and i + 1 < len(raw):
            cur += 2
            i += 2
        elif 0x20 <= b <= 0x7E:
            cur += 1
            i += 1
        else:
            i += 1
    return max(best, cur)


def active_has_single_byte_printable(raw: bytes) -> bool:
    i = 0
    while i < len(raw):
        b = raw[i]
        if b in (0x00, 0x0A):
            i += 1
        elif 0x81 <= b <= 0xE2 and i + 1 < len(raw):
            i += 2
        elif 0x20 <= b <= 0x7E:
            return True
        else:
            i += 1
    return False


def main() -> int:
    issues: list[dict] = []
    rows: list[dict] = []
    slots = load_slots()
    syl_to_code = {s: int(code, 16) for s, code in json.load(open(SYLCODE, encoding="utf-8")).items()}
    rom = ROM.read_bytes() if ROM.exists() else None
    if rom is None:
        issues.append({"type": "missing_rom", "path": str(ROM.relative_to(ROOT))})

    for addr, cfg in TARGETS.items():
        text = ADDRESS_TEXT_OVERRIDES.get(addr, "")
        slot = slots.get(addr, 0)
        row = {
            "address": f"0x{addr:08X}",
            "label": cfg["label"],
            "text": text,
            "slot": slot,
        }
        if not text:
            issues.append({"type": "missing_address_override", "address": row["address"]})
            rows.append(row)
            continue
        forbidden = sorted(ch for ch in set(text) if ch in FORBIDDEN_SOURCE_CHARS)
        if forbidden:
            issues.append({"type": "forbidden_source_punctuation", "address": row["address"], "chars": forbidden})
        if not slot:
            issues.append({"type": "missing_slot", "address": row["address"]})
            rows.append(row)
            continue

        enc, level = encode_fit(text, slot, syl_to_code, Counter(), addr)
        row["fit_level"] = level
        if enc is None:
            issues.append({"type": "encode_fit_failed", "address": row["address"], "slot": slot, "text": text})
            rows.append(row)
            continue

        cells = encoded_half_cells(enc)
        row["encoded_len"] = len(enc)
        row["encoded_half_cells"] = cells
        row["encoded_hex"] = enc.hex()
        row["single_byte_printable_in_active_payload"] = active_has_single_byte_printable(enc)
        if level != 0:
            issues.append({"type": "non_level0_fit", "address": row["address"], "level": level})
        if len(enc) > cfg["max_encoded_len"]:
            issues.append({
                "type": "encoded_len_over_limit",
                "address": row["address"],
                "encoded_len": len(enc),
                "limit": cfg["max_encoded_len"],
            })
        if cells > cfg["max_half_cells"]:
            issues.append({
                "type": "encoded_width_over_limit",
                "address": row["address"],
                "half_cells": cells,
                "limit": cfg["max_half_cells"],
            })
        if len(enc) >= slot:
            issues.append({
                "type": "no_tail_padding_margin",
                "address": row["address"],
                "encoded_len": len(enc),
                "slot": slot,
            })
        if row["single_byte_printable_in_active_payload"]:
            issues.append({
                "type": "single_byte_printable_in_active_payload",
                "address": row["address"],
                "encoded": enc.hex(),
            })
        if rom is not None:
            actual = rom[addr : addr + slot]
            tail = actual[len(enc) :]
            row["rom_prefix_matches"] = actual.startswith(enc)
            row["tail_padding_len"] = len(tail)
            row["tail_padding_ok"] = all(b in ALLOWED_TAIL_BYTES for b in tail)
            if not row["rom_prefix_matches"]:
                issues.append({
                    "type": "rom_prefix_mismatch",
                    "address": row["address"],
                    "expected_prefix": enc.hex(),
                    "actual": actual.hex(),
                })
            if not row["tail_padding_ok"]:
                issues.append({"type": "bad_tail_padding", "address": row["address"], "tail": tail.hex()})
        rows.append(row)

    report = {
        "target_count": len(TARGETS),
        "issue_count": len(issues),
        "forbidden_source_chars": sorted(FORBIDDEN_SOURCE_CHARS),
        "rows": rows,
        "issues": issues,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "target_count": report["target_count"],
        "issue_count": report["issue_count"],
        "report": str(OUT.relative_to(ROOT)),
    }, ensure_ascii=False))
    if issues:
        for issue in issues[:20]:
            print(f"[FAIL] {issue}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
