/*
 * Carnival TKL (AMK firmware, STM32F411) - GIF screen auto-sleep patch
 *
 * Adds:
 *   - SCR_TOG custom keycode (0x7E09): press to switch the screen off/on
 *   - SCR_NXT / SCR_PRV (0x7E0A / 0x7E0B): jump to the next / previous GIF
 *   - SLP_TOG (0x7E0C): enable / disable auto-sleep at runtime
 *   - optional auto-sleep after timeout_ms without key events (0 = disabled):
 *     the screen is powered off (PB9, backlight included) and all RGB LEDs go
 *     dark; the next key wakes both.
 *
 * Waking the panel needs the stock ST7735 init sequence, which has ~770 ms of
 * fixed delays.  The stock code runs it with blocking wait_ms() calls, which
 * freezes matrix scanning/USB (typing stalls, the wake key auto-repeats).  This
 * patch replays the same sequence from wake_table one step per main-loop pass
 * and waits with the timer instead, so the keyboard keeps working while the
 * screen comes back.  Host resume uses the same path; SCR_TOG "on" keeps the
 * stock power-on (see toggle).
 *
 * Placed in the unused zero-padding of the app image at PATCH_BASE and reached
 * through five redirected branches (see patch_fw.py):
 *
 *   0x080222f2  b.w  screen_init       -> init_hook    (seed idle timer)
 *   0x080222f6  b.w  screen_task       -> task_hook    (sleep / wake screen + RGB)
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
    .equ RGB_SLEEP,         0x200090b8  /* uint8: rgb task blanks all LEDs when set;
                                           written only by rgb init and suspend */
    .equ AUTO_SLEEP,        0x20000242  /* uint8 screen phase: 0 awake, 1 asleep
                                           (powered off), 2 waking (wake_table);
                                           padding after SCREEN_ON, zeroed at boot */
    .equ SLEEP_DIS,         0x20000243  /* uint8: 1 = auto-sleep disabled by SLP_TOG;
                                           padding after SCREEN_ON, zeroed at boot */
    .equ FLAG_RGB_SLEEP,    1
    .equ SCR_TOG,           0x7e09      /* QK_KB_9, customKeycodes[9] in Vial */
    .equ SCR_NXT,           0x7e0a      /* QK_KB_10 */
    .equ SCR_PRV,           0x7e0b      /* QK_KB_11 */
    .equ SLP_TOG,           0x7e0c      /* QK_KB_12: enable/disable auto-sleep */
    .equ ANIM_SCREEN,       0x20000210  /* +0x14 frame delay, +0x1c anim_t*,
                                           +0x28 frame timer.  +0x14/+0x28 are only
                                           read by the GIF task, which does not run
                                           while the screen is off, so phase 2
                                           borrows them: +0x14 = wake_table cursor,
                                           +0x28 = time the last step ran */
    .equ ANIM_DELAY,        0x14
    .equ ANIM_TICKS,        0x28
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
    .equ amk_memset,        0x08020944  /* void* (dst, val, n) */
    .equ lcd_fill,          0x08022968  /* (drv, x, y, w, data, size) - sync SPI fill */
    .equ SCREEN_OBJ,        0x20000210  /* screen object base; +32 buf, +36 size */
    .equ LCD_DRIVER,        0x20008818  /* st7735-family driver struct; +32 = bus
                                           context (pins + SPI) used by cmd/data */
    .equ LCD_PARAM,         0x20000244  /* screen_driver_param: +4 power pin,
                                           +12 reset pin, +16 cs pin */
    .equ PWR_ON_LEVEL,      0           /* PB9 is active low (power_on = 0) */
    .equ gpio_set_output,   0x080283c8  /* void (pin) */
    .equ gpio_write,        0x080283b0  /* void (pin, level) */
    .equ lcd_create,        0x08022a5c  /* void (drv, param): bind pins/SPI */
    .equ lcd_cmd,           0x08022820  /* void (ctx, cmd): DC low + 1 byte */
    .equ lcd_data,          0x08022840  /* void (ctx, buf, n): DC high + n bytes */
    .equ OP_END,            0
    .equ OP_CMD,            1           /* cmd, n, args[n] */
    .equ OP_RST_LOW,        2
    .equ OP_RST_HIGH,       3
    .equ OP_CS_LOW,         4
    .equ OP_CS_HIGH,        5
    .equ OP_BLACK_FILL,     6
    .equ OP_POWER_ON,       7

    .section .text
    .global timeout_ms

