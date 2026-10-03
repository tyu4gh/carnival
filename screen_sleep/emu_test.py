#!/usr/bin/env python3
"""Run the patch hooks in Unicorn with the original firmware functions stubbed.
usage: emu_test.py patched.uf2   (pip install unicorn)

Exits non-zero if any assertion fails."""
import os, struct, sys
from unicorn import *
from unicorn.arm_const import *
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import patch_fw as p

B, img = p.uf2_read(sys.argv[1])
TIMEOUT, _, FLAGS = struct.unpack_from('<I4sI', img, p.PATCH_BASE - B)
RGB_ON_SLEEP = FLAGS & 1          # 1: LEDs blank while idle, 0: --no-rgb-sleep

SCREEN_ON = 0x20000240; MANUAL = 0x20000241; AUTO = 0x20000242; SLPDIS = 0x20000243
LAST = 0x2000058c; USB = 0x2000cb60; SUSP = 0x2000cb54; RGB = 0x200090b8
ANIM_S = 0x20000210; LCD_PARAM = 0x20000244; LCD_DRV = 0x20008818; LCD_CTX = 0x20008840
PWR, RST, CS = 0x40020409, 0x40020408, 0x40020c02
STUBS = {0x8027e7e: 'timer_read32', 0x8027e90: 'timer_elapsed32', 0x80227f4: 'set_power',
         0x8026f04: 'anim_close', 0x8026f18: 'anim_open', 0x8020944: 'memset',
         0x8022968: 'lcd_fill', 0x80283c8: 'gpio_out', 0x80283b0: 'gpio_write',
         0x8022a5c: 'lcd_create', 0x8022820: 'lcd_cmd', 0x8022840: 'lcd_data',
         0x8022700: 'orig_init', 0x802279c: 'orig_task', 0x8022334: 'orig_kb',
         0x802232e: 'orig_wakeup', 0x802ab5e: 'orig_record'}
RET = 0x08000100
st = {'now': 0, 'calls': [], 'bad': set()}

mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
mu.mem_map(0x08000000, 0x80000); mu.mem_write(B, bytes(img))
mu.mem_write(RET, b'\xfe\xe7')
mu.mem_map(0x20000000, 0x20000)
mu.mem_write(0x20000000, bytes(img[0x803d158 - B:0x803d158 - B + 0x58c]))   # .data
mu.mem_write(LAST, b'\xa5\xa5\xa5\xa5')                                        # garbage at power-on
mu.mem_write(ANIM_S + 0x20, struct.pack('<II', 0x20013000, 0x8000))            # buf, size

def rd8(a): return mu.mem_read(a, 1)[0]
def wr8(a, v): mu.mem_write(a, bytes([v]))
def rd32(a): return struct.unpack('<I', mu.mem_read(a, 4))[0]

def hook(uc, addr, size, _):
    if addr not in STUBS:
        return
    n = STUBS[addr]
    r0, r1, r2 = (uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2))
    c = st['calls']
    if n == 'timer_read32': uc.reg_write(UC_ARM_REG_R0, st['now'])
    elif n == 'timer_elapsed32': uc.reg_write(UC_ARM_REG_R0, (st['now'] - r0) & 0xffffffff)
    elif n == 'set_power':
        if rd8(SCREEN_ON) != r0:
            wr8(SCREEN_ON, r0); c.append(('power', r0))
    elif n == 'orig_wakeup': c.append(('wakeup',)); wr8(SCREEN_ON, 1)
    elif n == 'memset': c.append(('memset', r0, r1, r2))
    elif n == 'lcd_fill': c.append(('fill', r0))
    elif n == 'gpio_out': c.append(('out', r0))
    elif n == 'gpio_write': c.append(('pin', r0, r1))
    elif n == 'lcd_create':                       # real one binds drv+32 -> bus context
        c.append(('create', r0, r1)); uc.mem_write(r0 + 32, struct.pack('<I', LCD_CTX))
    elif n == 'lcd_cmd': c.append(('cmd', r0, r1))
    elif n == 'lcd_data': c.append(('data', r0, bytes(uc.mem_read(r1, r2))))
    elif n == 'anim_close': c.append(('close', r0))
    elif n == 'anim_open':
        idx = struct.unpack('<H', uc.mem_read(r0 + 0x1448, 2))[0]
        ok = idx not in st['bad']
        c.append(('open', idx, ok)); uc.reg_write(UC_ARM_REG_R0, int(ok))
    elif n == 'orig_kb': c.append(('kb', r0)); uc.reg_write(UC_ARM_REG_R0, 1)
    else: c.append((n,))
    uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
