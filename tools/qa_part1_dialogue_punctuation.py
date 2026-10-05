#!/usr/bin/env python3
"""Gate Part 1 dialogue and Part 2 story payloads against unsafe punctuation.

The Part 1 dialogue renderer can treat standalone ASCII punctuation bytes as
stray bitmap fragments.  The safe path is two-byte SJIS punctuation, so shipped
These dialogue payloads must not contain standalone ASCII punctuation in their
active text bytes.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from dialogue_regions import PART1_DIALOG_RANGES, PART2_STORY_RANGES, is_part1_dialog_address, is_part2_story_address, needs_safe_dialogue_punctuation

ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "output" / "game_wars_korean_full.gba"
ORIGINAL = ROOT / "original" / "Game Boy Wars Advance 1+2 (Japan).gba"
INTEGRITY_MAP = ROOT / "temp" / "integrity_map.json"
REPOINT_MANIFEST = ROOT / "temp" / "repoint_manifest.json"
REPORT = ROOT / "temp" / "part1_dialogue_punctuation_qa.json"

PART1_DIALOG_LO = 0xD80000
PART1_DIALOG_HI = 0xE10000
UNSAFE_PUNCT = set(b"!?,.:;()[]{}\"'-/\\+*=#%&@~$")
SYMBOL_TABLE = 0xB8027C
FONT_BASE = 0xB974D0
BLANK_SLOT = 95
VISIBLE_PUNCT_CODES = {
    0x8141: "、",
    0x8142: "。",
    0x8145: "・",
    0x8147: "；",
    0x8148: "？",
    0x8149: "！",
    0x815B: "ー",
    0x815C: "―",
    0x815E: "／",
    0x8160: "〜",
    0x8168: "”",
    0x8169: "（",
    0x816A: "）",
    0x817B: "＋",
    0x8190: "＄",
    0x8193: "％",
    0x8194: "＃",
    0x8195: "＆",
}
INVISIBLE_PUNCT_CODES = {
    0x8144: "．",
    0x8146: "：",
    0x8166: "’",
    0x816D: "［",
    0x816E: "］",
    0x816F: "｛",
    0x8170: "｝",
    0x8196: "＊",
    0x8181: "＝",
    0x8197: "＠",
}


def in_part1_dialog(addr: int) -> bool:
    return is_part1_dialog_address(addr)


def active_text_payloads(integrity, rom):
    """Scan only surviving text tokens, never a stale row's shifted SJIS tail."""
    owners = {}
    for index, entry in enumerate(integrity):
        if not isinstance(entry, list) or len(entry) < 8:
            continue
        addr, slot, length = map(int, entry[:3])
        for pos in range(addr, addr + (slot if entry[4] is not None else length)):
            owners[pos] = index
    for index, entry in enumerate(integrity):
        if not isinstance(entry, list) or len(entry) < 8 or not needs_safe_dialogue_punctuation(entry[0]):
            continue
        addr, length = int(entry[0]), int(entry[2])
        encoded = bytes.fromhex(str(entry[3] or ''))[:length]
        offset = 0
        run_start = 0
        payload = bytearray()
        while offset < len(encoded):
            size = 2 if 0x81 <= encoded[offset] <= 0xE2 and offset + 1 < len(encoded) else 1
            live = [owners.get(addr + pos) == index for pos in range(offset, offset + size)]
            if any(live) and not all(live):
                raise ValueError(f'Partially overwritten text token at 0x{addr + offset:08X}')
            if all(live):
                if not payload:
                    run_start = addr + offset
                payload.extend(rom[addr + offset:addr + offset + size] if rom else encoded[offset:offset + size])
            elif payload:
                yield entry, run_start, bytes(payload)
                payload.clear()
            offset += size
        if payload:
            yield entry, run_start, bytes(payload)


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def scan_standalone_punct(payload: bytes, *, stop_at_nul: bool = False) -> Counter[str]:
    counts: Counter[str] = Counter()
    i = 0
    while i < len(payload):
        b = payload[i]
        if stop_at_nul and b == 0x00:
            break
        if 0x81 <= b <= 0xE2 and i + 1 < len(payload):
            i += 2
            continue
        if b in UNSAFE_PUNCT:
            counts[chr(b)] += 1
        i += 1
    return counts


