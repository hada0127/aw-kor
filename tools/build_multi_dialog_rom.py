#!/usr/bin/env python3
"""Build ROM with N dialogs patched for Korean 2-line display."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
from bdf import load_bdf, glyph_grid

ks = Ks(KS_ARCH_ARM, KS_MODE_THUMB)
gl, _ = load_bdf('reference/fonts/Galmuri11.bdf')

N_CELLS = 18
LEAD = 6
LINE1_BASE = 316  # Free tile range
LINE2_BASE = 256  # Replace v14's area

def render_msg_padded(msg, lead_cells, total_cells):
    width = total_cells * 8
    bm = [[0]*width for _ in range(11)]
    x_off = lead_cells * 8
    for k, ch in enumerate(msg):
        if ch == ' ':
            continue
        g = gl.get(ord(ch))
        if not g:
            continue
        grid, w, hh, xo, yo = glyph_grid(g)
        for r in range(min(11, len(grid))):
            for c in range(min(11, w)):
                x = x_off + k*12 + c
                if x < width and grid[r][c]:
                    bm[r][x] = 1
    return bm

def add_marker(bm, x_start):
    pattern = ["XXXXXXX", ".XXXXX.", "..XXX..", "...X..."]
    base_y = 4
    for dy, row in enumerate(pattern):
        y = base_y + dy
        if y >= len(bm):
            break
        for dx, ch in enumerate(row):
            x = x_start + dx
            if x < len(bm[0]) and ch == 'X':
                bm[y][x] = 1
    return bm

def make_tiles(bm, n_cells):
    glyph_top = bytearray()
    glyph_bot = bytearray()
    def sp(t, r, c, v):
        bi = r*4 + c//2
        if c%2 == 0:
            t[bi] = (t[bi] & 0xF0) | (v & 0xF)
        else:
            t[bi] = (t[bi] & 0x0F) | ((v & 0xF) << 4)
    for cell in range(n_cells):
        top = bytearray(32)
        for tr in range(8):
            for tc in range(8):
                gc = cell*8 + tc
                if tr < 11 and gc < len(bm[0]) and bm[tr][gc]:
                    sp(top, tr, tc, 10)
        glyph_top.extend(top)
        bot = bytearray(32)
        for tr in range(3):
            gr = 8 + tr
            for tc in range(8):
                gc = cell*8 + tc
                if gr < 11 and gc < len(bm[0]) and bm[gr][gc]:
                    sp(bot, tr, tc, 10)
        glyph_bot.extend(bot)
    return glyph_top + glyph_bot

def gen_glyph_data(line1, line2):
    bm1 = render_msg_padded(line1, LEAD, N_CELLS) if line1 else [[0]*(N_CELLS*8) for _ in range(11)]
    bm2 = render_msg_padded(line2, LEAD, N_CELLS) if line2 else [[0]*(N_CELLS*8) for _ in range(11)]
    if line2:
        end_x = LEAD*8 + len(line2)*12 - 4
        bm2 = add_marker(bm2, end_x)
    return make_tiles(bm1, N_CELLS), make_tiles(bm2, N_CELLS)

def build_rom(base_rom, dialogs, output):
    """dialogs = list of (text_addr, line1, line2)"""
    # Shared tilemap data (same for all dialogs)
    shared_row1 = bytearray()
    shared_row2 = bytearray()
    shared_row3 = bytearray()
    shared_row4 = bytearray()
    for i in range(N_CELLS):
        e1_top = (LINE1_BASE + i) | 0x8000
        e1_bot = (LINE1_BASE + N_CELLS + i) | 0x8000
        e2_top = (LINE2_BASE + i) | 0x8000
        e2_bot = (LINE2_BASE + N_CELLS + i) | 0x8000
        shared_row1 += bytes([e1_top & 0xFF, e1_top >> 8])
        shared_row2 += bytes([e1_bot & 0xFF, e1_bot >> 8])
        shared_row3 += bytes([e2_top & 0xFF, e2_top >> 8])
        shared_row4 += bytes([e2_bot & 0xFF, e2_bot >> 8])
    
    # Memory layout:
    # 0x08A3D200: shared tilemap (4 rows × 0x40 = 0x100 bytes)
    # 0x08A3D300+: per-dialog glyph data (2 lines × 1152 bytes = 2304 per dialog)
    DATA = 0x08A3D200
    HEADER_SIZE = 0x100
    PER_DIALOG = 2304
    
    data_buf = bytearray(0x10000)  # 64 KB
    data_buf[0x000:0x040] = shared_row1
    data_buf[0x040:0x080] = shared_row2
    data_buf[0x080:0x0C0] = shared_row3
    data_buf[0x0C0:0x100] = shared_row4
    
    for i, (addr, l1, l2) in enumerate(dialogs):
        g1, g2 = gen_glyph_data(l1, l2)
        off = HEADER_SIZE + i * PER_DIALOG
        data_buf[off:off+1152] = g1
        data_buf[off+1152:off+2304] = g2
    
    # Hook A: identify dialog index by addr. Use if/else chain.
    # For each dialog, generate compare + branch
    HOOK_A = 0x08A3CF14
    asm_A = "mov r7, r0\nldr r0, [r6, #0x20]\n"
    for i, (addr, _, _) in enumerate(dialogs):
        # SUBTRACT 2 from given address (welcome was 0xDF8E14 = 0xDF8E16 - 2)
        # Actually addr here is already the engine-loaded value (= text_addr - 2 maybe?)
        # From verified: welcome stored as 0x08DF8E14 (= 0xDF8E16 - 2)
        engine_addr = addr - 2 if addr >= 0x08000000 else addr
        asm_A += f"ldr r1, hA_a{i}\n"
        asm_A += f"cmp r0, r1\n"
        asm_A += f"beq match_{i}\n"
    asm_A += "movs r0, #0\nb store_flag\n"
    for i in range(len(dialogs)):
        asm_A += f"match_{i}:\nmovs r0, #{i+1}\nb store_flag\n"
    asm_A += "store_flag:\nldr r1, hA_flag\nstrb r0, [r1]\n"
    asm_A += "mov r0, r7\nstr r0, [r6, #0x3c]\npop {r4, r5, r6}\nbx lr\n.align 2\n"
    for i, (addr, _, _) in enumerate(dialogs):
        engine_addr = addr - 2 if addr >= 0x08000000 else addr
        asm_A += f"hA_a{i}: .word 0x{engine_addr:08X}\n"
    asm_A += "hA_flag: .word 0x0203FFF0\n"
    
    hookA_bytes = bytes(ks.asm(asm_A, addr=HOOK_A)[0])
    HOOK_B = (HOOK_A + len(hookA_bytes) + 3) & ~3  # 4-byte align
    if HOOK_B < 0x08A3CFA0:
        HOOK_B = 0x08A3CFA0
    
    # Hook B: dispatch based on flag value
    asm_B = """push {r4-r7, lr}
