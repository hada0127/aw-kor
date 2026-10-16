.syntax unified
.thumb
.global part1_yesno_wide_cursor
part1_yesno_wide_cursor:
    push {lr}
    ldr r0, [sp, #4]     @ wrapper's saved current object
    ldr r1, [r0, #0x3c]
    ldr r2, =0x08EC2808
    cmp r1, r2
    bne call_overlay
    ldr r0, =0x060060CE   @ name-confirm x7 top
    ldr r1, =0x0000A1BA
    strh r1, [r0]
    ldr r0, =0x0600610E   @ name-confirm x7 bottom
    ldr r1, =0x0000A1BB
    strh r1, [r0]
call_overlay:
    ldr r0, [sp, #4]     @ restore current object after writing VRAM cursors
    .hword 0x0000, 0x0000 @ builder patches BL to 0x08F10024
    pop {pc}
    .align 2
