"""Verify glyph dictionary source-role claims against original ROM bytes."""
import hashlib
from pathlib import Path
import struct
import sys
import unittest
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import glyph_dictionary_sources as G


class DictionarySourceTests(unittest.TestCase):
    def test_catalog_matches_original_rom(self):
        rom = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        self.assertEqual(hashlib.sha256(rom).hexdigest(), G.CATALOG['original_sha256'])
        previous_end = 0
        for address, size, row in G.SOURCES:
            with self.subTest(address=hex(address)):
                self.assertGreaterEqual(address, previous_end)
                self.assertGreater(size, 0)
                self.assertEqual(size % 2, 0)
                self.assertNotIn(0, rom[address:address + size])
                self.assertEqual(rom[address + size], 0)
                for pointer in row['pointer_offsets']:
                    self.assertEqual(struct.unpack_from('<I', rom, int(pointer, 16))[0],
                                     0x08000000 + address)
                self.assertEqual(G.glyph_dictionary_owner(address + size - 1), address)
                self.assertIsNone(G.glyph_dictionary_owner(address + size))
                previous_end = address + size
        self.assertFalse(G.is_glyph_dictionary_address(None))



if __name__ == '__main__':
    unittest.main()
