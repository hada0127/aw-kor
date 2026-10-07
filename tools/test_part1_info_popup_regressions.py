"""Static regression checks for the Part 1 info-panel asset repairs.

Run with AW_TEST_ROM=<candidate.gba> python3 -m unittest tools/test_part1_info_popup_regressions.py
The assertions cover final ROM bytes; they do not claim runtime visibility.
"""
import json
import os
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lz77_scan import lz77_decompress

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL = ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba'


def pixels(data, width):
    height = len(data) // 32 // (width // 8) * 8
    out = []
    for y in range(height):
        row = []
        for x in range(width):
            tile = (y // 8) * (width // 8) + x // 8
            value = data[tile * 32 + (y % 8) * 4 + (x % 8) // 2]
            row.append((value >> 4) & 15 if x & 1 else value & 15)
        out.append(row)
    return out


class Part1InfoPopupRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.environ.get('AW_TEST_ROM')
        if not path:
            raise RuntimeError('AW_TEST_ROM is required for final-ROM regression checks')
        cls.original = ORIGINAL.read_bytes()
        cls.rom = Path(path).read_bytes()

    def test_weapon_headings_and_backing(self):
        for address in (0xBA34D0, 0xEE436C):
            old = pixels(lz77_decompress(self.original, address)[0], 128)
            new = pixels(lz77_decompress(self.rom, address)[0], 128)
            for top in (1, 17):
                self.assertGreater(sum(new[y][x] == 4 for y in range(top, top + 14)
                                       for x in range(86, 126)), 50)
            for y in range(40):
                for x in range(128):
                    if not (86 <= x < 126 and y < 32):
                        self.assertEqual(new[y][x], old[y][x], (hex(address), x, y))

    def test_tab_ink_stays_below_screen_edge(self):
        spec = pixels(lz77_decompress(self.rom, 0xBC7C00)[0][:128], 32)
        for address in (0xBE9A5C, 0xBE989C):
            tab = pixels(self.rom[address:address + 128], 32)
            self.assertTrue(any(1 in row for row in tab[2:7]))
            self.assertNotIn(1, tab[1])
        self.assertNotIn(1, spec[1])

    def test_income_and_port_title(self):
        self.assertEqual(self.rom[0xB82AE8:0xB82AEC], b'--\0\0')
        self.assertEqual(struct.unpack_from('<I', self.rom, 0xB28AFC)[0], 0x08F3E000)
        self.assertEqual(self.rom[0xF3E000:0xF3E006], bytes.fromhex('815b815b0000'))
        code_map = json.loads((ROOT / 'data/syllable_to_code_2350.json').read_text())
        expected = bytes.fromhex(code_map['항'][2:] + code_map['구'][2:])
        self.assertEqual(self.rom[0xD85AF4:0xD85AFC], b'\x0a\x09' + expected + b'\x0a\x00')


if __name__ == '__main__':
    unittest.main()
