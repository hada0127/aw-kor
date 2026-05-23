#!/usr/bin/env python3
"""
v51: v50 + "はじめまして　_さん！" dialog SJIS를 distinct katakana로 재작성.

목표: name 입력 후 다음 화면 dialog 텍스트가 우리 알파벳 글리프로 깨끗하게 표시되게.
- 히라가나 → 카타카나(우리가 알파벳 글리프를 채운 슬롯) 사용
- name placeholder 0x69 + 0x8140 (전각공백) + 0x8149 (전각!) 는 그대로

원본:
  0xDF8E3C: 0a09 [0a09 control]
  0xDF8E3E: 82cd 82b6 82df 82dc 82b5 82c4 [はじめまして, 6 hiragana = 12 bytes]
  0xDF8E4A: 8140 [전각 공백]
  0xDF8E4C: 69 [i = name placeholder]
  0xDF8E4D: 82b3 82f1 [さん, 2 hiragana = 4 bytes]
  0xDF8E51: 8149 [전각 !]
  0xDF8E53: 6b 0a [end marker]

패치:
  "はじめまして" → "アイウエオカ" (A-F)
  "さん" → "キク" (G-H)
  공백+i+! 유지
  → "ABCDEF [A] GH!" 식으로 표시 + 사용자 입력 검증
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

ROM_IN  = "output/v50_clear_low_slots.gba"
ROM_OUT = "output/v51_dialog_alpha.gba"

# distinct katakana SJIS codes mapped to our A-Z glyphs (idx 9-34 → A-Z)
# A=ア(8341), B=イ(8343), C=ウ(8345), D=エ(8347), E=オ(8349), F=カ(834A=)... wait
# 우리 build_grid_v47.py에서 idx 9-34 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# idx 9 = ア(8341), idx 10 = イ(8343) 등. 정확한 SJIS 코드는 SJIS table에서 확인.

# Verified SJIS codes from table:
SJIS_A = b'\x83\x41'  # ア → A
SJIS_B = b'\x83\x43'  # イ → B
SJIS_C = b'\x83\x45'  # ウ → C
SJIS_D = b'\x83\x47'  # エ → D
SJIS_E = b'\x83\x49'  # オ → E
SJIS_F = b'\x83\x4A'  # カ → F (idx 14 = 0x834A)
SJIS_G = b'\x83\x4C'  # キ → G (idx 15)
SJIS_H = b'\x83\x4E'  # ク → H (idx 16)

def main():
    rom = bytearray(open(ROM_IN, "rb").read())

    print('Original 0xDF8E3E..0xDF8E53:')
    print(' ', rom[0xDF8E3E:0xDF8E53].hex())

    # "はじめまして" (12 bytes) → "アイウエオカ" (12 bytes)
    rom[0xDF8E3E:0xDF8E4A] = SJIS_A + SJIS_B + SJIS_C + SJIS_D + SJIS_E + SJIS_F

    # 0x8140 (전각 공백) 유지, 0x69 (name placeholder) 유지

    # "さん" (4 bytes) → "キク" (4 bytes)
    rom[0xDF8E4D:0xDF8E51] = SJIS_G + SJIS_H

    # 0x8149 (전각 !) 유지

    print('After patch 0xDF8E3E..0xDF8E53:')
    print(' ', rom[0xDF8E3E:0xDF8E53].hex())

    # Header 체크섬
    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk

    open(ROM_OUT, "wb").write(rom)
    print(f"[OK] {ROM_OUT}")

if __name__ == "__main__":
    main()
