#!/usr/bin/env python3
"""
v55: 통합 polished ROM — 사용자 피드백 반영

개선 사항:
1. 그리드 글자 두께/여백: Galmuri ASCII (얇은 I, 자연 간격)
2. 모든 grid 슬롯 cleanup: top/bottom/top_extra/bot_extra (일본어 잔재 완전 제거)
3. 소문자 a-z 모두 표시 (idx 47-72)
4. 다음 화면 한글: Galmuri 11px (더 크게)
5. Hook A/B 3-way (welcome/name_prompt/hajimemashite) — v53 그대로

베이스: output/v27_original_base.gba (clean)
"""
import os, sys, json, struct
sys.path.insert(0, os.path.dirname(__file__))
from cell_to_slots import cell_slots, FONT_BASE
from render_galmuri_8x16 import render_char

ROM_IN  = "output/v27_original_base.gba"
ROM_OUT = "output/v55_polished.gba"
SJIS_TBL = 0x08BE717A

BLANK = bytes(32)

# ============================================================
# 1. Dialog text patches (distinct katakana → alphabet 매핑)
# ============================================================
SJIS_A = b'\x83\x41'  # ア
SJIS_B = b'\x83\x43'  # イ
SJIS_C = b'\x83\x45'  # ウ
SJIS_D = b'\x83\x47'  # エ
SJIS_E = b'\x83\x49'  # オ
SJIS_F = b'\x83\x4A'  # カ
SJIS_G = b'\x83\x4C'  # キ
SJIS_H = b'\x83\x4E'  # ク

def patch_dialog_text(rom):
    """v51 + v52 패치 통합."""
    # "はじめまして" → "アイウエオカ" (0xDF8E3E)
    rom[0xDF8E3E:0xDF8E4A] = SJIS_A + SJIS_B + SJIS_C + SJIS_D + SJIS_E + SJIS_F
    # 0x8140 (전각공백) + 0x69 (placeholder) 유지
    # "さん" → "キク" (0xDF8E4D)
    rom[0xDF8E4D:0xDF8E51] = SJIS_G + SJIS_H
    # "私はキャサリン" → "アイウエオカキ" (0xDF8E58)
    rom[0xDF8E58:0xDF8E66] = SJIS_A + SJIS_B + SJIS_C + SJIS_D + SJIS_E + SJIS_F + SJIS_G

# ============================================================
# 2. Grid alphabet glyphs (Galmuri ASCII)
# ============================================================
def patch_grid_glyphs(rom):
    """모든 grid 슬롯 cleanup + 새 alphabet 글리프 주입."""
    # First: clear ALL slots in range 0-1024 to blank (catch dakuten/small katakana etc)
    for slot in range(0, 1024):
        addr = FONT_BASE + slot * 32
        off = addr - 0x08000000
        rom[off:off+32] = BLANK

    # SJIS table에서 각 idx의 SJIS code 추출
    tbl_off = SJIS_TBL - 0x08000000
    def get_sjis(idx):
        b = rom[tbl_off + idx*2 : tbl_off + idx*2 + 2]
        return (b[0]<<8) | b[1]

    # Mapping plan (v47 derived):
    # idx 9-34: A-Z (26 chars)
    # idx 35-38, 41-46: 0-9 (10 chars - some idx skipped for non-SJIS positions)
    # idx 47-72 + 73: a-z (26 chars)
    plan = []
    for i, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        plan.append((9+i, ch))
    digit_idx = [35, 36, 37, 38, 41, 42, 43, 44, 45, 46]
    for i, ch in enumerate("0123456789"):
        plan.append((digit_idx[i], ch))
    lower_idx = list(range(47, 73))  # 26 indices for a-z
    for i, ch in enumerate("abcdefghijklmnopqrstuvwxyz"):
        plan.append((lower_idx[i], ch))

    count = 0
    for idx, ch in plan:
        sjis = get_sjis(idx)
        if sjis == 0:
            continue
        slots = cell_slots(sjis)
        if not slots:
            continue
        top, bot = render_char(ch)
        # 좌측 main grid (top+bottom) 에만 글리프 주입
        # 우측 small panel (top_extra+bot_extra) 은 이미 cleanup으로 blank
        for slot_name in ('top', 'bottom'):
            slot = slots[slot_name]
            tile = top if slot_name == 'top' else bot
            addr = FONT_BASE + slot * 32
            off = addr - 0x08000000
            rom[off:off+32] = tile
        count += 1
    print(f'  Glyph 주입: {count}개 char × 4 slot types')

