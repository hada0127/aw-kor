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


def lz77_compress_optimal(data, vram_safe=True):
    """Size-oriented GBA LZ77 compressor.

    This keeps the same 0x10 format as lz77_compress(), but uses dynamic
    programming so tight original blocks can be reinserted after small edits.
    """
    n = len(data)

    def best_match(i):
        best_len = 0
        best_disp = 0
        start = max(0, i - 4096)
        maxlen = min(18, n - i)
        mindisp = 2 if vram_safe else 1
        for j in range(i - mindisp, start - 1, -1):
            length = 0
            while length < maxlen and data[j + length] == data[i + length]:
                length += 1
            if length > best_len:
                best_len = length
                best_disp = i - j
                if length == maxlen:
                    break
        return best_len, best_disp

    matches = [best_match(i) for i in range(n)]
    inf = 10 ** 9
    dp = [[inf] * 8 for _ in range(n + 1)]
    choice = [[None] * 8 for _ in range(n + 1)]
    for pending in range(8):
        dp[n][pending] = 0

    for i in range(n - 1, -1, -1):
        best_len, best_disp = matches[i]
        for pending in range(8):
            flag_cost = 1 if pending == 0 else 0
            next_pending = (pending + 1) & 7
            best_cost = flag_cost + 1 + dp[i + 1][next_pending]
            best_choice = ('lit', data[i])
            if best_len >= 3:
                for length in range(3, best_len + 1):
                    cost = flag_cost + 2 + dp[i + length][next_pending]
                    if cost < best_cost:
                        best_cost = cost
                        best_choice = ('match', length, best_disp)
            dp[i][pending] = best_cost
            choice[i][pending] = best_choice

    out = bytearray([0x10, n & 0xFF, (n >> 8) & 0xFF, (n >> 16) & 0xFF])
    i = 0
    pending = 0
    bit = 0
    flags = 0
    flagpos = None
    while i < n:
        if pending == 0:
            flagpos = len(out)
            out.append(0)
            flags = 0
            bit = 0
        item = choice[i][pending]
        if item[0] == 'lit':
            out.append(item[1])
            i += 1
        else:
            _kind, length, disp = item
            flags |= 0x80 >> bit
            packed_disp = disp - 1
            out.append(((length - 3) << 4) | ((packed_disp >> 8) & 0x0F))
            out.append(packed_disp & 0xFF)
            i += length
        bit += 1
        pending = (pending + 1) & 7
        if pending == 0:
            out[flagpos] = flags
    if pending != 0:
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
