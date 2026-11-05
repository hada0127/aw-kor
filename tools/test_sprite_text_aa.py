"""Focused tests for graphic-only supersampled palette rendering."""
import unittest

from PIL import Image

import aw_fonts
from hangul_pixel_fit import glyph, verify_glyph
from sprite_text_aa import (palette_blend_index, render_graphic_aa,
                            size_for_ink_height, supersampled_text)


PALETTE = ((0, 0, 0), (20, 20, 20), (100, 100, 100), (255, 255, 255))


class GraphicAATests(unittest.TestCase):
    def test_determinism_and_allowed_ramp(self):
        high = Image.new('L', (32, 32))
        for y in range(8, 24):
            for x in range(8, 24):
                high.putpixel((x, y), 255 if x >= 12 else 64)
        args = dict(palettes=(PALETTE,), allowed_indices=(1, 2, 3),
                    fills={'fill': 3}, backgrounds={'fill': 1}, scale=4)
        first, info = render_graphic_aa({'fill': high}, (8, 8), **args)
        second, again = render_graphic_aa({'fill': high}, (8, 8), **args)
        self.assertEqual(first.tobytes(), second.tobytes())
        self.assertEqual(info, again)
        self.assertLessEqual(set(first.tobytes()), {0, 1, 2, 3})
        self.assertEqual(first.getpixel((4, 4)), 3)
        self.assertEqual(palette_blend_index(1, 3, 64, (1, 2, 3), (PALETTE,)), 2)

    def test_transparent_edge_has_no_halo_and_protection_fails(self):
        high = Image.new('L', (8, 8), 0)
        high.putpixel((3, 3), 255)
        kwargs = dict(palettes=(PALETTE,), allowed_indices=(1, 3),
                      fills={'fill': 3}, backgrounds={'fill': 0}, scale=4)
        image, _ = render_graphic_aa({'fill': high}, (2, 2), **kwargs)
        self.assertEqual(set(image.tobytes()), {0})
        high.paste(255, (0, 0, 4, 4))
        protected = Image.new('1', (2, 2), 0)
        protected.putpixel((0, 0), 1)
        with self.assertRaisesRegex(ValueError, 'protected pixel'):
            render_graphic_aa({'fill': high}, (2, 2), protected=protected, **kwargs)

    @unittest.skipUnless(aw_fonts.OKDANDAN.is_file(), 'OkDanDan font unavailable')
    def test_counter_core_is_verified(self):
        core = glyph('똥', 24, 24)
        self.assertFalse(verify_glyph('똥', core)['failures'])
        high = core.resize((96, 96), Image.Resampling.NEAREST)
        args = dict(palettes=(PALETTE,), allowed_indices=(1, 3),
                    fills={'fill': 3}, backgrounds={'fill': 0},
                    glyphs=(('똥', (0, 0, 24, 24)),), scale=4)
        render_graphic_aa({'fill': high}, (24, 24), **args)
        # A damaged binary counter must fail, even if the palette is legal.
        damaged = core.copy()
        damaged.paste(255, (8, 8, 16, 16))
        with self.assertRaisesRegex(ValueError, 'closed counter|altered glyph'):
            render_graphic_aa({'fill': damaged.resize((96, 96), Image.Resampling.NEAREST)},
                              (24, 24), **args)

    @unittest.skipUnless(aw_fonts.OKDANDAN.is_file(), 'OkDanDan font unavailable')
    def test_height_target_and_graphic_policy(self):
        path = aw_fonts.okdandan_path()
        size, height = size_for_ink_height('한글', path, 13, (64, 18), max_size=32)
        self.assertLessEqual(height, 18)
        self.assertLessEqual(abs(height - 13), 1)
        mask = supersampled_text('한글', path, size, (64, 24), (1, 0))
        self.assertEqual(mask.size, (512, 192))
        self.assertEqual(aw_fonts.graphic_outline_font_allowed({(0, 0), (1, 9)}), 10)
        with self.assertRaises(aw_fonts.SmallLineError):
            aw_fonts.require_large_line({(0, 0), (1, 9)})


if __name__ == '__main__':
    unittest.main()
