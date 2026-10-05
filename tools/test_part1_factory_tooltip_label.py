import unittest

import part1_factory_tooltip_label as F
from lz77_scan import lz77_decompress


class FactoryTooltipLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (F.ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_only_text_interiors_change_and_frame_is_native(self):
        old = F.source_block(self.original)
        new = F.decoded_replacement(self.original)
        self.assertEqual(len(new), F.DECODED_SIZE)
        text_tiles = {tile + q for tile, *_ in F.HALVES for q in range(4)}
        for tile in range(F.DECODED_SIZE // 32):
            if tile not in text_tiles:
                self.assertEqual(old[tile * 32:tile * 32 + 32], new[tile * 32:tile * 32 + 32])
        for tile, _, (x0, y0, x1, y1), _, _ in F.HALVES:
            changed = False
            for y in range(16):
                for x in range(16):
                    before, after = F.get_pixel(old, tile, x, y), F.get_pixel(new, tile, x, y)
                    if x0 <= x <= x1 and y0 <= y <= y1:
                        self.assertIn(after, {F.FILL, F.INK, F.SHADOW})
                        changed |= before != after
                    else:
                        self.assertEqual(before, after)
            self.assertTrue(changed)

    def test_patch_recompresses_in_place_without_moving_pointer(self):
        rom = bytearray(self.original)
        self.assertEqual(F.patch(rom, self.original), 2)
        diff = [a for a, (x, y) in enumerate(zip(rom, self.original)) if x != y]
        self.assertTrue(diff)
        self.assertTrue(all(F.OFFSET <= a < F.OFFSET + F.COMPRESSED_SIZE for a in diff))
        data, consumed = lz77_decompress(rom, F.OFFSET)
        self.assertEqual(bytes(data), F.decoded_replacement(self.original))
        self.assertLessEqual(consumed, F.COMPRESSED_SIZE)
        F.patch(rom, self.original)  # idempotent

    def test_source_and_pointer_drift_fail_closed(self):
        for address in (F.OFFSET + 10, F.POINTER):
            original = bytearray(self.original)
            original[address] ^= 1
            with self.assertRaises(AssertionError):
                F.patch(bytearray(original), original)

    def test_earlier_and_later_writers_are_rejected(self):
        rom = bytearray(self.original)
        rom[F.OFFSET + 100] ^= 1
        with self.assertRaisesRegex(AssertionError, 'earlier writer'):
            F.patch(rom, self.original)
        rom = bytearray(self.original)
        F.patch(rom, self.original)
        evidence = F.capture_regions(rom, self.original)
        F.verify_regions(rom, evidence)
        rom[F.OFFSET + 200] ^= 1
        with self.assertRaisesRegex(AssertionError, 'overwritten'):
            F.verify_regions(rom, evidence)


if __name__ == '__main__':
    unittest.main()
