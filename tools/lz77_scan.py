#!/usr/bin/env python3
"""Scan a GBA ROM for BIOS LZ77 (type 0x10) compressed blocks and decompress.

Subcommands:
  scan                          -- find valid LZ77 blocks, print candidates (font-sized)
  decompress OFF OUT            -- decompress block at OFF to OUT (raw bin)
  render OFF OUT [cols]         -- decompress block at OFF, render as 8x8 4bpp tile sheet PNG
"""
import sys
from pathlib import Path

ROM = Path('original/Game Boy Wars Advance 1+2 (Japan).gba')


def lz77_decompress(data, off, max_out=0x200000):
    """Decompress GBA LZ77 (0x10) starting at off. Returns (bytes, consumed) or None."""
    if off + 4 > len(data) or data[off] != 0x10:
        return None
    size = data[off+1] | (data[off+2] << 8) | (data[off+3] << 16)
    if size == 0 or size > max_out:
        return None
    out = bytearray()
    p = off + 4
    try:
        while len(out) < size:
            if p >= len(data):
                return None
            flags = data[p]; p += 1
            for bit in range(8):
                if len(out) >= size:
                    break
                if flags & (0x80 >> bit):
                    if p + 1 >= len(data):
                        return None
                    b0 = data[p]; b1 = data[p+1]; p += 2
                    length = (b0 >> 4) + 3
                    disp = (((b0 & 0xF) << 8) | b1) + 1
                    if disp > len(out):
                        return None  # invalid backref
                    for _ in range(length):
                        if len(out) >= size:
                            break
                        out.append(out[len(out) - disp])
                else:
                    out.append(data[p]); p += 1
    except IndexError:
        return None
    if len(out) != size:
        return None
    return bytes(out), p - off


def scan(data):
    print("Scanning for valid LZ77 blocks (4-byte aligned, font-plausible)...")
    cands = []
    for off in range(0, len(data) - 4, 4):
        if data[off] != 0x10:
            continue
        size = data[off+1] | (data[off+2] << 8) | (data[off+3] << 16)
        # font-plausible: multiple of 32 (whole 4bpp tiles), reasonable range
        if size < 0x800 or size > 0x40000 or size % 32 != 0:
            continue
        res = lz77_decompress(data, off)
        if res is None:
            continue
        out, consumed = res
        # tile diversity heuristic: count distinct 32-byte tiles, and non-blank ratio
        ntiles = len(out) // 32
        distinct = len(set(out[i*32:i*32+32] for i in range(ntiles)))
        nonblank = sum(1 for i in range(ntiles) if any(out[i*32:i*32+32]))
        cands.append((off, size, ntiles, distinct, nonblank, consumed))
    cands.sort(key=lambda c: -c[2])
    print(f"valid font-plausible LZ77 blocks: {len(cands)}")
    print(f"{'ROM off':>10} {'usize':>8} {'tiles':>6} {'distinct':>8} {'nonblank':>8} {'csize':>7}")
    for off, size, nt, dist, nb, cons in cands[:40]:
        print(f"0x{off:08X} {size:8d} {nt:6d} {dist:8d} {nb:8d} {cons:7d}")


def render(data, off, out, cols=32):
    from PIL import Image
    res = lz77_decompress(data, off)
    if res is None:
        print("not a valid LZ77 block at", hex(off)); return
    tiles, _ = res
    n = len(tiles) // 32
    rows = (n + cols - 1) // cols
    img = Image.new('L', (cols*9+1, rows*9+1), 48); px = img.load()
    for t in range(n):
        gx = (t % cols)*9+1; gy = (t // cols)*9+1; base = t*32
        for row in range(8):
            for col in range(8):
                byte = tiles[base + row*4 + col//2]
                v = (byte & 0xF) if col % 2 == 0 else (byte >> 4)
                px[gx+col, gy+row] = v*17
    img = img.resize((img.width*2, img.height*2), Image.NEAREST)
    img.save(out)
    print(f"decompressed {len(tiles)} bytes ({n} tiles) from 0x{off:08X} -> {out}")


def main():
    data = ROM.read_bytes()
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]
    if cmd == 'scan':
        scan(data)
    elif cmd == 'decompress':
        res = lz77_decompress(data, int(sys.argv[2], 0))
        if res:
            Path(sys.argv[3]).write_bytes(res[0]); print("wrote", len(res[0]), "bytes")
        else:
            print("invalid block")
    elif cmd == 'render':
        render(data, int(sys.argv[2], 0), sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 32)
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
