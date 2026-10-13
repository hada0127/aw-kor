#!/usr/bin/env python3
"""Find ROM->IWRAM code/data copies by matching runtime IWRAM dumps against a ROM.

Static aid for the whole-ROM Ghidra analysis (tools/ghidra/full_analysis.sh).
For every IWRAM dump (32 KiB, base 0x03000000) it looks for 32-byte, non-trivial
chunks that occur in the ROM, groups chunks with the same (iwram - rom) delta into
contiguous runs, and prints/writes the runs.  Runs are evidence that the game copied
ROM bytes into IWRAM (CpuSet/DMA/loop); the exact copy routine is not identified here.

Usage:
  find_iwram_copies.py --rom ROM --out runs.json --label p1 DUMP [DUMP...] [--label p2 DUMP...]
Bytes that differ (variables inside copied code, patched hooks) split runs; small
gaps (<= --gap bytes) are bridged.
"""
import argparse
import json
import sys
from collections import defaultdict

CH = 32


def trivial(b):
    return len(set(b)) < 6


def runs_for_dump(rom, idx, dump, gap):
    hits = []  # (iwram_off, rom_off)
    for off in range(0, len(dump) - CH + 1, 4):
        c = dump[off:off + CH]
        if trivial(c):
            continue
        locs = idx.get(c[:8])
        if not locs:
            continue
        good = [r for r in locs if rom[r:r + CH] == c]
        if len(good) == 1:  # unique ROM source only; ambiguous chunks are skipped
            hits.append((off, good[0]))
    by_delta = defaultdict(list)
    for io, ro in hits:
        by_delta[ro - io].append(io)
    runs = []
    for delta, offs in by_delta.items():
        offs.sort()
        s = e = offs[0]
        for o in offs[1:]:
            if o <= e + CH + gap:
                e = o
            else:
                runs.append((s, e + CH, delta))
                s = e = o
        runs.append((s, e + CH, delta))
    out = []
    for s, e, delta in sorted(runs):
        if e - s < 64:
            continue
        ro = s + delta
        same = sum(1 for i in range(e - s) if dump[s + i] == rom[ro + i])
        out.append({'iwram': 0x03000000 + s, 'rom': 0x08000000 + ro, 'len': e - s,
                    'byte_match': round(same / (e - s), 4)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--gap', type=int, default=64)
    ap.add_argument('items', nargs='+', help='--label NAME dump... groups (use "label=NAME")')
    a = ap.parse_args()
    rom = open(a.rom, 'rb').read()
    idx = defaultdict(list)
    for r in range(0, len(rom) - CH + 1, 2):
        k = rom[r:r + 8]
        if len(set(k)) >= 4:
            idx[k].append(r)
    groups = defaultdict(list)
    label = 'default'
    for it in a.items:
        if it.startswith('label='):
            label = it[6:]
        else:
            groups[label].append(it)
    result = {}
    for label, dumps in groups.items():
        merged = {}
        for d in dumps:
            data = open(d, 'rb').read()[:0x8000]
            for r in runs_for_dump(rom, idx, data, a.gap):
                k = (r['iwram'], r['rom'])
                if k not in merged or merged[k]['len'] < r['len']:
                    merged[k] = dict(r, dumps=[])
                merged[k].setdefault('dumps', []).append(d)
        result[label] = sorted(merged.values(), key=lambda r: r['iwram'])
        for r in result[label]:
            print(f"{label}: IWRAM {r['iwram']:08X}..{r['iwram'] + r['len']:08X} <- ROM {r['rom']:08X} "
                  f"len=0x{r['len']:X} match={r['byte_match']} dumps={len(r['dumps'])}")
    json.dump(result, open(a.out, 'w'), indent=1)


if __name__ == '__main__':
    sys.exit(main())
