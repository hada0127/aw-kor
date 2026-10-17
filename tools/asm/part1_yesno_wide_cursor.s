.syntax unified
.thumb
.global part1_yesno_wide_cursor
part1_yesno_wide_cursor:
    push {lr}
    ldr r0, [sp, #4]     @ restore current object; overlay owns row readiness
    .hword 0x0000, 0x0000 @ builder patches BL to 0x08F10024
    pop {pc}
    .align 2
