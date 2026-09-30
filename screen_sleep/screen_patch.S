/*
 * Carnival TKL (AMK firmware, STM32F411) - GIF screen auto-sleep patch
 *
 * Adds:
 *   - SCR_TOG custom keycode (0x7E09): press to switch the screen off/on
 *   - SCR_NXT / SCR_PRV (0x7E0A / 0x7E0B): jump to the next / previous GIF
 *   - optional auto-sleep after timeout_ms without key events (0 = disabled)
 *
 * Placed in the unused zero-padding of the app image at PATCH_BASE and reached
 * through five redirected branches (see patch_fw.py):
 *
 *   0x080222f2  b.w  screen_init       -> init_hook    (seed idle timer)
 *   0x080222f6  b.w  screen_task       -> task_hook    (sleep / wake screen)
 *   0x0802a670  bl   process_record    -> record_hook  (every key event = activity)
 *   0x0802aa98  bl   process_record_kb -> kb_hook      (SCR_TOG/NXT/PRV keys)
 *   0x08027e14  bl   suspend_wakeup_kb -> resume_hook  (host resume = activity)
 */
    .syntax unified
    .cpu cortex-m4
    .thumb

/* ---- addresses taken from the disassembly of Carnival_TKL_v5.uf2 ---- */
    .equ LAST_ACTIVITY,     0x2000058c  /* 4 unused bytes between .data and .bss */
    .equ SCREEN_ON,         0x20000240  /* uint8: screen powered (runtime only) */
    .equ USB_SETTING,       0x2000cb60  /* bit1 = USB mass-storage mode */
    .equ SUSPENDED,         0x2000cb54  /* uint8: USB suspended */
    .equ MANUAL_OFF,        0x20000241  /* uint8: switched off by SCR_TOG; padding
                                           after SCREEN_ON, zeroed by .data init */
    .equ SCR_TOG,           0x7e09      /* QK_KB_9, customKeycodes[9] in Vial */
    .equ SCR_NXT,           0x7e0a      /* QK_KB_10 */
    .equ SCR_PRV,           0x7e0b      /* QK_KB_11 */
    .equ ANIM_SCREEN,       0x20000210  /* +0x14 frame delay, +0x1c anim_t* */
    .equ ANIM_FILE,         0x418       /* anim_t: FIL of the open .anm */
    .equ ANIM_COUNT,        0x1446      /* anim_t: uint16 number of files */
    .equ ANIM_INDEX,        0x1448      /* anim_t: uint16 current file index */

    .equ timer_read32,      0x08027e7e
    .equ timer_elapsed32,   0x08027e90
    .equ screen_set_power,  0x080227f4  /* void (bool on): blank + PB9 power */
    .equ screen_init,       0x08022700
    .equ screen_task,       0x0802279c
    .equ process_record,    0x0802ab5e
    .equ suspend_wakeup_kb, 0x0802232e
    .equ process_record_kb, 0x08022334
    .equ anim_close_file,   0x08026f04  /* void (FIL*) */
    .equ anim_open_index,   0x08026f18  /* bool (anim_t*): open file ANIM_INDEX */

    .section .text
    .global timeout_ms

/* header: patched in by patch_fw.py, keep at offset 0 */
timeout_ms:
    .word 0                     /* idle time before sleep, ms; 0 = never */
    .ascii "SSLP"               /* marker so the patcher can find/verify it */

    .thumb_func
    .global init_hook
init_hook:
    push    {r4, lr}
    bl      timer_read32
    ldr     r1, =LAST_ACTIVITY
    str     r0, [r1]
    pop     {r4, lr}
    b.w     screen_init

    .thumb_func
    .global record_hook
record_hook:                    /* r0 = keyrecord_t* */
    push    {r0, lr}
    bl      timer_read32
    ldr     r1, =LAST_ACTIVITY
    str     r0, [r1]
    pop     {r0, lr}
    b.w     process_record

    .thumb_func
    .global resume_hook
resume_hook:
    push    {r4, lr}
    bl      timer_read32
    ldr     r1, =LAST_ACTIVITY
    str     r0, [r1]
    pop     {r4, lr}
    ldr     r3, =MANUAL_OFF     /* switched off by hand: stay off after resume */
    ldrb    r3, [r3]
    cbnz    r3, 1f
    b.w     suspend_wakeup_kb
