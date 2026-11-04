@ 1편 이름 조합 Thumb 트램펄린 (PLAN B T3, D6). ARMv4T Thumb-1 전용.
@ Part 2 tools/name_compose/tramp.s 의 ENTER/LEAVE_TO/FAR_CALL 매크로를 복사해 1편 상수로 다시 쓴다
@ (공유 파일 include 금지 — D0: Part 2 SOURCE 는 1바이트도 바꾸지 않는다).
@
@ 훅 사이트(빌더가 IMAGE_RT + SYMBOLS[x] | 1 을 리터럴로 쓴다):
@   H1 0x08B49018 → nc1_tramp_press      일반 셀(사설 선택표 → nc_press)
@   H2 0x08B48FE4 → nc1_tramp_confirm    확정(START·OK 셀 공통)
@   H3 0x08B49162 → nc1_tramp_backspace  지우기(B·뒤로 셀, 진입 시 len ≥ 1)
@   H4 0x08B488FE → nc1_tramp_display    생성자 6행 그리기 자리(tail 초기화·host 업로드·사설 6행)
@   H5 0x08B48E50 → nc1_preview          미리보기 함수 전체 대체(bl 로 호출됨 — lr 복귀)
@ obj = [0x03004690]. H1–H4 는 ldr r3,=tramp; bx r3 로 들어오며 r0–r3·lr 은 dead.
@ 복귀점의 r0 는 모두 dead 이고 플래그를 읽지 않는다 → ldr r0,=ret|1; bx r0.

	.syntax unified
	.cpu arm7tdmi
	.thumb

	@ 런타임 주소 — gen_tables_p1.CONFIG 와 같아야 한다(build_image_p1.py 가 대조).
	.equ OBJ_PTR,       0x03004690
	.equ LIT_TILEMAP,   0x08BE7280  @ [LIT] = BG0 타일맵 버퍼(0x02012D44)
	.equ OFF_X,         0x1E        @ s16 커서 x
	.equ OFF_Y,         0x20        @ s16 커서 y
	.equ OFF_MAX,       0x62
	.equ OFF_BOXX,      0x63        @ NAME 박스 시작 x 타일
	.equ GRID_W,        15
	.equ GRID_H,        6
	.equ SND_ACCEPT,    0x65
	.equ SND_REJECT,    0x68

	@ 게임 함수(Thumb, |1)
	.equ FN_SOUND,      0x08B3E419  @ r0 = 효과음 id
	.equ FN_ASK,        0x08B48DA9  @ native 확정: 공백 전수 검사 → 질문 / 거부 메시지
	.equ FN_ROWDRAW,    0x08B1311D  @ r0 x, r1 y, r2 타일맵, r3 문자열, [sp] 0x8000, [sp+4] 1
	.equ FN_CLEAR,      0x08B10E35  @ r0 타일맵, r1 x, r2 y, r3 w, [sp] h, [sp+4] 채움
	.equ FN_FLUSH,      0x08B119C1
	@ 고정 복귀점(|1)
	.equ RET_INPUT_END, 0x08B49337  @ 입력 루프 epilogue
	.equ RET_S3,        0x08B4916F  @ 소리 0x66 → epilogue
	.equ RET_D1,        0x08B48965  @ 생성자 6행 다음

	@ 원거리 호출(bl 도달 거리 밖): r3 로 호출 — 인자 r0–r2 만
	.macro FAR_CALL fn
	ldr	r3, =\fn
	bl	nc1_call_r3
	.endm

	@ 원거리 호출: r7 로 호출 — 인자 r0–r3 + 스택. r7 은 ENTER 가 저장한다.
	.macro FAR_CALL7 fn
	ldr	r7, =\fn
	bl	nc1_call_r7
	.endm

	.macro LOAD_OBJ reg
	ldr	\reg, =OBJ_PTR
	ldr	\reg, [\reg]
	.endm

	@ r4-r11·lr 저장, r4 = 저장 직후 sp, sp 를 8정렬로 내림. r3 만 쓴다(r0-r2 보존).
	@ 저장 배치(r4 기준): +0 r8, +4 r9, +8 r10, +12 r11, +16 r4, +20 r5, +24 r6, +28 r7, +32 lr
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

	@ sp·r8-r11·r4-r7 복원, 저장한 lr 을 lr 에 되돌린다(r0 사용).
	.macro RESTORE
	mov	sp, r4
	pop	{r4-r7}
	mov	r8, r4
	mov	r9, r5
	mov	r10, r6
	mov	r11, r7
	pop	{r4-r7}
	pop	{r0}
	mov	lr, r0
	.endm

	@ 복원 후 고정 복귀
	.macro LEAVE_TO ret
	RESTORE
	ldr	r0, =\ret
	bx	r0
	.endm

	@ 복원 후 호출자(저장한 lr)로 복귀 — H5
	.macro LEAVE_LR
	RESTORE
	bx	lr
	.endm

	.text

