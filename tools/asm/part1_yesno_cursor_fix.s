.syntax unified
.thumb
.global part1_yesno_cursor_fix
part1_yesno_cursor_fix:
    ldr r0, =0x060060CE   @ yes cursor, top
    ldrh r1, [r0]
    ldr r2, =0x0000A1BA
    cmp r1, r2
    beq done
    movs r3, #4          @ legacy no cursor x9
    bl part1_yesno_prompt_id
    cmp r1, #0
    beq legacy
    lsls r3, r3, #1     @ name-wide no cursor x11
legacy:
    strh r2, [r0, r3]
    ldr r0, =0x0600610E
    ldr r2, =0x0000A1BB
    strh r2, [r0, r3]
done:
    pop {r0-r7,pc}      @ restore original overlay registers
    .align 2
