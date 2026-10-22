.syntax unified
.cpu arm7tdmi
.thumb

// Replaces B12CB4..B12CBB. At this point r1 is the bank-1 tile start.
// In the live editor route, Help has tile start 0x0E and r5=03000E00;
// the editor menu has tile start 0xAE and r5=020100B0.
editor_help_dictionary_loader:
    cmp r1, #14
    bne native
    ldr r2, help_state
    cmp r5, r2
    bne native
    ldr r0, help_dictionary
    b load
native:
    ldr r0, original_dictionary
load:
    movs r2, #0
    movs r3, #1
    push {r4}
    bl call_native
    pop {r4}
    ldr r3, resume
    bx r3
call_native:
    ldr r4, native_fn
    bx r4
    .align 2
help_state: .word 0x03000E00
help_dictionary: .word 0x08F51000
original_dictionary: .word 0x08D83278
native_fn: .word 0x08B12BDD
resume: .word 0x08B12CBF
