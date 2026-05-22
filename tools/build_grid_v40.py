#!/usr/bin/env python3
"""
v40: 그리드의 실제 타일 페어 구조 사용 — 슬롯 (N, N+1)이 각 셀의 top+bottom.

BG0 SB12 VRAM 덤프 분석 결과:
  Row 2 cols 0-6: 306, 308, 310, 312, 314, 316, 318  (cell top tiles)
  Row 3 cols 0-6: 307, 309, 311, 313, 315, 317, 319  (cell bot tiles)
  => 각 그리드 셀 = (top_tile, top_tile+1) 페어, 첫 셀=306, 다음=308, ...

ア = 페어 (306, 307). イ = 페어 (308, 309). 등.

A-Z + 0-9 = 36 글자, 72 타일. 슬롯 306-377.

각 글리프 8x8을 위/아래로 분할하여 두 타일에 저장.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from cell_to_slots import FONT_BASE
from hangul_glyph import split_tiles, render_tile

ROM_IN  = "output/v27_original_base.gba"
ROM_OUT = "output/v40_grid_pairs.gba"

CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"  # 36자

def main():
    rom = bytearray(open(ROM_IN, "rb").read())

    # 슬롯 306부터 페어로 (top, bot) 주입
    for i, ch in enumerate(CHARS):
        top_slot = 306 + i*2
        bot_slot = top_slot + 1
        top_tile, bot_tile = split_tiles(ch, ink=10)
        for slot, tile in ((top_slot, top_tile), (bot_slot, bot_tile)):
            addr = FONT_BASE + slot * 32
            off = addr - 0x08000000
            rom[off:off+32] = tile
        print(f'  {ch:2} → pair ({top_slot:3}, {bot_slot:3})')

    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk
    open(ROM_OUT, "wb").write(rom)
    print(f"\n[OK] {ROM_OUT} ({len(rom):,} B, chk=0x{chk:02X})")

if __name__ == "__main__":
    main()
