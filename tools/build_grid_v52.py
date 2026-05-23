#!/usr/bin/env python3
"""
v52: v51 + "私はキャサリン。" dialog도 distinct katakana 알파벳 매핑.

원본 0xDF8E58:
  0a09 0a09         # newline+tab control
  8e84              # 私 (kanji)
  82cd              # は (hiragana)
  834c              # キ (idx 15 → G)
  8383              # ャ (small katakana, 매핑 안 됨)
  8354              # サ (idx 19 → S)
  838a              # リ (idx 50, 매핑 안 됨)
  8393              # ン (idx 56, 매핑 안 됨)
  8142              # 。 (전각 마침표)
  6b0a              # end marker
  0000
  0a09              # next dialog start
  ...

패치: 私+は+キャサリン → 7개 distinct katakana (idx 9-15)
  → "ABCDEFG"로 표시. 마침표 유지.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

ROM_IN  = "output/v51_dialog_alpha.gba"
ROM_OUT = "output/v52_dialog_alpha2.gba"

# SJIS codes mapped to A-G
SJIS_A = b'\x83\x41'  # ア
SJIS_B = b'\x83\x43'  # イ
SJIS_C = b'\x83\x45'  # ウ
SJIS_D = b'\x83\x47'  # エ
SJIS_E = b'\x83\x49'  # オ
SJIS_F = b'\x83\x4A'  # カ
SJIS_G = b'\x83\x4C'  # キ

def main():
    rom = bytearray(open(ROM_IN, "rb").read())

    # 私はキャサリン → 7개 katakana (14 bytes 보존)
    # 원본 0xDF8E58: 8e84 82cd 834c 8383 8354 838a 8393 = 7 chars × 2 bytes = 14 bytes
    # 패치: アイウエオカキ
    new_seq = SJIS_A + SJIS_B + SJIS_C + SJIS_D + SJIS_E + SJIS_F + SJIS_G
    assert len(new_seq) == 14

    print('Original 0xDF8E58..0xDF8E66 (私はキャサリン):')
    print(' ', rom[0xDF8E58:0xDF8E66].hex())
    rom[0xDF8E58:0xDF8E66] = new_seq
    print('Patched:')
    print(' ', rom[0xDF8E58:0xDF8E66].hex())

    # 체크섬
    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk

    open(ROM_OUT, "wb").write(rom)
    print(f"[OK] {ROM_OUT}")

if __name__ == "__main__":
    main()
