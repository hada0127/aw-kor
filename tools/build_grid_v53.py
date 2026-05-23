#!/usr/bin/env python3
"""
v53: hook A/B 확장 + "はじめまして" dialog (0xDF8E3C) → flag=3 한글 overlay.

설계:
- Hook A 재작성 (3-way 비교: welcome=1, name_prompt=2, hajimemashite=3) @ 0xA3CF14
- Hook B 패치 (flag=3 → r4=welcome_row2 (0xA3D300), r5=new_glyph (0xA3E000))
- 한글 glyph 데이터 1408 bytes @ 0xA3E000 ("처음 뵙겠습니다!" Korean overlay)

Hook B 확장 방식:
- 기존 0xA3D00E의 `b SKIP` 명령(0xE020)을 `b FLAG3_CHECK`(0xA3D086)로 변경
- 0xA3D086에 새 코드: cmp r0,#3 → bne SKIP / 아니면 r4=0xA3D300, r5=0xA3E000, b COMMON

Glyph 데이터:
- cell 0-7: 처 음 (공백) 뵙 겠 습 니 다 (Korean syllables)
- cell 8: ! (또는 빈)
- cell 9-21: 빈 타일
- 각 cell 2 타일 (top + bot) × 32 bytes = 1408 bytes total

원본 dialog 0xDF8E3C 식별:
- 0xDF8E3C에서 0a 09 시작 (welcome=0xDF8E14, name_prompt=0xDF8DB0과 비슷한 형식)
"""
import os, sys, json, struct
sys.path.insert(0, os.path.dirname(__file__))

ROM_IN  = "output/v52_dialog_alpha2.gba"
ROM_OUT = "output/v53_korean_overlay.gba"

# 한글 텍스트
TEXT = "처음 뵙겠습니다"  # 7 음절 + 공백 = 9 cells (공백 = 빈 셀)
# cell 0=처, 1=음, 2=공백, 3=뵙, 4=겠, 5=습, 6=니, 7=다

def hex_to_tile_bytes(hex_str):
    """hex string (64 chars) → 32 bytes."""
    assert len(hex_str) == 64, f'expected 64 hex chars, got {len(hex_str)}'
    return bytes.fromhex(hex_str)

def reposition_glyph(top_hex, bot_hex):
    """Galmuri json: top rows 0-3 + bot rows 4-7 (8px char with center gap).
    Repositioning: top rows 0-3 → top rows 4-7 (push char top to bottom of top tile),
    bot rows 4-7 → bot rows 0-3 (push char bottom to top of bot tile).
    Result: char spans cell border seamlessly without gap."""
    top = bytes.fromhex(top_hex)
    bot = bytes.fromhex(bot_hex)
    # Each tile: 8 rows × 4 bytes/row = 32 bytes. Row i = bytes[i*4:(i+1)*4]
    new_top = bytearray(32)
    new_bot = bytearray(32)
    # Galmuri top tile has data in rows 0-3 → put in new_top rows 4-7
    new_top[16:32] = top[0:16]  # rows 4-7 = original rows 0-3
    # Galmuri bot tile has data in rows 4-7 → put in new_bot rows 0-3
    new_bot[0:16] = bot[16:32]  # rows 0-3 = original rows 4-7
    return bytes(new_top), bytes(new_bot)

def build_glyph_data():
    """22 cells × 2 tiles × 32 bytes = 1408 bytes glyph data."""
    glyphs = json.load(open('data/korean_glyphs_8px.json'))

    BLANK = bytes(32)
    cells = []  # list of (top_tile, bot_tile)

    # 처음 뵙겠습니다 — 한글 글리프 (재배치 적용)
    for ch in "처음":
        top, bot = reposition_glyph(glyphs[ch][0], glyphs[ch][1])
        cells.append((top, bot))

    # 공백
    cells.append((BLANK, BLANK))

    for ch in "뵙겠습니다":
        top, bot = reposition_glyph(glyphs[ch][0], glyphs[ch][1])
        cells.append((top, bot))

    # 8 cells filled. Pad to 22 with blanks.
    while len(cells) < 22:
        cells.append((BLANK, BLANK))

    # Layout: 22 top tiles followed by 22 bot tiles? Or interleaved?
    # Check welcome's layout
    # In welcome glyph @ 0xA3D400: 22 cells with each cell having (top, bot) interleaved.
    # We'll go with same: cell 0 top, cell 0 bot, cell 1 top, cell 1 bot, ...
    # Actually let me verify by looking at welcome cell 0: positions 0xA3D400-0xA3D43F (64 bytes = 2 tiles)
    # And tilemap: row 1 cell 0 = tile 0x13C, row 2 cell 0 = tile 0x152
    # VRAM dest 0x06002780 = tile 0x13C. So tiles laid out sequentially in glyph data starting at tile 0x13C.
    # That means cell 0 top (tile 0x13C) at offset 0, cell 1 top (tile 0x13D) at offset 0x20, ...
    # cell 0 bot would be tile 0x152, which is at offset (0x152-0x13C)*0x20 = 0x16 * 0x20 = 0x2C0 = 704 bytes

    # So layout: all top tiles first (22 × 32 = 704 bytes), then all bot tiles (22 × 32 = 704)

    data = b''
    for top, _ in cells:
        data += top  # 22 top tiles
    for _, bot in cells:
        data += bot  # 22 bot tiles

    assert len(data) == 1408
    return data

