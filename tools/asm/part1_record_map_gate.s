.syntax unified
.cpu arm7tdmi
.thumb
.align 2
// Lives at 08F30720. The existing hook has already called the native renderer
// and saved r4-r7. r5=source, r6=cell. r3 is scratch until the glyph lookup.
record_map_gate:
    ldr r0, single_live
    cmp r7, r0
    beq accepted
    ldr r0, record_live
    cmp r7, r0
    beq accepted
    adds r0, #0x60
    cmp r7, r0
    beq accepted
    ldr r0, rejected
    bx r0
accepted:
    // The eight-byte entry trampoline also replaced this source-bound load.
    ldr r0, source_start
    ldr r3, resumed
    bx r3
    .align 2
single_live: .word 0x03000F20
record_live: .word 0x03001220
rejected: .word 0x08F306DD
source_start: .word 0x08B81CA0
resumed: .word 0x08F3061D

// Fits the unused gap after the inactive B84 hook and before the source table.
.org 0x88
.set hook_exit, record_map_gate - 0x44
record_row_gate:
    ldr r7, [sp, #12]  // Original state saved by the existing push {r4-r7}.
    ldr r0, original_single
    cmp r7, r0
    beq single_rows
    // Observed record ring is exactly EWRAM 02000000..020003FF.
    lsrs r0, r6, #10
    ldr r5, record_ring_base
    cmp r0, r5
    bne hook_exit
    // Record names include seven-cell labels (e.g. 고양이의 낙원).
    cmp r1, #7
    bhs hook_exit
    // Record view scrolls through an eight-row ring, seven cells per row.
    adds r0, r6, #0
    lsrs r0, r0, #7
    movs r5, #7
    ands r0, r5
    lsls r5, r0, #3
    subs r5, r5, r0
    adds r0, r5, r1
    lsls r0, r0, #1
    ldr r1, record_tile_base
    adds r1, r1, r0
    ldr r0, record_cell_resume
    bx r0
single_rows:
    cmp r1, #6
    bhs hook_exit
    // Restore the overwritten row calculation, including the CMP flags.
    adds r0, r6, #0
    lsrs r0, r0, #7
    movs r5, #7
    ands r0, r5
    cmp r0, #6
    ldr r7, original_single_resume
    bx r7
    .align 2
original_single: .word 0x03000F20
record_tile_base: .word 0x00000280
record_cell_resume: .word 0x08F30695
original_single_resume: .word 0x08F3066D
record_ring_base: .word 0x00008000