1:  bx      lr

    .thumb_func
    .global kb_hook
kb_hook:                        /* r0 = keycode, r1 = keyrecord_t* */
    movw    r2, #SCR_TOG
    cmp     r0, r2
    beq     toggle
    adds    r2, #1
    cmp     r0, r2
    beq     next_anim
    adds    r2, #1
    cmp     r0, r2
    beq     prev_anim
    b.w     process_record_kb

next_anim:
    movs    r3, #1
    b       switch_anim
prev_anim:
    movs    r3, #0
switch_anim:                    /* r1 = record, r3 = 1 next / 0 previous */
    ldrb    r2, [r1, #5]        /* event.pressed */
    cbz     r2, 9f
    push    {r3, r4, r5, r6, r7, lr}
    mov     r7, r3
    ldr     r4, =ANIM_SCREEN
    ldr     r5, [r4, #0x1c]     /* anim_t* (NULL in MSC mode) */
    cbz     r5, 8f
    add.w   r0, r5, #ANIM_FILE  /* close the file being played */
    bl      anim_close_file
    add.w   r6, r5, #0x1000
    ldrh    r4, [r6, #(ANIM_COUNT - 0x1000)]
    cbz     r4, 8f
1:  ldrh    r3, [r6, #(ANIM_INDEX - 0x1000)]
    ldrh    r2, [r6, #(ANIM_COUNT - 0x1000)]
    cbz     r7, 2f
    adds    r3, #1              /* next, wrapping to 0 */
    cmp     r3, r2
    blo     3f
    movs    r3, #0
    b       3f
2:  cbnz    r3, 4f              /* previous, wrapping to count-1 */
    mov     r3, r2
4:  subs    r3, #1
3:  strh    r3, [r6, #(ANIM_INDEX - 0x1000)]
    mov     r0, r5
    bl      anim_open_index
    cbnz    r0, 5f
    subs    r4, #1              /* skip files that fail to open */
    bne     1b
    b       8f
5:  ldr     r4, =ANIM_SCREEN
    movs    r0, #0
    str     r0, [r4, #0x14]     /* show the new GIF right away */
8:  pop     {r3, r4, r5, r6, r7, lr}
9:  movs    r0, #0
    bx      lr

toggle:
    ldrb    r3, [r1, #5]        /* event.pressed */
    cbz     r3, 2f
    push    {r4, lr}
    ldr     r3, =SCREEN_ON
    ldrb    r0, [r3]
    ldr     r2, =MANUAL_OFF
    cbz     r0, 1f
    movs    r0, #1              /* on -> off */
    strb    r0, [r2]
    movs    r0, #0
    bl      screen_set_power
    pop     {r4, lr}
    b       2f
1:  strb    r0, [r2]            /* off -> on (r0 == 0) */
    bl      timer_read32
    ldr     r1, =LAST_ACTIVITY
    str     r0, [r1]
    movs    r0, #1
    bl      screen_set_power
    pop     {r4, lr}
2:  movs    r0, #0              /* key handled */
    bx      lr

    .thumb_func
    .global task_hook
task_hook:
    push    {r4, lr}
    ldr     r3, =USB_SETTING    /* leave the screen alone in MSC mode */
    ldr     r3, [r3]
    tst     r3, #2
    bne     done
    ldr     r3, =MANUAL_OFF     /* SCR_TOG owns the screen while off */
    ldrb    r3, [r3]
    cbnz    r3, done
    ldr     r3, =SUSPENDED      /* suspend/resume hooks own the screen then */
    ldrb    r3, [r3]
    cbnz    r3, done
    ldr     r3, timeout_ms
    cbz     r3, done
    ldr     r0, =LAST_ACTIVITY
    ldr     r0, [r0]
    bl      timer_elapsed32     /* r0 = now - last */
    ldr     r1, timeout_ms
    ldr     r3, =SCREEN_ON
    ldrb    r4, [r3]
    cmp     r0, r1
    bhi     idle
    cbnz    r4, done            /* active and already on */
    movs    r0, #1
    bl      screen_set_power
    b       done
idle:
    cbz     r4, done            /* idle and already off */
    movs    r0, #0
    bl      screen_set_power
done:
    pop     {r4, lr}
    b.w     screen_task

    .ltorg
