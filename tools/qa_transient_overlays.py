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

from render_galmuri_8x16 import render_char

ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "output" / "game_wars_korean_full.gba"
ORIGINAL = ROOT / "original" / "Game Boy Wars Advance 1+2 (Japan).gba"
REPORT = ROOT / "temp" / "transient_overlays_qa.json"

KANJI_TABLE = 0xB80B7C
KANJI_TABLE_END = 0xB8180C
FONT_BASE = 0xB974D0
PART1_DAY_BANNER_LZ77 = 0xEE5E14
SURRENDER_YESNO_ROW = 0xA34B6C
SURRENDER_YESNO_LEN = 16
SURRENDER_YESNO_TEXT = "　예　　　아뇨"
PART1_NAME_SUFFIX_SLOTS = {
    0xDF1F62: "part1 name-control suffix copy 1",
    0xDF1FA2: "part1 name-control suffix copy 2",
    0xDF230A: "part1 name-control suffix copy 3",
    0xDF2390: "part1 name-control suffix copy 4",
    0xDF26F2: "part1 name-control suffix copy 5",
    0xDF2786: "part1 name-control suffix copy 6",
    0xDF5DA9: "part1 operation-room name suffix",
    0xDF8E4D: "part1 post-name greeting suffix",
}
PART1_NAME_SUFFIX_TEXT = "님"
PART1_RAW_NAME_CONTROL_SAN = bytes.fromhex("6982b382f1")
PART1_ORPHAN_SAN_HITS = (0xDC3C62, 0xDCDEEA, 0xDCEA42)
# The native dialogue reader terminates on NUL. Bound a single message to the
# 0x1000-byte maximum used by the project's text QA; never accept an open span.
PART1_NAME_CONTROL_MAX_LEN = 0x1000
# Script consumers for the three name-control introductions. The old inline
# copies remain in the ROM after dialogue repointing, but these pointer cells
# select the text the game actually reads.
PART1_NAME_CONTROL_POINTERS = (0xDD373C, 0xDE3308, 0xDE4884)
PART1_YESNO_HOOK_FILE = 0xF10000
PART1_YESNO_WIDE_BRANCH = bytes.fromhex('00f0fbf8')
PART1_YESNO_WIDE_CURSOR_FILE = 0xF10200
PART1_YESNO_WIDE_CURSOR = bytes.fromhex(
    '00b50198fff70eff00bd'
)
PART1_YESNO_ROW_DISPATCH_FILE = 0xF10280
PART1_YESNO_ROW_DISPATCH = bytes.fromhex(
    '0db504a106230a88028002300231013bf9d10dbde280640164016401e480e6800000000000000000'
    '0000000000000000000000000000000000000000000000000db504a106230a88028002300231013b'
    'f9d10dbde380640164016401e580e780000000000000000000000000000000000000000000000000'
    '0000000000000000'
)
PART1_YESNO_ROW_SOURCE_FILE = 0xF10320
PART1_YESNO_ROW_SOURCE = bytes.fromhex(
    '10b582b0044b049c0094059c0194002102f4f4fe02b010bd8003f108'
)
PART1_YESNO_NAME_ROW_FILE = 0xF10380
PART1_YESNO_NAME_ROW = bytes.fromhex('81408eec8140814081408e9b89af0000')
PART1_YESNO_CURSOR_BRANCH_OFF = 0x98
PART1_YESNO_CURSOR_FIX_OFF = 0x3A0
PART1_YESNO_CURSOR_BRANCH = bytes.fromhex("82e1")
PART1_YESNO_CURSOR_FIX = bytes.fromhex(
    '00988069054902880a8002890a814030403102880a8002890a81ffbdce600006'
)
PART1_YESNO_UNUSED_CLASSIFIER_FILE = 0xF10400


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


def digit_tile_status(current: bytes, expected: bytes, source: bytes | None) -> tuple[bool, bool]:
    """Reject both corrupted tiles and the superseded Japanese ROM artwork."""
    return current == expected, source is None or current != source


