import unittest

import move_type_captions as m


class MoveTypeCaptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (m.ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_patch_changes_only_entry_bottoms(self):
        rom = bytearray(self.original)
        self.assertEqual(m.patch(rom, self.original), 7)
        outside = bytearray(rom)
        for address, text, _, _ in m.ENTRIES:
            old = m._decode(self.original[address:address + m.SIZE])
            new = m._decode(rom[address:address + m.SIZE])
            for y in range(7):
                self.assertEqual(old[y], new[y], (hex(address), y))
            ink = sum(row.count(m.INK) for row in new[8:15])
            self.assertGreater(ink, 10 * len(text), text)
            outside[address:address + m.SIZE] = self.original[address:address + m.SIZE]
        self.assertEqual(outside, self.original)
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)
        self.assertTrue(m.generated_matches(rom, self.original))
        again = bytearray(rom)
        m.patch(again, self.original)
        self.assertEqual(again, rom)
        rom[m.ENTRIES[3][0] + 200] ^= 1
        with self.assertRaises(AssertionError):
            m.verify(rom, regions)

    def test_conflict_and_source_drift_rejected(self):
        rom = bytearray(self.original)
        rom[m.ENTRIES[0][0] + 150] ^= 1
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        original = bytearray(self.original)
        original[m.ENTRIES[6][0]] ^= 1
        with self.assertRaises(AssertionError):
            m.expected_regions(original)

    def test_entries_are_contiguous_32x16_cells(self):
        self.assertEqual([row[0] for row in m.ENTRIES], [0xBE88BC + 0x100 * i for i in range(7)])
        self.assertEqual([row[1] for row in m.ENTRIES], ['보병', '바주카', '타이어', '전차', '배', '수송', '비행'])


if __name__ == '__main__':
    unittest.main()