# ============================================================
# 3. Hook A 3-way 재작성 (v53 같음)
# ============================================================
def patch_hook_a(rom):
    new_hook_a = bytes.fromhex(
        '0746306a0b4988420 7d0 0b498842 06d0 0a498842 05d0 0020 04e0 0120 02e0 0220 00e0 0320'
        '06490870384 6f06370bc7047 00bf ffff'.replace(' ', '')
    )
    assert len(new_hook_a) == 0x34, f'hook A size {len(new_hook_a)}'
    rom[0xA3CF14:0xA3CF14 + 0x34] = new_hook_a
    data = struct.pack('<IIII',
        0x08DF8E14,  # welcome
        0x08DF8DB0,  # name prompt
        0x08DF8E3C,  # hajimemashite
        0x0203FFF0,  # flag ptr
    )
    rom[0xA3CF48:0xA3CF58] = data

# ============================================================
# 4. Hook B: flag=3 handler @ 0xA3D086 (v53 같음)
# ============================================================
def patch_hook_b(rom):
    # 0xA3D00E의 b SKIP을 b 0xA3D086으로
    rom[0xA3D00E:0xA3D010] = bytes.fromhex('3ae0')
    handler = bytes.fromhex(
        '0328'   # cmp r0, #3
        'e3d1'   # bne 0xA3D052 (SKIP)
        '014c'   # ldr r4, [pc, #4]
        '014d'   # ldr r5, [pc, #4]
        'c5e7'   # b 0xA3D01C
    )
    rom[0xA3D086:0xA3D086 + len(handler)] = handler
    rom[0xA3D090:0xA3D094] = struct.pack('<I', 0x08A3D300)  # welcome row 2 tilemap (with ▼ marker)
    rom[0xA3D094:0xA3D098] = struct.pack('<I', 0x08A3E000)  # new Korean glyph

# ============================================================
# 5. Korean glyph data @ 0xA3E000 (Galmuri 11px, 더 크게)
# ============================================================
def build_korean_glyph():
    """22 cells × 2 tiles × 32 bytes = 1408 bytes."""
    cells = []
    # "처음 뵙겠습니다" = 처, 음, _, 뵙, 겠, 습, 니, 다
    for ch in "처음":
        top, bot = render_char(ch)
        cells.append((top, bot))
    cells.append((BLANK, BLANK))  # 공백
    for ch in "뵙겠습니다":
        top, bot = render_char(ch)
        cells.append((top, bot))

    while len(cells) < 22:
        cells.append((BLANK, BLANK))

    data = b''
    for top, _ in cells: data += top
    for _, bot in cells: data += bot
    assert len(data) == 1408
    return data

def main():
    rom = bytearray(open(ROM_IN, "rb").read())

    print('1. Dialog text patches...')
    patch_dialog_text(rom)

    print('2. Grid glyphs (Galmuri ASCII, all 4 slot types)...')
    patch_grid_glyphs(rom)

    print('3. Hook A 3-way 재작성...')
    patch_hook_a(rom)

    print('4. Hook B flag=3 handler...')
    patch_hook_b(rom)

    print('5. Korean glyph (Galmuri 11px) @ 0xA3E000...')
    glyph = build_korean_glyph()
    rom[0xA3E000:0xA3E000 + 1408] = glyph
    print(f'  {len(glyph)} bytes written')

    # 6. 체크섬
    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk

    open(ROM_OUT, "wb").write(rom)
    print(f'[OK] {ROM_OUT}')

if __name__ == "__main__":
    main()
