#!/usr/bin/env python3
"""Add GIF-screen auto-sleep to the Carnival TKL AMK firmware (UF2 -> UF2).

usage: patch_fw.py Carnival_TKL_v5.uf2 [-o out.uf2] [-t SECONDS]

Needs arm-none-eabi-as / arm-none-eabi-ld / arm-none-eabi-objcopy.
Only the exact v5 image is supported; every patched location is verified first.
"""
import argparse, hashlib, os, struct, subprocess, sys, tempfile

APP_BASE   = 0x08020000
PATCH_BASE = 0x0803E000          # inside the zero padding after .data (ends 0x0803D6E4)
PATCH_MAX  = 0x0803F700          # end of the original image
UF2_FAMILY = 0x57755A57          # STM32F4
SRC        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screen_sleep.S")
V5_SHA256  = "a995710d891b2805f56dc34d6113d676e1a3ea7b639731d4485254c5f596702d"

# (address, original instruction bytes, symbol in screen_sleep.S, is_bl)
SITES = [
    (0x080222F2, "00f005ba", "init_hook",   False),  # b.w 0x08022700 (screen init)
    (0x080222F6, "00f051ba", "task_hook",   False),  # b.w 0x0802279c (screen task)
    (0x0802A670, "00f075fa", "record_hook", True),   # bl  0x0802ab5e (process_record)
    (0x08027E14, "faf78bfa", "resume_hook", True),   # bl  0x0802232e (suspend_wakeup_kb)
]

def uf2_read(path):
    data = open(path, "rb").read()
    chunks = {}
    for off in range(0, len(data), 512):
        m0, m1, flags, addr, size, _, _, fam = struct.unpack_from("<8I", data, off)
        if (m0, m1) != (0x0A324655, 0x9E5D5157) or fam != UF2_FAMILY:
            sys.exit("not a STM32F4 UF2 file")
        chunks[addr] = data[off + 32: off + 32 + size]
    lo, hi = min(chunks), max(a + len(c) for a, c in chunks.items())
    img = bytearray(b"\xff" * (hi - lo))
    for a, c in chunks.items():
        img[a - lo: a - lo + len(c)] = c
    return lo, img

def uf2_write(path, base, img):
    blocks = [img[i:i + 256] for i in range(0, len(img), 256)]
    with open(path, "wb") as f:
        for n, blk in enumerate(blocks):
            hdr = struct.pack("<8I", 0x0A324655, 0x9E5D5157, 0x2000, base + n * 256,
                              256, n, len(blocks), UF2_FAMILY)
            f.write(hdr + bytes(blk).ljust(476, b"\0") + struct.pack("<I", 0x0AB16F30))

def thumb_branch(src, dst, link):
    off = dst - (src + 4)
    if off & 1 or not -(1 << 24) <= off < (1 << 24):
        raise ValueError("branch out of range")
    s = (off >> 24) & 1
    i1, i2 = (off >> 23) & 1, (off >> 22) & 1
    j1, j2 = (~i1 ^ s) & 1, (~i2 ^ s) & 1
    hw1 = 0xF000 | (s << 10) | ((off >> 12) & 0x3FF)
    hw2 = (0xD000 if link else 0x9000) | (j1 << 13) | (j2 << 11) | ((off >> 1) & 0x7FF)
    return struct.pack("<HH", hw1, hw2)

def build_patch(tmp):
    obj, elf, binf = (os.path.join(tmp, n) for n in ("p.o", "p.elf", "p.bin"))
    subprocess.check_call(["arm-none-eabi-as", "-o", obj, SRC])
    subprocess.check_call(["arm-none-eabi-ld", "-Ttext=0x%08x" % PATCH_BASE, "-e", "0",
                           "-o", elf, obj])
    subprocess.check_call(["arm-none-eabi-objcopy", "-O", "binary", "-j", ".text", elf, binf])
    syms = {}
    for line in subprocess.check_output(["arm-none-eabi-nm", elf], text=True).splitlines():
        addr, _, name = line.split()
        syms[name] = int(addr, 16)
    return open(binf, "rb").read(), syms

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("uf2")
    ap.add_argument("-o", "--out", default="Carnival_TKL_v5_screen_sleep.uf2")
    ap.add_argument("-t", "--timeout", type=int, default=300,
                    help="idle seconds before the screen sleeps (0 = never, default 300)")
    args = ap.parse_args()

    base, img = uf2_read(args.uf2)
    if base != APP_BASE:
        sys.exit("unexpected load address 0x%08x" % base)
    if hashlib.sha256(img).hexdigest() != V5_SHA256:
        sys.exit("this is not the Carnival TKL v5 image the patch was made for")

    with tempfile.TemporaryDirectory() as tmp:
        code, syms = build_patch(tmp)
    if PATCH_BASE + len(code) > PATCH_MAX:
        sys.exit("patch too large")
    p = PATCH_BASE - base
    if any(img[p:p + len(code)]):
        sys.exit("patch area is not empty")

    code = bytearray(code)
    struct.pack_into("<I", code, 0, args.timeout * 1000)
    assert code[4:8] == b"SSLP"
    img[p:p + len(code)] = code

    for addr, orig, sym, link in SITES:
        o = addr - base
        if img[o:o + 4].hex() != orig:
            sys.exit("unexpected code at 0x%08x" % addr)
        img[o:o + 4] = thumb_branch(addr, syms[sym], link)

    uf2_write(args.out, base, img)
    print("wrote %s (timeout %d s, patch %d bytes @ 0x%08x)"
          % (args.out, args.timeout, len(code), PATCH_BASE))

if __name__ == "__main__":
    main()