def patch_hook_a(rom):
    """Hook A 재작성 @ 0xA3CF14 (3-way dialog dispatch)."""
    # Disassembly:
    # 0xA3CF14: mov r7, r0           4607
    # 0xA3CF16: ldr r0, [r6, #0x20]  6830
    # 0xA3CF18: ldr r1, [pc, #0x2C]  490B  (addr1 @ 0xA3CF48)
    # 0xA3CF1A: cmp r0, r1           4288
    # 0xA3CF1C: beq +0xE (→ 0xA3CF2E W)  D007
    # 0xA3CF1E: ldr r1, [pc, #0x2C]  490B  (addr2 @ 0xA3CF4C)
    # 0xA3CF20: cmp r0, r1           4288
    # 0xA3CF22: beq +0xC (→ 0xA3CF32 P)  D006
    # 0xA3CF24: ldr r1, [pc, #0x28]  490A  (addr3 @ 0xA3CF50)
    # 0xA3CF26: cmp r0, r1           4288
    # 0xA3CF28: beq +0xA (→ 0xA3CF36 H)  D005
    # 0xA3CF2A: movs r0, #0          2000
    # 0xA3CF2C: b +8 (→ 0xA3CF38 S)  E004
    # 0xA3CF2E W: movs r0, #1        2001
    # 0xA3CF30: b +4 (→ 0xA3CF38 S)  E002
    # 0xA3CF32 P: movs r0, #2        2002
    # 0xA3CF34: b +0 (→ 0xA3CF38 S)  E000
    # 0xA3CF36 H: movs r0, #3        2003
    # 0xA3CF38 S: ldr r1, [pc, #0x18] 4906  (flag_ptr @ 0xA3CF54)
    # 0xA3CF3A: strb r0, [r1]        7008
    # 0xA3CF3C: mov r0, r7           4638
    # 0xA3CF3E: str r0, [r6, #0x3c]  63F0
    # 0xA3CF40: pop {r4, r5, r6}     BC70
    # 0xA3CF42: bx lr                4770
    # 0xA3CF44: nop                  BF00
    # 0xA3CF46: 0xFF FF              (padding)
    # 0xA3CF48: addr1 = 0x08DF8E14   (welcome)
    # 0xA3CF4C: addr2 = 0x08DF8DB0   (name prompt)
    # 0xA3CF50: addr3 = 0x08DF8E3C   (hajimemashite)
    # 0xA3CF54: flag_ptr = 0x0203FFF0

    new_hook_a = bytes.fromhex(
        '0746'      # 0xA3CF14 mov r7, r0
        '306a'      # 0xA3CF16 ldr r0, [r6, #0x20]
        '0b49'      # 0xA3CF18 ldr r1, [pc, #0x2C]
        '8842'      # 0xA3CF1A cmp r0, r1
        '07d0'      # 0xA3CF1C beq +0xE (W)
        '0b49'      # 0xA3CF1E ldr r1, [pc, #0x2C]
        '8842'      # 0xA3CF20 cmp r0, r1
        '06d0'      # 0xA3CF22 beq +0xC (P)
        '0a49'      # 0xA3CF24 ldr r1, [pc, #0x28]
        '8842'      # 0xA3CF26 cmp r0, r1
        '05d0'      # 0xA3CF28 beq +0xA (H)
        '0020'      # 0xA3CF2A movs r0, #0
        '04e0'      # 0xA3CF2C b +8 (S)
        '0120'      # 0xA3CF2E W: movs r0, #1
        '02e0'      # 0xA3CF30 b +4 (S)
        '0220'      # 0xA3CF32 P: movs r0, #2
        '00e0'      # 0xA3CF34 b +0 (S)
        '0320'      # 0xA3CF36 H: movs r0, #3
        '0649'      # 0xA3CF38 S: ldr r1, [pc, #0x18]
        '0870'      # 0xA3CF3A strb r0, [r1]
        '3846'      # 0xA3CF3C mov r0, r7
        'f063'      # 0xA3CF3E str r0, [r6, #0x3c]
        '70bc'      # 0xA3CF40 pop {r4, r5, r6}
        '7047'      # 0xA3CF42 bx lr
        '00bf'      # 0xA3CF44 nop (align padding)
        'ffff'      # 0xA3CF46 padding
    )
    assert len(new_hook_a) == 0x34, f'hook A wrong size {len(new_hook_a)}'
    rom[0xA3CF14:0xA3CF14 + 0x34] = new_hook_a

    # Data at 0xA3CF48
    data = struct.pack('<IIII',
        0x08DF8E14,  # addr1: welcome dialog
        0x08DF8DB0,  # addr2: name prompt dialog
        0x08DF8E3C,  # addr3: hajimemashite dialog
        0x0203FFF0,  # flag ptr
    )
    rom[0xA3CF48:0xA3CF58] = data

