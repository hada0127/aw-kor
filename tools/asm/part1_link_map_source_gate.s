.syntax unified
.cpu arm7tdmi
.thumb
.align 2
// Installed at 08F31F80; reached from the compact hook for source pointers
// below the B8 table. The unlocked link list also reads translated A5 labels.
source_gate:
    ldr r0, a5_start
    cmp r5, r0
    blo placeholder
    ldr r0, a5_end
    cmp r5, r0
    blo accepted
placeholder:
    ldr r0, placeholder_start
    cmp r5, r0
    beq accepted
    adds r0, #2
    cmp r5, r0
    beq accepted
    adds r0, #2
    cmp r5, r0
    beq accepted
    ldr r0, rejected
    bx r0
accepted:
    ldr r0, table_lookup
    bx r0
.align 2
a5_start: .word 0x08A5D0B4
a5_end: .word 0x08A5D0EC
placeholder_start: .word 0x08DF8C2A
rejected: .word 0x08F306DD
table_lookup: .word 0x08F3063B

.org 0x40
// The scrolled link state uses the same six-row/page allocation as 0F20.
// Other states continue through the record-map row gate unchanged.
link_row_state_gate:
    ldr r7, [sp, #12]
    ldr r0, scroll_live
    cmp r7, r0
    beq single_rows
    ldr r0, old_row_gate
    bx r0
single_rows:
    ldr r0, single_row_resume
    bx r0
.align 2
scroll_live: .word 0x030010A0
old_row_gate: .word 0x08F307A9
single_row_resume: .word 0x08F307D5
