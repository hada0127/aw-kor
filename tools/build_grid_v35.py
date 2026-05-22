#!/usr/bin/env python3
"""
v35: name input grid 검증 — ア-オ 슬롯에 A-E 완전 주입 (4-tile 모두).

cell_to_slots.py가 검증된 SJIS→4-tile 매핑을 제공:
- top_extra (top-left half)
- top       (top-right half)
- bottom    (bot-right half)
- bot_extra (bot-left half)

게임은 각 글자당 16x16 셀을 4-tile (2x2)로 렌더. 알파벳은 8x8이라 한 타일에 그리고
나머지 3타일은 빈 타일로 채움.

위치 가설: top_extra=좌상, top=우상, bot_extra=좌하, bottom=우하.
=> 글자를 top_extra (좌상)에 그리고, 나머지 빈 타일로 둠.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from cell_to_slots import cell_slots, FONT_BASE
from hangul_glyph import render_tile

ROM_IN = "original/Game Boy Wars Advance 1+2 (Japan).gba"
ROM_OUT = "output/v35_grid_AE_4tile.gba"

KATA_TO_LETTER = [
    (0x8341, 'A'),  # ア
    (0x8343, 'B'),  # イ
    (0x8345, 'C'),  # ウ
    (0x8347, 'D'),  # エ
    (0x8349, 'E'),  # オ
]

BLANK_TILE = bytes(32)

def main():
    rom = bytearray(open(ROM_IN, "rb").read())

    for sjis, letter in KATA_TO_LETTER:
        slots = cell_slots(sjis)
        if not slots:
            print(f"[ERROR] {letter} (0x{sjis:04X}) not in SJIS table")
            continue
        glyph = render_tile(letter, ink=10)
        # 글자: top_extra(좌상)에 그림. 나머지 빈 타일.
        layout = {
            "top_extra": glyph,
            "top":       BLANK_TILE,
            "bottom":    BLANK_TILE,
            "bot_extra": BLANK_TILE,
        }
        for kind, tile_bytes in layout.items():
            slot = slots[kind]
            rom_addr = FONT_BASE + slot * 32
            file_off = rom_addr - 0x08000000
            rom[file_off:file_off+32] = tile_bytes
        print(f"  {letter} → ア-slot family (top_extra={slots['top_extra']}, "
              f"top={slots['top']}, bot={slots['bottom']}, bot_extra={slots['bot_extra']})")

    # 체크섬 (실기 부팅을 위해)
    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk

    os.makedirs("output", exist_ok=True)
    open(ROM_OUT, "wb").write(rom)
    print(f"\nWrote {ROM_OUT} ({len(rom)} bytes, header chk=0x{chk:02X})")

if __name__ == "__main__":
    main()
