#!/usr/bin/env python3
"""
v54: v53 + 캐서린 dialog (0xDF8E54) → flag=4 "저는 캐서린입니다" 한글 overlay.

설계:
- Hook A 재작성 (4-way: welcome/name_prompt/hajimemashite/watashi) @ 0xA3CF14
- Hook B 패치: flag=3 핸들러 + flag=4 핸들러 (둘 다 0xA3D086+ 영역)
- 한글 glyph 데이터 추가 (1408 bytes) @ 0xA3F000 (flag=3 데이터 0xA3E000 다음)

Watashi dialog 0xDF8E54:
- 0xDF8E54: 0a 09 0a 09 (block prefix, double newline+tab)
- 0xDF8E58: 8e 84 82 cd ... (私はキャサリン text body)
"""
import os, sys, json, struct
sys.path.insert(0, os.path.dirname(__file__))

ROM_IN  = "output/v53_korean_overlay.gba"
ROM_OUT = "output/v54_caterine_korean.gba"

def reposition_glyph(top_hex, bot_hex):
    """Galmuri json 8px char → 16px 셀 중앙."""
    top = bytes.fromhex(top_hex)
    bot = bytes.fromhex(bot_hex)
    new_top = bytearray(32)
    new_bot = bytearray(32)
    new_top[16:32] = top[0:16]
    new_bot[0:16] = bot[16:32]
    return bytes(new_top), bytes(new_bot)

def build_caterine_glyph():
    """22 cells × 2 tiles × 32 bytes = 1408 bytes."""
    glyphs = json.load(open('data/korean_glyphs_8px.json'))
    BLANK = bytes(32)
    cells = []

    # "저는 캐서린입니다" = 8 cells + 공백 = 9 cells (저, 는, _, 캐, 서, 린, 입, 니, 다)
    for ch in "저는":
        top, bot = reposition_glyph(glyphs[ch][0], glyphs[ch][1])
        cells.append((top, bot))
    cells.append((BLANK, BLANK))  # 공백
    for ch in "캐서린입니다":
        top, bot = reposition_glyph(glyphs[ch][0], glyphs[ch][1])
        cells.append((top, bot))

    while len(cells) < 22:
        cells.append((BLANK, BLANK))

    data = b''
    for top, _ in cells: data += top
    for _, bot in cells: data += bot
    assert len(data) == 1408
    return data

def patch_hook_a_4way(rom):
    """Hook A 재작성 (4-way dialog dispatch) @ 0xA3CF14."""
    # New code @ 0xA3CF14, 60 bytes + data @ 0xA3CF50, 20 bytes
    # See bytes/offset calc in design comment
    code = bytes.fromhex(
        # 0xA3CF14
        '0746'   # mov r7, r0
        '306a'   # ldr r0, [r6, #0x20]
        '0d49'   # ldr r1, [pc, #0x34]   ; addr1 @ 0xA3CF50
        '8842'   # cmp r0, r1
        '0ad0'   # beq W (+0x14 → 0xA3CF34)
        '0d49'   # ldr r1, [pc, #0x34]   ; addr2 @ 0xA3CF54
        '8842'   # cmp r0, r1
        '09d0'   # beq P (+0x12 → 0xA3CF38)
        '0c49'   # ldr r1, [pc, #0x30]   ; addr3 @ 0xA3CF58
        '8842'   # cmp r0, r1
        '08d0'   # beq H (+0x10 → 0xA3CF3C)
        '0c49'   # ldr r1, [pc, #0x30]   ; addr4 @ 0xA3CF5C
        '8842'   # cmp r0, r1
        '07d0'   # beq K (+0x0E → 0xA3CF40)
        '0020'   # movs r0, #0
        '06e0'   # b S (+0x0C → 0xA3CF42)
        '0120'   # W: movs r0, #1
        '04e0'   # b S (+8 → 0xA3CF42)
        '0220'   # P: movs r0, #2
        '02e0'   # b S (+4 → 0xA3CF42)
        '0320'   # H: movs r0, #3
        '00e0'   # b S (+0 → 0xA3CF42)
        '0420'   # K: movs r0, #4
        '0749'   # S: ldr r1, [pc, #0x1C]   ; flag_ptr @ 0xA3CF60
        '0870'   # strb r0, [r1]
        '3846'   # mov r0, r7
        'f063'   # str r0, [r6, #0x3c]
        '70bc'   # pop {r4, r5, r6}
        '7047'   # bx lr
        '00bf'   # nop
    )
    assert len(code) == 0x3C, f'hook A code size wrong: {len(code)}'
    rom[0xA3CF14:0xA3CF14 + 0x3C] = code

    # Data @ 0xA3CF50
    data = struct.pack('<IIIII',
        0x08DF8E14,  # addr1: welcome
        0x08DF8DB0,  # addr2: name prompt
        0x08DF8E3C,  # addr3: hajimemashite
        0x08DF8E56,  # addr4: watashi (캐서린) — 두 번째 0a 09 prefix
        0x0203FFF0,  # flag_ptr
    )
    rom[0xA3CF50:0xA3CF64] = data