@ H1 — 커서로 사설 셀을 읽어 nc_press. 0 → pad·수락음·미리보기, 1/범위 밖 → 거부음. 모두 epilogue 로.
	.balign 4
	.global	nc1_tramp_press
	.type	nc1_tramp_press, %function
	.thumb_func
nc1_tramp_press:
	ENTER
	LOAD_OBJ r5
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
	orrs	r1, r0                  @ r1 = 셀 코드(BE → 값)
	adds	r0, r5, #0
	bl	nc_press
	cmp	r0, #0
	bne	.Lpress_reject
	adds	r0, r5, #0
	bl	nc1_pad
	movs	r0, #SND_ACCEPT
	FAR_CALL FN_SOUND
	bl	nc1_preview
	LEAVE_TO RET_INPUT_END
.Lpress_reject:
	movs	r0, #SND_REJECT
	FAR_CALL FN_SOUND
	LEAVE_TO RET_INPUT_END
	.ltorg
	.size	nc1_tramp_press, . - nc1_tramp_press

@ H2 — nc_confirm 1(미완성) → 거부음. 0 → pad → native 확정(공백 검사·질문·거부 메시지).
	.balign 4
	.global	nc1_tramp_confirm
	.type	nc1_tramp_confirm, %function
	.thumb_func
nc1_tramp_confirm:
	ENTER
	LOAD_OBJ r5
	adds	r0, r5, #0
	bl	nc_confirm
	cmp	r0, #0
	beq	.Lconfirm_ask
	movs	r0, #SND_REJECT
	FAR_CALL FN_SOUND
	LEAVE_TO RET_INPUT_END
.Lconfirm_ask:
	adds	r0, r5, #0
	bl	nc1_pad
	FAR_CALL FN_ASK
	LEAVE_TO RET_INPUT_END
	.ltorg
	.size	nc1_tramp_confirm, . - nc1_tramp_confirm

@ H3 — nc_backspace(진입 시 len ≥ 1) → pad → 미리보기 → 4916E(소리 0x66 → epilogue).
	.balign 4
	.global	nc1_tramp_backspace
	.type	nc1_tramp_backspace, %function
	.thumb_func
nc1_tramp_backspace:
	ENTER
	LOAD_OBJ r5
	adds	r0, r5, #0
	bl	nc_backspace
	adds	r0, r5, #0
	bl	nc1_pad
	bl	nc1_preview
	LEAVE_TO RET_S3
	.ltorg
	.size	nc1_tramp_backspace, . - nc1_tramp_backspace

@ H4 — 생성자 6행 자리(0x08B488FE). 들어올 때 r6 = 타일맵 버퍼(live), r7·r8–r11 live, r0–r5 dead.
@      tail 초기화 + host 자모 업로드 → 사설 6행 0x08B1311C(6, 6+2i, r6, row_i, [sp]=0x8000, [sp+4]=1)
@      → native 와 같은 r4=1·r5=0x8000·[sp]=0x8000·[sp+4]=1 로 0x08B48964 복귀.
	.balign 4
	.global	nc1_tramp_display
	.type	nc1_tramp_display, %function
	.thumb_func