mu.hook_add(UC_HOOK_CODE, hook)

def call(addr, *args):
    for r, v in zip([UC_ARM_REG_R0, UC_ARM_REG_R1], args):
        mu.reg_write(r, v)
    mu.reg_write(UC_ARM_REG_SP, 0x2001ff00); mu.reg_write(UC_ARM_REG_LR, RET | 1)
    st['calls'] = []
    mu.emu_start(addr | 1, RET, count=5000)
    return mu.reg_read(UC_ARM_REG_R0), st['calls']

def dest(site):
    hw1, hw2 = struct.unpack_from('<HH', img, site - B)
    s = (hw1 >> 10) & 1; j1 = (hw2 >> 13) & 1; j2 = (hw2 >> 11) & 1
    off = (s << 24) | ((1 - (j1 ^ s)) << 23) | ((1 - (j2 ^ s)) << 22) | ((hw1 & 0x3ff) << 12) | ((hw2 & 0x7ff) << 1)
    return site + 4 + off - ((1 << 25) if s else 0)
H = {'init': dest(0x80222f2), 'task': dest(0x80222f6), 'record': dest(0x802a670),
     'resume': dest(0x8027e14), 'kb': dest(0x802aa98)}

REC = 0x20010000
def key(code, pressed=1):
    mu.mem_write(REC, bytes(8)); wr8(REC + 5, pressed)
    call(H['record'], REC)
    return call(H['kb'], code, REC)
def task(): return call(H['task'])[1]
def names(calls): return [c[0] for c in calls]
def has(calls, n): return n in names(calls)

fail = []
def check(cond, msg):
    if not cond:
        fail.append(msg)

# stock init sequence the wake must replay
STOCK = [c for a in p.LCD_INIT_TABLES for c in p.lcd_table_cmds(img, B, a)]
STOCK_WAIT = 1 + 5 + sum(500 if d == 255 else d for _, _, d in STOCK)

def run_wake(max_ms=3000, between=None):
    """Tick task_hook every 1 ms until the wake finishes; return (ops, ms)."""
    ops, t0 = [], st['now']
    while rd8(AUTO) == 2 and st['now'] - t0 < max_ms:
        st['now'] += 1
        c = task()
        lcd = [x for x in c if x[0] in ('cmd', 'pin', 'out', 'create', 'fill')]
        check(len([x for x in c if x[0] in ('cmd', 'create', 'fill')]) <= 1, 'more than one wake step in a tick')
        check(not has(c, 'power'), 'wake used the blocking stock power-on')
        ops += c
        if between:
            between()
    return ops, st['now'] - t0

