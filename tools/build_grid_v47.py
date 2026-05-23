#!/usr/bin/env python3
"""
v47: 광범위 투명 처리 + 정확한 매핑.

전략:
1. 모든 그리드 슬롯 (128-511) 빈 타일
2. A-Z, 0-9, a-z 글리프만 주입 (top + bottom + top_extra + bot_extra 4개 모두)
3. 그러면 매핑된 글자만 보이고 나머지는 투명
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from cell_to_slots import cell_slots, FONT_BASE
from render_8x16 import render_8x16

ROM_IN  = "output/v27_original_base.gba"
ROM_OUT = "output/v47_grid_clean.gba"
SJIS_TBL = 0x08BE717A

BLANK = bytes(32)

def main():
    rom = bytearray(open(ROM_IN, "rb").read())
    tbl_off = SJIS_TBL - 0x08000000

    def get_sjis(idx):
        b = rom[tbl_off + idx*2 : tbl_off + idx*2 + 2]
        return (b[0]<<8) | b[1]

    plan = []
    for i, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        plan.append((9+i, ch))
    digit_idx = [35, 36, 37, 38, 41, 42, 43, 44, 45, 46]
    for i, ch in enumerate("0123456789"):
        plan.append((digit_idx[i], ch))
    lower_idx = list(range(47, 72)) + [73]
    for i, ch in enumerate("abcdefghijklmnopqrstuvwxyz"):
        plan.append((lower_idx[i], ch))

    # 1. 슬롯 128-511 모두 빈 타일 (광범위 투명)
    for slot in range(128, 512):
        addr = FONT_BASE + slot * 32
        off = addr - 0x08000000
        rom[off:off+32] = BLANK
    print(f"  Cleared slots 128-511 ({(512-128)*32} bytes)")

    # 2. 매핑된 글자만 4개 슬롯 모두에 주입
    for idx, ch in plan:
        sjis = get_sjis(idx)
        if sjis == 0:
            continue
        slots = cell_slots(sjis)
        if not slots:
            continue
        top, bot = render_8x16(ch)
        # 메인 그리드 (top + bottom) — 8x16 풀크기
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
