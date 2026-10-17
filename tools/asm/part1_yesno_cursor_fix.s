.syntax unified
.thumb
.global part1_yesno_cursor_fix
part1_yesno_cursor_fix:
    @ Called only after the overlay's row-ready check and wide row writes.
    @ Native 0x08B18CC0 has already cleared both slots in [host+0x18]
    @ and chosen x7/x11 using [host+0x1E]. Copy both cursor halves.
    ldr r0, [sp]        @ overlay's saved host pointer
    ldr r0, [r0, #0x18] @ native shadow row
    ldr r1, =0x060060CE @ visible x7 top
    ldrh r2, [r0]
    strh r2, [r1]
    ldrh r2, [r0, #8]
    strh r2, [r1, #8]
    adds r0, #0x40
    adds r1, #0x40
    ldrh r2, [r0]
    strh r2, [r1]
    ldrh r2, [r0, #8]
    strh r2, [r1, #8]
    pop {r0-r7,pc}      @ restore original overlay registers
    .align 2
