#!/usr/bin/env python3
"""Gate transient battle/operation overlay assets.

These screens pass quickly in normal play, so screenshot-only QA tends to miss
stale Japanese title art or shifted day/start sprites.  This gate checks the ROM
assets that feed those transient frames.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "output" / "game_wars_korean_full.gba"
ORIGINAL = ROOT / "original" / "Game Boy Wars Advance 1+2 (Japan).gba"
REPORT = ROOT / "temp" / "transient_overlays_qa.json"

KANJI_TABLE = 0xB80B7C
KANJI_TABLE_END = 0xB8180C
FONT_BASE = 0xB974D0
PART1_DAY_BANNER_LZ77 = 0xEE5E14

RAW_TITLE_PATTERNS = {
    "part1 opening battle title": "序盤戦".encode("shift_jis"),
    "part1 battle start title": "戦闘開始".encode("shift_jis"),
    "part1 last mission title": "ラストミッション".encode("shift_jis"),
}
TITLE_SOURCES = {
    0xB8200C: "序盤戦！",
    0xB82018: "戦闘開始！",
    0xB82024: "ラストミッション",
}
REQUIRED_KANJI_SUBS = {
    "序": "초",
    "盤": "반",
    "戦": "전",
}


def read(path: Path) -> bytes:
    return path.read_bytes()


def sjis_code(ch: str) -> int:
    data = ch.encode("shift_jis")
    if len(data) != 2:
        raise ValueError(ch)
    return (data[0] << 8) | data[1]


def kanji_slots(original: bytes, ch: str) -> tuple[int, int] | None:
    target = sjis_code(ch)
    for pos in range(KANJI_TABLE, KANJI_TABLE_END, 6):
        sjis_le = struct.unpack_from("<H", original, pos)[0]
        sjis = ((sjis_le & 0xFF) << 8) | (sjis_le >> 8)
        if sjis == target:
            return struct.unpack_from("<HH", original, pos + 2)
    return None


def glyph_bytes(rom: bytes, slots: tuple[int, int]) -> bytes:
    out = bytearray()
    for slot in slots:
        off = FONT_BASE + slot * 32
        out += rom[off:off + 32]
    return bytes(out)


def tile_to_pixels(tile: bytes) -> list[list[int]]:
    rows: list[list[int]] = []
    for y in range(8):
        row = []
        for xpair in range(4):
            v = tile[y * 4 + xpair]
            row.append(v & 0x0F)
            row.append(v >> 4)
        rows.append(row)
    return rows


def assemble_day_label(data: bytes) -> list[list[int]]:
    width, height = 64, 32
    pixels = [[0 for _ in range(width)] for _ in range(height)]
    for chunk_index, tile_base in enumerate((224, 240)):
        for local in range(16):
            tile_id = tile_base + local
            tile = data[tile_id * 32:tile_id * 32 + 32]
            tx = chunk_index * 4 + (local % 4)
            ty = local // 4
            rows = tile_to_pixels(tile)
            for y in range(8):
                for x in range(8):
                    pixels[ty * 8 + y][tx * 8 + x] = rows[y][x]
    return pixels


def bbox(pixels: list[list[int]]) -> list[int] | None:
    xs: list[int] = []
    ys: list[int] = []
    for y, row in enumerate(pixels):
        for x, value in enumerate(row):
            if value:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return [min(xs), min(ys), max(xs) + 1, max(ys) + 1]


def main() -> int:
    sys.path.insert(0, str(ROOT / "tools"))
    from lz77_scan import lz77_decompress  # noqa: WPS433

    issues: list[dict[str, Any]] = []
    rom = read(ROM) if ROM.exists() else b""
    original = read(ORIGINAL) if ORIGINAL.exists() else b""
    if not rom:
        issues.append({"type": "missing_rom", "path": str(ROM.relative_to(ROOT))})
    if not original:
        issues.append({"type": "missing_original", "path": str(ORIGINAL.relative_to(ROOT))})

    title_source_status = []
    if rom:
        for addr, text in TITLE_SOURCES.items():
            raw = text.encode("shift_jis")
            current = rom[addr:addr + len(raw)]
            raw_match = current == raw
            title_source_status.append({
                "addr": f"0x{addr:08X}",
                "japanese": text,
                "raw_match": raw_match,
                "current_hex": current.hex(),
            })
            if raw_match:
                issues.append({
                    "type": "raw_part1_title_source",
                    "addr": f"0x{addr:08X}",
                    "japanese": text,
                })

    raw_pattern_hits = []
    if rom:
        for label, pattern in RAW_TITLE_PATTERNS.items():
            hits = []
            pos = 0
            while True:
                hit = rom.find(pattern, pos)
                if hit < 0:
                    break
                hits.append(hit)
                pos = hit + 1
            raw_pattern_hits.append({
                "label": label,
                "pattern_hex": pattern.hex(),
                "hits": [f"0x{x:08X}" for x in hits[:20]],
                "count": len(hits),
            })

    glyph_status = []
    if rom and original:
        for jp, ko in REQUIRED_KANJI_SUBS.items():
            slots = kanji_slots(original, jp)
            if slots is None:
                issues.append({"type": "missing_kanji_table_entry", "jp": jp, "ko": ko})
                glyph_status.append({"jp": jp, "ko": ko, "slots": None})
                continue
            cur = glyph_bytes(rom, slots)
            orig = glyph_bytes(original, slots)
            status = {
                "jp": jp,
                "ko": ko,
                "slots": list(slots),
                "nonzero": sum(1 for b in cur if b),
                "changed_from_original": cur != orig,
            }
            glyph_status.append(status)
            if status["nonzero"] == 0 or not status["changed_from_original"]:
                issues.append({"type": "kanji_sub_not_applied", **status})

    day_label = {"bbox": None}
    if rom:
        dec = lz77_decompress(rom, PART1_DAY_BANNER_LZ77)
        if dec is None:
            issues.append({"type": "invalid_part1_day_banner_lz77", "addr": f"0x{PART1_DAY_BANNER_LZ77:08X}"})
        else:
            data, consumed = dec
            day_pixels = assemble_day_label(data)
            day_bbox = bbox(day_pixels)
            day_label = {
                "addr": f"0x{PART1_DAY_BANNER_LZ77:08X}",
                "consumed": consumed,
                "bbox": day_bbox,
            }
            if day_bbox is None:
                issues.append({"type": "blank_part1_day_label"})
            elif day_bbox[0] > 6:
                issues.append({
                    "type": "part1_day_label_shifted_right",
                    "bbox": day_bbox,
                    "max_left": 6,
                })

    report = {
        "rom": str(ROM.relative_to(ROOT)),
        "issue_count": len(issues),
        "issues": issues,
        "title_sources": title_source_status,
        "raw_pattern_hits": raw_pattern_hits,
        "required_kanji_subs": glyph_status,
        "part1_day_label": day_label,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "issue_count": len(issues),
        "part1_day_label_bbox": day_label.get("bbox"),
        "report": str(REPORT.relative_to(ROOT)),
    }, ensure_ascii=False))
    if issues:
        for issue in issues[:20]:
            print(f"[FAIL] {issue}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