def scan_sjis_punct(payload: bytes, *, extra_codes=()) -> Counter[int]:
    counts: Counter[int] = Counter()
    i = 0
    while i < len(payload):
        b = payload[i]
        if 0x81 <= b <= 0xE2 and i + 1 < len(payload):
            code = (b << 8) | payload[i + 1]
            if code in VISIBLE_PUNCT_CODES or code in INVISIBLE_PUNCT_CODES or code in extra_codes:
                counts[code] += 1
            i += 2
            continue
        i += 1
    return counts


def symbol_table_index(sjis: int) -> int:
    return (((sjis + 0xFFFF7EC0) & 0xFFF8) << 1) + (sjis & 7)



def scan_missing_renderer_symbols(payload: bytes, address: int) -> Counter[str]:
    """Symbols absent from P2 A3's linked glyph table display question marks."""
    if not is_part2_story_address(address):
        return Counter()
    missing = (0x815C, 0x8165, 0x8166, 0x8167, 0x8168, 0x8177, 0x8178)
    counts = scan_sjis_punct(payload, extra_codes=missing)
    return Counter({f'P2_missing_0x{code:04X}': counts[code]
                    for code in missing if counts[code]})


def glyph_state(rom: bytes, original: bytes, sjis: int) -> dict[str, Any]:
    idx = symbol_table_index(sjis)
    slots: list[int] = []
    nonzero: list[int] = []
    matches_original: list[bool] = []
    for delta in (0, 8):
        table_off = SYMBOL_TABLE + (idx + delta) * 2
        if table_off + 2 > len(original):
            continue
        slot = int.from_bytes(original[table_off:table_off + 2], "little")
        slots.append(slot)
        if slot == BLANK_SLOT:
            nonzero.append(0)
            matches_original.append(True)
            continue
        glyph_off = FONT_BASE + slot * 32
        cur = rom[glyph_off:glyph_off + 32]
        orig = original[glyph_off:glyph_off + 32]
        nonzero.append(sum(1 for b in cur if b))
        matches_original.append(cur == orig)
    return {
        "slots": slots,
        "nonzero": nonzero,
        "matches_original": matches_original,
        "visible": any(v > 0 for v in nonzero),
        "restored": all(matches_original),
    }


def issue_record(
    *,
    source: str,
    addr: int,
    payload: bytes,
    counts: Counter[str],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "source": source,
        "addr": f"0x{addr:08X}",
        "counts": dict(sorted(counts.items())),
        "payload_hex_prefix": payload[:96].hex(),
    }
    if extra:
        record.update(extra)
    return record


