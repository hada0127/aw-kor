import struct
import unittest

import part2_war_over_newspaper_sheet as m
from build_korean_full import patch_part2_menu_newspaper_bg
from lz77_scan import lz77_decompress

ROM_BASE = 0x08000000


class WarOverNewspaperSheetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        root = Path(m.__file__).resolve().parent.parent
        cls.original = (root / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def _literals(self, rom, value):
        pat = struct.pack('<I', value)
        out, i = [], rom.find(pat)
        while i >= 0:
            out.append(i)
            i = rom.find(pat, i + 1)
        return out

    def test_original_consumers(self):
        refs = self._literals(self.original, ROM_BASE + m.SOURCE)
        self.assertEqual(len(refs), 11)
        self.assertIn(m.LITERAL, refs)
        # every other loader also loads the collage tilemap 0x5B58E0 within 0x20 bytes
        collage = struct.pack('<I', ROM_BASE + 0x5B58E0)
        for ref in refs:
            near = self.original[ref:ref + 0x20]
            if ref == m.LITERAL:
                self.assertNotIn(collage, near)
                self.assertIn(struct.pack('<I', ROM_BASE + 0x509D6C), self.original[ref:ref + 0x14])
            else:
                self.assertIn(collage, near, hex(ref))
        self.assertEqual(self._literals(self.original, ROM_BASE + m.DEST), [])

    def test_patch_relocates_only_the_war_over_reference(self):
        rom = bytearray(self.original)
        self.assertEqual(m.patch(rom, self.original), 1)
        self.assertEqual(struct.unpack_from('<I', rom, m.LITERAL)[0], ROM_BASE + m.DEST)
        self.assertEqual(lz77_decompress(rom, m.DEST)[0], lz77_decompress(self.original, m.SOURCE)[0])
        self.assertEqual(len(self._literals(rom, ROM_BASE + m.SOURCE)), 10)
        changed = [i for i in range(len(rom)) if rom[i] != self.original[i]]
        self.assertTrue(all(m.DEST <= i < m.DEST + m.SOURCE_SIZE or m.LITERAL <= i < m.LITERAL + 4 for i in changed))
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)
        self.assertTrue(m.generated_matches(rom, self.original))
        again = bytearray(rom)
        m.patch(again, self.original)
        self.assertEqual(again, rom)
        rom[m.DEST + 10] ^= 1
        with self.assertRaises(AssertionError):
            m.verify(rom, regions)

    def test_conflicts_rejected(self):
        rom = bytearray(self.original)
        rom[m.DEST + 5] = 0
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        rom = bytearray(self.original)
        struct.pack_into('<I', rom, m.LITERAL, ROM_BASE + 0x123456)
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        original = bytearray(self.original)
        original[m.SOURCE + 100] ^= 1
        with self.assertRaises(AssertionError):
            m.patch(bytearray(original), original)

    def test_shared_source_mutation_does_not_reach_war_over(self):
        # WAR IS OVER still reads its original copy if another writer changes the shared source
        rom = bytearray(self.original)
        rom[m.SOURCE + 8:m.SOURCE + 40] = bytes(32)
        m.patch(rom, self.original)
        target = struct.unpack_from('<I', rom, m.LITERAL)[0] - ROM_BASE
        self.assertEqual(lz77_decompress(rom, target)[0], lz77_decompress(self.original, m.SOURCE)[0])

    def test_shared_source_restored_from_modified_base(self):
        rom = bytearray(self.original)
        before, after = m.SOURCE - 1, m.SOURCE + m.SOURCE_SIZE
        rom[m.SOURCE:after] = bytes([0xA5]) * m.SOURCE_SIZE
        self.assertEqual(patch_part2_menu_newspaper_bg(rom, self.original), 0)
        self.assertEqual(rom[m.SOURCE:after], self.original[m.SOURCE:after])
        self.assertEqual(rom[before], self.original[before])
        self.assertEqual(rom[after], self.original[after])
        self.assertEqual(rom, self.original)


if __name__ == '__main__':
    unittest.main()
