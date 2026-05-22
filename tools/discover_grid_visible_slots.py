#!/usr/bin/env python3
"""
그리드의 시각적으로 보이는 타일 슬롯 영역 발견.
288-511 슬롯에 슬롯 번호(2-3자리)를 표식으로 주입 → 화면 캡처 → 가독성 확인.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from cell_to_slots import FONT_BASE
from hangul_glyph import render_tile

ROM_IN  = "output/v27_original_base.gba"
ROM_OUT = "output/v38_discover_slots.gba"

def main():
    rom = bytearray(open(ROM_IN, "rb").read())

    # 슬롯 288-511 (8x28 = 224 슬롯, 14 그리드 행)
    # 각 슬롯에 마지막 자리 숫자 표식 (0-9 cycling) 주입
    for slot in range(288, 512):
        digit = str(slot % 10)
        glyph = render_tile(digit, ink=10)
        addr = FONT_BASE + slot * 32
        off = addr - 0x08000000
        rom[off:off+32] = glyph

    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk
    open(ROM_OUT, "wb").write(rom)
    print(f"[OK] {ROM_OUT} — 288-511 슬롯에 (슬롯%10) 숫자 표식 주입")

if __name__ == "__main__":
    main()
