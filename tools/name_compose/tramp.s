@ 2편 이름 조합 Thumb 트램펄린 (PLAN-v5 §1.5·§1.6, T2). ARMv4T Thumb-1 전용.
@
@ 훅 사이트(빌더가 IMAGE_RT + SYMBOLS[x] | 1 로 리터럴을 쓴다):
@   S1 0x0834B0BC → nc_tramp_press      일반 셀(mode1 사설 셀 조합, mode0 원 append)
@   S2 0x0834B084 → nc_tramp_confirm    START/OK(mode1 미완성 거부)
@   S3 0x0834B20E → nc_tramp_backspace  지우기(진입 시 r2 = obj+0x61 live)
@   D1 0x0834AB3C → nc_tramp_display    constructor 6행 그리기(r3 로 진입)
@   P1 [0x0883FD58] → nc_alloc          할당 콜백(0x80B + tail 초기화)
@ mode = [obj+0x60] (1 = mode1, 그 외 native 경로), obj = [0x03004650].
@ 복귀점의 r0 는 모두 dead 이고 플래그를 읽지 않는다 → ldr r0,=ret|1; bx r0.

	.syntax unified
	.cpu arm7tdmi
	.thumb

	.equ OBJ_PTR,       0x03004650
	.equ OFF_MODE,      0x60
	.equ OFF_X,         0x1E        @ s16 커서 x
	.equ OFF_Y,         0x20        @ s16 커서 y
	.equ OFF_TAIL,      0x70
	.equ GRID_W,        15
	.equ GRID_H,        6
	.equ SND_ACCEPT,    0x65
	.equ SND_REJECT,    0x68

	@ 게임 함수(Thumb, |1)
	.equ FN_SOUND,      0x0833BA35  @ r0 = 효과음 id
	.equ FN_REDRAW,     0x0834A955
	.equ FN_APPEND,     0x0834AE01  @ native 셀 append(mode0 전용)
	.equ FN_CLEAR,      0x0834AE61  @ native slot[len] = 0
	.equ FN_ASK,        0x0834AED9  @ native 확인 질문
	.equ FN_ALLOC,      0x08315301  @ r0 = 크기
	.equ FN_ROWDRAW,    0x08314EB1  @ r0 x, r1 y, r2 [r4], r3 문자열, [sp] 0x8000, [sp+4] 0
	@ 고정 복귀점(|1)
	.equ RET_INPUT_END, 0x0834B429  @ 입력 루프 epilogue
	.equ RET_S1_NATIVE, 0x0834B0C7
	.equ RET_S3,        0x0834B21B  @ sound 0x66 → B428
	.equ RET_D1_NATIVE, 0x0834AB45
	.equ RET_D1_PRIV,   0x0834ABA3
	.equ NATIVE_ROW0,   0x0883FE40

	@ 원거리 호출: lr 를 이 이미지 안으로 두고 bx r3 (bl 도달 거리 밖)
	.macro FAR_CALL fn
	ldr	r3, =\fn
	bl	nc_call_r3
	.endm

	.macro LOAD_MODE obj
	ldr	\obj, =OBJ_PTR
	ldr	\obj, [\obj]
	movs	r0, #OFF_MODE
	ldrb	r0, [\obj, r0]
	cmp	r0, #1
	.endm

	@ r4-r11·lr 저장, r4 = 저장 직후 sp, sp 를 8정렬로 내림. r3 만 쓴다(r0-r2 보존).
	.macro ENTER
	push	{r4-r7, lr}
	mov	r4, r8
	mov	r5, r9
	mov	r6, r10
	mov	r7, r11
	push	{r4-r7}
	mov	r4, sp
	mov	r3, sp
	lsrs	r3, r3, #3
	lsls	r3, r3, #3
	mov	sp, r3
	.endm

	@ sp·r8-r11·r4-r7·lr 복원 후 고정 복귀
	.macro LEAVE_TO ret
	mov	sp, r4
	pop	{r4-r7}
	mov	r8, r4
	mov	r9, r5
	mov	r10, r6
	mov	r11, r7
	pop	{r4-r7}
	pop	{r0}
	mov	lr, r0
	ldr	r0, =\ret
	bx	r0
	.endm

	.text

