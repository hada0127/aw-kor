import struct
import unittest

import part1_campaign_clear_banner as m
from lz77_scan import lz77_decompress


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
        self.assertEqual(m.patch(rom, self.original), 3)
        sheet, used = lz77_decompress(rom, m.SOURCE)
        self.assertLessEqual(used, m.CAPACITY)
        native = lz77_decompress(self.original, m.SOURCE)[0]
        self.assertNotEqual(sheet[:m.CELL_BASE_TILE * 32], native[:m.CELL_BASE_TILE * 32])
        import part1_obj_header_labels as headers
        self.assertEqual(sheet[:16 * 32], headers.render(16, '캠페인 랭크', 'left'))
        self.assertEqual(sheet[16 * 32:32 * 32], headers.render(16, '하드 캠페인 랭크', 'left'))
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
            self.assertTrue(values <= {0, 1, 2, 3, 4, 5, 6, 7, 8, 13, 14}, char)
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