ldr r0, hB_flag
ldrb r0, [r0]
cmp r0, #0
beq hB_skip
"""
    # For each dialog, branch
    for i in range(len(dialogs)):
        asm_B += f"cmp r0, #{i+1}\nbeq render_d{i}\n"
    asm_B += "b hB_skip\n"
    for i in range(len(dialogs)):
        asm_B += f"render_d{i}:\nldr r4, hB_d{i}_g1\nldr r5, hB_d{i}_g2\nb do_render\n"
    asm_B += "do_render:\n"
    
    # Copy tilemaps (shared)
    for n, src_label, dst_label in [
        (18, "hB_r1src", "hB_r1dst"),
        (18, "hB_r2src", "hB_r2dst"),
        (18, "hB_r3src", "hB_r3dst"),
        (18, "hB_r4src", "hB_r4dst"),
    ]:
        asm_B += f"ldr r0, {src_label}\nldr r1, {dst_label}\nmovs r2, #{n}\ncp_{src_label}:\nldrh r3, [r0]\nstrh r3, [r1]\nadds r0, #2\nadds r1, #2\nsubs r2, #1\nbne cp_{src_label}\n"
    
    # Copy line 1 glyphs (src in r4)
    asm_B += "mov r0, r4\nldr r1, hB_g1dst\nldr r2, hB_n_g\ncp_g1:\nldrh r3, [r0]\nstrh r3, [r1]\nadds r0, #2\nadds r1, #2\nsubs r2, #1\nbne cp_g1\n"
    # Copy line 2 glyphs (src in r5)
    asm_B += "mov r0, r5\nldr r1, hB_g2dst\nldr r2, hB_n_g\ncp_g2:\nldrh r3, [r0]\nstrh r3, [r1]\nadds r0, #2\nadds r1, #2\nsubs r2, #1\nbne cp_g2\n"
    
    asm_B += """hB_skip:
