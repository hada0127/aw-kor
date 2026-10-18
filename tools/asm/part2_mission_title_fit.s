.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.global title_load, title_settle, title_static

// Far-jump entry replacing 0x0837C7E4..0x0837C7F3.
// Only the title caller is redirected; map-list glyph loading stays native.
.thumb_func
title_load:
    mov r1, r9
    str r1, [sp]
    push {r4-r7, lr}
    movs r4, r0
    movs r5, #0
1:
    ldrb r1, [r0]
    cmp r1, #0
    beq 2f
    adds r5, #1
    adds r0, #2
    b 1b
2:
    movs r0, r4
    cmp r5, #9
    bhi 3f
    movs r1, #0
    movs r2, #0
    movs r3, #128
    ldr r7, =0x0837C4E5
    bl call_r7
    b 7f
3:
    movs r6, #0
4:
    ldrb r0, [r4]
    cmp r0, #0
    beq 6f
    ldrb r1, [r4, #1]
    lsls r0, r0, #8
    orrs r0, r1
    adds r4, #2
    ldr r5, =0x08F66800
5:
    ldrh r1, [r5]
    cmp r0, r1
    beq 8f
    adds r5, #12
    b 5b
8:
    ldr r0, [r5, #4]
    lsls r1, r6, #9
    ldr r2, =0x06011000
    adds r1, r1, r2
    ldr r7, =0x08311CC1
    bl call_r7
    adds r6, #1
    b 4b
6:
    movs r0, r6
7:
    pop {r4-r7}
    pop {r1}
    mov lr, r1
    lsls r0, r0, #16
    ldr r1, =0x0837C7F5
    bx r1
.thumb_func
call_r7:
    bx r7
.balign 4
.ltorg

// Both phases retain native 24px placement for titles of nine codes or less.
// Build validation bounds every active title to eleven codes: 11*20 <= 224.
.thumb_func
title_settle:
    mov r1, r10
    ldrh r1, [r1]
    cmp r1, #9
    bhi 1f
    lsls r2, r0, #1
    adds r2, r2, r0
    lsls r2, r2, #3
    b 2f
1:
    lsls r2, r0, #2
    adds r2, r2, r0
    lsls r2, r2, #2
2:
    movs r1, #224
    subs r1, r1, r2
    str r6, [sp]
    ldr r0, =0x0837CEB9
    bx r0
.balign 4
.ltorg

.thumb_func
title_static:
    ldrh r1, [r6]
    cmp r1, #9
    bhi 1f
    lsls r2, r0, #1
    adds r2, r2, r0
    lsls r2, r2, #3
    b 2f
1:
    lsls r2, r0, #2
    adds r2, r2, r0
    lsls r2, r2, #2
2:
    movs r1, #224
    subs r1, r1, r2
    str r7, [sp]
    ldr r0, =0x0837CF19
    bx r0
.balign 4
.ltorg

// Ending-record titles use at most nine native 32x32 OBJ slots per bank.
// The descriptor contains a precomposed raster split into <=9 such slots.
// The remaining titles, including user-map names, retain the native loader.
.global map_title_load
.thumb_func
map_title_load:
    pop {r3}                    // dedicated trampoline preserves live tile base
    push {r4-r7, lr}
    sub sp, #16
    str r0, [sp]
    str r1, [sp, #4]             // native u16 sumWidth output
    str r2, [sp, #8]             // native byte widths; element zero is first x
    str r3, [sp, #12]
    ldr r4, =0x08F66400
1:
    ldr r5, [r4]
    cmp r5, #0
    beq 2f
    cmp r0, r5
    beq 3f
    adds r4, #32
    b 1b
2:
    ldr r7, =0x0837C4E5
    bl call_r7
    b 6f
3:
    ldr r0, [r4, #4]
    ldr r1, [sp, #12]
    lsls r1, r1, #5
    ldr r2, =0x06010000
    adds r1, r1, r2
    ldr r7, =0x08311CC1
    bl call_r7
    ldr r1, [sp, #4]
    ldrh r0, [r4, #8]
    strh r0, [r1]
    ldr r2, [sp, #8]
    adds r2, #1
    ldrb r6, [r4, #10]
    movs r5, #0
    movs r7, r4
    adds r7, #12
4:
    ldrb r0, [r7, r5]
    strb r0, [r2, r5]
    adds r5, #1
    cmp r5, r6
    blo 4b
    movs r0, r6
6:
    add sp, #16
    pop {r4-r7}
    pop {r1}
    mov lr, r1
    lsls r0, r0, #16
    lsrs r0, r0, #16
    str r0, [r4, #0x40]
    ldr r2, =0x088FD6C4
    ldr r1, =0x0836B649
    bx r1
.balign 4
.ltorg
