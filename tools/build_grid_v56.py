#!/usr/bin/env python3
"""
v56: 사용자 피드백 반영 — 채팅창 잔재 제거 + 그리드 layout 재배치

사용자 요청:
1. 채팅창 좌측 "HC" 잔재 제거 — dialog text body를 SJIS 전각공백으로 채워 game typewrite가 안 보이게
2. 그리드 layout 분리:
   - 좌측 (idx 9-34): A-Z 대문자
   - 가운데 (idx 35-60): a-z 소문자
   - 우측 (idx 61-70): 0-9 숫자

베이스: output/v27_original_base.gba
"""
import os, sys, json, struct
sys.path.insert(0, os.path.dirname(__file__))
from cell_to_slots import cell_slots, FONT_BASE
from render_galmuri_8x16 import render_char

ROM_IN  = "output/v27_original_base.gba"
ROM_OUT = "output/v56_polished.gba"
SJIS_TBL = 0x08BE717A
BLANK = bytes(32)
SJIS_FULL_SPACE = b'\x81\x40'  # 전각 공백

def get_sjis(rom, idx):
    tbl_off = SJIS_TBL - 0x08000000
    b = rom[tbl_off + idx*2 : tbl_off + idx*2 + 2]
    return (b[0]<<8) | b[1]