def message_span(rom: bytes, target: int) -> tuple[int, int] | None:
    if not 0 <= target < len(rom):
        return None
    end = rom.find(b"\x00", target, min(len(rom), target + PART1_NAME_CONTROL_MAX_LEN))
    return (target, end + 1) if end >= 0 else None


def name_control_san_status(rom: bytes) -> tuple[list[dict[str, Any]], list[int], list[dict[str, Any]], list[int], list[dict[str, Any]]]:
    rows = []
    live_hits = []
    invalid_spans = []
    for pointer in PART1_NAME_CONTROL_POINTERS:
        value = struct.unpack_from("<I", rom, pointer)[0] if pointer + 4 <= len(rom) else 0
        target = value - 0x08000000
        span = message_span(rom, target) if 0x08000000 <= value < 0x08000000 + len(rom) else None
        valid = span is not None
        hit = rom.find(PART1_RAW_NAME_CONTROL_SAN, *span) if span else -1
        rows.append({"pointer": f"0x{pointer:08X}",
                     "target": f"0x{target:08X}" if valid else None,
                     "valid": valid, "live_san": hit >= 0})
        if not valid:
            invalid_spans.append({"pointer": f"0x{pointer:08X}", "target_value": f"0x{value:08X}"})
        elif hit >= 0:
            live_hits.append(hit)

    # An old inline copy is exempt only while its entire terminated message
    # has no 4-byte-aligned GBA ROM pointer to any byte within that span.
    orphan_spans = {}
    for hit in PART1_ORPHAN_SAN_HITS:
        start = hit - 2  # native 0A 09 message prefix
        span = message_span(rom, start)
        if (span is None or rom[start:hit] != b"\x0a\x09" or
                not (span[0] <= hit < span[1]) or
                rom[hit:hit + len(PART1_RAW_NAME_CONTROL_SAN)] != PART1_RAW_NAME_CONTROL_SAN):
            invalid_spans.append({"orphan_hit": f"0x{hit:08X}", "reason": "missing_or_truncated_message"})
        else:
            orphan_spans[hit] = span
    references = {hit: [] for hit in orphan_spans}
    for pointer in range(0, len(rom) - 3, 4):
        value = struct.unpack_from("<I", rom, pointer)[0]
        if not 0x08000000 <= value < 0x08000000 + len(rom):
            continue
        target = value - 0x08000000
        for hit, (start, end) in orphan_spans.items():
            if start <= target < end:
                references[hit].append(pointer)
    unexplained = []
    pos = 0
    while (pos := rom.find(PART1_RAW_NAME_CONTROL_SAN, pos)) >= 0:
        if pos not in orphan_spans or references[pos]:
            unexplained.append(pos)
        pos += 1
    proof = [{"hit": f"0x{hit:08X}", "span": [f"0x{start:08X}", f"0x{end:08X}"],
              "references": [f"0x{x:08X}" for x in references[hit]]}
             for hit, (start, end) in orphan_spans.items()]
    return rows, live_hits, invalid_spans, unexplained, proof


def load_syllable_codes() -> dict[str, int]:
    path = ROOT / "data" / "syllable_to_code_2350.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("map", data)
    out: dict[str, int] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or len(key) != 1:
            continue
        if isinstance(value, str):
            out[key] = int(value, 16)
        else:
            out[key] = int(value)
    return out


def encode_korean_ui(text: str, syllable_codes: dict[str, int]) -> bytes:
    out = bytearray()
    for ch in text:
        if "가" <= ch <= "힣":
            code = syllable_codes[ch]
            out += bytes([code >> 8, code & 0xFF])
        elif ch == "　":
            out += b"\x81\x40"
        elif ch == " ":
            out += b"\x20"
        elif 0x20 <= ord(ch) <= 0x7E:
            out.append(ord(ch))
        else:
            out += ch.encode("shift_jis")
    return bytes(out)


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


def font_tile_bytes(rom: bytes, slot: int) -> bytes:
    off = FONT_BASE + slot * 32
    return rom[off:off + 32]


