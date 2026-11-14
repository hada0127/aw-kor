import hashlib
import struct
import unittest

import part1_campaign_clear_banner as m
from lz77_scan import lz77_decompress

# Current-generator golden of both rank strips (R20, 2026-11-09).
RANK_STRIPS_SHA256 = '356284697cb14558bf06640ddba43db84ee7d90dff97f11abc55f4b529538d3b'


class CampaignClearBannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (m.ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def _rows(self, rom, table, entries):
        return [struct.unpack_from('<hhHH', rom, table + 8 * i) for i in range(entries + 1)]

    def test_native_composition_is_what_the_module_assumes(self):
        m.source_guard(self.original)
        kana = 'キャンペークリア!ハド'
        cell = lambda t: kana[(t - m.OBJ_TILE0) // 16]
        normal = self._rows(self.original, m.NORMAL_TABLE, m.NORMAL_ENTRIES)
        hard = self._rows(self.original, m.HARD_TABLE, m.HARD_ENTRIES)
        self.assertEqual(''.join(cell(r[2]) for r in normal[:-1]), 'キャンペーンクリア!')
        self.assertEqual(''.join(cell(r[2]) for r in hard[:-1]), 'ハードキャンペーンクリア!')
        self.assertLess(normal[-1][0], 0)
        self.assertLess(hard[-1][0], 0)

    def test_patch_reads_korean_and_keeps_counts_and_delays(self):
        rom = bytearray(self.original)
        self.assertEqual(m.patch(rom, self.original), 5)   # R17: relocated sheet + 2 pointers
        for pointer in m.SOURCE_POINTERS:
            self.assertEqual(struct.unpack_from('<I', rom, pointer)[0], m.RELOCATION + 0x08000000)
        self.assertEqual(rom[m.SOURCE:m.FOLLOWING], self.original[m.SOURCE:m.FOLLOWING])   # retired
        sheet, used = lz77_decompress(rom, m.RELOCATION)
        self.assertLessEqual(used, m.RELOCATION_END - m.RELOCATION)
        native = lz77_decompress(self.original, m.SOURCE)[0]
        self.assertNotEqual(sheet[:m.CELL_BASE_TILE * 32], native[:m.CELL_BASE_TILE * 32])
        # R20: JP strip composition (white six-row letters, black outline, no box).
        self.assertEqual(sheet[:16 * 32], m.rank_strip('캠페인 랭크'))
        self.assertEqual(sheet[16 * 32:32 * 32], m.rank_strip('하드 캠페인 랭크'))
        for first in (0, 16):
            strip = sheet[first * 32:(first + 16) * 32]
            px = [[(strip[x // 8 * 32 + y * 4 + x % 8 // 2] >> (4 * (x % 2))) & 15 for x in range(128)]
                  for y in range(8)]
            self.assertEqual({v for row in px for v in row}, {0, 1, 5})
            self.assertNotIn(1, px[0] + px[7])
            self.assertEqual(px[3][0], 5)   # outline from column 0 like the JP strip
        self.assertEqual(hashlib.sha256(sheet[:32 * 32]).hexdigest(), RANK_STRIPS_SHA256)
        glyph = lambda t: (m.GLYPHS + '__')[(t - m.OBJ_TILE0) // 16]
        for table, entries, text in ((m.NORMAL_TABLE, m.NORMAL_ENTRIES, '캠페인클리어!'),
                                     (m.HARD_TABLE, m.HARD_ENTRIES, '하드캠페인클리어!')):
            old = self._rows(self.original, table, entries)
            new = self._rows(rom, table, entries)
            self.assertEqual([r[3] for r in new], [r[3] for r in old])
            self.assertEqual(new[-1], old[-1])
            self.assertEqual(''.join(glyph(r[2]) for r in new[:-1]).rstrip('_'), text)
            for x, y, tile, _ in new[:-1]:
                self.assertTrue(0 <= x <= 240 - 32 and 0 <= y <= 160 - 32)
                self.assertTrue(m.OBJ_TILE0 <= tile < m.OBJ_TILE0 + 16 * m.CELLS)
        for cell in (m.BLANK, m.BLANK + 1):
            start = (m.CELL_BASE_TILE + 16 * cell) * 32
            self.assertEqual(sheet[start:start + 512], bytes(512))
        outside = bytearray(rom)
        for address, raw in m.expected_regions(self.original):
            outside[address:address + len(raw)] = self.original[address:address + len(raw)]
        self.assertEqual(outside, self.original)
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)
        self.assertTrue(m.generated_matches(rom, self.original))
        again = bytearray(rom)
        m.patch(again, self.original)
        self.assertEqual(again, rom)
        rom[m.HARD_TABLE] ^= 1
        with self.assertRaises(AssertionError):
            m.verify(rom, regions)

    def test_glyph_cells_use_native_palette_roles(self):
        for char in m.GLYPHS:
            values = {v for row in m.render_cell(char) for v in row}
            # R15a: + 11, the JP B edge AA of the green rows.
            self.assertTrue(values <= {0, 1, 2, 3, 4, 5, 6, 7, 8, 11, 13, 14}, char)
            self.assertIn(14, values)

    def test_conflicts_rejected(self):
        rom = bytearray(self.original)
        rom[m.NORMAL_TABLE + 2] ^= 1
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        rom = bytearray(self.original)
        rom[m.NORMAL_POOL] ^= 4
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        original = bytearray(self.original)
        original[m.SOURCE + 40] ^= 1
        with self.assertRaises(AssertionError):
            m.source_guard(original)


if __name__ == '__main__':
    unittest.main()