def check_wake_ops(ops, label):
    cmds = [(x[2], b'') for x in ops if x[0] == 'cmd']
    data = [x[2] for x in ops if x[0] == 'data']
    got, di = [], 0
    for x in ops:
        if x[0] == 'cmd':
            got.append([x[2], b''])
        elif x[0] == 'data':
            got[-1][1] = x[2]
    if not got:
        check(False, label + ': no init commands sent'); return
    check([(c, a) for c, a in got] == [(c, a) for c, a, _ in STOCK], label + ': command bytes differ from stock init')
    check(all(x[1] == LCD_CTX for x in ops if x[0] in ('cmd', 'data')), label + ': wrong lcd context')
    seq = [x for x in ops if x[0] in ('out', 'pin', 'create', 'fill')]
    want_head = [('out', PWR), ('pin', PWR, 0), ('create', LCD_DRV, LCD_PARAM), ('pin', CS, 0), ('pin', RST, 0), ('pin', RST, 1)]
    check(seq[:6] == want_head, label + ': power/reset preamble wrong: %r' % (seq[:6],))
    check(seq[6:] == [('fill', LCD_DRV), ('pin', CS, 0), ('pin', CS, 1)], label + ': fill/CS tail wrong: %r' % (seq[6:],))
    if 'fill' not in names(ops):
        check(False, label + ': no black fill'); return
    i_fill = names(ops).index('fill')
    check([x[2] for x in ops[:i_fill] if x[0] == 'cmd'][-1] == 0xe1 and
          [x[2] for x in ops[i_fill:] if x[0] == 'cmd'] == [0x13, 0x29], label + ': black fill not between T4 and T5')

def reset_state():
    for a, v in ((SCREEN_ON, 1), (MANUAL, 0), (AUTO, 0), (SLPDIS, 0), (SUSP, 0), (RGB, 0)):
        wr8(a, v)
    mu.mem_write(USB, bytes(4))

# ---------------------------------------------------------------- boot
st['now'] = 1000
call(H['init'])
check(rd32(LAST) == 1000, 'init_hook did not seed LAST')