nc1_tramp_display:
	ENTER
	LOAD_OBJ r5
	adds	r0, r5, #0
	bl	nc1_display_init
	sub	sp, #8
	ldr	r6, [r4, #24]           @ 원래 r6 (타일맵 버퍼)
	movs	r5, #0x80
	lsls	r5, r5, #8              @ 0x8000
	.irp	row, 0, 1, 2, 3, 4, 5
	str	r5, [sp]
	movs	r0, #1
	str	r0, [sp, #4]
	movs	r0, #6
	movs	r1, #(6 + 2 * \row)
	adds	r2, r6, #0
	ldr	r3, =nc_row_priv_\row
	FAR_CALL7 FN_ROWDRAW
	.endr
	RESTORE
	movs	r4, #1
	movs	r5, #0x80
	lsls	r5, r5, #8
	str	r5, [sp]
	str	r4, [sp, #4]
	ldr	r0, =RET_D1
	bx	r0
	.ltorg
	.size	nc1_tramp_display, . - nc1_tramp_display

@ H5 — 미리보기(0x08B48E50) 전체 대체. native 와 같은 지우기·칸별 그리기·flush 순서.
@      칸 코드는 nc1_preview_codes 가 정한다(한글은 placeholder 로 치환하고 그 사전 타일에 글리프 업로드).
@      프레임(sp 기준): +0/+4 스택 인자, +8..+23 코드 16B, +24..+27 3B 문자열, +28 칸 수.
	.balign 4
	.global	nc1_preview
	.type	nc1_preview, %function
	.thumb_func
nc1_preview:
	ENTER
	sub	sp, #32
	LOAD_OBJ r5
	adds	r0, r5, #0
	add	r1, sp, #8
	bl	nc1_preview_codes
	str	r0, [sp, #28]
	movs	r0, #2
	str	r0, [sp]
	movs	r0, #0xB2
	lsls	r0, r0, #1              @ 0x164
	str	r0, [sp, #4]
	ldr	r0, =LIT_TILEMAP
	ldr	r0, [r0]
	movs	r1, #OFF_BOXX
	ldrb	r1, [r5, r1]
	movs	r2, #2
	movs	r3, #OFF_MAX
	ldrb	r3, [r5, r3]
	FAR_CALL7 FN_CLEAR
	movs	r6, #0                  @ i
.Lpreview_loop:
	ldr	r0, [sp, #28]
	cmp	r6, r0
	bhs	.Lpreview_done
	lsls	r0, r6, #1
	add	r1, sp, #8
	adds	r1, r1, r0
	add	r2, sp, #24
	ldrb	r0, [r1]
	strb	r0, [r2]
	ldrb	r0, [r1, #1]
	strb	r0, [r2, #1]
	movs	r0, #0
	strb	r0, [r2, #2]
	movs	r0, #0x80
	lsls	r0, r0, #8
	str	r0, [sp]
	movs	r0, #1
	str	r0, [sp, #4]
	movs	r0, #OFF_BOXX
	ldrb	r0, [r5, r0]
	adds	r0, r0, r6
	movs	r1, #2
	ldr	r2, =LIT_TILEMAP
	ldr	r2, [r2]
	add	r3, sp, #24
	FAR_CALL7 FN_ROWDRAW
	adds	r6, r6, #1
	b	.Lpreview_loop
.Lpreview_done:
	FAR_CALL7 FN_FLUSH
	LEAVE_LR
	.ltorg
	.size	nc1_preview, . - nc1_preview

	.balign 4
	.global	nc1_call_r3
	.type	nc1_call_r3, %function
	.thumb_func
nc1_call_r3:
	bx	r3
	.size	nc1_call_r3, . - nc1_call_r3

	.balign 2
	.global	nc1_call_r7
	.type	nc1_call_r7, %function
	.thumb_func
nc1_call_r7:
	bx	r7
	.size	nc1_call_r7, . - nc1_call_r7

	.section .rodata.nc1_grid, "a"
	.include "grid_p1.inc"

	.section .note.GNU-stack, "", %progbits