def main() -> int:
    issues: list[dict[str, Any]] = []
    totals: Counter[str] = Counter()

    if not ROM.exists():
        issues.append({"source": "rom", "type": "missing_rom", "path": str(ROM.relative_to(ROOT))})
        rom = b""
    else:
        rom = ROM.read_bytes()
    original = ORIGINAL.read_bytes() if ORIGINAL.exists() else b""
    if not original:
        issues.append({"source": "original", "type": "missing_original", "path": str(ORIGINAL.relative_to(ROOT))})

    integrity = load_json(INTEGRITY_MAP, [])
    if not isinstance(integrity, list):
        issues.append({"source": "integrity_map", "type": "invalid_json_shape"})
        integrity = []

    checked_integrity = 0
    sjis_totals: Counter[int] = Counter()
    for entry, addr, payload in active_text_payloads(integrity, rom):
        if not isinstance(entry, list) or len(entry) < 8:
            continue
        try:
            enc_len = int(entry[2])
        except (TypeError, ValueError):
            continue
        if not needs_safe_dialogue_punctuation(addr) or enc_len <= 0:
            continue
        enc_hex = str(entry[3] or "")
        if not enc_hex:
            continue
        checked_integrity += 1
        counts = scan_standalone_punct(payload)
        counts.update(scan_missing_renderer_symbols(payload, addr))
        sjis_totals.update(scan_sjis_punct(payload))
        if counts:
            totals.update(counts)
            issues.append(issue_record(
                source="integrity_map",
                addr=addr,
                payload=payload,
                counts=counts,
                extra={
                    "kind": str(entry[7] or ""),
                    "ko": str(entry[5] or "")[:120],
                    "slot": int(entry[1]) if isinstance(entry[1], int) else entry[1],
                    "enc_len": enc_len,
                },
            ))

    manifest = load_json(REPOINT_MANIFEST, [])
    if not isinstance(manifest, list):
        manifest = []
    checked_repoint = 0
    for item in manifest:
        if not isinstance(item, dict) or item.get("status") != "relocated":
            continue
        try:
            msg = int(str(item["msg"]), 16)
            new_addr = int(str(item["new_addr"]), 16)
            new_len = int(item.get("new_len", 0))
        except (KeyError, TypeError, ValueError):
            continue
        if not needs_safe_dialogue_punctuation(msg) or new_len <= 0 or not rom:
            continue
        checked_repoint += 1
        payload = rom[new_addr:new_addr + new_len]
        counts = scan_standalone_punct(payload, stop_at_nul=False)
        counts.update(scan_missing_renderer_symbols(payload, msg))
        sjis_totals.update(scan_sjis_punct(payload))
        if counts:
            totals.update(counts)
            issues.append(issue_record(
                source="repoint_manifest",
                addr=new_addr,
                payload=payload,
                counts=counts,
                extra={
                    "msg": f"0x{msg:08X}",
                    "new_len": new_len,
                    "fixed": item.get("fixed", []),
                },
            ))

    glyph_issues = []
    if rom and original:
        for code, count in sorted(sjis_totals.items()):
            state = glyph_state(rom, original, code)
            if code in INVISIBLE_PUNCT_CODES or not state["visible"] or not state["restored"]:
                glyph_issues.append({
                    "code": f"0x{code:04X}",
                    "char": VISIBLE_PUNCT_CODES.get(code) or INVISIBLE_PUNCT_CODES.get(code),
                    "count": count,
                    **state,
                })
    issues.extend({"source": "symbol_glyph", **issue} for issue in glyph_issues)

    report = {
        "rom": str(ROM.relative_to(ROOT)),
        "part1_dialog_range": [f"0x{PART1_DIALOG_LO:08X}", f"0x{PART1_DIALOG_HI:08X}"],
        "part1_dialog_ranges": [[f"0x{start:08X}", f"0x{end:08X}"] for start, end in PART1_DIALOG_RANGES],
        "part2_story_ranges": [[f"0x{start:08X}", f"0x{end:08X}"] for start, end in PART2_STORY_RANGES],
        "checked_integrity_payloads": checked_integrity,
        "checked_repoint_payloads": checked_repoint,
        "unsafe_punctuation": "".join(chr(b) for b in sorted(UNSAFE_PUNCT)),
        "sjis_punctuation_totals": {
            f"0x{code:04X}": {
                "char": VISIBLE_PUNCT_CODES.get(code) or INVISIBLE_PUNCT_CODES.get(code),
                "count": count,
            }
            for code, count in sorted(sjis_totals.items())
        },
        "glyph_issue_count": len(glyph_issues),
        "issue_count": len(issues),
        "issue_totals": dict(sorted(totals.items())),
        "issues": issues[:200],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "checked_integrity_payloads": checked_integrity,
        "checked_repoint_payloads": checked_repoint,
        "issue_count": len(issues),
        "issue_totals": dict(sorted(totals.items())),
        "glyph_issue_count": len(glyph_issues),
        "report": str(REPORT.relative_to(ROOT)),
    }, ensure_ascii=False))
    if issues:
        for issue in issues[:20]:
            print(f"[FAIL] {issue}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
