"""Round 2 Part 2 prologue lettering geometry and allocation guards."""
import hashlib
from pathlib import Path
import unittest

from build_korean_full import patch_part2_prologue_logo_obj
import aw_fonts
from lz77_scan import lz77_decompress


ROOT = Path(__file__).resolve().parents[1]
OFFSET = 0x5BBB3C
OWNED = {base + tx for base in (0x08, 0x28) for tx in range(12)}


def ink_box(raw):
    points, colors = [], set()
    for ty, base in enumerate((0x08, 0x28)):
        for tx in range(12):
            tile = raw[(base + tx) * 32:(base + tx + 1) * 32]
            for row in range(8):
                for col in range(8):
                    value = (tile[row * 4 + col // 2] >> (4 * (col % 2))) & 15
                    if value:
                        points.append((tx * 8 + col, ty * 8 + row))
                        colors.add(value)
    box = (min(x for x, _ in points), min(y for _, y in points),
           max(x for x, _ in points) + 1, max(y for _, y in points) + 1)
    return box, colors


class PrologueLogoTests(unittest.TestCase):
    def test_jp_height_and_protected_tiles(self):
        original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(),
                         'a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c')
        native, capacity = lz77_decompress(original, OFFSET)
        rom = bytearray(original)
        self.assertEqual(patch_part2_prologue_logo_obj(rom), 24)
        generated, consumed = lz77_decompress(rom, OFFSET)
        self.assertEqual(hashlib.sha256(Path(aw_fonts.hadasans_black_path()).read_bytes()).hexdigest(),
                         aw_fonts.HADASANS_BLACK_SHA256)
        self.assertEqual(hashlib.sha256(generated).hexdigest(),
                         '921459f21c4d61bae0541907d80237ad53f736e4d4595005e4a72e1952aa7727')
        self.assertEqual(len(generated), len(native))
        self.assertLessEqual(consumed, capacity)
        self.assertEqual(ink_box(native)[0][3] - ink_box(native)[0][1], 16)
        self.assertEqual(ink_box(generated)[0], (16, 0, 80, 16))
        self.assertEqual(ink_box(generated)[1], {3, 7, 11})
        # R5 filled this entire horizontal span with 7, joining the letters.
        blank_inside = 0
        for y in range(16):
            for x in range(16, 80):
                tile = (0x08 if y < 8 else 0x28) + x // 8
                value = (generated[tile*32 + (y%8)*4 + (x%8)//2] >> (4*(x%2))) & 15
                blank_inside += value == 0
        self.assertGreater(blank_inside, 40)
        self.assertEqual(rom[:OFFSET], original[:OFFSET])
        self.assertEqual(rom[OFFSET + capacity:], original[OFFSET + capacity:])
        self.assertFalse(any(rom[OFFSET + consumed:OFFSET + capacity]))
        self.assertTrue(any(generated[t * 32:t * 32 + 32] != native[t * 32:t * 32 + 32]
                            for t in OWNED))
        for tile in range(len(native) // 32):
            if tile not in OWNED:
                self.assertEqual(generated[tile * 32:tile * 32 + 32],
                                 native[tile * 32:tile * 32 + 32], tile)


if __name__ == '__main__':
    unittest.main()
