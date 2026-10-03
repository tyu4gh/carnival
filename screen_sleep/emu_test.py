#!/usr/bin/env python3
"""Run the patch hooks in Unicorn with the original firmware functions stubbed.
usage: emu_test.py patched.uf2   (pip install unicorn)"""
import struct,sys
from unicorn import *
from unicorn.arm_const import *
import os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import patch_fw as p
B,img=p.uf2_read(sys.argv[1])
SCREEN_ON=0x20000240; MANUAL=0x20000241; AUTO=0x20000242; SLPDIS=0x20000243; LAST=0x2000058c; USB=0x2000cb60; SUSP=0x2000cb54; RGB=0x200090b8
STUBS={0x8027e7e:'timer_read32',0x8027e90:'timer_elapsed32',0x80227f4:'set_power',
       0x8026f04:'anim_close',0x8026f18:'anim_open',0x8020944:'memset',0x8022968:'lcd_fill',
       0x8022700:'orig_init',0x802279c:'orig_task',0x8022334:'orig_kb',0x802232e:'orig_wakeup',0x802ab5e:'orig_record'}
RET=0x08000100
st={'now':0,'calls':[]}
mu=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
mu.mem_map(0x08000000,0x80000); mu.mem_write(B,bytes(img))
mu.mem_write(RET,b'\xfe\xe7')
mu.mem_map(0x20000000,0x20000)
# .data init like startup code
mu.mem_write(0x20000000,bytes(img[0x803d158-B:0x803d158-B+0x58c]))
mu.mem_write(LAST,b'\xa5\xa5\xa5\xa5')  # garbage padding at power-on
mu.mem_write(0x20000230,struct.pack('<II',0x20013000,0x8000))  # screen obj buf,size
def hook(uc,addr,size,_):
    if addr in STUBS:
        n=STUBS[addr]; r0=uc.reg_read(UC_ARM_REG_R0)
        if n=='timer_read32': uc.reg_write(UC_ARM_REG_R0,st['now'])
        elif n=='timer_elapsed32': uc.reg_write(UC_ARM_REG_R0,(st['now']-r0)&0xffffffff)
        elif n=='set_power':
            cur=uc.mem_read(SCREEN_ON,1)[0]
            if cur!=r0: uc.mem_write(SCREEN_ON,bytes([r0])); st['calls'].append(('power',r0))
        elif n=='orig_wakeup':
            st['calls'].append(('wakeup',)); uc.mem_write(SCREEN_ON,b'\x01')
        elif n=='memset':
            # record black-fill of the screen buffer; leave r0 (dst) as return
            st['calls'].append(('memset',hex(r0)))
        elif n=='lcd_fill': st['calls'].append(('blank',))
        elif n=='anim_close': st['calls'].append(('close',hex(r0)))
        elif n=='anim_open':
            idx=struct.unpack('<H',uc.mem_read(r0+0x1448,2))[0]
            ok=idx not in st.get('bad',())
            st['calls'].append(('open',idx,ok)); uc.reg_write(UC_ARM_REG_R0,int(ok))
        elif n=='orig_kb': st['calls'].append(('kb',hex(r0))); uc.reg_write(UC_ARM_REG_R0,1)
        else: st['calls'].append((n,))
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
mu.hook_add(UC_HOOK_CODE,hook)
def call(addr,*args):
    for r,v in zip([UC_ARM_REG_R0,UC_ARM_REG_R1],args): mu.reg_write(r,v)
    mu.reg_write(UC_ARM_REG_SP,0x2001ff00); mu.reg_write(UC_ARM_REG_LR,RET|1)
    st['calls']=[]
    mu.emu_start(addr|1,RET,count=2000)
    return mu.reg_read(UC_ARM_REG_R0),st['calls']
REC=0x20010000
def key(code,pressed):
    mu.mem_write(REC,struct.pack('<HBBBxxx',0,0,0,0)); mu.mem_write(REC+5,bytes([pressed]))
    call(p_sym('record_hook'),REC)
    return call(p_sym('kb_hook'),code,REC)
import subprocess,re
syms={}
# find hooks from branch sites
def dest(site):
    hw1,hw2=struct.unpack_from('<HH',img,site-B)
    s=(hw1>>10)&1; imm10=hw1&0x3ff; j1=(hw2>>13)&1; j2=(hw2>>11)&1; imm11=hw2&0x7ff
    i1=1-(j1^s); i2=1-(j2^s)
    off=(s<<24)|(i1<<23)|(i2<<22)|(imm10<<12)|(imm11<<1)
    if s: off-=1<<25
    return site+4+off