def patch_hook_b_flag34(rom):
    """Hook B에 flag=3, flag=4 핸들러 작성 @ 0xA3D086+.

    이미 v53에서 0xA3D00E의 b SKIP을 b 0xA3D086로 변경.
    여기서 0xA3D086에 flag=3 + flag=4 chain check 작성.

    Layout:
      0xA3D086: cmp r0, #3       (2803)
      0xA3D088: bne FLAG4_CHECK  (d1?? → 0xA3D098)
      0xA3D08A: ldr r4, [pc, #?] (r4 = 0xA3D300, welcome row 2 tilemap)
      0xA3D08C: ldr r5, [pc, #?] (r5 = 0xA3E000, flag3 glyph)
      0xA3D08E: b 0xA3D01C       (COMMON)
      0xA3D090: .word 0x08A3D300
      0xA3D094: .word 0x08A3E000
      0xA3D098: cmp r0, #4       (FLAG4_CHECK)
      0xA3D09A: bne SKIP (0xA3D052)
      0xA3D09C: ldr r4, [pc, #?] (r4 = 0xA3D300)
      0xA3D09E: ldr r5, [pc, #?] (r5 = 0xA3F000, flag4 glyph)
      0xA3D0A0: b 0xA3D01C       (COMMON)
      0xA3D0A2: padding
      0xA3D0A4: .word 0x08A3D300
      0xA3D0A8: .word 0x08A3F000

    bne FLAG4_CHECK @ 0xA3D088: target=0xA3D098, dist=(0xA3D098-0xA3D08C)=0xC, /2=6, instr 0xD106
    ldr r4 @ 0xA3D08A: target=0xA3D090, base=align(0xA3D08E)=0xA3D08C, offset=4, /4=1, instr 0x4C01
    ldr r5 @ 0xA3D08C: target=0xA3D094, base=align(0xA3D090)=0xA3D090, offset=4, /4=1, instr 0x4D01
    b 0xA3D01C @ 0xA3D08E: dist=(0xA3D01C-0xA3D092)=-0x76=-118, /2=-59, 11-bit=0x7C5, instr 0xE7C5
    cmp r0,#4 @ 0xA3D098: instr 0x2804
    bne SKIP @ 0xA3D09A: target=0xA3D052, dist=(0xA3D052-0xA3D09E)=-0x4C=-76, /2=-38, 8-bit=0xDA, instr 0xD1DA
    ldr r4 @ 0xA3D09C: target=0xA3D0A4, base=align(0xA3D0A0)=0xA3D0A0, offset=4, /4=1, instr 0x4C01
    ldr r5 @ 0xA3D09E: target=0xA3D0A8, base=align(0xA3D0A2)=0xA3D0A0, offset=8, /4=2, instr 0x4D02
    b 0xA3D01C @ 0xA3D0A0: dist=(0xA3D01C-0xA3D0A4)=-0x88=-136, /2=-68, 11-bit=0x7BC, instr 0xE7BC
    """
    handler = bytes.fromhex(
        # FLAG3_CHECK @ 0xA3D086
        '0328'   # cmp r0, #3
        '06d1'   # bne FLAG4_CHECK (→ 0xA3D098)
        '014c'   # ldr r4, [pc, #4] → 0xA3D090
        '014d'   # ldr r5, [pc, #4] → 0xA3D094
        'c5e7'   # b 0xA3D01C
    )
    rom[0xA3D086:0xA3D086 + len(handler)] = handler  # 10 bytes
    rom[0xA3D090:0xA3D094] = struct.pack('<I', 0x08A3D300)
    rom[0xA3D094:0xA3D098] = struct.pack('<I', 0x08A3E000)

    # FLAG4_CHECK @ 0xA3D098
    handler4 = bytes.fromhex(
        '0428'   # cmp r0, #4
        'dad1'   # bne SKIP (→ 0xA3D052)
        '014c'   # ldr r4, [pc, #4] → 0xA3D0A4
        '024d'   # ldr r5, [pc, #8] → 0xA3D0A8
        'bce7'   # b 0xA3D01C
        '00bf'   # nop (padding)
    )
    rom[0xA3D098:0xA3D098 + len(handler4)] = handler4  # 12 bytes
    rom[0xA3D0A4:0xA3D0A8] = struct.pack('<I', 0x08A3D300)
    rom[0xA3D0A8:0xA3D0AC] = struct.pack('<I', 0x08A3F000)

def main():
    rom = bytearray(open(ROM_IN, "rb").read())

    # 1. 캐서린 glyph data @ 0xA3F000
    glyph = build_caterine_glyph()
    rom[0xA3F000:0xA3F000 + 1408] = glyph
    print(f'캐서린 glyph data: {len(glyph)} bytes @ 0xA3F000')

    # 2. Hook A 4-way 재작성
    patch_hook_a_4way(rom)
    print('Hook A patched (4-way comparison)')

    # 3. Hook B flag=3+4 핸들러 작성
    patch_hook_b_flag34(rom)
    print('Hook B patched (flag=3 + flag=4 handlers)')

    # 4. 체크섬
    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk

    open(ROM_OUT, "wb").write(rom)
    print(f'[OK] {ROM_OUT}')

if __name__ == "__main__":
    main()
