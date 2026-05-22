#!/usr/bin/env python3
"""Font locator / renderer for the Game Wars ROM.

Subcommands:
  scan                 -- score ROM for 1bpp-glyph-like regions, print top runs
  render OFF LEN [opts]-- render a region as a tile sheet PNG for visual inspection

render opts: --w 8 --h 8 --bpp 1 --cols 32 --out /tmp/font.png --invert

The goal is to FIND the game's font tiles by eye, then confirm glyph size.
"""
import sys
from pathlib import Path
from PIL import Image

ROM = Path('original/Game Boy Wars Advance 1+2 (Japan).gba')


def load():
    return ROM.read_bytes()


def popcount(b):
    return bin(b).count('1')


def scan(data):
    # classify each 8-byte chunk as glyph-like (1bpp 8x8 heuristic)
    glyphlike = bytearray(len(data) // 8)
    for i in range(len(glyphlike)):
        chunk = data[i*8:i*8+8]
        bits = sum(popcount(x) for x in chunk)
        # text glyphs: not empty, not full, some structure
        distinct = len(set(chunk))
        if 5 <= bits <= 45 and distinct >= 3:
            glyphlike[i] = 1
    # find runs of glyph-like chunks
    runs = []
    i = 0
    n = len(glyphlike)
    while i < n:
        if glyphlike[i]:
            j = i
            while j < n and glyphlike[j]:
                j += 1
            runs.append((i*8, (j-i)*8))  # (offset, length_bytes)
            i = j
        else:
            i += 1
    runs.sort(key=lambda r: -r[1])
    print("Top 25 glyph-like runs (offset, bytes, ~glyphs@8byte):")
    for off, length in runs[:25]:
        print(f"  0x{off:08X}  {length:8d} bytes  (~{length//8} glyphs)")


def render(data, off, length, w=8, h=8, bpp=1, cols=32, out='/tmp/font.png', invert=False):
    glyph_bytes = (w * h * bpp) // 8
    nglyphs = length // glyph_bytes
    rows = (nglyphs + cols - 1) // cols
    pad = 1
    img = Image.new('L', (cols*(w+pad)+pad, rows*(h+pad)+pad), 64)
    px = img.load()
    for g in range(nglyphs):
        gx = (g % cols) * (w+pad) + pad
        gy = (g // cols) * (h+pad) + pad
        base = off + g*glyph_bytes
        for row in range(h):
            if bpp == 1:
                rowbyte_count = w // 8
                for cb in range(rowbyte_count):
                    byte = data[base + row*rowbyte_count + cb]
                    for bit in range(8):
                        on = (byte >> (7-bit)) & 1
                        if invert:
                            on ^= 1
                        val = 255 if on else 0
                        px[gx+cb*8+bit, gy+row] = val
            elif bpp == 4:
                # 4bpp: each byte = 2 pixels (low nibble first, GBA order)
                for cb in range(w // 2):
                    byte = data[base + row*(w//2) + cb]
                    lo = byte & 0xF
                    hi = (byte >> 4) & 0xF
                    px[gx+cb*2,   gy+row] = lo * 17
                    px[gx+cb*2+1, gy+row] = hi * 17
    img = img.resize((img.width*3, img.height*3), Image.NEAREST)
    img.save(out)
    print(f"rendered {nglyphs} glyphs ({w}x{h} {bpp}bpp) from 0x{off:08X} -> {out}")


def main():
    data = load()
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]
    if cmd == 'scan':
        scan(data)
    elif cmd == 'render':
        off = int(sys.argv[2], 0); length = int(sys.argv[3], 0)
        opts = {}
        args = sys.argv[4:]
        i = 0
        while i < len(args):
            a = args[i]
            if a == '--invert':
                opts['invert'] = True; i += 1
            else:
                opts[a.lstrip('-')] = args[i+1]; i += 2
        render(data, off, length,
               w=int(opts.get('w', 8)), h=int(opts.get('h', 8)),
               bpp=int(opts.get('bpp', 1)), cols=int(opts.get('cols', 32)),
               out=opts.get('out', '/tmp/font.png'),
               invert=opts.get('invert', False))
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
