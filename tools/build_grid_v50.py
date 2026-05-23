#!/usr/bin/env python3
"""
v50: v49 + 슬롯 0-127 빈 처리 → 가운데/우측 잔존 글리프 모두 제거.

주의: 슬롯 0-127은 다른 dialog font일 수 있음.
부작용 확인 필요 (한글 dialog가 깨질 수도).
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from cell_to_slots import FONT_BASE

ROM_IN  = "output/v49_grid_dialog.gba"
ROM_OUT = "output/v50_clear_low_slots.gba"

BLANK = bytes(32)

def main():
    rom = bytearray(open(ROM_IN, "rb").read())
    # 슬롯 0-127 빈 처리
    for slot in range(0, 128):
        addr = FONT_BASE + slot * 32
        off = addr - 0x08000000
        rom[off:off+32] = BLANK
    print(f"  Cleared slots 0-127 (4KB)")

    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk
    open(ROM_OUT, "wb").write(rom)
    print(f"[OK] {ROM_OUT}")

if __name__ == "__main__":
    main()