S={'init_hook':dest(0x80222f2),'task_hook':dest(0x80222f6),'record_hook':dest(0x802a670),'resume_hook':dest(0x8027e14),'kb_hook':dest(0x802aa98)}
p_sym=lambda n:S[n]
def screen(): return mu.mem_read(SCREEN_ON,1)[0], mu.mem_read(MANUAL,1)[0], mu.mem_read(AUTO,1)[0], mu.mem_read(RGB,1)[0]
def step(msg,r): print(f"{msg:46s} -> calls={str(r[1]):42s} on,man,auto,rgb={screen()}")
st['now']=1000; step('boot init_hook',call(S['init_hook']))
st['now']=2000; step('task (active)',call(S['task_hook']))
st['now']=5000; step('normal key A press',key(0x04,1))
st['now']=299000+5000; step('task at 299s idle',call(S['task_hook']))
st['now']=301000+5000; step('task at 301s idle',call(S['task_hook']))
st['now']=400000; step('key A press (wake)',key(0x04,1))
st['now']=400010; step('task',call(S['task_hook']))
st['now']=500000; step('SCR_TOG press (off)',key(0x7e09,1))
st['now']=500100; step('SCR_TOG release',key(0x7e09,0))
st['now']=500200; step('key A press',key(0x04,1))
st['now']=500300; step('task',call(S['task_hook']))
mu.mem_write(SUSP,b'\x00'); st['now']=600000; step('host resume (manual off)',call(S['resume_hook']))
st['now']=700000; step('SCR_TOG press (on)',key(0x7e09,1))
st['now']=700100; step('task',call(S['task_hook']))
st['now']=800000; step('host resume (manual on)',call(S['resume_hook']))
st['now']=0xfffffff0; step('SCR_MOD 0x7e07 passes through',key(0x7e07,1))
st['now']=0x00000100; step('task after 32-bit timer wrap',call(S['task_hook']))

# ---- RGB sleep follows the idle timer, independent of SCR_TOG ----
st['now']=0x1000; key(0x04,1); call(S['task_hook'])
st['now']=0x1000+10000; step('SCR_TOG off while active',key(0x7e09,1))
st['now']=0x1000+400000; step('idle > timeout, screen manually off',call(S['task_hook']))
st['now']=0x1000+400100; step('key press',key(0x04,1))
st['now']=0x1000+400200; step('task: LEDs back, screen stays off',call(S['task_hook']))
st['now']=0x1000+400300; key(0x7e09,1)
st['now']=0x1000+900000; step('idle again',call(S['task_hook']))
mu.mem_write(SUSP,b'\x01'); mu.mem_write(RGB,b'\x01')
st['now']=0x1000+900100; step('USB suspended: hook leaves LED flag alone',key(0x04,1)); call(S['task_hook'])
mu.mem_write(SUSP,b'\x00'); mu.mem_write(RGB,b'\x00'); step('host resume (firmware clears flag)',call(S['resume_hook']))
st['now']=0x1000+900200; step('task after resume',call(S['task_hook']))
mu.mem_write(USB,struct.pack('<I',2)); mu.mem_write(RGB,b'\x00')
st['now']=0x1000+2000000; step('MSC mode + idle: untouched',call(S['task_hook']))
mu.mem_write(USB,b'\0\0\0\0')

# ---- GIF next / previous ----
ANIM_S=0x20000210; ANIM=0x20012000
print('boot play mode (0=loop current, 1=all in order):', struct.unpack('<I',mu.mem_read(ANIM_S+0x18,4))[0])
def anim_state(): return struct.unpack('<HH',mu.mem_read(ANIM+0x1446,4)), struct.unpack('<I',mu.mem_read(ANIM_S+0x14,4))[0]
mu.mem_write(ANIM_S+0x1c,struct.pack('<I',ANIM))
mu.mem_write(ANIM+0x1446,struct.pack('<HH',4,0))   # 4 files, index 0
mu.mem_write(ANIM_S+0x14,struct.pack('<I',500))
def step2(msg,r): print(f"{msg:45s} -> ret={r[0]} calls={r[1]} (count,index),delay={anim_state()}")
step2('SCR_NXT press',key(0x7e0a,1))
step2('SCR_NXT release (ignored)',key(0x7e0a,0))
step2('SCR_NXT x2',key(0x7e0a,1)); step2('',key(0x7e0a,1))
step2('SCR_NXT wraps 3 -> 0',key(0x7e0a,1))
step2('SCR_PRV wraps 0 -> 3',key(0x7e0b,1))
st['bad']={2,1}
step2('SCR_PRV skips broken files 2,1 -> 0',key(0x7e0b,1))
st['bad']={0,1,2,3}
step2('SCR_NXT all broken: gives up',key(0x7e0a,1))
st['bad']=set()
mu.mem_write(ANIM_S+0x1c,b'\0\0\0\0')
step2('SCR_NXT with no anim (MSC mode)',key(0x7e0a,1))
step2('key 0x7e0d passes through',key(0x7e0d,1))


