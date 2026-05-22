#!/usr/bin/env python3
"""
v36: v27 (welcome+name_prompt 한글) 베이스 + 그리드 알파벳/숫자 전체 매핑.

cell_to_slots.py 공식이 검증됨: top_extra가 그리드 셀 상단 절반 슬롯.
알파벳/숫자는 8x8이라 top_extra만 채우고 bot_extra는 비움.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from cell_to_slots import cell_slots, FONT_BASE
from hangul_glyph import render_tile

ROM_IN  = "output/v27_original_base.gba"
ROM_OUT = "output/v36_grid_AZ09.gba"

# 일본어 50음순 카타카나 → A-Z, 0-9 매핑 (총 36자)
KATA_TO_CHAR = [
    # 첫 26개 → A-Z
    (0x8341, 'A'), (0x8343, 'B'), (0x8345, 'C'), (0x8347, 'D'), (0x8349, 'E'),
    (0x834A, 'F'), (0x834C, 'G'), (0x834E, 'H'), (0x8350, 'I'), (0x8352, 'J'),
    (0x8354, 'K'), (0x8356, 'L'), (0x8358, 'M'), (0x835A, 'N'), (0x835C, 'O'),
    (0x835E, 'P'), (0x8360, 'Q'), (0x8362, 'R'), (0x8364, 'S'), (0x8366, 'T'),
    (0x8369, 'U'), (0x836A, 'V'), (0x836C, 'W'), (0x836D, 'X'), (0x836E, 'Y'),
    (0x836F, 'Z'),
    # 다음 10개 → 0-9
    (0x8371, '0'), (0x8374, '1'), (0x8376, '2'), (0x8378, '3'), (0x837D, '4'),
    (0x837E, '5'), (0x8380, '6'), (0x8381, '7'), (0x8382, '8'), (0x8384, '9'),
]

BLANK_TILE = bytes(32)

def main():
    if not os.path.exists(ROM_IN):
        print(f"[ERROR] base ROM not found: {ROM_IN}")
        sys.exit(1)
    rom = bytearray(open(ROM_IN, "rb").read())

    for sjis, ch in KATA_TO_CHAR:
        slots = cell_slots(sjis)
        if not slots:
            print(f"[SKIP] {ch} (0x{sjis:04X}) not in SJIS table")
            continue
        glyph = render_tile(ch, ink=10)
        # 그리드 셀은 8x16. top_extra=상단 8x8, bot_extra=하단 8x8.
        # 알파벳은 8x8이라 top_extra에 글리프, bot_extra는 빈 타일.
        for kind, tile_bytes in (
            ("top_extra", glyph),
            ("bot_extra", BLANK_TILE),
            ("top", BLANK_TILE),
            ("bottom", BLANK_TILE),
        ):
            slot = slots[kind]
            rom_addr = FONT_BASE + slot * 32
            file_off = rom_addr - 0x08000000
            rom[file_off:file_off+32] = tile_bytes
        print(f"  {ch} ← 0x{sjis:04X} (te={slots['top_extra']:4} be={slots['bot_extra']:4})")

    # 체크섬
    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk

    os.makedirs("output", exist_ok=True)
    open(ROM_OUT, "wb").write(rom)
    print(f"\n[OK] Wrote {ROM_OUT} ({len(rom):,} bytes, chk=0x{chk:02X})")

if __name__ == "__main__":
    main()