def patch_dialog_text(rom):
    """모든 dialog text body를 전각공백으로 채워 game typewrite 잔재 제거.
    Hook B의 한글 overlay만 보임."""
    # name prompt 0xDF8DB0 (text body 0xDF8DB2~0xDF8DCC 정도)
    # 길이 유지하면서 모두 전각 공백으로
    # 원본 16개 katakana (각 2바이트) = 32 bytes
    fill_len = 0xDF8DCE - 0xDF8DB2  # 28 bytes = 14 full-space chars
    rom[0xDF8DB2:0xDF8DCE] = (SJIS_FULL_SPACE * (fill_len // 2))

    # welcome 0xDF8E14 (text body 0xDF8E16~)
    # 원본 16 katakana = 32 bytes
    fill_len = 0xDF8E36 - 0xDF8E16  # 32 bytes = 16 full-space
    rom[0xDF8E16:0xDF8E36] = (SJIS_FULL_SPACE * (fill_len // 2))

    # hajimemashite 0xDF8E3C (body 0xDF8E3E~)
    # placeholder 0x69 (1바이트)는 유지 + 전후를 공백으로
    # 원본: は じ め ま し て [공백] [i] さ ん ！
    # 0xDF8E3E~0xDF8E4A = 6 chars (12 bytes) → 6 전각공백
    rom[0xDF8E3E:0xDF8E4A] = (SJIS_FULL_SPACE * 6)
    # 0xDF8E4A:0xDF8E4C = 전각공백 유지 (이미 8140)
    # 0xDF8E4C = 0x69 placeholder 유지
    # 0xDF8E4D:0xDF8E51 = さ ん (4 bytes) → 2 전각공백
    rom[0xDF8E4D:0xDF8E51] = (SJIS_FULL_SPACE * 2)
    # 0xDF8E51:0xDF8E53 = 8149 (전각 !) 유지

    # watashi 0xDF8E58 (private は キャサリン)
    # 14 bytes → 7 전각공백
    rom[0xDF8E58:0xDF8E66] = (SJIS_FULL_SPACE * 7)

    # Character nameplate "キャサリン" 모든 occurrence (5+ 위치) 전각공백으로
    # 각 위치는 5 SJIS chars (10 bytes) = 5 전각공백
    catherine = bytes.fromhex('834c83838354838a8393')
    nameplate_addrs = [0x9292A8, 0x961F30, 0x99A7D4, 0x9D3078]
    for addr in nameplate_addrs:
        if rom[addr:addr+10] == catherine:
            rom[addr:addr+10] = (SJIS_FULL_SPACE * 5)
            print(f'  Nameplate patched at 0x{addr:08X}')

def patch_grid_glyphs(rom):
    """그리드 layout 재배치 + 모든 슬롯 cleanup.
    - idx 9-34 → A-Z
    - idx 35-60 → a-z
    - idx 61-70 → 0-9 (10 cells)
    """
    # 모든 슬롯 0-1024 cleanup
    for slot in range(0, 1024):
        addr = FONT_BASE + slot * 32
        off = addr - 0x08000000
        rom[off:off+32] = BLANK
    print('  Cleanup: slots 0-1023')

    # Plan: SJIS=0 skip
    def get_valid_idxs(start, end):
        valid = []
        for i in range(start, end+1):
            if get_sjis(rom, i) != 0:
                valid.append(i)
        return valid

    upper_idxs = get_valid_idxs(9, 34)
    print(f'  Upper idxs ({len(upper_idxs)}): {upper_idxs}')
    plan = list(zip(upper_idxs, "ABCDEFGHIJKLMNOPQRSTUVWXYZ"))

    lower_idxs = get_valid_idxs(35, 60)
    print(f'  Lower idxs ({len(lower_idxs)}): {lower_idxs}')
    plan += list(zip(lower_idxs[:26], "abcdefghijklmnopqrstuvwxyz"))

    digit_idxs = get_valid_idxs(61, 72)
    print(f'  Digit idxs ({len(digit_idxs)}): {digit_idxs}')
    plan += list(zip(digit_idxs[:10], "0123456789"))

    count = 0
    for idx, ch in plan:
        sjis = get_sjis(rom, idx)
        if sjis == 0:
            continue
        slots = cell_slots(sjis)
        if not slots:
            continue
        top, bot = render_char(ch)
        # 좌측 main grid (top + bottom) 에만 주입
        for slot_name in ('top', 'bottom'):
            slot = slots[slot_name]
            tile = top if slot_name == 'top' else bot
            addr = FONT_BASE + slot * 32
            off = addr - 0x08000000
            rom[off:off+32] = tile
        count += 1
    print(f'  Glyph 주입: {count}개 char')

def patch_hook_a(rom):
    new_hook_a = bytes.fromhex(
        '0746306a0b4988420 7d0 0b498842 06d0 0a498842 05d0 0020 04e0 0120 02e0 0220 00e0 0320'
        '06490870384 6f06370bc7047 00bf ffff'.replace(' ', '')
    )
    rom[0xA3CF14:0xA3CF14 + 0x34] = new_hook_a
    data = struct.pack('<IIII',
        0x08DF8E14, 0x08DF8DB0, 0x08DF8E3C, 0x0203FFF0,
    )
    rom[0xA3CF48:0xA3CF58] = data

def patch_hook_b(rom):
    rom[0xA3D00E:0xA3D010] = bytes.fromhex('3ae0')
    handler = bytes.fromhex('0328e3d1014c014dc5e7')
    rom[0xA3D086:0xA3D086 + len(handler)] = handler
    rom[0xA3D090:0xA3D094] = struct.pack('<I', 0x08A3D300)
    rom[0xA3D094:0xA3D098] = struct.pack('<I', 0x08A3E000)

def build_korean_glyph():
    cells = []
    for ch in "처음":
        top, bot = render_char(ch)
        cells.append((top, bot))
    cells.append((BLANK, BLANK))
    for ch in "뵙겠습니다":
        top, bot = render_char(ch)
        cells.append((top, bot))
    while len(cells) < 22:
        cells.append((BLANK, BLANK))
    data = b''
    for top, _ in cells: data += top
    for _, bot in cells: data += bot
    return data

def main():
    rom = bytearray(open(ROM_IN, "rb").read())

    print('1. Dialog text body 정리 (전각공백으로 채움)...')
    patch_dialog_text(rom)

    print('2. Grid layout 재배치...')
    patch_grid_glyphs(rom)

    print('3. Hook A 3-way...')
    patch_hook_a(rom)

    print('4. Hook B flag=3...')
    patch_hook_b(rom)

    print('5. Korean glyph @ 0xA3E000...')
    rom[0xA3E000:0xA3E000 + 1408] = build_korean_glyph()

    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk
    open(ROM_OUT, "wb").write(rom)
    print(f'[OK] {ROM_OUT}')

if __name__ == "__main__":
    main()
