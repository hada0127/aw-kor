#!/usr/bin/env python3
"""슬롯 0-287에 표식 — 좌측 그리드가 이 영역인지 확인.
주의: 0-127, 144-159 등은 dialog 폰트 영역이라 위험. 그러나 어쩔수 없이 시도.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from cell_to_slots import FONT_BASE
from hangul_glyph import render_tile

ROM_IN  = "output/v27_original_base.gba"
ROM_OUT = "output/v41_probe_low.gba"

def main():
    rom = bytearray(open(ROM_IN, "rb").read())
    for slot in range(0, 288):
        # 모든 슬롯에 'O' (감지 쉬운 글리프) 채움
        glyph = render_tile('O', ink=10)
        addr = FONT_BASE + slot * 32
        off = addr - 0x08000000
        rom[off:off+32] = glyph

    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk
    open(ROM_OUT, "wb").write(rom)
    print(f"[OK] {ROM_OUT} — 슬롯 0-287에 'O' 표식 주입")

if __name__ == "__main__":
    main()
