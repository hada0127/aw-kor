.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.global editor_source_entry, editor_first_row_entry, predicate, code_end, blob_end
.thumb_func
editor_source_entry:
    push {r1,lr}
    movs r0,r7
    bl predicate
    pop {r1}
    pop {r0}
    mov lr,r0
    beq reject
    ldr r0, source_base
    subs r0,r5,r0
    // The Japanese menu reserves two cells for the icon. The Korean source
    // uses those cells for text; shift all File/Help captions as well as the
    // existing File-submenu and Fill captions into the visible text column.
    // In the two three-glyph labels (File Save, Help), the third native glyph
    // would overwrite the first overlay; draw those two labels in reverse
    // source order, using matching display-glyph table entries.
    cmp r0,#0x10
    beq lookup
    // 0x3c falls through the high-range subtraction and stays unshifted.
    cmp r0,#0x3c
    blo shift
    subs r0,#0x4c
    cmp r0,#4
    bhs lookup
shift:
    adds r6,#4
    cmp r0,#0x0c
    beq extra_shift
    cmp r0,#0x38
    bne lookup
extra_shift:
    adds r6,#4
lookup:
    ldr r0, lookup_target
    bx r0
.thumb_func
editor_first_row_entry:
    // Keep the non-editor path out of the editor pool predicate entirely.
    ldr r0, source_base
    subs r0,r5,r0
    cmp r0,#0x62
    bhs legacy
    ldr r0,[sp,#12]
    push {r1,lr}
    bl predicate
    pop {r1}
    pop {r0}
    mov lr,r0
    beq reject
    ldr r0, cell_base
    subs r0,r6,r0
    // File-submenu cells occupy the lower half of each 0x80-byte row.
    // Normalize the row arithmetic only; r6 remains the physical destination.
    ldr r7, source_base
    subs r7,r5,r7
    cmp r7,#0x28
    bhs row_origin_ready
    subs r0,#0x40
row_origin_ready:
    // Underflow is also >= 5 after unsigned right shift.
    lsrs r7,r0,#7
    cmp r7,#5
    bhs row_fail
    // delta low 7 bits must equal 2*column and column < 8.
    // r4 is the exhausted table pointer and F3068E never reads it again.
    subs r4,r1,#2
    cmp r4,#6
    bhs row_fail
    lsls r0,r0,#25
    lsrs r0,r0,#25
    lsls r4,r1,#1
    cmp r0,r4
    bne row_fail
    // Native compact rendering has already populated the source cell. Clear
    // it and give the destination the same palette 8 attribute as the native
    // Korean caption. Both tilemap lines must be updated before F3068E.
    movs r0,#0x81
    lsls r0,r0,#8
    adds r0,#0x64
    // The information and exit icons occupy the first two cells of rows 2
    // and 4. Native rendering has shifted their caption to column two; do
    // not erase those icon cells while removing stale text on other rows.
    cmp r7,#2
    beq icon_row
    cmp r7,#4
    beq icon_row
    subs r4,r6,#4
    strh r0,[r4]
    adds r4,#0x40
    strh r0,[r4]
icon_row:
    strh r0,[r6]
    movs r4,r6
    adds r4,#0x40
    strh r0,[r4]
    lsls r0,r7,#3
    adds r0,r0,r1
    // F3068E computes 0xD0 + 2*index. Editor glyphs use 0x280..0x2CF,
    // which the record renderer owns only while its own screen is active.
    adds r0,#0xd8
    // r7 is dead table-end scratch here, as in the original row gate.
    ldr r7, lookup_target
    adds r7,#0x54
    bx r7
row_fail:
reject:
    ldr r0, lookup_target
    adds r0,#0xa2
    bx r0
legacy:
    // Thumb-1 B at 08F31E9E: PC 08F31EA2 + 0x11E = 08F31FC0.
    .hword 0xe08f
.thumb_func
predicate:
    // r0=P; r5=S; r1-r7/LR/high/SP preserved, r0=boolean.
    push {r1,r2}
    movs r2,r0
    ldr r1, pool_base
    subs r0,r0,r1
    lsrs r1,r0,#8
    cmp r1,#0x0f
    bhs no
align_loop:
    subs r0,#0x60
    bhs align_loop
    adds r0,#0x60
    bne no
    ldr r0,[r2]
    cmp r0,#0
    bne no
    ldr r0,[r2,#0x28]
    ldr r1, cell_base
    subs r1,#0xc6
    cmp r0,r1
    bne no
    ldr r1, source_base
    subs r0,r5,r1
    cmp r0,#0x62
    bhs no
    adds r1,r5,#2
    ldr r0,[r2,#0x20]
    cmp r0,r1
    bne no
    movs r0,#1
    b pred_return
no:
    movs r0,#0
pred_return:
    pop {r1,r2}
    bx lr
code_end:
.balign 4
source_base: .word 0x08d8244c
pool_base: .word 0x03000e00
cell_base: .word 0x02012e0a
// The native record-map tail already owns this exact literal at F31FB8.
// Reuse it to keep the editor gate inside its 236-byte allocation.
.equ lookup_target, editor_source_entry + 0x1b8
blob_end:
