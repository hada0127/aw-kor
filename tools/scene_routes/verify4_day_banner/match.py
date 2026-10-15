#!/usr/bin/env python3
"""Exact-palette 32x32 OBJ-cell matcher for VERIFY-4 client frames.

Usage: python3 tools/scene_routes/verify4_day_banner/match.py ROM FRAME.png OUT.json
Scores describe pixels only; identical alternate sheets need source-read evidence.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from lz77_scan import lz77_decompress

PAIRS = [
    (0x92DF84, 0x92EB5C, 0x90DC7C),
    (0x966C0C, 0x9677E4, 0x9463FC),
    (0x99F4B0, 0x9A0088, 0x97ECA0),
    (0x9D7D54, 0x9D892C, 0x9B7544),
]
PALETTE = {0: (0, 0, 0), 6: (140, 140, 140), 9: (82, 82, 82),
           11: (222, 222, 222), 13: (0, 0, 0), 15: (255, 255, 255)}


def cell_pixels(sheet, cell_index):
    cell = sheet[cell_index * 512:(cell_index + 1) * 512]
    assert len(cell) == 512
    indexed = np.zeros((32, 32), dtype=np.uint8)
    for y in range(32):
        for x in range(32):
            offset = ((y // 8) * 4 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
            indexed[y, x] = (cell[offset] >> (4 * (x % 2))) & 15
    opaque = indexed != 0
    assert set(np.unique(indexed)).issubset(PALETTE)
    rgb = np.zeros((32, 32, 3), dtype=np.uint8)
    for idx, color in PALETTE.items():
        rgb[indexed == idx] = color
    return rgb, opaque, hashlib.sha256(cell).hexdigest()


def find_matches(frame, rgb, opaque, limit=5):
    height, width, _ = frame.shape
    best = []
    opaque_count = int(np.count_nonzero(opaque))
    for y in range(height - 31):
        for x in range(width - 31):
            crop = frame[y:y + 32, x:x + 32]
            score = int(np.count_nonzero(np.all(crop == rgb, axis=2) & opaque))
            if len(best) < limit or score > best[-1][0]:
                best.append((score, x, y))
                best.sort(reverse=True)
                best = best[:limit]
    return [{"x": x, "y": y, "matched": score, "opaque": opaque_count,
             "score": round(score / opaque_count, 6)} for score, x, y in best]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", type=Path)
    ap.add_argument("frame", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()
    rom = args.rom.read_bytes()
    frame = np.asarray(Image.open(args.frame).convert("RGB"))
    result = {"rom_sha256": hashlib.sha256(rom).hexdigest(),
              "frame": str(args.frame), "frame_sha256": hashlib.sha256(args.frame.read_bytes()).hexdigest(),
              "method": "Exact RGB match of every opaque 4bpp cell pixel; source reads required to identify equal art.",
              "pairs": []}
    match_cache = {}
    for main_off, word_off, base in PAIRS:
        main_sheet, _ = lz77_decompress(rom, main_off)
        word_sheet, _ = lz77_decompress(rom, word_off)
        assert len(main_sheet) == 7168 and len(word_sheet) == 1024
        cells = {}
        for label, data, idx in [
            ("일", main_sheet, 10), ("째", main_sheet, 11),
            ("개", main_sheet, 12), ("시", main_sheet, 13),
            ("작", word_sheet, 0), ("전", word_sheet, 1),
        ]:
            rgb, opaque, digest = cell_pixels(data, idx)
            if digest not in match_cache:
                match_cache[digest] = find_matches(frame, rgb, opaque)
            cells[label] = {"cell_sha256": digest, "best": match_cache[digest]}
        result["pairs"].append({"main_offset": f"0x{main_off:06X}",
                                "word_offset": f"0x{word_off:06X}",
                                "embedded_image_base": f"0x{base:06X}", "cells": cells})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(args.out)


if __name__ == "__main__":
    main()
