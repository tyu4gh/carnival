#!/usr/bin/env python3
"""Run the patch hooks in Unicorn with the original firmware functions stubbed.
usage: emu_test.py patched.uf2   (pip install unicorn)"""
import struct,sys
from unicorn import *
from unicorn.arm_const import *
import os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import patch_fw as p
B,img=p.uf2_read(sys.argv[1])
SCREEN_ON=0x20000240; MANUAL=0x20000241; LAST=0x2000058c; USB=0x2000cb60; SUSP=0x2000cb54
STUBS={0x8027e7e:'timer_read32',0x8027e90:'timer_elapsed32',0x80227f4:'set_power',
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
def screen(): return mu.mem_read(SCREEN_ON,2)[0], mu.mem_read(MANUAL,1)[0]
def step(msg,r): print(f"{msg:45s} -> ret={r[0]} calls={r[1]} screen_on,manual_off={screen()}")
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
