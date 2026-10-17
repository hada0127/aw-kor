.syntax unified
.thumb
.global part1_yesno_prompt_id
@ Return r1=1 for the name-confirm/first-time choices and the b38-wide
@ campaign 80c choice. Preserve every other register used by the four callers.
.thumb_func
part1_yesno_prompt_id:
    push {r0,r2-r4,lr}
    ldr r3, =0x08D826FC   @ dialogue VM class
    @ These live slots occur on the measured 80c and name/tutorial routes.
    @ Check their liveness and class; fall back to the complete pool scan.
    ldr r0, =0x030010A0
    bl 6f
    cmp r1, #0
    bne 2f
    ldr r0, =0x03000FE0
    bl 6f
    cmp r1, #0
    bne 2f
    ldr r0, =0x03000E00   @ first object
    ldr r2, =0x03001D00   @ 40 objects, exclusive end
1:  ldr r4, [r0]         @ +0 is cleared when a pool slot is freed
    cmp r4, #0
    beq 5f
    ldr r4, [r0, #4]
    cmp r4, r3
    beq 2f
5:  adds r0, #0x60
    cmp r0, r2
    blo 1b
    b 4f
2:  ldr r4, [r0, #0x20] @ VM +0x20 script cursor
    ldr r3, =0x08DF8E11   @ name-confirm, observed +0/+1
    subs r3, r4, r3
    cmp r3, #1
    bls 3f
    ldr r3, =0x08DF8ED3   @ first-time, observed +0
    subs r3, r4, r3
    cmp r3, #1
    bls 3f
    ldr r3, =0x08E104C6   @ campaign 80c: preserve b38's wide row
    subs r3, r4, r3
    cmp r3, #1
    bhi 4f
3:  movs r1, #1
    pop {r0,r2-r4,pc}
4:  movs r1, #0
    pop {r0,r2-r4,pc}
6:  ldr r4, [r0]
    cmp r4, #0
    beq 7f
    ldr r4, [r0, #4]
    cmp r4, r3
    beq 8f
7:  movs r1, #0
    bx lr
8:  movs r1, #1
    bx lr
    .align 2
