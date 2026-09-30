#!/usr/bin/env python3
"""Add screen keys and optional auto-sleep to the Carnival TKL AMK firmware
(UF2 -> UF2).

usage: patch_fw.py Carnival_TKL_v5.uf2 [-o out.uf2] [-t SECONDS] [--no-rgb-sleep] [--sequence]

New keys, also added to the Vial definition inside the firmware so they show up
in Vial's "User" key tab:
  SCR_TOG (0x7E09)  screen on/off
  SCR_NXT (0x7E0A)  next GIF
  SCR_PRV (0x7E0B)  previous GIF
With -t N the screen powers off and all RGB LEDs go dark after N idle seconds
(--no-rgb-sleep keeps the LEDs on); the next key press wakes both.
By default the screen now starts in "loop current GIF" mode (SCR_MOD still
switches to "play all in order"); --sequence keeps the original default.

Needs arm-none-eabi-as / arm-none-eabi-ld / arm-none-eabi-objcopy.
Only the exact v5 image is supported; every patched location is verified first.
"""
import argparse, hashlib, json, lzma, os, struct, subprocess, sys, tempfile

APP_BASE   = 0x08020000
PATCH_BASE = 0x0803E000          # inside the zero padding after .data (ends 0x0803D6E4)
VIAL_BASE  = 0x0803E200          # re-compressed Vial definition goes here
PATCH_MAX  = 0x0803F700          # end of the original image
UF2_FAMILY = 0x57755A57          # STM32F4
SRC        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screen_patch.S")
V5_SHA256  = "a995710d891b2805f56dc34d6113d676e1a3ea7b639731d4485254c5f596702d"

# (address, original instruction bytes, symbol in screen_patch.S, is_bl)
SITES = [
    (0x080222F2, "00f005ba", "init_hook",   False),  # b.w 0x08022700 (screen init)
    (0x080222F6, "00f051ba", "task_hook",   False),  # b.w 0x0802279c (screen task)
    (0x0802A670, "00f075fa", "record_hook", True),   # bl  0x0802ab5e (process_record)
    (0x08027E14, "faf78bfa", "resume_hook", True),   # bl  0x0802232e (suspend_wakeup_kb)
    (0x0802AA98, "f7f74cfc", "kb_hook",     True),   # bl  0x08022334 (process_record_kb)
]

# Vial definition (xz-compressed JSON) and the code that serves it
VIAL_DEF      = 0x0803C6CC
VIAL_DEF_LEN  = 1924
VIAL_PTR      = 0x0802CF04       # literal pool word = VIAL_DEF
VIAL_SIZE_LO  = 0x0802CD42       # movs r3, #0x84   (size & 0xff)
VIAL_SIZE_HI  = 0x0802CD46       # movs r3, #0x07   (size >> 8)
VIAL_MOVW_M1  = 0x0802CD56       # movw r1, #1923   (size - 1)
VIAL_MOVW     = 0x0802CD68       # movw r2, #1924   (size)
NEW_KEYS      = [                # appended as customKeycodes[9..] -> 0x7E09..
    {"name": "SCR_TOG", "title": "Toggle screen on/off/开关屏幕", "shortName": "Screen\nOn/Off"},
    {"name": "SCR_NXT", "title": "Next GIF/下一个动画", "shortName": "GIF\nNext"},
    {"name": "SCR_PRV", "title": "Previous GIF/上一个动画", "shortName": "GIF\nPrev"},
]

# .data initial value of the screen play mode (0 = loop current GIF, 1 = all in order)
DATA_LMA      = 0x0803D158       # load address of .data (RAM 0x20000000)
MODE_INIT     = DATA_LMA + 0x228 # anim screen struct 0x20000210 + 0x18

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

def movw(rd, imm):
    i, imm4, imm3, imm8 = (imm >> 11) & 1, imm >> 12, (imm >> 8) & 7, imm & 0xFF
    return struct.pack("<HH", 0xF240 | (i << 10) | imm4, (imm3 << 12) | (rd << 8) | imm8)

def movs(rd, imm):
    return struct.pack("<H", 0x2000 | (rd << 8) | imm)