@ S1 — mode1: 좌표로 사설 셀을 읽어 nc_press. 0 → 수락음·redraw, 1/범위 밖 → 거부음.
@      mode0: 원 명령 재생(수락음 → native append) 후 B0C6 복귀.
	.balign 4
	.global	nc_tramp_press
	.type	nc_tramp_press, %function
	.thumb_func
nc_tramp_press:
	ENTER
	LOAD_MODE r5
	bne	.Lpress_native
	movs	r0, #OFF_X
	ldrsh	r1, [r5, r0]
	movs	r0, #OFF_Y
	ldrsh	r2, [r5, r0]
	cmp	r1, #GRID_W
	bhs	.Lpress_reject          @ 음수는 부호 없는 비교에서 큰 값
	cmp	r2, #GRID_H
	bhs	.Lpress_reject
	lsls	r0, r2, #4
	subs	r0, r0, r2              @ y*15
	adds	r0, r0, r1
	lsls	r0, r0, #1
	ldr	r1, =nc_sel_priv
	adds	r1, r1, r0
	ldrb	r0, [r1]
	ldrb	r1, [r1, #1]
	lsls	r0, r0, #8
	orrs	r1, r0                  @ r1 = 셀 코드(BE → 값, 0 확장)
	adds	r0, r5, #0
	bl	nc_press
	cmp	r0, #0
	bne	.Lpress_reject
	movs	r0, #SND_ACCEPT
	FAR_CALL FN_SOUND
	FAR_CALL FN_REDRAW
	LEAVE_TO RET_INPUT_END
.Lpress_reject:
	movs	r0, #SND_REJECT
	FAR_CALL FN_SOUND
	LEAVE_TO RET_INPUT_END
.Lpress_native:
	movs	r0, #SND_ACCEPT
	FAR_CALL FN_SOUND
	FAR_CALL FN_APPEND
	LEAVE_TO RET_S1_NATIVE
	.ltorg
	.size	nc_tramp_press, . - nc_tramp_press

@ S2 — mode1: nc_confirm 1(미완성) → 거부음, 0 → native 확인 질문. mode0: native 확인 질문.
	.balign 4
	.global	nc_tramp_confirm
	.type	nc_tramp_confirm, %function
	.thumb_func
nc_tramp_confirm:
	ENTER
	LOAD_MODE r5
	bne	.Lconfirm_native
	adds	r0, r5, #0
	bl	nc_confirm
	cmp	r0, #0
	beq	.Lconfirm_native
	movs	r0, #SND_REJECT
	FAR_CALL FN_SOUND
	LEAVE_TO RET_INPUT_END
.Lconfirm_native:
	FAR_CALL FN_ASK
	LEAVE_TO RET_INPUT_END
	.ltorg
	.size	nc_tramp_confirm, . - nc_tramp_confirm

@ S3 — mode1: nc_backspace(len ≥ 1 인 지점, 상태 불변 거부도 같은 경로) → redraw → B21A.
@      mode0: len-- (r2 = obj+0x61) → native slot clear → redraw → B21A.
	.balign 4
	.global	nc_tramp_backspace
	.type	nc_tramp_backspace, %function
	.thumb_func
nc_tramp_backspace:
	ENTER
	LOAD_MODE r5
	bne	.Lbackspace_native
	adds	r0, r5, #0
	bl	nc_backspace
	b	.Lbackspace_redraw
.Lbackspace_native:
	ldrb	r0, [r2]
	subs	r0, #1
	strb	r0, [r2]
	FAR_CALL FN_CLEAR
.Lbackspace_redraw:
	FAR_CALL FN_REDRAW
	LEAVE_TO RET_S3
	.ltorg
	.size	nc_tramp_backspace, . - nc_tramp_backspace

@ D1 — r3 로 진입. r0-r3 dead, r4 = 0x08814FB0 포인터(live), r7·r8·sb live.
@      mode0: 원 4명령(r2=[r4], r3=원 행 0, r6=0x8000) 재생 → AB44.
@      mode1: 사설 6행을 그린다. 행 함수 r3 는 문자열 인자이므로 함수 주소는 r7(nc_call_r7).
@             복귀 전 r5=0·r6=0x8000 과 native 스택 인자 [sp]=0x8000·[sp+4]=0 을 native 와 같게 둔다.
	.balign 4
	.global	nc_tramp_display
	.type	nc_tramp_display, %function
	.thumb_func
nc_tramp_display:
	ldr	r0, =OBJ_PTR
	ldr	r0, [r0]
	movs	r1, #OFF_MODE
	ldrb	r0, [r0, r1]
	cmp	r0, #1
	beq	.Ldisplay_private
	ldr	r2, [r4]
	ldr	r3, =NATIVE_ROW0
	movs	r6, #0x80
	lsls	r6, r6, #8
	ldr	r0, =RET_D1_NATIVE
	bx	r0
.Ldisplay_private:
	push	{r7, lr}
	sub	sp, #8
	movs	r6, #0x80
	lsls	r6, r6, #8
	movs	r5, #0
	.irp	row, 0, 1, 2, 3, 4, 5
	str	r6, [sp]
	str	r5, [sp, #4]
	movs	r0, #6
	movs	r1, #(6 + 2 * \row)
	ldr	r2, [r4]
	ldr	r3, =nc_row_priv_\row
	ldr	r7, =FN_ROWDRAW
	bl	nc_call_r7
	.endr
	add	sp, #8
	pop	{r7}
	pop	{r0}
	mov	lr, r0
	movs	r5, #0
	movs	r6, #0x80
	lsls	r6, r6, #8
	str	r6, [sp]
	str	r5, [sp, #4]
	ldr	r0, =RET_D1_PRIV
	bx	r0
	.ltorg
	.size	nc_tramp_display, . - nc_tramp_display

@ P1 — B970 과 같은 프레임. 0x80B 할당 → [0x03004650] 에 저장(0 이어도) → 0 이 아니면 tail 초기화
@      (+70 active 0, +71 L FF, +72 V FF, +73 T 0, +74..+7F 0). 복귀도 B970 과 같이 pop {r0}; bx r0.
	.balign 4
	.global	nc_alloc
	.type	nc_alloc, %function
	.thumb_func
nc_alloc:
	push	{r4, lr}
	ldr	r4, =OBJ_PTR
	movs	r0, #0x80
	FAR_CALL FN_ALLOC
	str	r0, [r4]
	cmp	r0, #0
	beq	.Lalloc_done
	movs	r1, #OFF_TAIL
	adds	r1, r1, r0
	movs	r2, #0
	movs	r3, #16
.Lalloc_zero:
	subs	r3, #1
	strb	r2, [r1, r3]
	bne	.Lalloc_zero
	movs	r2, #0xFF
	strb	r2, [r1, #1]
	strb	r2, [r1, #2]
.Lalloc_done:
	pop	{r4}
	pop	{r0}
	bx	r0
	.ltorg
	.size	nc_alloc, . - nc_alloc

	.balign 4
	.global	nc_call_r3
	.type	nc_call_r3, %function
	.thumb_func
nc_call_r3:
	bx	r3
	.size	nc_call_r3, . - nc_call_r3

	.balign 2
	.global	nc_call_r7
	.type	nc_call_r7, %function
	.thumb_func
nc_call_r7:
	bx	r7
	.size	nc_call_r7, . - nc_call_r7

	.section .rodata.nc_grid, "a"
	.global	nc_sel_priv
	.global	nc_row_priv
	.include "grid.inc"

	.section .note.GNU-stack, "", %progbits
