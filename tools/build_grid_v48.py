#!/usr/bin/env python3
"""
v48: 전체 SJIS 테이블 idx (9-200) 처리 + 매핑된 것만 글리프, 나머지 빈.
v47의 한자/濁音 잔존 글리프 제거.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from cell_to_slots import cell_slots, FONT_BASE
from render_8x16 import render_8x16

ROM_IN  = "output/v27_original_base.gba"
ROM_OUT = "output/v48_grid_clean2.gba"
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

    mapped_idxs = {idx for idx, _ in plan}

    # 1. SJIS table 전체 (idx 0-200) — 매핑 안 된 idx 모두 빈 처리
    cleared = 0
    for idx in range(0, 200):
        if idx in mapped_idxs:
            continue
        sjis = get_sjis(idx)
        if sjis == 0:
            continue
        slots = cell_slots(sjis)
        if not slots:
            continue
        for slot in (slots['top'], slots['bottom'], slots['top_extra'], slots['bot_extra']):
            addr = FONT_BASE + slot * 32
            off = addr - 0x08000000
            rom[off:off+32] = BLANK
            cleared += 1
    print(f"  Cleared {cleared} slots from unmapped idx")

    # 2. 매핑된 글자 주입 (메인 그리드 top+bottom + 보조 패널은 빈 유지)
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
        # 보조 패널 빈
        for slot in (slots['top_extra'], slots['bot_extra']):
            addr = FONT_BASE + slot * 32
            off = addr - 0x08000000
            rom[off:off+32] = BLANK

    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk
    open(ROM_OUT, "wb").write(rom)
    print(f"[OK] {ROM_OUT}")

if __name__ == "__main__":
    main()