if TIMEOUT:
    # ------------------------------------------------ sleep powers off
    reset_state(); st['now'] = 0x10000; key(0x04)
    c = task()
    check(names(c) == ['orig_task'], 'active tick touched the panel')
    st['now'] += TIMEOUT - 1; c = task()
    check(rd8(AUTO) == 0 and rd8(RGB) == 0, 'slept before the timeout')
    st['now'] += 2; c = task()
    check(('power', 0) in c, 'sleep did not power the screen off (backlight stays on)')
    check(rd8(AUTO) == 1 and rd8(SCREEN_ON) == 0 and rd8(RGB) == RGB_ON_SLEEP, 'sleep state wrong')
    st['now'] += 1000; c = task()
    check(not has(c, 'power') and rd8(AUTO) == 1, 'asleep tick changed state')

    # ------------------------------------------------ typing wakes without blocking
    st['now'] += 1000; r, c = key(0x04)
    check(r == 1 and c == [('kb', 0x04)], 'wake key not passed through to the keyboard')
    c = task()
    check(rd8(AUTO) == 2 and rd8(RGB) == 0, 'key did not start the wake / RGB not back at once')
    check(not has(c, 'power') and not has(c, 'cmd'), 'wake start blocked')
    def typing():                     # keys keep working during the wake
        r, c = key(0x05)
        check(r == 1 and c == [('kb', 0x05)], 'key swallowed during wake')
    ops, ms = run_wake(between=typing)
    check(rd8(AUTO) == 0 and rd8(SCREEN_ON) == 1, 'wake did not finish (%d ms)' % ms)
    check(STOCK_WAIT <= ms <= STOCK_WAIT + 80, 'wake took %d ms, stock waits %d ms' % (ms, STOCK_WAIT))
    check(rd32(ANIM_S + 0x14) == 0, 'GIF delay not reset after wake')
    check_wake_ops(ops, 'typing wake')
    c = task()
    check(names(c) == ['orig_task'], 'GIF does not resume after wake')

    # ------------------------------------------------ GIF keys during a wake keep the cursor
    st['now'] += TIMEOUT + 10; task(); st['now'] += 10; key(0x04); task()
    ANIM = 0x20012000
    mu.mem_write(ANIM_S + 0x1c, struct.pack('<I', ANIM)); mu.mem_write(ANIM + 0x1446, struct.pack('<HH', 4, 0))
    for _ in range(50):
        st['now'] += 1; task()
    cur = rd32(ANIM_S + 0x14)
    key(0x7e0a)
    check(rd32(ANIM_S + 0x14) == cur, 'SCR_NXT clobbered the wake cursor')
    ops, ms = run_wake()
    check(rd8(AUTO) == 0 and rd8(SCREEN_ON) == 1, 'wake broken after SCR_NXT')
    mu.mem_write(ANIM_S + 0x1c, bytes(4))

    # ------------------------------------------------ SLP_TOG
    reset_state(); st['now'] = 0x200000; key(0x04); task()
    key(0x7e0c); check(rd8(SLPDIS) == 1, 'SLP_TOG did not disable')
    st['now'] += TIMEOUT * 2; c = task()
    check(rd8(AUTO) == 0 and rd8(RGB) == 0 and not has(c, 'power'), 'slept while disabled')
    key(0x7e0c); check(rd8(SLPDIS) == 0, 'SLP_TOG did not re-enable')
    st['now'] += TIMEOUT * 2; task()
    check(rd8(AUTO) == 1 and rd8(RGB) == RGB_ON_SLEEP, 'no sleep after re-enable')
    st['now'] += 100; wr8(SLPDIS, 0); key(0x7e0c)             # disable while asleep
    st['now'] += TIMEOUT * 2; c = task()                       # no key, just the toggle
    check(rd8(RGB) == 0 and rd8(AUTO) == 2, 'disable-while-asleep did not wake')
    run_wake(); check(rd8(SCREEN_ON) == 1 and rd8(AUTO) == 0, 'disable-while-asleep wake failed')
    wr8(SLPDIS, 0)

    # ------------------------------------------------ SCR_TOG off keeps LEDs on the idle timer
    reset_state(); st['now'] = 0x300000; key(0x04); task()
    key(0x7e09); check(rd8(MANUAL) == 1 and rd8(SCREEN_ON) == 0, 'SCR_TOG off failed')
    st['now'] += TIMEOUT + 10; c = task()
    check(rd8(RGB) == RGB_ON_SLEEP and rd8(AUTO) == 0 and not has(c, 'power'), 'manual-off + idle wrong')
    st['now'] += 10; key(0x04); c = task()
    check(rd8(RGB) == 0 and rd8(SCREEN_ON) == 0 and rd8(AUTO) == 0, 'typing woke a manually-off screen')

    # ------------------------------------------------ suspend in the middle of a wake
    reset_state(); st['now'] = 0x400000; key(0x04); task()
    st['now'] += TIMEOUT + 10; task(); st['now'] += 10; key(0x04); task()
    for _ in range(200):
        st['now'] += 1; task()
    check(rd8(AUTO) == 2, 'setup: not waking')
    wr8(SUSP, 1); c = task()
    check(rd8(AUTO) == 1 and ('pin', PWR, 1) in c and ('pin', CS, 1) in c, 'suspend did not abort the wake')
    wr8(SUSP, 0); st['now'] += 5000
    r, c = call(H['resume'])
    check(not has(c, 'wakeup') and rd8(AUTO) == 1, 'resume used the blocking stock power-on')
    task(); ops, ms = run_wake()
    check(rd8(SCREEN_ON) == 1 and rd8(AUTO) == 0, 'wake after aborted wake failed')
    check_wake_ops(ops, 'restarted wake')

# ---------------------------------------------------- host resume (both builds)
reset_state(); st['now'] = 0x500000
wr8(SCREEN_ON, 0); wr8(SUSP, 0)                     # stock suspend powered it off
r, c = call(H['resume'])
check(not has(c, 'wakeup') and rd8(AUTO) == 1, 'resume did not queue a non-blocking wake')
task(); ops, ms = run_wake()
check(rd8(SCREEN_ON) == 1 and rd8(AUTO) == 0, 'resume wake failed')
check_wake_ops(ops, 'resume wake')

reset_state(); wr8(SCREEN_ON, 0); wr8(MANUAL, 1)
r, c = call(H['resume'])
check(c == [] and rd8(AUTO) == 0, 'resume woke a manually-off screen')

