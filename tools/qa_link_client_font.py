#!/usr/bin/env python3
"""QA gate: link-play client Korean font (Design A, tools/link_client_font.py).

Checks the final ROM:
  * charset table decodes to <= 59 codes with 0x8140 sentinel fill, no duplicates;
  * every live-string code is in the table; no halfwidth bytes except r w Q n k;
    NUL padding; control sequence equal to the native string;
  * live strings equal the pinned wording in link_client_font;
  * preload pages contain every label code drawn from them;
  * glyph cell non-empty for each table entry (except U+3000);
  * client program bytes outside {table, sheet, live slots, LZ77 art blocks}
    equal the original; dead copies / stage-1 headers / dead charset tables equal
    the original outside the art blocks.

Exit 0 = pass, 1 = problems, 2 = usage/input error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import link_client_font as L  # noqa: E402

DEFAULT_ORIG = os.path.join(L.BASE, 'original', 'Game Boy Wars Advance 1+2 (Japan).gba')


def check(rom, orig, codes=None):
    codes = codes or L.load_codes()
    problems = list(L.verify(rom, orig, codes))
    summary = []
    for spec in L.SPECS:
        table = L.decode_table(rom, spec)
        for item in spec.live:
            name, off, slot, _jp, ko, _src = item
            expected = L.encode(ko, codes)
            expected += bytes(slot - len(expected))
            if bytes(rom[off:off + slot]) != expected:
                problems.append(f'{spec.name} {name}: ROM slot 0x{off:06X} != pinned wording {ko!r}')
        summary.append({'image': spec.name, 'codes': len(table), 'capacity': L.MAX_CODES,
                        'live_strings': len(spec.live)})
    return problems, summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--rom', required=True)
    ap.add_argument('--orig', default=DEFAULT_ORIG)
    ap.add_argument('--json')
    args = ap.parse_args(argv)
    try:
        rom = open(args.rom, 'rb').read()
        orig = open(args.orig, 'rb').read()
    except OSError as exc:
        print(f'ERROR: {exc}')
        return 2
    if len(rom) != len(orig):
        print('ERROR: ROM size differs from original')
        return 2
    problems, summary = check(rom, orig)
    result = {'rom': os.path.abspath(args.rom), 'rom_sha256': hashlib.sha256(rom).hexdigest(),
              'images': summary, 'problems': problems, 'pass': not problems}
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=1)
    for row in summary:
        print(f"{row['image']}: {row['codes']}/{row['capacity']} codes, {row['live_strings']} live strings")
    for problem in problems:
        print('FAIL', problem)
    print('PASS' if not problems else f'FAIL ({len(problems)} problems)')
    return 0 if not problems else 1


if __name__ == '__main__':
    sys.exit(main())