def patch_hook_b(rom):
    """Hook B: 0xA3D00E의 b SKIP → b FLAG3_CHECK 변경, FLAG3_CHECK @ 0xA3D086 작성."""
    # 0xA3D00E currently: 20E0 = `b 0xA3D052` (offset = +0x40 from PC+4)
    # Change to: `b 0xA3D086`.
    # offset = 0xA3D086 - (0xA3D012) = 0x74, /2 = 0x3A. instruction = 0xE03A. bytes = `3A E0`
    rom[0xA3D00E:0xA3D010] = bytes.fromhex('3ae0')

    # FLAG3_CHECK @ 0xA3D086:
    #   cmp r0, #3                ; 2803
    #   bne SKIP (0xA3D052)        ; offset = 0xA3D052 - (0xA3D08C) = -0x3A, /2 = -0x1D = 0xE3 (8-bit two's comp), instr = D1E3, bytes E3 D1
    #   ldr r4, [pc, #imm1]        ; load r4 = 0xA3D300 (welcome row 2 tilemap)
    #   ldr r5, [pc, #imm2]        ; load r5 = 0xA3E000 (new Korean glyph data)
    #   b COMMON (0xA3D01C)        ; offset = 0xA3D01C - (PC+4)
    #   .word 0x08A3D300           ; r4_val
    #   .word 0x08A3E000           ; r5_val

    # Layout @ 0xA3D086:
    # 0xA3D086: cmp r0, #3              2803
    # 0xA3D088: bne SKIP                d1e3 (target 0xA3D052)
    # 0xA3D08A: ldr r4, [pc, #?]        4c?? — need offset
    # 0xA3D08C: ldr r5, [pc, #?]        4d??
    # 0xA3D08E: b COMMON                e0??
    # 0xA3D090: .word 0x08A3D300
    # 0xA3D094: .word 0x08A3E000

    # ldr r4, [pc, #imm] @ 0xA3D08A: PC+4=0xA3D08E, align=0xA3D08C, target=0xA3D090
    #   offset = 0xA3D090 - 0xA3D08C = 0x04, encoded as imm/4 = 1, instr = 0x4C00|0x01 = 0x4C01, bytes 01 4C
    # ldr r5, [pc, #imm] @ 0xA3D08C: PC+4=0xA3D090, align=0xA3D090, target=0xA3D094
    #   offset = 0xA3D094 - 0xA3D090 = 0x04, imm/4 = 1, instr = 0x4D00|0x01 = 0x4D01, bytes 01 4D
    # b COMMON @ 0xA3D08E: target=0xA3D01C, PC+4=0xA3D092, offset = 0xA3D01C - 0xA3D092 = -0x76 = -118
    #   /2 = -59
    #   11-bit two's comp of 59 (0x3B): ~0x3B + 1 = 0x7C4 + 1 = 0x7C5
    #   instr = 0xE000|0x7C5 = 0xE7C5, bytes C5 E7

    handler = bytes.fromhex(
        '0328'   # cmp r0, #3
        'e3d1'   # bne 0xA3D052 (SKIP)
        '014c'   # ldr r4, [pc, #4]
        '014d'   # ldr r5, [pc, #4]
        'c5e7'   # b 0xA3D01C (COMMON)
    )
    rom[0xA3D086:0xA3D086 + len(handler)] = handler

    # data
    rom[0xA3D090:0xA3D094] = struct.pack('<I', 0x08A3D300)
    rom[0xA3D094:0xA3D098] = struct.pack('<I', 0x08A3E000)

def main():
    rom = bytearray(open(ROM_IN, "rb").read())

    # 1. Korean glyph data @ 0xA3E000
    glyph_data = build_glyph_data()
    rom[0xA3E000:0xA3E000 + 1408] = glyph_data
    print(f'Korean glyph data: {len(glyph_data)} bytes @ 0xA3E000')

    # 2. Hook A 재작성
    patch_hook_a(rom)
    print('Hook A patched (3-way comparison)')

    # 3. Hook B 확장
    patch_hook_b(rom)
    print('Hook B patched (flag=3 handler @ 0xA3D086)')

    # 4. 체크섬
    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk

    open(ROM_OUT, "wb").write(rom)
    print(f'[OK] {ROM_OUT}')

if __name__ == "__main__":
    main()
