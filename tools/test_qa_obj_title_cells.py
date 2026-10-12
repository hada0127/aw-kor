"""Regression tests for the active Part 1 power-title source pointer."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qa_obj_title_cells import power_title_source


class PowerTitleSourceTests(unittest.TestCase):
    def setUp(self):
        self.rom = bytearray(0xB3C1F8)
        self.source = 0x100
        self.write_sheet(45)
        struct.pack_into('<I', self.rom, 0xB3C1F4, 0x08000000 + self.source)

    def write_sheet(self, cells, extra=b''):
        raw = bytes(cells * 2 * 4 * 32) + extra
        packed = bytes((0x10, len(raw) & 255, len(raw) >> 8, 0))
        packed += b''.join(b'\0' + raw[i:i + 8] for i in range(0, len(raw), 8))
        self.rom[self.source:self.source + len(packed)] = packed

    def test_follows_relocated_pointer(self):
        off, raw, count = power_title_source(self.rom)
        self.assertEqual(off, self.source)
        self.assertEqual(len(raw), 45 * 2 * 4 * 32)
        self.assertEqual(count, 45)

    def test_short_or_partial_sheet_fails_closed(self):
        for cells, extra in ((44, b''), (45, b'\0')):
            with self.subTest(cells=cells, extra=bool(extra)):
                self.write_sheet(cells, extra)
                with self.assertRaisesRegex(ValueError, 'invalid source LZ77'):
                    power_title_source(self.rom)

    def test_corrupted_pointer_fails_closed(self):
        for pointer in (0, 0x09000000, 0x08000200):
            with self.subTest(pointer=pointer):
                struct.pack_into('<I', self.rom, 0xB3C1F4, pointer)
                with self.assertRaisesRegex(ValueError, 'source pointer|source LZ77'):
                    power_title_source(self.rom)


if __name__ == '__main__':
    unittest.main()
