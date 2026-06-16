#!/usr/bin/env python3
"""한글 글리프 contact sheet — 출하 ROM의 KOR_BASE 글리프를 음절별로 렌더.

깨지는 픽셀(글리프 손상/누락) 시각 점검용. ROM 0x08F00000(파일 0xF00000)의 4bpp 8x8
타일을 syllable_to_glyph 매핑(top/bot)으로 8x16 음절 글리프로 합쳐 그린다.
또한 빈 글리프/과밀 글리프를 자동 플래그.
"""
from __future__ import annotations
import argparse, json, os
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KOR_BASE_OFF = 0xF00000
TILE = 32  # 4bpp 8x8
MAP = os.path.join(BASE, "data", "syllable_to_glyph_2350.json")


def tile_pixels(data, idx, ink):
    """4bpp 8x8 타일 → 8x8 0/1 매트릭스(ink 인덱스만 1)."""
    off = idx * TILE
    px = [[0] * 8 for _ in range(8)]
    for y in range(8):
        for x in range(0, 8, 2):
            b = data[off + y * 4 + x // 2]
            lo, hi = b & 0xF, (b >> 4) & 0xF
            px[y][x] = 1 if lo == ink else 0
            px[y][x + 1] = 1 if hi == ink else 0
    return px


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=os.path.join(BASE, "output", "game_wars_korean_full.gba"))
    ap.add_argument("--out", default=os.path.join(BASE, "temp", "glyph_sheet.png"))
    ap.add_argument("--cols", type=int, default=64)
    ap.add_argument("--scale", type=int, default=2)
    args = ap.parse_args()

    rom = open(args.rom, "rb").read()
    meta = json.load(open(MAP, encoding="utf-8"))
    ink = meta["_meta"]["ink_index"]
    nt = meta["_meta"]["unique_tiles"]
    blob = rom[KOR_BASE_OFF: KOR_BASE_OFF + nt * TILE]
    syl = meta["map"]

    cell_w, cell_h = 8, 16
    s = args.scale
    cols = args.cols
    rows = (len(syl) + cols - 1) // cols
    pad = 1
    W = cols * (cell_w * s + pad) + pad
    H = rows * (cell_h * s + pad) + pad
    img = Image.new("RGB", (W, H), (30, 30, 40))
    px = img.load()

    empty, dense = [], []
    for i, (ch, g) in enumerate(syl.items()):
        r, c = divmod(i, cols)
        x0 = pad + c * (cell_w * s + pad)
        y0 = pad + r * (cell_h * s + pad)
        top = tile_pixels(blob, g["top"], ink)
        bot = tile_pixels(blob, g["bot"], ink)
        ink_count = 0
        for ty, tile in ((0, top), (8, bot)):
            for yy in range(8):
                for xx in range(8):
                    if tile[yy][xx]:
                        ink_count += 1
                        for dy in range(s):
                            for dx in range(s):
                                px[x0 + xx * s + dx, y0 + (ty + yy) * s + dy] = (235, 235, 235)
        if ink_count == 0:
            empty.append(ch)
        elif ink_count > 100:
            dense.append(ch)

    img.save(args.out)
    print(f"[sheet] {args.out}  ({len(syl)} syllables, {rows}x{cols})")
    print(f"[flag] empty glyphs: {len(empty)} {empty[:20]}")
    print(f"[flag] over-dense(>100/128): {len(dense)} {dense[:20]}")


if __name__ == "__main__":
    main()
