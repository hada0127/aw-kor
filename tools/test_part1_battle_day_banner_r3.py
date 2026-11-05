"""R4 golden restoring the R2 Part 1 OkDanDan day/start OBJ artwork."""
from hashlib import sha256
from pathlib import Path
import unittest

import aw_fonts
import build_korean_full as build
from lz77_scan import lz77_decompress

ROOT = Path(__file__).resolve().parent.parent
PHRASE = (0xBBF8C0, 0xBBFAC0, 0xBBFCC0, 0xBBFEC0)
DAY = (0xBC14C0, 0xBC16C0)


class Part1BattleDayR3Tests(unittest.TestCase):
    def test_pinned_font_and_raw_lz_art_goldens(self):
        font = Path(aw_fonts.okdandan_path())
        self.assertEqual(sha256(font.read_bytes()).hexdigest(),
                         aw_fonts.OKDANDAN_SHA256)
        original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        rom = bytearray(original)
        self.assertEqual(build.patch_part1_battle_day_banner(rom), 96)
        self.assertEqual(sha256(b''.join(rom[a:a+512] for a in PHRASE)).hexdigest(),
                         '2719b67ca59ebe9c564ebe6689530c8642391339ff515e20064270e6531f154a')
        self.assertEqual(sha256(b''.join(rom[a:a+512] for a in DAY)).hexdigest(),
                         '61a0d5e19e9c4d9d8ba9b4ee8649a9728fb0b756e1603b3216857680aebee6bb')
        raw, packed = lz77_decompress(rom, 0xEE5E14)
        self.assertEqual((len(raw), packed), (8192, 2795))
        self.assertEqual(sha256(raw).hexdigest(),
                         '13c1008dcaac1273aa518575cd1dbdcb04cd6522e4a34974640d9be616e0bc26')


if __name__ == '__main__':
    unittest.main()
