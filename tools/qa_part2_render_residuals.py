#!/usr/bin/env python3
"""Static scan of Part 2 story messages for two render defects (2026-10-07).

1. ASCII punctuation (0x21-0x2F, 0x3A-0x40, 0x5B-0x60, 0x7B-0x7E) left in a
   message payload. In the A3 dialogue consumer it renders as nothing and can
   corrupt following Hangul (Snake A30E40 「큭큭큭 ???」).
2. Fragment seams: [Hangul/！？][0x20*n][0x77+][Hangul] with no rendered space
   (몸에{20}{20}w혹시 -> "몸에혹시"). See dialogue_repoint.find_seams. Seams that
   join a word to its particle (탄약w과) are counted separately, not as defects.

Messages are reached through the native table 0xA357B4 (3315 entries) via the
pointer in the scanned ROM, so relocated copies are what is checked. Scope is
the original target being inside dialogue_regions.PART2_STORY_RANGES.
Static bytes only: this does not prove pixels on screen.

Exit 1 if ASCII punctuation remains in the CO quote or system prompt ranges.
"""
import argparse
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dialogue_regions import (PART2_CO_QUOTE_RANGE, PART2_STORY_RANGES,
                              PART2_SYSTEM_PROMPT_RANGE, is_part2_story_address)
from dialogue_repoint import _tokens, find_seams, seam_is_bound, source_context

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGINAL = os.path.join(BASE, 'original', 'Game Boy Wars Advance 1+2 (Japan).gba')
SYLCODE = os.path.join(BASE, 'data', 'syllable_to_code_2350.json')
TABLE, COUNT = 0xA357B4, 3315


def is_ascii_punct(b):
    return 0x21 <= b <= 0x2F or 0x3A <= b <= 0x40 or 0x5B <= b <= 0x60 or 0x7B <= b <= 0x7E


def region_name(addr):
    if PART2_CO_QUOTE_RANGE[0] <= addr < PART2_CO_QUOTE_RANGE[1]:
        return 'co_quote'
    if PART2_SYSTEM_PROMPT_RANGE[0] <= addr < PART2_SYSTEM_PROMPT_RANGE[1]:
        return 'system_prompt'
    return 'story_other'


def scan(rom, orig, hangul):
    out = {'messages': 0, 'ascii_punct': {}, 'seams': {}, 'details': []}
    seen = set()
    for i in range(COUNT):
        ptr = TABLE + 4 * i
        src = struct.unpack_from('<I', orig, ptr)[0] - 0x08000000
        if src in seen or not is_part2_story_address(src):
            continue
        seen.add(src)
        cur = struct.unpack_from('<I', rom, ptr)[0] - 0x08000000
        end = rom.find(b'\x00', cur)
        payload = rom[cur:end]
        region = region_name(src)
        out['messages'] += 1
        punct = [payload[o] for o, n in _tokens(payload) if n == 1 and is_ascii_punct(payload[o])]
        org_end = orig.find(b'\x00', src)
        source = orig[src:org_end]
        seams = []
        for seam in find_seams(payload, hangul):
            bound = seam_is_bound(seam, *source_context(source, payload, seam))
            if bound:
                out['bound_seams'] = out.get('bound_seams', 0) + 1
                continue
            if bound is None:
                out['unaligned_seams'] = out.get('unaligned_seams', 0) + 1
            seams.append(seam)
        if punct:
            out['ascii_punct'][region] = out['ascii_punct'].get(region, 0) + 1
        if seams:
            out['seams'][region] = out['seams'].get(region, 0) + len(seams)
        if punct or seams:
            out['details'].append({'msg': f'0x{src:08X}', 'at': f'0x{cur:08X}', 'region': region,
                                   'ascii_punct': bytes(punct).decode('ascii'),
                                   'seams': [{'at': f'0x{cur + s["glyph_end"]:08X}', 'pads': s['pads'],
                                              'row_half_cells': s['row_half_cells']} for s in seams]})
    out['ascii_punct_messages'] = sum(out['ascii_punct'].values())
    out['seam_total'] = sum(out['seams'].values())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rom', default=os.path.join(BASE, 'output', 'game_wars_korean_full.gba'))
    ap.add_argument('--json', help='write details here')
    args = ap.parse_args()
    rom = open(args.rom, 'rb').read()
    orig = open(ORIGINAL, 'rb').read()
    hangul = {int(v, 16): k for k, v in json.load(open(SYLCODE, encoding='utf-8')).items()}
    result = scan(rom, orig, hangul)
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"messages={result['messages']} ranges={[(hex(a), hex(b)) for a, b in PART2_STORY_RANGES]}")
    print(f"ascii_punct messages by region: {result['ascii_punct']}")
    print(f"unrendered fragment seams by region: {result['seams']} (total {result['seam_total']}, "
          f"of which source-unaligned {result.get('unaligned_seams', 0)}); "
          f"particle-bound seams left joined: {result.get('bound_seams', 0)}")
    bad = result['ascii_punct'].get('co_quote', 0) + result['ascii_punct'].get('system_prompt', 0)
    print('RESULT:', 'FAIL' if bad else 'PASS', '(CO quote / system prompt ASCII punctuation)')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
