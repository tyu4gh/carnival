/*
 * Carnival TKL (AMK firmware, STM32F411) - GIF screen auto-sleep patch
 *
 * Placed in the unused zero-padding of the app image at PATCH_BASE and reached
 * through four redirected branches (see patch_fw.py):
 *
 *   0x080222f2  b.w  screen_init      -> init_hook    (seed idle timer)
 *   0x080222f6  b.w  screen_task      -> task_hook    (sleep / wake screen)
 *   0x0802a670  bl   process_record   -> record_hook  (every key event = activity)
 *   0x08027e14  bl   suspend_wakeup_kb-> resume_hook  (host resume = activity)
 */
    .syntax unified
    .cpu cortex-m4
    .thumb

/* ---- addresses taken from the disassembly of Carnival_TKL_v5.uf2 ---- */
    .equ LAST_ACTIVITY,     0x2000058c  /* 4 unused bytes between .data and .bss */
    .equ SCREEN_ON,         0x20000240  /* uint8: screen powered (runtime only) */
    .equ USB_SETTING,       0x2000cb60  /* bit1 = USB mass-storage mode */
    .equ SUSPENDED,         0x2000cb54  /* uint8: USB suspended */

    .equ timer_read32,      0x08027e7e
    .equ timer_elapsed32,   0x08027e90
    .equ screen_set_power,  0x080227f4  /* void (bool on): blank + PB9 power */
    .equ screen_init,       0x08022700
    .equ screen_task,       0x0802279c
    .equ process_record,    0x0802ab5e
    .equ suspend_wakeup_kb, 0x0802232e

    .section .text
    .global timeout_ms

/* header: patched in by patch_fw.py, keep at offset 0 */
timeout_ms:
    .word 300000                /* idle time before sleep, ms; 0 = never */
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
    b.w     suspend_wakeup_kb

    .thumb_func
    .global task_hook
task_hook:
    push    {r4, lr}
    ldr     r3, =USB_SETTING    /* leave the screen alone in MSC mode */
    ldr     r3, [r3]
    tst     r3, #2
    bne     done
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