reset_state(); wr8(SCREEN_ON, 0); mu.mem_write(USB, struct.pack('<I', 2))
r, c = call(H['resume'])
check(has(c, 'wakeup'), 'MSC-mode resume should use the stock init')

# ---------------------------------------------------- SCR_TOG on/off (both builds)
reset_state(); st['now'] = 0x600000
r, c = key(0x7e09)
check(r == 0 and ('power', 0) in c and rd8(MANUAL) == 1, 'SCR_TOG on->off failed')
r, c = key(0x7e09, 0)
check(r == 0 and not has(c, 'power'), 'SCR_TOG release acted')
r, c = key(0x7e09)
check(r == 0 and ('power', 1) in c and rd8(MANUAL) == 0 and rd8(AUTO) == 0, 'SCR_TOG off->on should use the stock power-on')

if TIMEOUT:                                          # SCR_TOG on in the middle of an auto wake
    reset_state(); st['now'] = 0x680000; key(0x04); task()
    st['now'] += TIMEOUT + 10; task(); st['now'] += 10; key(0x04); task()
    for _ in range(100):
        st['now'] += 1; task()
    check(rd8(AUTO) == 2, 'setup: not waking')
    r, c = key(0x7e09)
    check(('power', 1) in c and rd8(AUTO) == 0, 'SCR_TOG during a wake should abort it and power on')
    st['now'] += 1; c = task()
    check(names(c) == ['orig_task'], 'aborted wake kept sending init commands')

reset_state(); wr8(SCREEN_ON, 0); wr8(MANUAL, 1); mu.mem_write(USB, struct.pack('<I', 2))
r, c = key(0x7e09)
check(('power', 1) in c, 'MSC-mode SCR_TOG on should use the stock power-on')
mu.mem_write(USB, bytes(4))

if not TIMEOUT:
    reset_state(); wr8(RGB, 1); st['now'] = 0x700000; key(0x04)
    st['now'] += 3600 * 1000; c = task()
    check(rd8(RGB) == 1 and rd8(AUTO) == 0 and names(c) == ['orig_task'], 'timeout=0 build slept or touched the RGB flag')

# ---------------------------------------------------- GIF next / previous
reset_state()
ANIM = 0x20012000
mu.mem_write(ANIM_S + 0x1c, struct.pack('<I', ANIM))
mu.mem_write(ANIM + 0x1446, struct.pack('<HH', 4, 0))
mu.mem_write(ANIM_S + 0x14, struct.pack('<I', 500))
def idx(): return struct.unpack('<H', mu.mem_read(ANIM + 0x1448, 2))[0]
key(0x7e0a); check(idx() == 1 and rd32(ANIM_S + 0x14) == 0, 'SCR_NXT')
key(0x7e0a, 0); check(idx() == 1, 'SCR_NXT release acted')
key(0x7e0a); key(0x7e0a); key(0x7e0a); check(idx() == 0, 'SCR_NXT wrap')
key(0x7e0b); check(idx() == 3, 'SCR_PRV wrap')
st['bad'] = {2, 1}; key(0x7e0b); check(idx() == 0, 'SCR_PRV skip broken')
st['bad'] = {0, 1, 2, 3}; r, c = key(0x7e0a); check(len([x for x in c if x[0] == 'open']) == 4, 'SCR_NXT all broken')
st['bad'] = set(); mu.mem_write(ANIM_S + 0x1c, bytes(4))
r, c = key(0x7e0a); check(c == [], 'SCR_NXT without anim')
r, c = key(0x7e0d); check(r == 1 and c == [('kb', 0x7e0d)], '0x7e0d not passed through')
r, c = key(0x7e07); check(r == 1 and c == [('kb', 0x7e07)], 'SCR_MOD not passed through')

print('timeout %d ms, stock init waits %d ms' % (TIMEOUT, STOCK_WAIT))
print('PASS: all assertions' if not fail else 'FAIL:\n  ' + '\n  '.join(fail))
sys.exit(1 if fail else 0)
