.equ SOURCE_PTR, 0x0201DB40
.equ ATLAS, 0x08FFC800
.equ INPUT_PTR, 0x0848727C
.equ CLEANUP_SCRIPT, 0x0883E0E8
.syntax unified
.cpu arm7tdmi
.thumb
.section .text
.balign 4
.global _start
_start:
init_bridge:
 push {r4-r7,lr}
 ldr r3, =0x0831F709
 bl call_r3
 ldr r4, =ATLAS
 adr r5, obj_destinations
 movs r6, #7
1:
 movs r0, r4
 ldr r1, [r5]
 movs r2, #64
 ldr r3, =0x0838B435
 bl call_r3
 movs r0, #128
 lsls r0, r0, #1
 adds r4, r4, r0
 adds r5, #4
 subs r6, #1
 bne 1b
 movs r0, r4
 ldr r1, =0x06006800
 movs r2, #112
 ldr r3, =0x0838B435
 bl call_r3
 pop {r4-r7}
 pop {r3}
 mov lr, r3
 ldr r1, =INPUT_PTR
 ldr r0, [r1]
 ldrb r2, [r0]
 ldr r3, =0x08347501
 bx r3
 .ltorg
.balign 4
obj_destinations:
 .word 0x6013ee0,0x6013fe0,0x60140e0,0x60141e0,0x60143e0,0x60142e0,0x60144e0

.balign 4
draw_bridge:
 push {r4-r7,lr}
 sub sp, #4
 movs r4, r0
 movs r5, r1
 movs r6, r2
 ldr r7, [sp,#24]
 str r7, [sp]
 movs r3, #0
 ldr r7, =0x0831F821
 mov ip, r7
 bl call_ip
 subs r4, #28
 cmp r4, #6
 bhi 2f
 movs r0, #7
 movs r1, r5
 orrs r1, r6
 tst r1, r0
 bne 2f
 adds r5, #32
 lsrs r5, r5, #3
 lsls r5, r5, #1
 lsrs r6, r6, #3
 lsls r6, r6, #6
 adds r5, r5, r6
 @ Permit only top cells from the same interleaved top/bottom clear table.
 adr r0, cell_offsets
 movs r1, #14
5:
 ldrh r2, [r0]
 cmp r5, r2
 beq 6f
 adds r0, #4
 subs r1, #1
 bne 5b
 b 2f
6:
 ldr r0, =0x0201BB40
 adds r5, r5, r0
 @ Never destroy an existing native fill/text cell; prior own tails were cleared.
 ldrh r0, [r5]
 movs r1, r5
 adds r1, #64
 ldrh r1, [r1]
 orrs r0, r1
 bne 2f
 lsls r4, r4, #1
 ldr r0, =0xA340
 adds r4, r4, r0
 strh r4, [r5]
 adds r4, #1
 adds r5, #64
 strh r4, [r5]
 ldr r3, =0x08313B01
 bl call_r3
2:
 add sp, #4
 pop {r4-r7}
 pop {r3}
 mov lr, r3
 ldr r0, [sp,#12]
 adds r0, #1
 ldr r3, =0x083472C1
 bx r3
 .ltorg

.balign 4
frame_bridge:
 push {r4-r7,lr}
 movs r4, r0
 movs r5, r1
 bl clear_cells
 movs r0, r4
 movs r1, r5
 ldr r3, =0x083470C1
 bl call_r3
 pop {r4-r7}
 pop {r3}
 mov lr, r3
 pop {r0}
 bx r0
 .ltorg

.balign 4
late_exit_bridge:
 @ This is the existing parent's one-shot callback after its native wait1.
 push {r4-r7,lr}
 @ Native destructor already cleared BG0 shadow; preserve its hardware upload timing.
 @ Synchronous 512B copy, identical to native initialization3196D2..DE.
 ldr r0, =SOURCE_PTR
 ldr r1, =0x06006800
 movs r2, #128
 lsls r2, r2, #2
 ldr r3, =0x08311C7D
 bl call_r3
 @ Preserve the original callback, followed by the untouched33549C/END script.
 ldr r3, =0x083476F5
 bl call_r3
 pop {r4-r7}
 pop {r3}
 bx r3
 .ltorg

.balign 4
clear_cells:
 push {r4-r7,lr}
 adr r4, cell_offsets
 movs r5, #28
 ldr r6, =0x0201BB40
 ldr r7, =0xA340
3:
 ldrh r0, [r4]
 adds r0, r0, r6
 ldrh r1, [r0]
 subs r1, r1, r7
 cmp r1, #13
 bhi 4f
 movs r1, #0
 strh r1, [r0]
4:
 adds r4, #2
 subs r5, #1
 bne 3b
 ldr r3, =0x08313B01
 bl call_r3
 pop {r4-r7}
 pop {r3}
 bx r3
 .ltorg
.balign 4
cell_offsets:
 .hword 714,778,726,790,842,906,854,918,970,1034,982,1046,1098,1162,746,810,758,822,874,938,886,950,1002,1066,1014,1078,1130,1194

call_r3:
 bx r3
call_ip:
 bx ip
