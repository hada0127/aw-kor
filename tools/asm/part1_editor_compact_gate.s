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
    cmp r0,#0
    pop {r1}
    pop {r0}
    mov lr,r0
    beq reject
    ldr r0, source_base
    subs r0,r5,r0
    cmp r0,#0x28
    blo shift
    subs r0,#0x4c
    cmp r0,#4
    bhs lookup
shift:
    adds r6,#4
lookup:
    ldr r0, lookup_target
    bx r0
reject:
    ldr r0, native_target
    bx r0
.thumb_func
editor_first_row_entry:
    ldr r0, source_base
    subs r0,r5,r0
    cmp r0,#0x62
    bhs legacy
    ldr r0,[sp,#12]
    push {r1,lr}
    bl predicate
    cmp r0,#0
    pop {r1}
    pop {r0}
    mov lr,r0
    beq reject
    push {r7}
    ldr r0, cell_base
    subs r0,r6,r0
    // Underflow is also >= 5 after unsigned right shift.
    lsrs r7,r0,#7
    cmp r7,#5
    bhs row_fail
    // delta low 7 bits must equal 2*column and column < 8.
    cmp r1,#8
    bhs row_fail
    lsls r0,r0,#25
    lsrs r0,r0,#25
    lsls r7,r1,#1
    cmp r0,r7
    bne row_fail
    ldr r0, cell_base
    subs r0,r6,r0
    lsrs r0,r0,#7
    lsls r0,r0,#3
    adds r0,r0,r1
    pop {r7}
    // r7 is dead table-end scratch here, as in the original row gate.
    ldr r7, cell_target
    bx r7
row_fail:
    pop {r7}
    b reject
legacy:
    ldr r0, legacy_target
    bx r0
.thumb_func
predicate:
    // r0=P; r5=S; r1-r7/LR/high/SP preserved, r0=boolean.
    push {r1,r2}
    movs r2,r0
    ldr r1, pool_base
    subs r0,r0,r1
    movs r1,#0xf0
    lsls r1,r1,#4
    cmp r0,r1
    bhs no
align_loop:
    cmp r0,#0x60
    blo align_end
    subs r0,#0x60
    b align_loop
align_end:
    cmp r0,#0
    bne no
    ldr r0,[r2]
    cmp r0,#0
    bne no
    ldr r0,[r2,#0x28]
    ldr r1, buffer_base
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
buffer_base: .word 0x02012d44
cell_base: .word 0x02012e0a
lookup_target: .word 0x08f3063b
native_target: .word 0x08f306dd
legacy_target: .word 0x08f31fc1
cell_target: .word 0x08f3068f
blob_end:
