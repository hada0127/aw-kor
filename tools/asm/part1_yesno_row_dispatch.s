.syntax unified
.thumb
.global part1_yesno_top_row
.global part1_yesno_bottom_row
part1_yesno_top_row:
    push {r0,r2,r3,lr}
    adr r1, top_wide
    movs r3, #6
1:  ldrh r2, [r1]
    strh r2, [r0]
    adds r0, #2
    adds r1, #2
    subs r3, #1
    bne 1b
    pop {r0,r2,r3,pc}
    .align 2
top_wide:
    .hword 0x80E2,0x0164,0x0164,0x0164,0x80E4,0x80E6
    .org 0x40
part1_yesno_bottom_row:
    push {r0,r2,r3,lr}
    adr r1, bottom_wide
    movs r3, #6
1:  ldrh r2, [r1]
    strh r2, [r0]
    adds r0, #2
    adds r1, #2
    subs r3, #1
    bne 1b
    pop {r0,r2,r3,pc}
    .align 2
bottom_wide:
    .hword 0x80E3,0x0164,0x0164,0x0164,0x80E5,0x80E7
