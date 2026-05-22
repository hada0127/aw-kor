#!/usr/bin/env python3
"""v45: 좌측 그리드에 가독성 높은 8x16 알파벳/숫자."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from cell_to_slots import cell_slots, FONT_BASE
from render_8x16 import render_8x16

ROM_IN  = "output/v27_original_base.gba"
ROM_OUT = "output/v45_grid_8x16.gba"
SJIS_TBL = 0x08BE717A

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGITS = "0123456789"

def main():
    rom = bytearray(open(ROM_IN, "rb").read())
    tbl_off = SJIS_TBL - 0x08000000
    def get_sjis(idx):
        b = rom[tbl_off + idx*2 : tbl_off + idx*2 + 2]
        return (b[0]<<8) | b[1]

    plan = [(9+i, ch) for i, ch in enumerate(ALPHABET)]
    digit_idx = [35, 36, 37, 38, 41, 42, 43, 44, 45, 46]
    plan += [(digit_idx[i], ch) for i, ch in enumerate(DIGITS)]

    for idx, ch in plan:
        sjis = get_sjis(idx)
        if sjis == 0:
            continue
        slots = cell_slots(sjis)
        if not slots:
            continue
        top, bot = render_8x16(ch)
        for slot, tile in ((slots['top'], top), (slots['bottom'], bot)):
            addr = FONT_BASE + slot * 32
            off = addr - 0x08000000
            rom[off:off+32] = tile

    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk
    open(ROM_OUT, "wb").write(rom)
    print(f"[OK] {ROM_OUT}")

if __name__ == "__main__":
    main()
