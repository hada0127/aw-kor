"""R7: Part 1 mission-entry band keeps the JP band and carves 작전 as a knockout."""
import hashlib
from pathlib import Path
import unittest

from build_title_hangul import (PART1_MISSION_BAND, PART1_MISSION_LOGO_LZ77_OFF, PART1_MISSION_RIM,
                                PART1_MISSION_RIM_DIAG, PART1_MISSION_SHADOW, patch_part1_mission_block,
                                part1_mission_letter_mask)
from lz77_scan import lz77_decompress

ROOT = Path(__file__).resolve().parents[1]


def grid(raw):
    g = [[0] * 128 for _ in range(32)]
    for t in range(64):
        tx, ty = t % 16, t // 16
        for i in range(32):
            b = raw[t*32 + i]
            g[ty*8 + i//4][tx*8 + (i % 4)*2] = b & 15
            g[ty*8 + i//4][tx*8 + (i % 4)*2 + 1] = b >> 4
    return g


class MissionRibbonR7Test(unittest.TestCase):
    def setUp(self):
        self.original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        self.raw, self.consumed = lz77_decompress(self.original, PART1_MISSION_LOGO_LZ77_OFF)

    def test_jp_mission_is_a_knockout(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),
                         'aebeae35112184841282f410d105f039c926d81f09fa4431bdedc44e2a527c67')
        jp = grid(self.raw[:0x800])
        # JP band index is 1 on the outer rows; MISSION letters are 0 holes.
        self.assertEqual(set(jp[0]) | set(jp[31]), {PART1_MISSION_BAND})
        self.assertEqual(jp[6][80], 0)  # inside the 'I'
        self.assertEqual(jp[1][76], PART1_MISSION_RIM)

    def test_korean_knockout(self):
        rom = bytearray(self.original)
        used, limit = patch_part1_mission_block(rom)
        self.assertEqual(limit, self.consumed)
        self.assertLessEqual(used, limit)
        changed, _ = lz77_decompress(rom, PART1_MISSION_LOGO_LZ77_OFF)
        self.assertEqual(changed[0x800:], self.raw[0x800:])  # number/other art untouched
        self.assertEqual(rom[:PART1_MISSION_LOGO_LZ77_OFF], self.original[:PART1_MISSION_LOGO_LZ77_OFF])
        self.assertEqual(rom[PART1_MISSION_LOGO_LZ77_OFF+limit:],
                         self.original[PART1_MISSION_LOGO_LZ77_OFF+limit:])
        g = grid(changed[:0x800])
        mask = part1_mission_letter_mask()
        inside = lambda x, y: 0 <= x < 128 and 0 <= y < 32 and mask[y][x]
        holes = 0
        for y in range(32):
            for x in range(128):
                v = g[y][x]
                if inside(x, y):
                    lit = all(inside(x-i, y-j) for i in range(3) for j in range(3))
                    # Letter interior is transparent; only the top/left wall is shadow.
                    self.assertEqual(v, 0 if lit else PART1_MISSION_SHADOW, (x, y))
                    holes += v == 0
                elif any(inside(x+a, y+b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    self.assertEqual(v, PART1_MISSION_RIM, (x, y))
                elif any(inside(x+a, y+b) for a in (-1, 1) for b in (-1, 1)):
                    self.assertEqual(v, PART1_MISSION_RIM_DIAG, (x, y))
                else:
                    # Everything else is the JP band index.
                    self.assertEqual(v, PART1_MISSION_BAND, (x, y))
        self.assertGreater(holes, 600)
        # 작전 sits at MISSION height: letter rows 2..29, rim rows 1 and 30.
        rows = [y for y in range(32) if any(mask[y])]
        self.assertEqual((rows[0], rows[-1]), (2, 29))
        self.assertEqual(set(g[0]) | set(g[31]), {PART1_MISSION_BAND})
        self.assertEqual(hashlib.sha256(changed).hexdigest(), GOLDEN)


GOLDEN = 'c4e7db2681316130c17d53c78a01fca32a254cbf23785f5c5e5e629d5cd8d292'

if __name__ == '__main__':
    unittest.main()
