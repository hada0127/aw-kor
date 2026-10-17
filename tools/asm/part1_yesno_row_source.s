.syntax unified
.thumb
.global part1_yesno_row_source
part1_yesno_row_source:
    push {r4,lr}
    sub sp, #8
    ldr r3, =0x08F10380  @ native wide row for every Part 1 choice
    ldr r4, [sp, #16]     @ original fifth argument
    str r4, [sp]
    ldr r4, [sp, #20]     @ original sixth argument
    str r4, [sp, #4]
    movs r1, #0          @ original call's second argument
    .hword 0x0000,0x0000 @ builder patches BL 0x08B1311C
    add sp, #8
    pop {r4,pc}
    .align 2
