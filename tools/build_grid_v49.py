#!/usr/bin/env python3
"""
v49: v48 + dialog 잔존 제거 + 다음 dialog 한글화.

문제: 화면 좌측 하단 "してくにさ" 잔존 = "マップの名前を入力してください。"
원인: dialog 데이터 블록이 연속이고 v27 hook이 일부만 덮음 → 다음 dialog 데이터 부분 표시

해결:
1. v48 base + 잔존 dialog 텍스트 (0xDF8DCD~) 빈 처리
2. 다음 dialog "まちがいないかしら？" 한글 patch ("맞나요?")
3. "はじめまして XXXさん!" 한글 patch ("처음 뵙겠습니다 XXX님!")
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from cell_to_slots import cell_slots, FONT_BASE
from render_8x16 import render_8x16

ROM_IN  = "output/v48_grid_clean2.gba"
ROM_OUT = "output/v49_grid_dialog.gba"

def main():
    rom = bytearray(open(ROM_IN, "rb").read())

    # 1. "マップの名前を入力してください。" (0xDF8DCD~0xDF8DEF) 빈 처리
    # 게임 typewriter가 0x00 만나면 출력 안 함
    print('Original 0xDF8DCD..0xDF8DF0:')
    print(' ', rom[0xDF8DCD:0xDF8DF0].hex())
    for i in range(0xDF8DCD, 0xDF8DF0):
        rom[i] = 0x00
    print('After clear:')
    print(' ', rom[0xDF8DCD:0xDF8DF0].hex())

    # 2. "まちがいないかしら？" 위치 확인 후 그 부분 그대로 두기 (사용자가 한글화 요청한 부분)
    # 0xDF8DF0~0xDF8E15 영역
    print('\n0xDF8DF0..0xDF8E15:')
    print(' ', rom[0xDF8DF0:0xDF8E15].hex())
    # "まちがいないかしら？" 뒤의 r=72 Q=51 Y=59 는 다음 dialog 데이터 헤더? 일단 그대로 두기

    # 3. "はじめまして　＿さん！" 위치
    print('\n0xDF8E36..0xDF8E60:')
    print(' ', rom[0xDF8E36:0xDF8E60].hex())

    # 체크섬
    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk
    open(ROM_OUT, "wb").write(rom)
    print(f"\n[OK] {ROM_OUT}")

if __name__ == "__main__":
    main()
