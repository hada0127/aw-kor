#!/usr/bin/env python3
"""Build ROM with N dialogs - DYNAMIC layout for scaling."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from keystone import Ks, KS_ARCH_ARM, KS_MODE_THUMB
from bdf import load_bdf, glyph_grid

ks = Ks(KS_ARCH_ARM, KS_MODE_THUMB)
gl, _ = load_bdf('reference/fonts/Galmuri11.bdf')

N_CELLS = 18
LEAD = 6
LINE1_BASE = 316
LINE2_BASE = 256

def render_msg_padded(msg, lead_cells, total_cells):
    width = total_cells * 8
    bm = [[0]*width for _ in range(11)]
    x_off = lead_cells * 8
    for k, ch in enumerate(msg):
        if ch == ' ': continue
        g = gl.get(ord(ch))
        if not g: continue
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
        if y >= len(bm): break
        for dx, ch in enumerate(row):
            x = x_start + dx
            if x < len(bm[0]) and ch == 'X': bm[y][x] = 1
    return bm

def make_tiles(bm, n_cells):
    glyph_top = bytearray(); glyph_bot = bytearray()
    def sp(t, r, c, v):
        bi = r*4 + c//2
        if c%2 == 0: t[bi] = (t[bi]&0xF0) | (v&0xF)
        else: t[bi] = (t[bi]&0x0F) | ((v&0xF)<<4)
    for cell in range(n_cells):
        top = bytearray(32)
        for tr in range(8):
            for tc in range(8):
                gc = cell*8 + tc
                if tr<11 and gc<len(bm[0]) and bm[tr][gc]: sp(top, tr, tc, 10)
        glyph_top.extend(top)
        bot = bytearray(32)
        for tr in range(3):
            gr = 8+tr
            for tc in range(8):
                gc = cell*8 + tc
                if gr<11 and gc<len(bm[0]) and bm[gr][gc]: sp(bot, tr, tc, 10)
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
    # Plan memory:
    HOOK_A_ADDR = 0x08A3CF14
    # Hook A size: ~5 instructions per dialog (cmp, beq, b) + literals (4 bytes each)
    # Estimate: 5*4 + 4 = 24 bytes per dialog + 40 base = ~28 base + 28 per dialog
    # For safety, use:
    HOOK_A_EST = 50 + 30 * len(dialogs)
    HOOK_B_ADDR = (HOOK_A_ADDR + HOOK_A_EST + 0xFF) & ~0xFF  # 256-byte align
    # Hook B size: ~30 base + 20 per dialog (just literal addresses)
    HOOK_B_EST = 200 + 24 * len(dialogs)
    DATA_ADDR = (HOOK_B_ADDR + HOOK_B_EST + 0xFF) & ~0xFF

    print(f"Layout plan:")
    print(f"  HOOK_A: 0x{HOOK_A_ADDR:08X} (est {HOOK_A_EST} bytes)")
    print(f"  HOOK_B: 0x{HOOK_B_ADDR:08X} (est {HOOK_B_EST} bytes)")
    print(f"  DATA:   0x{DATA_ADDR:08X}")

    # Build shared tilemap data
    shared_row1 = bytearray(); shared_row2 = bytearray()
    shared_row3 = bytearray(); shared_row4 = bytearray()
    for i in range(N_CELLS):
        e1_top = (LINE1_BASE + i) | 0x8000
        e1_bot = (LINE1_BASE + N_CELLS + i) | 0x8000
        e2_top = (LINE2_BASE + i) | 0x8000
        e2_bot = (LINE2_BASE + N_CELLS + i) | 0x8000
        shared_row1 += bytes([e1_top & 0xFF, e1_top >> 8])
        shared_row2 += bytes([e1_bot & 0xFF, e1_bot >> 8])
        shared_row3 += bytes([e2_top & 0xFF, e2_top >> 8])
        shared_row4 += bytes([e2_bot & 0xFF, e2_bot >> 8])

    HEADER_SIZE = 0x100
    PER_DIALOG = 2304
    total_data = HEADER_SIZE + len(dialogs) * PER_DIALOG

    data_buf = bytearray(total_data)
    data_buf[0x000:0x040] = shared_row1
    data_buf[0x040:0x080] = shared_row2
    data_buf[0x080:0x0C0] = shared_row3
    data_buf[0x0C0:0x100] = shared_row4

    for i, (addr, l1, l2) in enumerate(dialogs):
        g1, g2 = gen_glyph_data(l1, l2)
        off = HEADER_SIZE + i * PER_DIALOG
        data_buf[off:off+1152] = g1
        data_buf[off+1152:off+2304] = g2

    # Build Hook A asm
    asm_A = "mov r7, r0\nldr r0, [r6, #0x20]\n"
    for i, (addr, _, _) in enumerate(dialogs):
        engine_addr = addr - 2 if addr >= 0x08000000 else addr
        asm_A += f"ldr r1, hA_a{i}\ncmp r0, r1\nbeq match_{i}\n"
    asm_A += "movs r0, #0\nb store_flag\n"
    for i in range(len(dialogs)):
        asm_A += f"match_{i}:\nmovs r0, #{i+1}\nb store_flag\n"
    asm_A += "store_flag:\nldr r1, hA_flag\nstrb r0, [r1]\n"
    asm_A += "mov r0, r7\nstr r0, [r6, #0x3c]\npop {r4, r5, r6}\nbx lr\n.align 2\n"
    for i, (addr, _, _) in enumerate(dialogs):
        engine_addr = addr - 2 if addr >= 0x08000000 else addr
        asm_A += f"hA_a{i}: .word 0x{engine_addr:08X}\n"
    asm_A += "hA_flag: .word 0x0203FFF0\n"

    hookA_bytes = bytes(ks.asm(asm_A, addr=HOOK_A_ADDR)[0])
    if HOOK_A_ADDR + len(hookA_bytes) > HOOK_B_ADDR:
        print(f"ERROR: Hook A overflowed (actual {len(hookA_bytes)}, est {HOOK_A_EST})")
        return False

    # Build Hook B asm with computed DATA addresses
    g1dst = 0x06002780  # VRAM tile 316
    g2dst = 0x06002000  # VRAM tile 256

    asm_B = """push {r4-r7, lr}