# ================= auto-sleep must NOT power-cycle the panel =================
def only(calls,*names):
    got=[c[0] for c in calls]; return got==list(names)
def has(calls,name): return any(c[0]==name for c in calls)

import sys
fail=[]
# fresh state
for a in (SCREEN_ON,): mu.mem_write(a,b'\x01')
mu.mem_write(MANUAL,b'\x00'); mu.mem_write(AUTO,b'\x00'); mu.mem_write(SUSP,b'\x00'); mu.mem_write(USB,b'\x00\x00\x00\x00'); mu.mem_write(RGB,b'\x00'); mu.mem_write(SLPDIS,b'\x00')
st['now']=0x5000; key(0x04,1)                       # activity
st['now']=0x5000+100; _,c=call(S['task_hook'])      # active
if has(c,'power') or has(c,'blank'): fail.append('active frame touched panel')
st['now']=0x5000+400000; _,c=call(S['task_hook'])   # idle -> sleep
if not has(c,'blank'): fail.append('sleep did not blank')
if has(c,'power'): fail.append('sleep power-cycled panel')
if has(c,'orig_task'): fail.append('sleep still ran screen_task')
if mu.mem_read(AUTO,1)[0]!=1: fail.append('AUTO not set')
if mu.mem_read(RGB,1)[0]!=1: fail.append('RGB not slept')
st['now']=0x5000+400100; _,c=call(S['task_hook'])   # still idle -> stay asleep, no re-blank
if has(c,'blank') or has(c,'power'): fail.append('re-blanked while asleep')
# THE FIX: typing wakes without any panel power/init, and resumes refresh
st['now']=0x5000+500000; key(0x04,1)                # type -> activity
_,c=call(S['task_hook'])
if has(c,'power'): fail.append('WAKE power-cycled panel (the bug)')
if not has(c,'orig_task'): fail.append('wake did not resume screen_task')
if mu.mem_read(AUTO,1)[0]!=0: fail.append('AUTO not cleared on wake')
if mu.mem_read(RGB,1)[0]!=0: fail.append('RGB not woken')

# ================= SLP_TOG: enable/disable auto-sleep at runtime =================
# default: sleep enabled (SLPDIS byte 0)
if mu.mem_read(SLPDIS,1)[0]!=0: fail.append('SLP default not enabled')
# press SLP_TOG -> disables auto-sleep
st['now']=0x9000; key(0x7e0c,1)
if mu.mem_read(SLPDIS,1)[0]!=1: fail.append('SLP_TOG did not disable')
# now go idle past timeout: must NOT sleep
mu.mem_write(AUTO,b'\x00'); mu.mem_write(RGB,b'\x00'); mu.mem_write(SCREEN_ON,b'\x01')
st['now']=0x9000+400000; _,c=call(S['task_hook'])
if has(c,'blank'): fail.append('slept while disabled')
if mu.mem_read(AUTO,1)[0]!=0: fail.append('AUTO set while disabled')
if mu.mem_read(RGB,1)[0]!=0: fail.append('RGB slept while disabled')
if not has(c,'orig_task'): fail.append('no refresh while disabled')
# disable WHILE already asleep -> next tick wakes everything, no power-cycle
mu.mem_write(SLPDIS,b'\x00')                        # re-enable
st['now']=0xA000; key(0x04,1); call(S['task_hook'])  # active baseline
st['now']=0xA000+400000; call(S['task_hook'])        # sleep
if mu.mem_read(AUTO,1)[0]!=1 or mu.mem_read(RGB,1)[0]!=1: fail.append('did not sleep before disable test')
st['now']=0xA000+400100; key(0x7e0c,1)               # disable while asleep
_,c=call(S['task_hook'])
if has(c,'power'): fail.append('disable-while-asleep power-cycled panel')
if mu.mem_read(AUTO,1)[0]!=0: fail.append('disable-while-asleep did not resume GIF')
if mu.mem_read(RGB,1)[0]!=0: fail.append('disable-while-asleep did not wake RGB')
if not has(c,'orig_task'): fail.append('disable-while-asleep did not refresh')
# re-enable -> sleep works again
st['now']=0xB000; key(0x7e0c,1)                      # enable
if mu.mem_read(SLPDIS,1)[0]!=0: fail.append('re-enable failed')
st['now']=0xB000+100; key(0x04,1); call(S['task_hook'])
st['now']=0xB000+400000; _,c=call(S['task_hook'])
if not has(c,'blank'): fail.append('does not sleep after re-enable')

print('\n==== fix assertions ====')
print('PASS: all sleep/wake/toggle assertions' if not fail else 'FAIL: '+'; '.join(fail))
sys.exit(1 if fail else 0)
