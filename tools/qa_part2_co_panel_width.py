#!/usr/bin/env python3
"""Count visible SJIS cells in all Part 2 CO profile pages.

The 0x08385E30 consumer selects four 16-bit message indices per CO from
0xA3C074; the indices address the native 0xA357B4 message pointer table.
0x72 advances a row and 0x20 is non-drawing padding in this consumer.
"""
import argparse
from collections import Counter
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CO_TABLE = 0xA3C074
MESSAGE_TABLE = 0xA357B4
CO_COUNT = 19
PAGES = 4
LIMIT = 13


def census(rom):
    rows = []
    for co in range(CO_COUNT):
        for page in range(PAGES):
            index = struct.unpack_from('<H', rom, CO_TABLE + 2 * (co * PAGES + page))[0]
            if index != 2421 + co * PAGES + page:
                raise ValueError(f'CO {co} page {page}: unexpected message index {index}')
            pointer = struct.unpack_from('<I', rom, MESSAGE_TABLE + 4 * index)[0]
            address = pointer - 0x08000000
            if not 0 <= address < len(rom):
                raise ValueError(f'CO {co} page {page}: pointer outside ROM')
            end = rom.find(b'\x00', address, min(address + 512, len(rom)))
            if end < 0:
                raise ValueError(f'CO {co} page {page}: missing bounded terminator')
            row = 0
            width = 0
            pos = address
            while pos < end:
                lead = rom[pos]
                if 0x81 <= lead <= 0x9F or 0xE0 <= lead <= 0xFC:
                    if pos + 1 >= end or not (0x40 <= rom[pos + 1] <= 0xFC) or rom[pos + 1] == 0x7F:
                        raise ValueError(f'CO {co} page {page}: invalid SJIS pair at {pos:#x}')
                    width += 1
                    pos += 2
                elif lead == 0x72:
                    rows.append(dict(co=co, page=page, row=row, cells=width, address=f'0x{address:06X}'))
                    row += 1
                    width = 0
                    pos += 1
                elif lead == 0x20:
                    pos += 1
                else:
                    raise ValueError(f'CO {co} page {page}: unsupported control {lead:#x} at {pos:#x}')
            rows.append(dict(co=co, page=page, row=row, cells=width, address=f'0x{address:06X}'))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rom', default=str(ROOT / 'output/game_wars_korean_full.gba'))
    parser.add_argument('--report', default=str(ROOT / 'temp/part2_co_panel_width.json'))
    args = parser.parse_args()
    rows = census(Path(args.rom).read_bytes())
    overflow = [row for row in rows if row['cells'] > LIMIT]
    page_rows = Counter((row['co'], row['page']) for row in rows)
    clipped_pages = [dict(co=co, page=page, rows=count)
                     for (co, page), count in sorted(page_rows.items()) if count > 6]
    report = dict(rom=args.rom, pages=CO_COUNT * PAGES, rows=len(rows), limit=LIMIT,
                  overflows=overflow, clipped_pages=clipped_pages)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Part 2 CO panels: {report["pages"]} pages, {len(rows)} rows, '
          f'{len(overflow)} rows over {LIMIT} cells')
    for row in overflow:
        print(f'  CO {row["co"]} page {row["page"]} row {row["row"]}: '
              f'{row["cells"]} cells at {row["address"]}')
    for page in clipped_pages:
        print(f'  CO {page["co"]} page {page["page"]}: '
              f'{page["rows"]} rows exceed six visible panel rows')
    return bool(overflow or clipped_pages)


if __name__ == '__main__':
    raise SystemExit(main())
