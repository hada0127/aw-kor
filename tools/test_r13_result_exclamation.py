"""R13 current-generator golden and fresh full-build rollback checks."""
import hashlib
import os
import unittest
from pathlib import Path

import build_korean_full as build
from lz77_scan import lz77_decompress
from test_r11_result_graphics import pixels

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba'
R13_GOLDEN = '6082c9ef07cde601435e958a71537542adb5db721de8c3581c078ee9bd9752ce'
ROM_GOLDEN = '7e0bca529afd6e4ab2bab970906be689edfd88f9e40c360d5dec4cb14ed14c1d'
HEAD_DAY_STREAM_GOLDEN = '11ff06daf01ebe607c6ef95d4a6addf5aa1696a5326447abe90b17b1d8758237'
HEAD_DAY_SLOT_GOLDEN = '6f75ecaf3a4060675138cc3bc323724cccc6568af615d8bf884287d88ade9b9a'
MARK = (
    '.EEE.', 'E565E', 'E666E', 'E666E', 'E666E', 'E666E', 'E666E',
    'E565E', '.EEE.', '.....', '.EEE.', 'E565E', 'E666E', '.EEE.',
)


class R13ResultExclamation(unittest.TestCase):
    def test_current_generator_golden_and_mark(self):
        original = bytearray(ORIGINAL.read_bytes())
        build.patch_part2_result_summary_obj(original)
        data = lz77_decompress(original, 0x59DA5C)[0]
        self.assertEqual(hashlib.sha256(data).hexdigest(), R13_GOLDEN)
        art = pixels(data, 256, 256)
        actual = tuple(''.join(format(art[y][x], 'X') if art[y][x] else '.'
                               for x in range(193, 198)) for y in range(81, 95))
        self.assertEqual(actual, MARK)
        self.assertEqual({art[y][x] for y in range(80, 96)
                          for x in range(191, 212)}, {0, 5, 6, 14})
        self.assertTrue(all(art[90][x] == 0 for x in range(191, 212)))

    def test_fresh_full_build_failure_rollback(self):
        candidate = os.environ.get('AW_TEST_ROM')
        if not candidate:
            self.skipTest('AW_TEST_ROM required for fresh candidate checks')
        original = ORIGINAL.read_bytes()
        rom = Path(candidate).read_bytes()
        self.assertEqual(hashlib.sha256(rom).hexdigest(), ROM_GOLDEN)
        self.assertEqual(rom[0x34A3D0:0x34A3D4], original[0x34A3D0:0x34A3D4])
        self.assertEqual(rom[0x34A3D0:0x34A3D4], bytes.fromhex('74ec4508'))
        self.assertEqual(rom[0xFDA000:0xFDB000], original[0xFDA000:0xFDB000])
        _, used = lz77_decompress(rom, 0x45EC74)
        self.assertEqual(used, 3281)
        self.assertEqual(hashlib.sha256(rom[0x45EC74:0x45EC74 + used]).hexdigest(),
                         HEAD_DAY_STREAM_GOLDEN)
        # The source block's original 4147-byte allocation, including padding,
        # matches the HEAD-built graphics candidate byte for byte.
        self.assertEqual(hashlib.sha256(rom[0x45EC74:0x45EC74 + 4147]).hexdigest(),
                         HEAD_DAY_SLOT_GOLDEN)
        self.assertEqual(hashlib.sha256(lz77_decompress(rom, 0x59DA5C)[0]).hexdigest(),
                         R13_GOLDEN)


if __name__ == '__main__':
    unittest.main()
