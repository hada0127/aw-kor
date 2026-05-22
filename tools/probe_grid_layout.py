#!/usr/bin/env python3
"""슬롯 0-71 (그리드 셀 36개 × 2 타일/셀)에 알파벳/숫자 페어 주입.
좌측 그리드의 정확한 슬롯→셀 위치 매핑 발견.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from cell_to_slots import FONT_BASE
from hangul_glyph import split_tiles

ROM_IN  = "output/v27_original_base.gba"
ROM_OUT = "output/v42_grid_low_pairs.gba"

CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"  # 36자

def main():
    rom = bytearray(open(ROM_IN, "rb").read())

    # 슬롯 0부터 페어로 주입
    for i, ch in enumerate(CHARS):
        top_slot = i * 2
        bot_slot = top_slot + 1
        top_tile, bot_tile = split_tiles(ch, ink=10)
        for slot, tile in ((top_slot, top_tile), (bot_slot, bot_tile)):
            addr = FONT_BASE + slot * 32
            off = addr - 0x08000000
            rom[off:off+32] = tile

    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk
    open(ROM_OUT, "wb").write(rom)
    print(f"[OK] {ROM_OUT}: 슬롯 0-71에 A-Z 0-9 페어 주입")

if __name__ == "__main__":
    main()
