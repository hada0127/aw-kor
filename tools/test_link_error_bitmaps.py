import struct
import unittest
from pathlib import Path

import link_error_bitmaps as m
from lz77_scan import lz77_decompress


class LinkErrorBitmapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent.parent
        cls.original = (root / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_patch_only_owned_allocations(self):
        rom = bytearray(self.original)
        self.assertEqual(m.patch(rom, self.original), 15)
        outside = bytearray(rom)
        for offset, capacity, size, _, key in m._blocks():
            decoded, used = lz77_decompress(rom, offset)
            self.assertEqual(decoded, m.generated()[key])
            self.assertEqual(len(decoded), size)
            self.assertLessEqual(used, capacity)
            outside[offset:offset + capacity] = self.original[offset:offset + capacity]
        self.assertEqual(outside, self.original)
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)
        self.assertTrue(m.generated_matches(rom))
        rom[0x930B30 + 40] ^= 1
        with self.assertRaises(AssertionError):
            m.verify(rom, regions)

    def test_pointerless_copies_identical_to_live_pair(self):
        rom = bytearray(self.original)
        m.patch(rom, self.original)
        for sheet, tmap in m.SCREENS[0][12]:
            self.assertEqual(rom[sheet:sheet + 866], rom[0xC2A040:0xC2A040 + 866])
            self.assertEqual(rom[tmap:tmap + 390], rom[0xC2A3A4:0xC2A3A4 + 390])

    def test_tilemaps_only_reference_pool_tiles_and_keep_fill(self):
        for screen in m.SCREENS:
            sheet, tmap = m.build_screen(screen)
            entries = struct.unpack(f'<{len(tmap) // 2}H', tmap)
            blank = screen[10]
            self.assertTrue(all(e < len(sheet) // 32 for e in entries))
            self.assertEqual(sheet[blank * 32:blank * 32 + 32], bytes(32))
            used = {e for e in entries if e != blank}
            self.assertTrue(used)
            # Only native text rows are written.
            rows = {i // 32 for i, e in enumerate(entries) if e != blank}
            self.assertTrue(rows <= {6, 7, 9, 10, 11, 12})
            cols = {i % 32 for i, e in enumerate(entries) if e != blank}
            self.assertLess(max(cols), 30)
            colors = {n for b in sheet for n in (b & 15, b >> 4)}
            self.assertEqual(colors, {0, m.INK})

    def test_strip_fits_and_uses_native_ink(self):
        strip = m.build_strip()
        self.assertEqual(len(strip), 1728)
        self.assertEqual({n for b in strip for n in (b & 15, b >> 4)}, {0, m.INK})

    def test_foreign_writer_and_source_drift_rejected(self):
        rom = bytearray(self.original)
        rom[0x5481E4 + 30] ^= 1
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        original = bytearray(self.original)
        original[0xB305E4] ^= 4
        with self.assertRaises(AssertionError):
            m.patch(bytearray(self.original), original)


if __name__ == '__main__':
    unittest.main()
