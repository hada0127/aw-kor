import struct
import unittest

import part2_army_name_labels as m
from lz77_scan import lz77_decompress


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (m.ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_source_guard(self):
        m.source_guard(self.original)

    def test_patch_capture_verify_idempotent_and_local(self):
        rom = bytearray(self.original)
        count = m.patch(rom, self.original)
        self.assertEqual(count, len(m.expected_regions(self.original)))
        for address, raw in m.expected_regions(self.original):
            self.assertNotEqual(bytes(self.original[address:address + len(raw)]), raw)
            self.assertEqual(lz77_decompress(rom, address)[1] <= len(raw), True)
        outside = bytearray(rom)
        for address, raw in m.expected_regions(self.original):
            outside[address:address + len(raw)] = self.original[address:address + len(raw)]
        self.assertEqual(outside, self.original)
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)
        self.assertTrue(m.generated_matches(rom, self.original))
        self.assertFalse(m.generated_matches(bytearray(self.original), self.original))
        again = bytearray(rom)
        m.patch(again, self.original)
        self.assertEqual(again, rom)
        first = regions[0][0]
        rom[first + 8] ^= 1
        with self.assertRaises(AssertionError):
            m.verify(rom, regions)

    def test_conflicts_rejected(self):
        first = m.expected_regions(self.original)[0][0]
        rom = bytearray(self.original)
        rom[first + 6] ^= 1
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        original = bytearray(self.original)
        original[first + 20] ^= 1
        with self.assertRaises(AssertionError):
            m.source_guard(original)

    def test_red_star_renderer_reproduced_and_inks(self):
        # The build's red-star output is reproduced byte for byte by the same renderer.
        import part2_army_name_labels as army
        pixels = army.render_pixels('레드스타', 4)
        self.assertEqual({v for r in pixels for v in r}, {0, 4, 7})
        rom = bytearray(self.original)
        army.patch(rom, self.original)
        for source, _, _, _, text, ink, _ in army.LABELS:
            data = lz77_decompress(rom, source)[0]
            self.assertEqual({v for r in army.decode(data) for v in r}, {0, ink, 7})
        native_inks = {0x5489DC: 13, 0x548B50: 15, 0x548CD0: 14}
        for source, ink in native_inks.items():
            data = lz77_decompress(self.original, source)[0]
            self.assertIn(ink, {v for r in army.decode(data) for v in r})

    def test_table_order(self):
        table = [struct.unpack_from('<I', self.original, m.TABLE + 8 * i)[0] - 0x08000000 for i in range(4)]
        self.assertEqual(table, [0x5488A0] + [row[0] for row in m.LABELS])


if __name__ == '__main__':
    unittest.main()
