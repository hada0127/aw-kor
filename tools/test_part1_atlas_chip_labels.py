import struct
import unittest

import part1_atlas_chip_labels as m


class AtlasChipLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (m.ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_entries_match_atlas_table(self):
        for number, address, w, h, *_ in m.ENTRIES:
            tile, tw, th = struct.unpack_from('<HBB', self.original, m.TABLE + 8 * number)
            self.assertEqual((0xBE743C + tile * 32, tw, th), (address, w, h), number)
        # 1P..4P player-number badges (98..101) are deliberately not owned.
        self.assertFalse({98, 99, 100, 101} & {e[0] for e in m.ENTRIES})

    def test_patch_capture_verify(self):
        rom = bytearray(self.original)
        self.assertEqual(m.patch(rom, self.original), len(m.ENTRIES))
        outside = bytearray(rom)
        for number, address, w, h, _, text, kind, _ in m.ENTRIES:
            new = m._decode(rom[address:address + w * h * 32], w, h)
            values = {v for row in new for v in row}
            if kind == 'chip':
                self.assertTrue(values <= {0, m.WHITE, m.GREY, m.BLACK, m.YELLOW}, number)
                self.assertGreater(sum(row.count(m.BLACK) for row in new[4:11]), 8 * len(text), number)
            elif kind in ('strip', 'badge'):
                self.assertTrue(values <= {0, m.WHITE, m.BLACK}, number)
            else:
                old = m._decode(self.original[address:address + w * h * 32], w, h)
                # art rows 2..8 moved up one row (row 1 was uniform background); frame kept
                self.assertEqual([r[1:14] for r in new[1:8]], [r[1:14] for r in old[2:9]], number)
                self.assertEqual(new[0], old[0], number)
                self.assertEqual(new[14:], old[14:], number)
                self.assertEqual([(r[0], r[14]) for r in new], [(r[0], r[14]) for r in old], number)
                band = [r[1:14] for r in new[8:14]]
                self.assertTrue({v for r in band for v in r} == {m.BLACK, m.WHITE}, number)
            outside[address:address + w * h * 32] = self.original[address:address + w * h * 32]
        self.assertEqual(outside, self.original)
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)
        self.assertTrue(m.generated_matches(rom, self.original))
        again = bytearray(rom)
        m.patch(again, self.original)
        self.assertEqual(again, rom)
        rom[m.ENTRIES[2][1] + 40] ^= 1
        with self.assertRaises(AssertionError):
            m.verify(rom, regions)

    def test_labels_review6(self):
        labels = {e[7]: e[5] for e in m.ENTRIES}
        self.assertEqual((labels['Day'], labels['Com'], labels['Play'], labels['CP']), ('날짜', '컴', '유저', '컴'))
        # 16px chips keep a 1px gap between the two syllables (자금 = 15px with gap 1)
        for text in ('수입', '자금'):
            ink, width = m._ink7(text)
            self.assertLessEqual(width, 15, text)
            px = m._chip(16, text)
            cols = [x for x in range(16) if any(px[y][x] == m.BLACK for y in range(4, 11))]
            gaps = [x for x in range(cols[0], cols[-1] + 1) if x not in cols]
            self.assertTrue(gaps, text)
        for glyph in m.ICON_GLYPHS.values():
            self.assertEqual(len(glyph), m.ICON_BAND[1] - m.ICON_BAND[0])
            self.assertEqual(len({len(r) for r in glyph}), 1)

    def test_conflicts_rejected(self):
        rom = bytearray(self.original)
        rom[m.ENTRIES[0][1] + 33] ^= 1
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        rom = bytearray(self.original)
        rom[m.TABLE + 8 * 51 + 2] ^= 1
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        original = bytearray(self.original)
        original[m.ENTRIES[4][1] + 5] ^= 1
        with self.assertRaises(AssertionError):
            m.expected_regions(original)


if __name__ == '__main__':
    unittest.main()
