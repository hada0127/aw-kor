#!/usr/bin/env python3
"""Pins for review5 (candidate5 -> candidate6) static findings.

1. BATTLE INFO header: its second 32x8 OBJ is [0xBE973C x3, 0xBE979C], so the
   4th tile of that OBJ is BATTLE tile 0 (0xBE979C).  The Korean 전투 label is
   right aligned, so that tile must stay fully transparent or a stray piece of
   the BATTLE label appears after 정보.
2. Campaign clear-banner sheet 0xC43400, first consumer (load 0x08B6D56C ->
   OBJ tile 489, screen init 0x08B6D4F0..):
   - the only sprite draw of the sheet base there is 0x08B6D634: frame
     0x08EC1A68 (5 x 16x8 OBJ = 80 px, tiles +0..+9) at tile 489 (CAMPAIGN
     RANK strip) or 505 (+0x10, H.CAMPAIGN RANK strip);
   - 0x08B6D59A then loads the cursor graphics to OBJ tile 559
     (0x08B4A588 -> 0x08B4A4D0, 0x06010000 + 559*0x20), overwriting sheet
     tiles 70.. (kana cells 2..).  The kana cells of this load are therefore
     not drawn by this screen; the Korean strips must fit the 80 px frame.
3. Link status rows (Part 1, table 0xB831E0, consumer 0x08B332C0): the field
   at x=14 is cleared 8 tiles wide x 2 tall (0x08B10E34 call at 0x08B33304)
   and the compact drawer 0x08B1311C writes one 8x16 cell per character
   (strh at +0 / +0x40).  Every row must fit 8 cells; the B-team 준비 중 stays
   unchanged.

Optional built-ROM checks: REVIEW5_ROM=<built rom> python3 tools/test_review5_pins.py
"""
import json
import os
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import part1_campaign_clear_banner as banner  # noqa: E402
import part1_obj_header_labels as header  # noqa: E402
from lz77_scan import lz77_decompress  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL = ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba'
BATTLE_TILE0 = 0xBE979C
FRAME = 0xEC1A68
STRIP_FIELD_TILES = 10
LINK_TABLE, LINK_ENTRIES, LINK_FIELD_CELLS = 0xB831E0, 5, 8


def _u16(rom, a):
    return struct.unpack_from('<H', rom, a)[0]


def _u32(rom, a):
    return struct.unpack_from('<I', rom, a)[0]


