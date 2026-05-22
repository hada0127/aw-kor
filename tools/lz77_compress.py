#!/usr/bin/env python3
"""GBA BIOS LZ77 (type 0x10) compressor (greedy). For reinserting edited tile data."""

def lz77_compress(data, vram_safe=True):
    n = len(data)
    out = bytearray([0x10, n & 0xFF, (n >> 8) & 0xFF, (n >> 16) & 0xFF])
    i = 0
    while i < n:
        flagpos = len(out)
        out.append(0)
        flags = 0
        for bit in range(8):
            if i >= n:
                break
            best_len = 0
            best_disp = 0
            start = max(0, i - 4096)
            maxlen = min(18, n - i)
            # vram-safe: BIOS VRAM decompressor processes 2 bytes at a time;
            # disp of 1 can corrupt. Require disp>=2 when vram_safe.
            mindisp = 2 if vram_safe else 1
            for j in range(i - mindisp, start - 1, -1):
                l = 0
                while l < maxlen and data[j + l] == data[i + l]:
                    l += 1
                if l > best_len:
                    best_len = l
                    best_disp = i - j
                    if l == maxlen:
                        break
            if best_len >= 3:
                flags |= (0x80 >> bit)
                disp = best_disp - 1
                out.append(((best_len - 3) << 4) | ((disp >> 8) & 0xF))
                out.append(disp & 0xFF)
                i += best_len
            else:
                out.append(data[i])
                i += 1
        out[flagpos] = flags
    return bytes(out)


if __name__ == '__main__':
    import sys
    sys.path.insert(0, 'tools')
    from lz77_scan import lz77_decompress
    # self-test: roundtrip a ROM block
    rom = open('original/Game Boy Wars Advance 1+2 (Japan).gba', 'rb').read()
    off = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x228AC
    dec, consumed = lz77_decompress(rom, off)
    comp = lz77_compress(dec)
    red, _ = lz77_decompress(comp, 0)
    print("orig_comp=%d  my_comp=%d  roundtrip_ok=%s" % (consumed, len(comp), red == dec))