def glyph_pair_bbox(rom: bytes, slots: tuple[int, int]) -> list[int] | None:
    pixels = tile_to_pixels(font_tile_bytes(rom, slots[0]))
    pixels += tile_to_pixels(font_tile_bytes(rom, slots[1]))
    return bbox(pixels)


def tile_nonzero(tile: bytes) -> int:
    return sum(1 for b in tile if b)


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


def column_runs(pixels: list[list[int]]) -> list[list[int]]:
    cols = [any(row[x] for row in pixels) for x in range(len(pixels[0]))]
    runs: list[list[int]] = []
    start: int | None = None
    for idx, used in enumerate(cols + [False]):
        if used and start is None:
            start = idx
        elif not used and start is not None:
            runs.append([start, idx])
            start = None
    return runs


def main() -> int:
    sys.path.insert(0, str(ROOT / "tools"))
    import build_korean_full as build  # noqa: WPS433
    from lz77_scan import lz77_decompress  # noqa: WPS433

    issues: list[dict[str, Any]] = []
    rom = read(ROM) if ROM.exists() else b""
    original = read(ORIGINAL) if ORIGINAL.exists() else b""
    if not rom:
        issues.append({"type": "missing_rom", "path": str(ROM.relative_to(ROOT))})
    if not original:
        issues.append({"type": "missing_original", "path": str(ORIGINAL.relative_to(ROOT))})

    surrender_yesno = {"addr": f"0x{SURRENDER_YESNO_ROW:08X}", "expected_text": SURRENDER_YESNO_TEXT}
    if rom:
        wide_branch = rom[PART1_YESNO_HOOK_FILE + 6:PART1_YESNO_HOOK_FILE + 10]
        wide_cursor = rom[PART1_YESNO_WIDE_CURSOR_FILE:PART1_YESNO_WIDE_CURSOR_FILE + len(PART1_YESNO_WIDE_CURSOR)]
        row_dispatch = rom[PART1_YESNO_ROW_DISPATCH_FILE:PART1_YESNO_ROW_DISPATCH_FILE + len(PART1_YESNO_ROW_DISPATCH)]
        row_source = rom[PART1_YESNO_ROW_SOURCE_FILE:PART1_YESNO_ROW_SOURCE_FILE + len(PART1_YESNO_ROW_SOURCE)]
        name_row = rom[PART1_YESNO_NAME_ROW_FILE:PART1_YESNO_NAME_ROW_FILE + len(PART1_YESNO_NAME_ROW)]
        row_calls = rom[PART1_YESNO_HOOK_FILE + 0x8E:PART1_YESNO_HOOK_FILE + 0x98]
        expected_calls = bytes.fromhex('00f0f7f82a4800f014f9')
        source_call = rom[0xB18D26:0xB18D2A]
        if (wide_branch != PART1_YESNO_WIDE_BRANCH or wide_cursor != PART1_YESNO_WIDE_CURSOR
                or row_dispatch != PART1_YESNO_ROW_DISPATCH or row_calls != expected_calls
                or row_source != PART1_YESNO_ROW_SOURCE or name_row != PART1_YESNO_NAME_ROW
                or rom[PART1_YESNO_HOOK_FILE + 0xAA:PART1_YESNO_HOOK_FILE + 0xE0] != bytes(0x36)
                or rom[PART1_YESNO_UNUSED_CLASSIFIER_FILE:PART1_YESNO_UNUSED_CLASSIFIER_FILE + 136] != bytes(136)
                or rom[PART1_YESNO_WIDE_CURSOR_FILE + len(PART1_YESNO_WIDE_CURSOR):PART1_YESNO_WIDE_CURSOR_FILE + 48] != bytes(48 - len(PART1_YESNO_WIDE_CURSOR))
                or rom[PART1_YESNO_ROW_SOURCE_FILE + len(PART1_YESNO_ROW_SOURCE):PART1_YESNO_ROW_SOURCE_FILE + 36] != bytes(36 - len(PART1_YESNO_ROW_SOURCE))
                or source_call != bytes.fromhex('f7f3fbfa')):
            issues.append({
                "type": "part1_yesno_wide_overlay_missing",
                "branch_matches": wide_branch == PART1_YESNO_WIDE_BRANCH,
                "cursor_matches": wide_cursor == PART1_YESNO_WIDE_CURSOR,
                "row_dispatch_matches": row_dispatch == PART1_YESNO_ROW_DISPATCH,
                "row_calls_match": row_calls == expected_calls,
                "source_matches": row_source == PART1_YESNO_ROW_SOURCE,
                "source_call_matches": source_call == bytes.fromhex('f7f3fbfa'),
            })
        expected = encode_korean_ui(SURRENDER_YESNO_TEXT, load_syllable_codes())
        expected_slot = expected + b"\x00" * (SURRENDER_YESNO_LEN - len(expected))
        current = rom[SURRENDER_YESNO_ROW:SURRENDER_YESNO_ROW + SURRENDER_YESNO_LEN]
        surrender_yesno.update({
            "expected_hex": expected.hex(),
            "expected_slot_hex": expected_slot.hex(),
            "current_hex": current.hex(),
            "expected_len": len(expected),
            "slot_len": SURRENDER_YESNO_LEN,
            "matches": current == expected_slot,
        })
        if len(expected) + 1 > SURRENDER_YESNO_LEN:
            issues.append({
                "type": "surrender_yesno_expected_exceeds_terminated_slot",
                "addr": f"0x{SURRENDER_YESNO_ROW:08X}",
                "expected_len": len(expected),
                "slot_len": SURRENDER_YESNO_LEN,
            })
        elif current != expected_slot:
            issues.append({
                "type": "surrender_yesno_cursor_spacing_regression",
                "addr": f"0x{SURRENDER_YESNO_ROW:08X}",
                "expected_text": SURRENDER_YESNO_TEXT,
                "expected_hex": expected.hex(),
                "current_hex": current.hex(),
            })

    name_suffix_status = []
    name_suffix_pattern_status = {}
    name_grid_dialogue_font_status = {}
    if rom:
        suffix_encoded = encode_korean_ui(PART1_NAME_SUFFIX_TEXT, load_syllable_codes())
        suffix_expected = suffix_encoded + b"\x20" * 4
        for addr, label in PART1_NAME_SUFFIX_SLOTS.items():
            current = rom[addr:addr + 6]
            row = {
                "addr": f"0x{addr:08X}",
                "label": label,
                "expected_text": PART1_NAME_SUFFIX_TEXT,
                "expected_hex": suffix_expected.hex(),
                "current_hex": current.hex(),
                "matches": current == suffix_expected,
            }
            name_suffix_status.append(row)
            if current != suffix_expected:
                issues.append({
                    "type": "part1_name_suffix_spacing_regression",
                    **row,
                })
        bad_leading_space = b"\x69\x81\x40" + suffix_encoded
        bad_hits = []
        pos = 0
        while True:
            pos = rom.find(bad_leading_space, pos)
            if pos < 0:
                break
            bad_hits.append(pos)
            pos += 1
        raw_hits = []
        pos = 0
        while True:
            pos = rom.find(PART1_RAW_NAME_CONTROL_SAN, pos)
            if pos < 0:
                break
            raw_hits.append(pos)
            pos += 1
        name_suffix_pattern_status = {
            "bad_leading_space_pattern_hex": bad_leading_space.hex(),
            "bad_leading_space_hits": [f"0x{x:08X}" for x in bad_hits],
            "raw_name_control_san_pattern_hex": PART1_RAW_NAME_CONTROL_SAN.hex(),
            "raw_name_control_san_hits": [f"0x{x:08X}" for x in raw_hits],
        }
        if bad_hits:
            issues.append({
                "type": "part1_name_suffix_bad_leading_space_pattern",
                "pattern_hex": bad_leading_space.hex(),
                "hits": [f"0x{x:08X}" for x in bad_hits],
            })
        pointer_rows, live_raw_hits, invalid_spans, unexplained_hits, orphan_proof = name_control_san_status(rom)
        name_suffix_pattern_status["name_control_pointers"] = pointer_rows
        name_suffix_pattern_status["live_raw_name_control_san_hits"] = [f"0x{x:08X}" for x in live_raw_hits]
        name_suffix_pattern_status["orphan_proof"] = orphan_proof
        name_suffix_pattern_status["unexplained_raw_hits"] = [f"0x{x:08X}" for x in unexplained_hits]
        if invalid_spans:
            issues.append({"type": "part1_name_control_invalid_message_span", "spans": invalid_spans})
        if unexplained_hits or live_raw_hits:
            issues.append({
                "type": "raw_part1_name_control_san_pattern",
                "pattern_hex": PART1_RAW_NAME_CONTROL_SAN.hex(),
                "hits": [f"0x{x:08X}" for x in sorted(set(unexplained_hits + live_raw_hits))],
            })

        dialogue_glyphs = json.loads(Path(build.SYLMAP_2350).read_text(encoding="utf-8"))["map"]
        dialogue_blob = read(Path(build.GLYPH_BLOB_2350))

        def dialogue_tile(slot: int) -> bytes:
            start = slot * 32
            return dialogue_blob[start:start + 32]

        checks = []
        digit_checks = []
        fallback_checks = []

        def add_grid_check(label: str, slots: tuple[int, int], source: str) -> None:
            if label not in dialogue_glyphs:
                if label.isdigit():
                    for (half, font_slot), expected in zip(
                        (("top", slots[0]), ("bot", slots[1])), render_char(label)
                    ):
                        current = font_tile_bytes(rom, font_slot)
                        source_tile = font_tile_bytes(original, font_slot) if original else None
                        matches, differs = digit_tile_status(current, expected, source_tile)
                        row = {
                            "label": label,
                            "source": source,
                            "half": half,
                            "font_slot": font_slot,
                            "matches_galmuri_digit": matches,
                            "differs_from_original": differs,
                        }
                        digit_checks.append(row)
                        if current != expected:
                            issues.append({
                                "type": "part1_name_grid_digit_not_galmuri_font",
                                **row,
                            })
                        if original and not row["differs_from_original"]:
                            issues.append({"type": "part1_name_grid_digit_still_original", **row})
                    return
                if label:
                    top = font_tile_bytes(rom, slots[0])
                    bot = font_tile_bytes(rom, slots[1])
                    row = {
                        "label": label,
                        "source": source,
                        "slots": list(slots),
                        "bbox_8x16": glyph_pair_bbox(rom, slots),
                        "top_nonzero": tile_nonzero(top),
                        "bot_nonzero": tile_nonzero(bot),
                        "has_bottom_pixels": tile_nonzero(bot) > 0,
                    }
                    fallback_checks.append(row)
                    if not row["has_bottom_pixels"]:
                        issues.append({
                            "type": "part1_name_grid_fallback_top_only",
                            **row,
                        })
                return
            glyph = dialogue_glyphs[label]
            for half, font_slot, glyph_slot in (
                ("top", slots[0], int(glyph["top"])),
                ("bot", slots[1], int(glyph["bot"])),
            ):
                current = font_tile_bytes(rom, font_slot)
                expected = dialogue_tile(glyph_slot)
                row = {
                    "label": label,
                    "source": source,
                    "half": half,
                    "font_slot": font_slot,
                    "dialogue_glyph_slot": glyph_slot,
                    "matches": current == expected,
                }
                checks.append(row)
                if current != expected:
                    issues.append({
                        "type": "part1_name_grid_not_dialogue_font",
                        **row,
                    })

        for ch, slots in build.NAME_GRID_SLOTS.items():
            add_grid_check(build.NAME_GRID_LABELS.get(ch, ch), slots, f"NAME_GRID_SLOTS[{ch!r}]")
            for mirror_slots in build.NAME_GRID_MIRROR_SLOTS.get(ch, []):
                add_grid_check(build.NAME_GRID_LABELS.get(ch, ch), mirror_slots, f"NAME_GRID_MIRROR_SLOTS[{ch!r}]")
        for label, slots in build.NAME_GRID_EXTRA_LABEL_SLOTS.items():
            add_grid_check(label, slots, f"NAME_GRID_EXTRA_LABEL_SLOTS[{label!r}]")
        name_grid_dialogue_font_status = {
            "checked_tiles": len(checks),
            "mismatches": [row for row in checks if not row["matches"]],
            "digit_galmuri_tiles": len(digit_checks),
            "digit_mismatches": [row for row in digit_checks if not row["matches_galmuri_digit"]],
            "fallback_16px_checks": fallback_checks,
            "fallback_top_only": [row for row in fallback_checks if not row["has_bottom_pixels"]],
        }

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
            day_runs = column_runs(day_pixels)
            inner_gaps = [
                day_runs[idx + 1][0] - day_runs[idx][1]
                for idx in range(len(day_runs) - 1)
            ]
            day_label = {
                "addr": f"0x{PART1_DAY_BANNER_LZ77:08X}",
                "consumed": consumed,
                "bbox": day_bbox,
                "column_runs": day_runs,
                "max_inner_gap": max(inner_gaps) if inner_gaps else 0,
            }
            if day_bbox is None:
                issues.append({"type": "blank_part1_day_label"})
            elif day_bbox[0] < 6:
                issues.append({
                    "type": "part1_day_label_too_close_to_digit",
                    "bbox": day_bbox,
                    "min_left": 6,
                })
            elif day_bbox[0] > 10:
                issues.append({
                    "type": "part1_day_label_shifted_right",
                    "bbox": day_bbox,
                    "max_left": 10,
                })
            elif day_label["max_inner_gap"] < 8:
                issues.append({
                    "type": "part1_day_label_char_gap_too_small",
                    "column_runs": day_runs,
                    "min_gap": 8,
                })

    part1_yesno_cursor_fix = {}
    if rom:
        branch = rom[
            PART1_YESNO_HOOK_FILE + PART1_YESNO_CURSOR_BRANCH_OFF:
            PART1_YESNO_HOOK_FILE + PART1_YESNO_CURSOR_BRANCH_OFF + len(PART1_YESNO_CURSOR_BRANCH)
        ]
        helper = rom[
            PART1_YESNO_HOOK_FILE + PART1_YESNO_CURSOR_FIX_OFF:
            PART1_YESNO_HOOK_FILE + PART1_YESNO_CURSOR_FIX_OFF + len(PART1_YESNO_CURSOR_FIX)
        ]
        part1_yesno_cursor_fix = {
            "branch_file_offset": f"0x{PART1_YESNO_HOOK_FILE + PART1_YESNO_CURSOR_BRANCH_OFF:08X}",
            "helper_file_offset": f"0x{PART1_YESNO_HOOK_FILE + PART1_YESNO_CURSOR_FIX_OFF:08X}",
            "branch_matches": branch == PART1_YESNO_CURSOR_BRANCH,
            "helper_matches": helper == PART1_YESNO_CURSOR_FIX,
            "expected_branch_hex": PART1_YESNO_CURSOR_BRANCH.hex(),
            "current_branch_hex": branch.hex(),
            "expected_helper_hex": PART1_YESNO_CURSOR_FIX.hex(),
            "current_helper_hex": helper.hex(),
        }
        if branch != PART1_YESNO_CURSOR_BRANCH or helper != PART1_YESNO_CURSOR_FIX:
            issues.append({
                "type": "part1_name_yesno_cursor_fix_missing",
                **part1_yesno_cursor_fix,
            })

    report = {
        "rom": str(ROM.relative_to(ROOT)),
        "issue_count": len(issues),
        "issues": issues,
        "title_sources": title_source_status,
        "raw_pattern_hits": raw_pattern_hits,
        "required_kanji_subs": glyph_status,
        "part1_day_label": day_label,
        "surrender_yesno": surrender_yesno,
        "part1_name_suffixes": name_suffix_status,
        "part1_name_suffix_patterns": name_suffix_pattern_status,
        "part1_name_grid_dialogue_font": name_grid_dialogue_font_status,
        "part1_yesno_cursor_fix": part1_yesno_cursor_fix,
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
