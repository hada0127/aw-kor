#!/usr/bin/env python3
"""이분탐색으로 좌측 그리드 슬롯 범위 발견."""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(__file__))
from cell_to_slots import FONT_BASE
from hangul_glyph import render_tile

ROM_IN = "output/v27_original_base.gba"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lo', type=int, default=72)
    ap.add_argument('--hi', type=int, default=287)
    ap.add_argument('--ch', default='X')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    rom = bytearray(open(ROM_IN, "rb").read())
    g = render_tile(a.ch, ink=10)
    for slot in range(a.lo, a.hi+1):
        addr = FONT_BASE + slot * 32
        off = addr - 0x08000000
        rom[off:off+32] = g
    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk
    open(a.out, "wb").write(rom)
    print(f"[OK] {a.out}: slots {a.lo}-{a.hi} = '{a.ch}'")

if __name__ == "__main__":
    main()
