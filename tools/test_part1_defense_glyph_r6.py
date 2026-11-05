"""R7 battle DEF card and R8 map HUD: one outlined 8x8 방 design, no plate."""
import hashlib
from pathlib import Path
import unittest

from bdf import load_bdf
from build_korean_full import (BATTLE_DEF_CARD_OFFSETS, BATTLE_DEF_GLYPH, BATTLE_DEF_GLYPH_ORIGIN,
                               patch_battle_defense_label_tiles)
from part1_terrain_hud_labels import DEFENSE_GLYPH_8, DEFENSE_GLYPH_ORIGIN, LABELS, render_outlined_16

ROOT = Path(__file__).resolve().parents[1]
JP_DEF_INTERIOR, JP_DEF_OUTLINE = 11, 7
HUD_GOLDEN = '358746e514377abec795311838ce516441a44edd726009bdf6dff3e41f5f00af'
GOLDEN = (
    '8b98c0b75ecc2168e4e4aa2f9e0ffb49064fccd17ce1303597526c97cfa9a172',
    '0889d964e87ccd7ff22ca83e2a78f24d66b21fae411aa6f0a9351bb015613f8a',
    '6c742fd3531d6cd403783eaffa44577d0215fbbed56de97c4c956d3e9e5ec8b7',
    'a32e5ec2fb0eb213548b40107b780ed438e6660620c6eb4638eca7ed114c747f',
    '04849740c8cb78ca910a98f9b29cea59aeecfeb747af4200dbf1b8812d669775',
    'cdfecc13d0997e935e7b5db8e26d759b2babb3ef4cd2a49ee90dbd6c7e70d343',
) * 2


def pixel(block, x, y):
    tile = (y // 8) * 4 + x // 8
    return (block[tile*32 + (y%8)*4 + (x%8)//2] >> (4*(x%2))) & 15


def components(points):
    left, groups = set(points), []
    while left:
        stack, group = [left.pop()], set()
        while stack:
            x, y = stack.pop(); group.add((x, y))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if (x+dx, y+dy) in left:
                        left.remove((x+dx, y+dy)); stack.append((x+dx, y+dy))
        groups.append(group)
    return groups


class DefenseGlyphR7Test(unittest.TestCase):
    def test_jp_def_uses_interior_11_outline_7(self):
        original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        block = original[BATTLE_DEF_CARD_OFFSETS[0]:BATTLE_DEF_CARD_OFFSETS[0]+0x100]
        # 'D' left stem of JP DEF: light interior column wrapped by dark outline.
        self.assertEqual([pixel(block, 1, y) for y in range(7, 12)], [JP_DEF_INTERIOR]*5)
        self.assertEqual([pixel(block, 0, y) for y in range(6, 13)], [JP_DEF_OUTLINE]*7)

    def test_outlined_glyph_without_plate(self):
        original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        rom = bytearray(original)
        self.assertEqual(patch_battle_defense_label_tiles(rom), 12)
        gx, gy = BATTLE_DEF_GLYPH_ORIGIN
        glyph = {(gx+c, gy+r) for r, row in enumerate(BATTLE_DEF_GLYPH) for c, v in enumerate(row) if v == 'X'}
        ring = {(x+dx, y+dy) for x, y in glyph for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - glyph
        # ㅂ, ㅏ and ㅇ stay three separate light strokes.
        self.assertEqual(len(components(glyph)), 3)
        digests = []
        for off in BATTLE_DEF_CARD_OFFSETS:
            before, after = original[off:off+0x100], rom[off:off+0x100]
            digests.append(hashlib.sha256(after).hexdigest())
            for y in range(16):
                for x in range(32):
                    got, jp = pixel(after, x, y), pixel(before, x, y)
                    where = (hex(off), x, y)
                    if (x, y) in glyph:
                        self.assertEqual(got, JP_DEF_INTERIOR, where)
                    elif (x, y) in ring:
                        self.assertEqual(got, JP_DEF_OUTLINE, where)
                    elif x <= 12 and 6 <= y <= 12 and (jp == 7 or (x <= 11 and jp in (5, 11, 13))):
                        # Former DEF letters/plate become the card itself.
                        self.assertEqual(got, {0: 0, 1: 1, 2: 15}.get(x, 12), where)
                    else:
                        self.assertEqual(got, jp, where)
                    # No dark plate: outline colour only on the glyph's 1px ring.
                    if x <= 12 and 4 <= y <= 13 and (x, y) not in ring:
                        self.assertNotEqual(got, JP_DEF_OUTLINE, where)
            # Card border, stars and everything right of the DEF area are JP.
            for y in range(16):
                for x in range(13, 32):
                    self.assertEqual(pixel(after, x, y), pixel(before, x, y), (hex(off), x, y))
        self.assertEqual(digests, list(GOLDEN))

    def test_map_hud_uses_same_glyph(self):
        # Map HUD / terrain card 방 (0xB93BD0): same design as the battle card.
        self.assertEqual(DEFENSE_GLYPH_8, BATTLE_DEF_GLYPH)
        self.assertEqual(LABELS[0][:2], (0xB93BD0, '방'))
        font, _ = load_bdf(str(ROOT / 'reference/fonts/Galmuri7.bdf'))
        block = render_outlined_16('방', font)
        self.assertEqual(hashlib.sha256(block).hexdigest(), HUD_GOLDEN)
        gx, gy = DEFENSE_GLYPH_ORIGIN
        glyph = {(gx+c, gy+r) for r, row in enumerate(DEFENSE_GLYPH_8) for c, v in enumerate(row) if v == 'X'}
        ring = {(x+dx, y+dy) for x, y in glyph for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - glyph
        # Cell position/size kept: glyph starts at (4,4) like the R6 7x7 glyph.
        self.assertEqual((min(x for x, _ in glyph), min(y for _, y in glyph)), (4, 4))

        def value(x, y):
            # Map HUD is 16x16, 2x2 tiles.
            tile = (y//8)*2+x//8
            return (block[tile*32+(y%8)*4+(x%8)//2] >> (4*(x%2))) & 15

        for y in range(16):
            for x in range(16):
                # Interior 1, 1px outline 15 following the glyph, everything else
                # transparent 0 (no plate).
                self.assertEqual(value(x, y), 1 if (x, y) in glyph else 15 if (x, y) in ring else 0, (x, y))
        light = {(x, y) for y in range(16) for x in range(16) if value(x, y) == 1}
        groups = sorted(components(light), key=lambda g: (min(p[1] for p in g), min(p[0] for p in g)))
        # ㅂ, ㅏ and ㅇ are three separate light strokes ...
        self.assertEqual(len(groups), 3)
        bieup, a, ieung = groups
        self.assertEqual(min(x for x, _ in bieup), 4)
        self.assertGreater(min(x for x, _ in a), max(x for x, _ in bieup) + 2)  # gray gap between ㅂ and ㅏ
        # ... with a full outline row between ㅂ bottom and ㅇ top (not touching).
        gap = max(y for _, y in bieup) + 1
        self.assertEqual(min(y for _, y in ieung), gap + 1)
        self.assertTrue(all(value(x, gap) != 1 for x in range(16)))
        # The R6 defect: ㅂ bottom directly above ㅇ top must not recur.
        self.assertFalse(any((x, y+1) in ieung or (x-1, y+1) in ieung or (x+1, y+1) in ieung for x, y in bieup))


if __name__ == '__main__':
    unittest.main()
