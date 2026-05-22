#!/usr/bin/env python3
"""
v37: SJIS 테이블에서 SJIS 코드를 직접 추출하여 연속 인덱스로 매핑.

핵심 발견 (2026-05-23):
- 게임의 SJIS lookup table (0x08BE717A)은 표준 SJIS와 약간 다른 변종 코드 사용
  (예: 테이블에는 ツ=0x8363인데 표준 SJIS는 0x8362)
- 표준 코드로 cell_slots() 호출 시 일부는 매우 다른 페이지로 점프 → 그리드 깨짐
- 테이블 인덱스 순서(0,1,2,…)대로 SJIS 코드를 읽으면 슬롯이 정확히 연속

매핑:
- idx 9 (ア) → A, idx 10 (イ) → B, … idx 34 (ハ) → Z
- idx 0-8 (１-９)는 건드리지 않음
- 또는 idx 35-44 → 0-9 (조정 가능)
"""
import os, sys, struct
sys.path.insert(0, os.path.dirname(__file__))
from cell_to_slots import cell_slots, FONT_BASE
from hangul_glyph import render_tile

ROM_IN  = "output/v27_original_base.gba"
ROM_OUT = "output/v37_grid_AZ_idx.gba"
SJIS_TBL = 0x08BE717A

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGITS = "0123456789"

BLANK_TILE = bytes(32)

def main():
    rom = bytearray(open(ROM_IN, "rb").read())
    tbl_off = SJIS_TBL - 0x08000000

    # 테이블 idx → SJIS 코드 매핑 가져오기
    def get_sjis_at(idx):
        b = rom[tbl_off + idx*2 : tbl_off + idx*2 + 2]
        return (b[0] << 8) | b[1]

    # 영문 A-Z: idx 9..34 (26개)
    # 숫자 0-9: idx 35..44 (10개) — 비어있는 39, 40은 스킵하고 41부터 채움
    plan = []
    for i, ch in enumerate(ALPHABET):
        plan.append((9 + i, ch))
    # 35,36,37,38 (ヒ,フ,ヘ,ホ), 41-46 (マ,ミ,ム,メ,モ,ヤ) → 10자리
    digit_indices = [35, 36, 37, 38, 41, 42, 43, 44, 45, 46]
    for i, ch in enumerate(DIGITS):
        plan.append((digit_indices[i], ch))

    for idx, ch in plan:
        sjis = get_sjis_at(idx)
        if sjis == 0:
            print(f"[SKIP] {ch} ← idx {idx}: empty slot")
            continue
        slots = cell_slots(sjis)
        if not slots:
            print(f"[ERR] {ch} ← idx {idx} (0x{sjis:04X}): not in cell_to_slots")
            continue
        glyph = render_tile(ch, ink=10)
        # 그리드: top_extra만 글리프, 나머지 빈 타일
        for kind, t in (("top_extra", glyph), ("bot_extra", BLANK_TILE),
                       ("top", BLANK_TILE), ("bottom", BLANK_TILE)):
            slot = slots[kind]
            addr = FONT_BASE + slot * 32
            off = addr - 0x08000000
            rom[off:off+32] = t
        print(f"  {ch} ← idx {idx:3} (0x{sjis:04X}) te={slots['top_extra']:4} be={slots['bot_extra']:4}")

    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk
    open(ROM_OUT, "wb").write(rom)
    print(f"\n[OK] {ROM_OUT} ({len(rom):,} B, chk=0x{chk:02X})")

if __name__ == "__main__":
    main()