/* header: patched in by patch_fw.py, keep at offset 0 */
timeout_ms:
    .word 0                     /* idle time before sleep, ms; 0 = never */
    .ascii "SSLP"               /* marker so the patcher can find/verify it */
flags:
    .word FLAG_RGB_SLEEP        /* bit0: RGB LEDs sleep with the screen */

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
resume_hook:                    /* replaces suspend_wakeup_kb (= screen_set_power(1)) */
    push    {r4, lr}
    bl      timer_read32
    ldr     r1, =LAST_ACTIVITY
    str     r0, [r1]
    pop     {r4, lr}
    ldr     r3, =MANUAL_OFF     /* switched off by hand: stay off after resume */
    ldrb    r3, [r3]
    cbnz    r3, 1f
    ldr     r3, =USB_SETTING    /* MSC mode: task_hook is idle, use stock init */
    ldr     r3, [r3]
    tst     r3, #2
    bne.w   suspend_wakeup_kb
    ldr     r3, =SCREEN_ON      /* already on: nothing to do */
    ldrb    r3, [r3]
    cbnz    r3, 1f
    ldr     r2, =AUTO_SLEEP     /* off: let task_hook bring it back without */
    ldrb    r3, [r2]            /* blocking (phase 1 -> 2); keep a wake that */
    cbnz    r3, 1f              /* is already queued/running                 */
    movs    r3, #1
    strb    r3, [r2]
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
    adds    r2, #1
    cmp     r0, r2
    beq     toggle_sleep
    b.w     process_record_kb