def _pixels(raw, tiles):
    return [[(raw[(x // 8) * 32 + y * 4 + (x % 8) // 2] >> (4 * (x % 2))) & 15
             for x in range(tiles * 8)] for y in range(8)]


def _sheet(rom):
    data = lz77_decompress(rom, banner.SOURCE)
    return data[0] if isinstance(data, tuple) else data


def _strip_max_x(sheet, first_tile):
    xs = [x for row in _pixels(bytes(sheet[first_tile * 32:(first_tile + 16) * 32]), 16)
          for x, v in enumerate(row) if v]
    return max(xs) if xs else -1


def _sjis_cells(rom, address, limit=32):
    cells, i = 0, address
    while i < address + limit:
        b = rom[i]
        if b == 0:
            return cells
        i += 2 if (0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC) else 1
        cells += 1
    raise AssertionError(f'unterminated row at 0x{address:X}')


class OriginalRomFacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = ORIGINAL.read_bytes()

    def test_battle_info_second_obj_reaches_battle_tile0(self):
        # Shared INFO piece (3 tiles) is immediately followed by BATTLE tile 0.
        self.assertEqual(BATTLE_TILE0, 0xBE973C + 3 * 32)
        labels = {row[0]: row for row in header.LABELS}
        self.assertEqual(labels[0xBE973C][1], 3)
        self.assertEqual(labels[BATTLE_TILE0][3], 'right')

    def test_strip_consumer_draws_80px_from_tile_489_or_505(self):
        rom = self.original
        self.assertEqual(_u32(rom, 0xB6D61C), 0x08C43400)      # load source (0x08B6D56C)
        self.assertEqual(_u32(rom, 0xB6D620), 0x06013D20)      # -> OBJ tile 489
        self.assertEqual(_u32(rom, 0xB6D6D4), 0x08EC1A68)      # frame literal (0x08B6D648)
        self.assertEqual(_u32(rom, 0xB6D6D8), 0x1E9)           # tile literal  (0x08B6D64A)
        self.assertEqual(_u16(rom, 0xB6D650), 0x3310)          # adds r3, #0x10 -> 505
        count = _u16(rom, FRAME)
        self.assertEqual(count, 5)
        width, tiles = 0, 0
        for i in range(count):
            attr0, attr1, off = struct.unpack_from('<HHH', rom, FRAME + 2 + 6 * i)
            self.assertEqual(attr0 & 0xC000, 0x4000)           # horizontal
            self.assertEqual(attr1 & 0xC000, 0)                # size 0 -> 16x8
            self.assertEqual(off, 2 * i)
            width = max(width, (attr1 & 0x1FF) + 16)
            tiles = max(tiles, off + 2)
        self.assertEqual((width, tiles), (80, STRIP_FIELD_TILES))

    def test_cursor_load_overwrites_kana_cells_of_first_load(self):
        rom = self.original
        self.assertEqual(_u32(rom, 0xB6D62C), 0x22F)           # r4 literal at 0x08B6D592
        self.assertEqual(_u32(rom, 0xB4A540), 0x06010000)      # 0x08B4A4D0: 0x06010000 + tile*0x20
        first_cursor_sheet_tile = 0x22F - 489
        self.assertEqual(first_cursor_sheet_tile, 70)
        self.assertLess(banner.CELL_BASE_TILE, first_cursor_sheet_tile)

    def test_link_field_is_8_cells(self):
        rom = self.original
        self.assertEqual(_u32(rom, 0xB33350), 0x08000000 + LINK_TABLE)
        self.assertEqual(_u16(rom, 0xB33300), 0x210E)          # movs r1, #0xe   (x)
        self.assertEqual(_u16(rom, 0xB33302), 0x2308)          # movs r3, #8     (width)
        self.assertEqual(_u16(rom, 0xB332F4), 0x2002)          # movs r0, #2     (height)
        self.assertEqual(_u16(rom, 0xB33344), 0x200E)          # movs r0, #0xe   (draw x)
        widest = max(_sjis_cells(rom, _u32(rom, LINK_TABLE + 4 * i) - 0x08000000)
                     for i in range(LINK_ENTRIES))
        self.assertEqual(widest, 5)                            # 接続エラー
        self.assertLessEqual(widest, LINK_FIELD_CELLS)


class PatchedOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = ORIGINAL.read_bytes()

    def test_battle_tile0_transparent_after_header_patch(self):
        rom = bytearray(self.original)
        header.patch(rom, self.original)
        self.assertEqual(bytes(rom[BATTLE_TILE0:BATTLE_TILE0 + 32]), bytes(32))
        rendered = header.render(4, '전투', 'right')
        self.assertTrue(all(v == 0 for row in _pixels(rendered, 4) for v in row[:8]))

    def test_banner_strips_fit_first_consumer_frame(self):
        sheet = banner.sheet(self.original)
        for first, *_ in banner.RANK_STRIPS:
            self.assertLess(_strip_max_x(sheet, first), STRIP_FIELD_TILES * 8, first)


@unittest.skipUnless(os.environ.get('REVIEW5_ROM'), 'set REVIEW5_ROM to a built ROM')
class BuiltRom(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = Path(os.environ['REVIEW5_ROM']).read_bytes()

    def test_battle_tile0_transparent(self):
        self.assertEqual(self.rom[BATTLE_TILE0:BATTLE_TILE0 + 32], bytes(32))

    def test_banner_strips_fit(self):
        sheet = _sheet(self.rom)
        for first, *_ in banner.RANK_STRIPS:
            self.assertLess(_strip_max_x(sheet, first), STRIP_FIELD_TILES * 8, first)

    def test_link_rows_fit_and_bteam_text_kept(self):
        rows = []
        for i in range(LINK_ENTRIES):
            target = _u32(self.rom, LINK_TABLE + 4 * i) - 0x08000000
            self.assertTrue(0 <= target < len(self.rom))
            cells = _sjis_cells(self.rom, target)
            self.assertLessEqual(cells, LINK_FIELD_CELLS, hex(target))
            rows.append(cells)
        baseline = json.loads((ROOT / 'data/bteam_baseline.json').read_text(encoding='utf-8'))
        self.assertEqual(baseline['overrides']['0x00B831C4'], '준비 중')
        self.assertEqual(rows[1], 4)    # 준 비 (U+3000) 중


if __name__ == '__main__':
    unittest.main()
