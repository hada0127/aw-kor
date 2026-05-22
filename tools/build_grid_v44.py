#!/usr/bin/env python3
"""
v44: 좌측 그리드 알파벳/숫자 변환 (정확한 슬롯 발견 후).

핵심 발견 (2026-05-23 17:00):
- 좌측 그리드 = cell_to_slots의 `top` + `bottom` 슬롯
  - ア (idx 9): top=128, bottom=144
  - 첫 32 셀 = 슬롯 128-191
- 우측 패널 = cell_to_slots의 `top_extra` + `bot_extra` (v37에서 본 ABCDE)

SJIS 테이블 (0x08BE717A)의 인덱스 순서대로 가져옴:
- idx 9-34: 26개 katakana → A-Z
- idx 35-46 (39,40 제외): 12개 katakana → 0-9 + 여분

각 문자 8x8 → top half에 slot top, bot half에 slot bottom.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from cell_to_slots import cell_slots, FONT_BASE
from hangul_glyph import split_tiles

ROM_IN  = "output/v27_original_base.gba"
ROM_OUT = "output/v44_grid_left_alpha.gba"
SJIS_TBL = 0x08BE717A

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGITS = "0123456789"

def main():
    rom = bytearray(open(ROM_IN, "rb").read())
    tbl_off = SJIS_TBL - 0x08000000

    def get_sjis(idx):
        b = rom[tbl_off + idx*2 : tbl_off + idx*2 + 2]
        return (b[0]<<8) | b[1]

    plan = []
    for i, ch in enumerate(ALPHABET):
        plan.append((9+i, ch))
    digit_idx = [35, 36, 37, 38, 41, 42, 43, 44, 45, 46]
    for i, ch in enumerate(DIGITS):
        plan.append((digit_idx[i], ch))

    for idx, ch in plan:
        sjis = get_sjis(idx)
        if sjis == 0:
            print(f"[SKIP] {ch} ← idx {idx}: empty")
            continue
        slots = cell_slots(sjis)
        if not slots:
            print(f"[ERR] {ch} ← idx {idx} (0x{sjis:04X}): no slots")
            continue
        # 좌측 그리드에는 top + bottom 슬롯 사용
        top_tile, bot_tile = split_tiles(ch, ink=10)
        for slot, tile in ((slots['top'], top_tile), (slots['bottom'], bot_tile)):
            addr = FONT_BASE + slot * 32
            off = addr - 0x08000000
            rom[off:off+32] = tile
        print(f"  {ch} ← idx {idx:3} sjis=0x{sjis:04X} top={slots['top']:3} bot={slots['bottom']:3}")

    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk
    open(ROM_OUT, "wb").write(rom)
    print(f"\n[OK] {ROM_OUT} ({len(rom):,} B, chk=0x{chk:02X})")

if __name__ == "__main__":
    main()