toggle_sleep:                   /* flip the auto-sleep enable flag; the next
                                   task_hook tick wakes everything if disabling */
    ldrb    r3, [r1, #5]        /* event.pressed */
    cbz     r3, 1f
    ldr     r2, =SLEEP_DIS
    ldrb    r3, [r2]
    eor     r3, r3, #1
    strb    r3, [r2]
1:  movs    r0, #0
    bx      lr

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
5:  ldr     r3, =AUTO_SLEEP     /* +0x14 is the wake cursor in phase 2 */
    ldrb    r3, [r3]
    cmp     r3, #2
    beq     8f
    ldr     r4, =ANIM_SCREEN
    movs    r0, #0
    str     r0, [r4, #ANIM_DELAY] /* show the new GIF right away */
8:  pop     {r3, r4, r5, r6, r7, lr}
9:  movs    r0, #0
    bx      lr

toggle:                         /* SCR_TOG keeps the stock (blocking) power-on:
                                   the toggle key never reaches the host, so the
                                   pause cannot auto-repeat a key, and it stays a
                                   known-good way to bring the panel back */
    ldrb    r3, [r1, #5]        /* event.pressed */
    cbz     r3, 2f
    push    {r4, lr}
    ldr     r3, =AUTO_SLEEP     /* either way, any auto sleep/wake is over */
    movs    r0, #0
    strb    r0, [r3]
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
    push    {r4, r5, r6, lr}
    ldr     r3, =USB_SETTING    /* MSC mode: behave exactly like stock */
    ldr     r3, [r3]
    tst     r3, #2
    bne     do_task
    ldr     r6, =AUTO_SLEEP
    ldr     r3, =SUSPENDED      /* USB suspended: stock suspend owns screen+RGB */
    ldrb    r3, [r3]
    cbz     r3, 1f
    ldrb    r3, [r6]            /* ...but a wake in progress is cut off again */
    cmp     r3, #2
    bne     do_task
    movs    r3, #1
    strb    r3, [r6]
    bl      power_off_pins
    b       do_task

1:  movs    r4, #0              /* r4 = idle */
    ldr     r3, timeout_ms
    cbz     r3, 3f              /* auto-sleep not built in: never idle, and the */
                                /* stock RGB flag is left alone               */
    ldr     r3, =SLEEP_DIS      /* SLP_TOG turned auto-sleep off */
    ldrb    r3, [r3]
    cbnz    r3, 2f
    ldr     r0, =LAST_ACTIVITY
    ldr     r0, [r0]
    bl      timer_elapsed32     /* r0 = now - last */
    ldr     r1, timeout_ms
    cmp     r0, r1
    it      hi
    movhi   r4, #1
2:  ldr     r3, flags           /* RGB follows the idle timer (cheap flag) */
    tst     r3, #FLAG_RGB_SLEEP
    beq     3f
    ldr     r3, =RGB_SLEEP
    strb    r4, [r3]

3:  ldr     r3, =MANUAL_OFF     /* SCR_TOG keeps the screen off on its own */
    ldrb    r3, [r3]
    cbnz    r3, do_task
    ldrb    r5, [r6]            /* r5 = phase */
    ldr     r3, =SCREEN_ON
    ldrb    r3, [r3]
    cbz     r4, active

    /* idle */
    cmp     r5, #2              /* idle while waking (not expected): back off */
    bne     4f
    movs    r0, #1
    strb    r0, [r6]
    bl      power_off_pins
    b       do_task
4:  cbnz    r5, do_task         /* already asleep */
    cbz     r3, do_task         /* already off */
    movs    r0, #1              /* go to sleep: stock blank + PB9 off (fast) */
    strb    r0, [r6]
    movs    r0, #0
    bl      screen_set_power
    b       do_task

active:
    cmp     r5, #1
    bne     5f
    cbz     r3, 6f
    movs    r0, #0              /* someone else already powered it: done */
    strb    r0, [r6]
    b       do_task
6:  movs    r0, #2              /* start the non-blocking wake */
    strb    r0, [r6]
    ldr     r4, =ANIM_SCREEN
    ldr     r0, =wake_table + 1
    str     r0, [r4, #ANIM_DELAY]
    bl      timer_read32
    str     r0, [r4, #ANIM_TICKS]
    b       do_task
5:  cmp     r5, #2
    bne     do_task
    bl      wake_step

do_task:                        /* stock task returns at once while SCREEN_ON=0 */
    pop     {r4, r5, r6, lr}
    b.w     screen_task

/* Run the next wake_table step once the previous step's wait has passed.
 * Each step is: op, [op args], wait (ms, 255 = 500) - same encoding as the
 * stock init tables.  The cursor always points just past the previous step,
 * so its wait byte is cursor[-1]. */
    .thumb_func
    .global wake_step
wake_step:
    push    {r4, r5, r6, lr}
    ldr     r4, =ANIM_SCREEN
    ldr     r5, [r4, #ANIM_DELAY]   /* cursor */
    ldrb    r6, [r5, #-1]           /* wait of the previous step */
    cmp     r6, #255
    it      eq
    moveq.w r6, #500
    ldr     r0, [r4, #ANIM_TICKS]
    bl      timer_elapsed32
    cmp     r0, r6
    blo     ws_done
    ldrb    r0, [r5], #1            /* op */
    cmp     r0, #OP_END
    beq     ws_end
    cmp     r0, #OP_CMD
    bne     1f
    ldrb    r1, [r5], #1            /* command byte */
    ldr     r0, =LCD_DRIVER
    ldr     r0, [r0, #32]
    bl      lcd_cmd
    ldrb    r2, [r5], #1            /* number of data bytes */
    cbz     r2, ws_next
    mov     r1, r5
    add     r5, r2
    ldr     r0, =LCD_DRIVER
    ldr     r0, [r0, #32]
    bl      lcd_data
    b       ws_next
1:  cmp     r0, #OP_RST_LOW
    bne     1f
    movs    r1, #0
    b       ws_rst
1:  cmp     r0, #OP_RST_HIGH
    bne     1f
    movs    r1, #1
ws_rst:
    ldr     r0, =LCD_PARAM
    ldr     r0, [r0, #12]
    bl      gpio_write
    b       ws_next
1:  cmp     r0, #OP_CS_LOW
    bne     1f
    movs    r1, #0
    b       ws_cs
1:  cmp     r0, #OP_CS_HIGH
    bne     1f
    movs    r1, #1
ws_cs:
    ldr     r0, =LCD_PARAM
    ldr     r0, [r0, #16]
    bl      gpio_write
    b       ws_next
1:  cmp     r0, #OP_BLACK_FILL
    bne     1f
    bl      blank_screen
    b       ws_next
1:  cmp     r0, #OP_POWER_ON        /* stock screen_power(1) without the init */
    bne     ws_next
    ldr     r0, =LCD_PARAM
    ldr     r0, [r0, #4]
    bl      gpio_set_output
    ldr     r0, =LCD_PARAM
    ldr     r0, [r0, #4]
    movs    r1, #PWR_ON_LEVEL
    bl      gpio_write
    ldr     r0, =LCD_DRIVER
    ldr     r1, =LCD_PARAM
    bl      lcd_create
ws_next:
    adds    r5, #1                  /* skip this step's wait byte */
    str     r5, [r4, #ANIM_DELAY]
    bl      timer_read32
    str     r0, [r4, #ANIM_TICKS]
ws_done:
    pop     {r4, r5, r6, pc}
ws_end:                             /* panel is up: resume the GIF */
    movs    r0, #0
    str     r0, [r4, #ANIM_DELAY]   /* draw the next frame right away */
    ldr     r3, =AUTO_SLEEP
    strb    r0, [r3]
    ldr     r3, =SCREEN_ON
    movs    r0, #1
    strb    r0, [r3]
    bl      timer_read32
    str     r0, [r4, #ANIM_TICKS]
    pop     {r4, r5, r6, pc}

/* Abort a wake: CS high and PB9 off again (SCREEN_ON is still 0). */
    .thumb_func
    .global power_off_pins
power_off_pins:
    push    {r4, lr}
    ldr     r4, =LCD_PARAM
    ldr     r0, [r4, #16]
    movs    r1, #1
    bl      gpio_write
    ldr     r0, [r4, #4]
    movs    r1, #(1 - PWR_ON_LEVEL)
    bl      gpio_write
    pop     {r4, pc}

/* Fill the LCD with black: faithful copy of the stock screen_power(0) blank
 * (buffer memset + sync lcd_fill).  Used as the black-fill step of the wake
 * sequence, where the stock init writes the same 128x128 black frame. */
    .thumb_func
    .global blank_screen
blank_screen:
    push    {r4, r5, lr}
    sub     sp, #20
    movs    r4, #0
    ldr     r5, =SCREEN_OBJ
    movs    r1, #0
    ldr     r2, [r5, #36]       /* size */
    ldr     r0, [r5, #32]       /* buf  */
    bl      amk_memset          /* memset(buf, 0, size) */
    ldr     r3, [r5, #36]
    str     r3, [sp, #8]
    ldr     r3, [r5, #32]
    str     r3, [sp, #4]
    movs    r3, #128
    str     r3, [sp, #0]
    mov     r2, r4
    mov     r1, r4
    ldr     r0, =LCD_DRIVER
    bl      lcd_fill
    add     sp, #20
    pop     {r4, r5, pc}

    .ltorg

/* Stock ST7735 power-up, flattened: screen_power(1) (0x080225E4) followed by
 * lcd_init (0x080229C4) with its five command tables (0x0803B785, 0x20000268,
 * 0x0803B774, 0x0803B74F, 0x0803B748).  patch_fw.py checks the OP_CMD entries
 * against those tables in the original image. */
    .global wake_table
wake_table:
    .byte   0x00                /* wait before the first step */
    .byte   0x07, 0x01   /* OP_POWER_ON  (PB9 on + lcd_create), wait 1 ms */
    .byte   0x04, 0x00   /* OP_CS_LOW */
    .byte   0x02, 0x05   /* OP_RST_LOW, wait 5 ms */
    .byte   0x03, 0x00   /* OP_RST_HIGH */
    .byte   0x01, 0x01, 0x00, 0x96   /* T1 cmd 0x01, wait 150 ms */
    .byte   0x01, 0x11, 0x00, 0xff   /* T1 cmd 0x11, wait 500 ms */
    .byte   0x01, 0xb1, 0x03, 0x01, 0x2c, 0x2d, 0x00   /* T1 cmd 0xb1 */
    .byte   0x01, 0xb2, 0x03, 0x01, 0x2c, 0x2d, 0x00   /* T1 cmd 0xb2 */
    .byte   0x01, 0xb3, 0x06, 0x01, 0x2c, 0x2d, 0x01, 0x2c, 0x2d, 0x00   /* T1 cmd 0xb3 */
    .byte   0x01, 0xb4, 0x01, 0x07, 0x00   /* T1 cmd 0xb4 */
    .byte   0x01, 0xc0, 0x03, 0xa2, 0x02, 0x84, 0x00   /* T1 cmd 0xc0 */
    .byte   0x01, 0xc1, 0x01, 0xc5, 0x00   /* T1 cmd 0xc1 */
    .byte   0x01, 0xc2, 0x02, 0x0a, 0x00, 0x00   /* T1 cmd 0xc2 */
    .byte   0x01, 0xc3, 0x02, 0x8a, 0x2a, 0x00   /* T1 cmd 0xc3 */
    .byte   0x01, 0xc4, 0x02, 0x8a, 0xee, 0x00   /* T1 cmd 0xc4 */
    .byte   0x01, 0xc5, 0x01, 0x0e, 0x00   /* T1 cmd 0xc5 */
    .byte   0x01, 0x20, 0x00, 0x00   /* T1 cmd 0x20 */
    .byte   0x01, 0x36, 0x01, 0xa8, 0x00   /* T2 cmd 0x36 */
    .byte   0x01, 0x3a, 0x01, 0x05, 0x00   /* T2 cmd 0x3a */
    .byte   0x01, 0x2a, 0x04, 0x00, 0x1a, 0x00, 0x69, 0x00   /* T3 cmd 0x2a */
    .byte   0x01, 0x2b, 0x04, 0x00, 0x01, 0x00, 0xa0, 0x00   /* T3 cmd 0x2b */
    .byte   0x01, 0x2c, 0x00, 0x00   /* T3 cmd 0x2c */
    .byte   0x01, 0x21, 0x00, 0x00   /* T3 cmd 0x21 */
    .byte   0x01, 0xe0, 0x10, 0x02, 0x1c, 0x07, 0x12, 0x37, 0x32, 0x29, 0x2d, 0x29, 0x25, 0x2b, 0x39, 0x00, 0x01, 0x03, 0x10, 0x00   /* T4 cmd 0xe0 */
    .byte   0x01, 0xe1, 0x10, 0x03, 0x1d, 0x07, 0x06, 0x2e, 0x2c, 0x29, 0x2d, 0x2e, 0x2e, 0x37, 0x3f, 0x00, 0x00, 0x02, 0x10, 0x00   /* T4 cmd 0xe1 */
    .byte   0x06, 0x00   /* OP_BLACK_FILL (stock blank: memset + lcd_fill, leaves CS high) */
    .byte   0x04, 0x00   /* OP_CS_LOW */
    .byte   0x01, 0x13, 0x00, 0x0a   /* T5 cmd 0x13, wait 10 ms */
    .byte   0x01, 0x29, 0x00, 0x64   /* T5 cmd 0x29, wait 100 ms */
    .byte   0x05, 0x00   /* OP_CS_HIGH */
    .byte   0x00   /* OP_END */

    .global wake_table_end
wake_table_end:
