.syntax unified
.thumb
.global part1_yesno_top_row
.global part1_yesno_bottom_row
part1_yesno_top_row:
    push {r0,r2,r3,lr}
    bl part1_yesno_prompt_id
    cmp r1, #0
    bne 1f
    adr r1, top_legacy
    b 2f
1:  adr r1, top_wide
2:  movs r3, #6
3:  ldrh r2, [r1]
    strh r2, [r0]
    adds r0, #2
    adds r1, #2
    subs r3, #1
    bne 3b
    pop {r0,r2,r3,pc}
    .align 2
top_legacy:
    .hword 0x80E2,0x0164,0x80E4,0x80E6,0x80E8,0x0164
top_wide:
    .hword 0x80E2,0x0164,0x0164,0x0164,0x80E4,0x80E6
    .org 0x40
part1_yesno_bottom_row:
    push {r0,r2,r3,lr}
    bl part1_yesno_prompt_id
    cmp r1, #0
    bne 4f
    adr r1, bottom_legacy
    b 5f
4:  adr r1, bottom_wide
5:  movs r3, #6
6:  ldrh r2, [r1]
    strh r2, [r0]
    adds r0, #2
    adds r1, #2
    subs r3, #1
    bne 6b
    pop {r0,r2,r3,pc}
    .align 2
bottom_legacy:
    .hword 0x80E3,0x0164,0x80E5,0x80E7,0x80E9,0x0164
bottom_wide:
    .hword 0x80E3,0x0164,0x0164,0x0164,0x80E5,0x80E7