ldr r0, hB_flag
ldrb r0, [r0]
cmp r0, #0
beq hB_skip
"""
    for i in range(len(dialogs)):
        asm_B += f"cmp r0, #{i+1}\nbeq render_d{i}\n"
    asm_B += "b hB_skip\n"
    for i in range(len(dialogs)):
        asm_B += f"render_d{i}:\nldr r4, hB_d{i}_g1\nldr r5, hB_d{i}_g2\nb do_render\n"
    asm_B += "do_render:\n"

    for src_label, dst_label in [
        ("hB_r1src", "hB_r1dst"),
        ("hB_r2src", "hB_r2dst"),
        ("hB_r3src", "hB_r3dst"),
        ("hB_r4src", "hB_r4dst"),
    ]:
        asm_B += f"ldr r0, {src_label}\nldr r1, {dst_label}\nmovs r2, #18\ncp_{src_label}:\nldrh r3, [r0]\nstrh r3, [r1]\nadds r0, #2\nadds r1, #2\nsubs r2, #1\nbne cp_{src_label}\n"

    asm_B += "mov r0, r4\nldr r1, hB_g1dst\nldr r2, hB_n_g\ncp_g1:\nldrh r3, [r0]\nstrh r3, [r1]\nadds r0, #2\nadds r1, #2\nsubs r2, #1\nbne cp_g1\n"
    asm_B += "mov r0, r5\nldr r1, hB_g2dst\nldr r2, hB_n_g\ncp_g2:\nldrh r3, [r0]\nstrh r3, [r1]\nadds r0, #2\nadds r1, #2\nsubs r2, #1\nbne cp_g2\n"

    asm_B += """hB_skip:
pop {r4-r7}
pop {r3}
pop {r4, r5, r6}
pop {r0}
bx r0
.align 2
"""
    asm_B += f"hB_flag:  .word 0x0203FFF0\n"
    asm_B += f"hB_r1src: .word 0x{DATA_ADDR + 0x000:08X}\n"
    asm_B += f"hB_r1dst: .word 0x0600604E\n"
    asm_B += f"hB_r2src: .word 0x{DATA_ADDR + 0x040:08X}\n"
    asm_B += f"hB_r2dst: .word 0x0600608E\n"
    asm_B += f"hB_r3src: .word 0x{DATA_ADDR + 0x080:08X}\n"
    asm_B += f"hB_r3dst: .word 0x060060CE\n"
    asm_B += f"hB_r4src: .word 0x{DATA_ADDR + 0x0C0:08X}\n"
    asm_B += f"hB_r4dst: .word 0x0600610E\n"
    asm_B += f"hB_g1dst: .word 0x{g1dst:08X}\n"
    asm_B += f"hB_g2dst: .word 0x{g2dst:08X}\n"
    asm_B += f"hB_n_g:   .word 576\n"
    for i in range(len(dialogs)):
        g1_addr = DATA_ADDR + HEADER_SIZE + i * PER_DIALOG
        g2_addr = g1_addr + 1152
        asm_B += f"hB_d{i}_g1: .word 0x{g1_addr:08X}\n"
        asm_B += f"hB_d{i}_g2: .word 0x{g2_addr:08X}\n"

    hookB_bytes = bytes(ks.asm(asm_B, addr=HOOK_B_ADDR)[0])
    if HOOK_B_ADDR + len(hookB_bytes) > DATA_ADDR:
        print(f"ERROR: Hook B overflowed (actual {len(hookB_bytes)}, est {HOOK_B_EST})")
        return False

    # BL bytecode
    PATCH_INIT = 0x08B129D4
    PATCH_LOOP_EXIT = 0x08B12798
    bl_A = bytes(ks.asm(f"bl 0x{HOOK_A_ADDR:08X}", addr=PATCH_INIT)[0])
    bl_B = bytes(ks.asm(f"bl 0x{HOOK_B_ADDR:08X}", addr=PATCH_LOOP_EXIT)[0])

    # Write ROM
    rom = bytearray(open(base_rom, "rb").read())
    rom[0xB175AA] = 0x02
    rom[HOOK_A_ADDR - 0x08000000:HOOK_A_ADDR - 0x08000000 + len(hookA_bytes)] = hookA_bytes
    rom[HOOK_B_ADDR - 0x08000000:HOOK_B_ADDR - 0x08000000 + len(hookB_bytes)] = hookB_bytes
    rom[DATA_ADDR - 0x08000000:DATA_ADDR - 0x08000000 + total_data] = data_buf
    rom[0xB129D4:0xB129D4 + 4] = bl_A
    rom[0xB12798:0xB12798 + 4] = bl_B
    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk
    open(output, "wb").write(rom)

    print(f"\n✓ Built: {output}")
    print(f"  Dialogs: {len(dialogs)}")
    print(f"  Hook A: {len(hookA_bytes)} bytes at 0x{HOOK_A_ADDR:08X}")
    print(f"  Hook B: {len(hookB_bytes)} bytes at 0x{HOOK_B_ADDR:08X}")
    print(f"  Data:   {total_data} bytes at 0x{DATA_ADDR:08X}")
    print(f"  Total code cave: ~{len(hookA_bytes) + len(hookB_bytes) + total_data} bytes")
    return True

if __name__ == "__main__":
    import csv

    # Load Korean translations from CSV
    dialogs = []
    with open('data/translation_for_import.csv', 'r') as f:
        r = csv.DictReader(f)
        for row in r:
            addr = row.get('address', '').strip()
            if not addr.startswith('0x00DF'): continue
            try:
                addr_int = int(addr, 16)
            except: continue
            if not (0xDF8E16 <= addr_int <= 0xDF9200): continue
            k = row.get('korean', '').strip()
            if not k: continue
            if len(k) <= 8:
                line1, line2 = k, ''
            else:
                half = len(k) // 2
                best = 0
                for i, c in enumerate(k):
                    if c == ' ' and abs(i - half) < abs(best - half) and i <= 9:
                        best = i
                if best > 0:
                    line1 = k[:best].strip()
                    line2 = k[best:].strip()
                else:
                    line1 = k[:8]
                    line2 = k[8:]
            dialogs.append((addr_int + 0x08000000, line1, line2))

    print(f"Found {len(dialogs)} dialogs in welcome scene")

    build_rom(
        "output/welcome_korean_v14_tight.gba",
        dialogs,
        "output/multi_dialog_v5_dynamic.gba"
    )