pop {r4-r7}
pop {r3}
pop {r4, r5, r6}
pop {r0}
bx r0
.align 2
hB_flag: .word 0x0203FFF0
hB_r1src: .word 0x08A3D200
hB_r1dst: .word 0x0600604E
hB_r2src: .word 0x08A3D240
hB_r2dst: .word 0x0600608E
hB_r3src: .word 0x08A3D280
hB_r3dst: .word 0x060060CE
hB_r4src: .word 0x08A3D2C0
hB_r4dst: .word 0x0600610E
hB_g1dst: .word 0x06002780
hB_g2dst: .word 0x06002000
hB_n_g:   .word 576
"""
    for i in range(len(dialogs)):
        g1_addr = 0x08A3D200 + HEADER_SIZE + i * PER_DIALOG
        g2_addr = g1_addr + 1152
        asm_B += f"hB_d{i}_g1: .word 0x{g1_addr:08X}\nhB_d{i}_g2: .word 0x{g2_addr:08X}\n"
    
    hookB_bytes = bytes(ks.asm(asm_B, addr=HOOK_B)[0])
    
    # Calculate ROM size and check
    total_data = HEADER_SIZE + len(dialogs) * PER_DIALOG
    
    # BL bytecode
    PATCH_INIT = 0x08B129D4
    PATCH_LOOP_EXIT = 0x08B12798
    bl_A = bytes(ks.asm(f"bl 0x{HOOK_A:08X}", addr=PATCH_INIT)[0])
    bl_B = bytes(ks.asm(f"bl 0x{HOOK_B:08X}", addr=PATCH_LOOP_EXIT)[0])
    
    # Write ROM
    rom = bytearray(open(base_rom, "rb").read())
    rom[0xB175AA] = 0x02  # engine patch
    rom[HOOK_A - 0x08000000:HOOK_A - 0x08000000 + len(hookA_bytes)] = hookA_bytes
    rom[HOOK_B - 0x08000000:HOOK_B - 0x08000000 + len(hookB_bytes)] = hookB_bytes
    rom[0xA3D200:0xA3D200 + total_data] = data_buf[:total_data]
    rom[0xB129D4:0xB129D4 + 4] = bl_A
    rom[0xB12798:0xB12798 + 4] = bl_B
    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk
    open(output, "wb").write(rom)
    
    print(f"Built: {output}")
    print(f"  Dialogs: {len(dialogs)}")
    print(f"  Hook A: {len(hookA_bytes)} bytes")
    print(f"  Hook B: {len(hookB_bytes)} bytes")
    print(f"  Data size: {total_data} bytes")
    print(f"  Total code cave usage: ~{len(hookA_bytes) + len(hookB_bytes) + total_data} bytes")

if __name__ == "__main__":
    # 10 dialogs for testing
    dialogs = [
        (0x08DF8E16, "게임보이 워즈에", "어서 와!"),
        (0x08DF8E3E, "처음 뵙겠습니다", ""),
        (0x08DF8E58, "나는 캐서린.", ""),
        (0x08DF8E6E, "레드스타국의 쇼군,", ""),
        (0x08DF8E8D, "캐서린이야.", "잘 부탁해!"),
        (0x08DF8EAE, "너, 이 게임은", "처음이니?"),
        (0x08DF8EDA, "그럼, 간단히", "설명할게."),
        (0x08DF8EFF, "게임보이 워즈에는", "여러 가지"),
        (0x08DF8F26, "「모드」가 있어.", ""),
        (0x08DF8F3F, "게임보이 1대로", "대전을 할 수 있는"),
    ]
    build_rom(
        "output/welcome_korean_v14_tight.gba",
        dialogs,
        "output/multi_dialog_v3.gba"
    )