def patch_vial(img, base):
    """Append SCR_TOG to customKeycodes and point Vial at the new definition."""
    def at(addr, n=4):
        return img[addr - base: addr - base + n]
    def put(addr, data):
        img[addr - base: addr - base + len(data)] = data

    expect = [(VIAL_PTR, struct.pack("<I", VIAL_DEF)), (VIAL_SIZE_LO, movs(3, VIAL_DEF_LEN & 0xFF)),
              (VIAL_SIZE_HI, movs(3, VIAL_DEF_LEN >> 8)), (VIAL_MOVW_M1, movw(1, VIAL_DEF_LEN - 1)),
              (VIAL_MOVW, movw(2, VIAL_DEF_LEN))]
    for addr, orig in expect:
        if at(addr, len(orig)) != orig:
            sys.exit("unexpected Vial code at 0x%08x" % addr)

    js = json.loads(lzma.decompress(bytes(at(VIAL_DEF, VIAL_DEF_LEN))))
    if len(js["customKeycodes"]) != 9:
        sys.exit("unexpected Vial customKeycodes")
    js["customKeycodes"].extend(NEW_KEYS)
    blob = lzma.compress(json.dumps(js, ensure_ascii=False, separators=(",", ":")).encode())
    if VIAL_BASE + len(blob) > PATCH_MAX or len(blob) > 0xFFFF:
        sys.exit("Vial definition too large")
    if any(at(VIAL_BASE, len(blob))):
        sys.exit("Vial area is not empty")

    put(VIAL_BASE, blob)
    put(VIAL_PTR, struct.pack("<I", VIAL_BASE))
    put(VIAL_SIZE_LO, movs(3, len(blob) & 0xFF))
    put(VIAL_SIZE_HI, movs(3, len(blob) >> 8))
    put(VIAL_MOVW_M1, movw(1, len(blob) - 1))
    put(VIAL_MOVW, movw(2, len(blob)))
    return len(blob)

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
    ap.add_argument("-o", "--out", default="Carnival_TKL_v5_screen.uf2")
    ap.add_argument("-t", "--timeout", type=int, default=0,
                    help="idle seconds before the screen sleeps (default 0 = never)")
    ap.add_argument("--no-rgb-sleep", action="store_true",
                    help="keep the RGB LEDs on when the screen auto-sleeps")
    ap.add_argument("--sequence", action="store_true",
                    help="keep the original default of playing all GIFs in order")
    args = ap.parse_args()

    base, img = uf2_read(args.uf2)
    if base != APP_BASE:
        sys.exit("unexpected load address 0x%08x" % base)
    if hashlib.sha256(img).hexdigest() != V5_SHA256:
        sys.exit("this is not the Carnival TKL v5 image the patch was made for")

    with tempfile.TemporaryDirectory() as tmp:
        code, syms = build_patch(tmp)
    if PATCH_BASE + len(code) > VIAL_BASE:
        sys.exit("patch too large")
    p = PATCH_BASE - base
    if any(img[p:p + len(code)]):
        sys.exit("patch area is not empty")

    code = bytearray(code)
    struct.pack_into("<I", code, 0, args.timeout * 1000)
    assert code[4:8] == b"SSLP"
    struct.pack_into("<I", code, 8, 0 if args.no_rgb_sleep else 1)
    img[p:p + len(code)] = code

    for addr, orig, sym, link in SITES:
        o = addr - base
        if img[o:o + 4].hex() != orig:
            sys.exit("unexpected code at 0x%08x" % addr)
        img[o:o + 4] = thumb_branch(addr, syms[sym], link)

    vial_len = patch_vial(img, base)

    o = MODE_INIT - base
    if img[o:o + 4] != struct.pack("<I", 1):
        sys.exit("unexpected screen mode initial value")
    if not args.sequence:
        img[o:o + 4] = struct.pack("<I", 0)

    uf2_write(args.out, base, img)
    print("wrote %s (timeout %d s, rgb sleep %s, code %d bytes @ 0x%08x, vial def %d bytes @ 0x%08x)"
          % (args.out, args.timeout, "off" if args.no_rgb_sleep else "on", len(code), PATCH_BASE, vial_len, VIAL_BASE))

if __name__ == "__main__":
    main()
