"""Native plate geometry and palette regressions for mode-select graphics."""
import unittest
import os
from PIL import Image
import hangul_pixel_fit as fit
from pathlib import Path
from aw_fonts import obj_canvas
from build_korean_full import patch_part2_mode_menu_obj_labels
from lz77_scan import lz77_decompress

ROOT = Path(__file__).resolve().parents[1]
BIG = (0x5B7930, 0x5B7CB0, 0x5B7F38, 0x5B82B4, 0x5B8564, 0x5B8850, 0x5B8B20)
SMALL = (0x5B8E44, 0x5B9050, 0x5B9378, 0x5B8F48, 0x5B917C, 0x5B9280)


class ModeMenuStyleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        cls.rom = bytearray(cls.original)
        patch_part2_mode_menu_obj_labels(cls.rom)

    def test_original_plate_boundaries(self):
        for off in BIG + SMALL:
            big = off in BIG
            a = obj_canvas(lz77_decompress(self.original, off)[0], 2 if big else 4, 8 if big else 4, 4 if big else 2)
            b = obj_canvas(lz77_decompress(self.rom, off)[0], 2 if big else 4, 8 if big else 4, 4 if big else 2)
            for y in range(len(a)):
                for x in range(128):
                    # Only the native text interiors may change.
                    editable = (4 <= x < 124 and (2 <= y < 22 or 23 <= y < 30)) if big else True
                    if not big:
                        # 9px Galmuri needs an 11px field: expand by two rows
                        # each side while preserving width and one-pixel trim.
                        expected = (0 if y == 15 else 15 if x < 3 or x >= 125 or y in (0, 14)
                                    else 1 if x in (3, 124) or y in (1, 13) else None)
                        if expected is not None:
                            self.assertEqual(b[y][x], expected, (hex(off), x, y))
                    if not editable:
                        self.assertEqual(a[y][x], b[y][x], (hex(off), x, y))

    def test_small_labels_keep_native_white_on_color(self):
        for off in SMALL:
            p = obj_canvas(lz77_decompress(self.rom, off)[0], 4, 4, 2)
            values = [p[y][x] for y in range(3, 12) for x in range(4, 124)]
            self.assertGreater(values.count(1), 12, hex(off))
            self.assertGreater(values.count(5), 500, hex(off))
            self.assertEqual(set(values), {1, 5})

    def test_large_ink_clears_lower_band(self):
        for off in BIG:
            p = obj_canvas(lz77_decompress(self.rom, off)[0], 2, 8, 4)
            ys = [y for y in range(2, 22) if any(5 <= v <= 12 for v in p[y][4:124])]
            self.assertGreater(max(ys) - min(ys) + 1, 16, hex(off))
            self.assertEqual(set(p[22][3:125]), {1})

    def test_complete_ink_on_shared_baseline_in_final_rom(self):
        rom = Path(os.environ['AW_TEST_ROM']).read_bytes() if os.environ.get('AW_TEST_ROM') else self.rom
        for off, text in zip(BIG, fit.PLATE_LABELS):
            grid = obj_canvas(lz77_decompress(rom, off)[0], 2, 8, 4)
            layer = Image.new('L', (128, 32)); layer.putdata([v for row in grid for v in row])
            records = fit.verify_plate_ink(layer, text)
            for ch, (a, b, c, d) in records:
                self.assertEqual((b, d), (0, 19), (text, ch))
                ref = fit.plate_glyph(ch)
                # Match all rows, including 받침, against an oversized render.
                unclipped = Image.new('L', (160, 64)); unclipped.paste(ref, (20, 20))
                self.assertEqual(layer.crop((a+6,b+2,c+6,d+2)).point(lambda v:255 if v==5 else 0).tobytes(), unclipped.crop((20,20,20+ref.width,39)).tobytes())
            self.assertTrue(all(grid[y][x] == 1 for y in (21,22) for x in range(4,124)))
            self.assertTrue(all(grid[y][x] == 5 for y in range(23,30) for x in range(4,124)))

    def test_clipped_or_shifted_syllable_rejected(self):
        for text in ('편집', '통신'):
            mask, records = fit.plate_line(text)
            good = Image.new('L', (128,32), 1); good.paste(5, (6,2), mask)
            fit.verify_plate_ink(good, text)
            for ch, (a,b,c,d) in records:
                bad = good.copy()
                for x in range(a+6,c+6): bad.putpixel((x,d+1),1)
                with self.assertRaises(AssertionError): fit.verify_plate_ink(bad,text)
            shifted = Image.new('L',(128,32),1); shifted.paste(5,(6,3),mask)
            with self.assertRaises(AssertionError): fit.verify_plate_ink(shifted,text)

    def test_heavy_stems_and_open_dense_counters(self):
        # Each syllable retains a solid 2x2 stem; dense initials have open
        # one-pixel counters instead of unconditional dilation/emboldening.
        for ch in set(''.join(fit.PLATE_LABELS)):
            m = fit.plate_glyph(ch)
            self.assertTrue(any(all(m.getpixel((x+dx,y+dy)) for dx in (0,1) for dy in (0,1)) for y in range(m.height-1) for x in range(m.width-1)),ch)
        for ch in ('통','룸'):
            m=fit.plate_glyph(ch)
            self.assertEqual([bool(m.getpixel((5,y))) for y in range(7)], [True,True,False,True,False,True,True])

    def test_only_declared_compressed_allocations_change(self):
        allowed = bytearray(len(self.rom))
        for off in BIG + SMALL + (0x5B9474,):
            original, capacity = lz77_decompress(self.original, off)
            result, used = lz77_decompress(self.rom, off)
            self.assertEqual(len(original), len(result))
            self.assertLessEqual(used, capacity)
            allowed[off:off + capacity] = b'\1' * capacity
        self.assertFalse(any(a != b and not permitted for a, b, permitted in zip(self.original, self.rom, allowed)))


if __name__ == '__main__':
    unittest.main()
