#!/usr/bin/env python3
"""
v46: 대소문자 + 숫자 매핑 + 나머지 투명.

매핑 (SJIS table idx 순):
- idx 9-34 (26): A-Z 대문자
- idx 35-44 (10): 0-9 숫자 (35,36,37,38,41,42,43,44,45,46 - 39,40 skip)
- idx 47-72 (26): a-z 소문자 (47-71 + skip 72)
- idx 73+: 투명 (빈 타일)
- 매핑된 idx 중 cell_to_slots의 다른 슬롯 영역도 같이 빈 타일 처리

cell_to_slots: top + bottom = 메인 그리드, top_extra + bot_extra = 보조 패널.
v46: 두 영역 모두 알파벳 매핑 (메인=대문자, 보조=숫자)
나머지 위치는 투명
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from cell_to_slots import cell_slots, FONT_BASE
from render_8x16 import render_8x16

ROM_IN  = "output/v27_original_base.gba"
ROM_OUT = "output/v46_grid_full.gba"
SJIS_TBL = 0x08BE717A

BLANK = bytes(32)

def main():
    rom = bytearray(open(ROM_IN, "rb").read())
    tbl_off = SJIS_TBL - 0x08000000

    def get_sjis(idx):
        b = rom[tbl_off + idx*2 : tbl_off + idx*2 + 2]
        return (b[0]<<8) | b[1]

    # 매핑 계획
    plan = []
    # A-Z (26): idx 9-34
    for i, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        plan.append((9+i, ch))
    # 0-9 (10): idx 35,36,37,38 + 41,42,43,44,45,46
    digit_idx = [35, 36, 37, 38, 41, 42, 43, 44, 45, 46]
    for i, ch in enumerate("0123456789"):
        plan.append((digit_idx[i], ch))
    # a-z (26): idx 47-71 (25 slots) + idx 73 (skip 72 empty)
    lower_idx = list(range(47, 72)) + [73]  # 26 slots
    for i, ch in enumerate("abcdefghijklmnopqrstuvwxyz"):
        plan.append((lower_idx[i], ch))

    mapped_idxs = {idx for idx, _ in plan}

    # 1. 매핑된 글자 주입 (메인 그리드 top+bottom + 보조 패널 top_extra+bot_extra 모두)
    for idx, ch in plan:
        sjis = get_sjis(idx)
        if sjis == 0:
            print(f"[SKIP] {ch} ← idx {idx}: empty")
            continue
        slots = cell_slots(sjis)
        if not slots:
            print(f"[ERR] {ch} ← idx {idx}: no cell_slots")
            continue
        top, bot = render_8x16(ch)
        # 메인 그리드 (top + bottom)
        for slot, tile in ((slots['top'], top), (slots['bottom'], bot)):
            addr = FONT_BASE + slot * 32
            off = addr - 0x08000000
            rom[off:off+32] = tile
        # 보조 패널 (top_extra + bot_extra)도 같은 글자 (또는 빈 타일)
        for slot in (slots['top_extra'], slots['bot_extra']):
            addr = FONT_BASE + slot * 32
            off = addr - 0x08000000
            # 보조 패널 작은 영역에는 글자가 8x8라 작은 글리프 적절. 일단 빈으로
            rom[off:off+32] = BLANK
        print(f"  {ch} ← idx {idx:3} top={slots['top']:3} bot={slots['bottom']:3}")

    # 2. 매핑 안 된 idx 모두 → 4 슬롯 모두 빈 타일 (투명)
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

    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk
    open(ROM_OUT, "wb").write(rom)
    print(f"\n[OK] {ROM_OUT} ({len(rom):,} B, chk=0x{chk:02X})")

if __name__ == "__main__":
    main()
