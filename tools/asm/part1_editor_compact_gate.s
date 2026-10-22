.syntax unified
.cpu arm7tdmi
.thumb
.align 2
// Called only from the rejected exits of the existing compact map gates.
// The D824 editor caption sources share state 03000F80 with a hidden map
// buffer, so accepting that state alone would overwrite map glyph tiles.
editor_state_gate:
    ldr r0, editor_state
    cmp r7, r0
    bne state_reject
    ldr r0, editor_start
    cmp r5, r0
    blo state_reject
    ldr r0, editor_end
    cmp r5, r0
    bhs state_reject
    ldr r0, source_start
    ldr r3, state_resume
    bx r3
state_reject:
    ldr r0, native_return
    bx r0
    .align 2
editor_state: .word 0x03000F80
editor_start: .word 0x08D8244C
editor_end: .word 0x08D824AE
source_start: .word 0x08B81CA0
state_resume: .word 0x08F3061D
native_return: .word 0x08F306DD

.org 0x60
editor_source_gate:
    ldr r0, editor_start2
    cmp r5, r0
    blo source_reject
    ldr r0, editor_end2
    cmp r5, r0
    bhs source_reject
    // File submenu and Fill command icons occupy their first caption cells.
    // Shift only those Korean display glyphs two cells to the right.
    ldr r0, file_menu_end
    cmp r5, r0
    blo shift_caption
    ldr r0, fill_start
    cmp r5, r0
    blo source_ready
    ldr r0, fill_end
    cmp r5, r0
    bhs source_ready
shift_caption:
    adds r6, #4
source_ready:
    ldr r0, table_lookup
    bx r0
source_reject:
    ldr r0, native_return2
    bx r0
    .align 2
editor_start2: .word 0x08D8244C
editor_end2: .word 0x08D824AE
file_menu_end: .word 0x08D82474
fill_start: .word 0x08D82498
fill_end: .word 0x08D8249C
table_lookup: .word 0x08F3063B
native_return2: .word 0x08F306DD

.org 0xB0
editor_row_gate:
    ldr r7, [sp, #12]
    ldr r0, editor_state3
    cmp r7, r0
    bne old_row
    cmp r1, #8
    bhs row_reject
    ldr r0, editor_base_cell
    subs r0, r6, r0
    lsrs r0, r0, #7
    cmp r0, #5
    bhs row_reject
    // The shared continuation treats this EWRAM page as a category title
    // (one row only). Use five editor rows in the same private 112-tile pool.
    lsls r0, r0, #3
    adds r0, r0, r1
    ldr r7, editor_cell_resume
    bx r7
old_row:
    ldr r0, old_row_gate
    bx r0
row_reject:
    ldr r0, native_return3
    bx r0
    .align 2
editor_state3: .word 0x03000F80
editor_base_cell: .word 0x02012E0A
editor_cell_resume: .word 0x08F3068F
old_row_gate: .word 0x08F307A9
native_return3: .word 0x08F306DD
