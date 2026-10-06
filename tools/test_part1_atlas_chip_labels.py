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
                self.assertEqual(new[:7], old[:7], number)   # icon picture kept
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
