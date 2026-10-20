"""Approved 2026-10-14 title logo geometry and font regression checks."""
import hashlib
import sys
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aw_fonts
import build_title_hangul as title
import qa_visual_regions as visual


class TitleB32Tests(unittest.TestCase):
    def test_select_english_band_cleared_with_protected_pixels(self):
        rom = Path("original/Game Boy Wars Advance 1+2 (Japan).gba").read_bytes()
        original, _ = title.lz77_decompress(rom, title.SELECT_OBJ_LZ77_OFF)
        patched = bytearray(original)
        title.patch_select_residual_tiles(patched)
        changed = 0
        trailing_band_pixels = 0
        for _idx, sx, sy, w, h, base, _pal in title.SELECT_RESIDUAL_SPRITES:
            for ly in range(h):
                for lx in range(w):
                    x, y = sx + lx, sy + ly
                    tile = base + (ly // 8) * (w // 8) + lx // 8
                    offset = tile * 32 + (ly % 8) * 4 + (lx % 8) // 2
                    shift = 4 if lx & 1 else 0
                    before = (original[offset] >> shift) & 15
                    after = (patched[offset] >> shift) & 15
                    if 184 <= x < 200 and 124 <= y < 141:
                        trailing_band_pixels += before != 0
                    edited = _idx != 22 and ((200 <= x < 221 and 28 <= y < 36) or (56 <= x < 200 and 124 <= y < 141))
                    if edited:
                        self.assertEqual(after, 0, (x, y))
                    else:
                        self.assertEqual(after, before, (x, y))
                    changed += before != after
        self.assertGreater(changed, 0)
        self.assertGreater(trailing_band_pixels, 0)

    def test_select_lower_tm_preserved_from_jp(self):
        rom = Path("original/Game Boy Wars Advance 1+2 (Japan).gba").read_bytes()
        original, _ = title.lz77_decompress(rom, title.SELECT_OBJ_LZ77_OFF)
        patched = bytearray(original)
        title.patch_select_residual_tiles(patched)
        tm = next(sprite for sprite in title.SELECT_RESIDUAL_SPRITES if sprite[0] == 22)
        _idx, _sx, _sy, w, h, base, _pal = tm
        for y in range(h):
            for x in range(w):
                tile = base + (y // 8) * (w // 8) + x // 8
                offset = tile * 32 + (y % 8) * 4 + (x % 8) // 2
                shift = 4 if x & 1 else 0
                self.assertEqual((patched[offset] >> shift) & 15,
                                 (original[offset] >> shift) & 15, (x, y))

    def test_shared_badge_removed_and_tm_retained(self):
        rom = Path("original/Game Boy Wars Advance 1+2 (Japan).gba").read_bytes()
        tile_data, _ = title.lz77_decompress(rom, title.TITLE_OBJ_LZ77_OFF)
        tile_data = bytearray(tile_data)
        title.patch_title_residual_tiles(tile_data)

        def pixel(x, y):
            for _idx, sx, sy, w, h, base, _pal in title.TITLE_BACKDROP_SPRITES:
                if sx <= x < sx + w and sy <= y < sy + h:
                    lx, ly = x - sx, y - sy
                    tile = base + (ly // 8) * (w // 8) + lx // 8
                    value = tile_data[tile * 32 + (ly % 8) * 4 + (lx % 8) // 2]
                    return (value >> (4 if lx & 1 else 0)) & 0xF
            self.fail(f"no backdrop sprite at {(x, y)}")

        for y in range(9, 28):
            for x in range(52, 191):
                self.assertEqual(pixel(x, y), 0, (x, y))
        for dy, row in enumerate(title.TM_PIXEL_PATTERN):
            for dx, mark in enumerate(row):
                if mark != ".":
                    self.assertEqual(pixel(213 + dx, 35 + dy), int(mark, 16))

    def test_five_okdandan_placements(self):
        self.assertEqual(hashlib.sha256(Path(aw_fonts.okdandan_path()).read_bytes()).hexdigest(),
                         aw_fonts.OKDANDAN_SHA256)
        with mock.patch.object(title, "draw_mock_a_logo", wraps=title.draw_mock_a_logo) as draw:
            layers = {
                "shared": title.make_title_index_layer(),
                "select_top": title.make_select_index_layer(),
                "part1": title.make_part1_index_layer(),
                "part2": title.make_part2_index_layer(),
            }
        layers["select_bottom"] = layers["select_top"]
        self.assertEqual(draw.call_count, 5)
        self.assertEqual([call.args[1] for call in draw.call_args_list],
                         ["어드밴스워즈"] + ["어드밴스 워즈"] * 4)
        self.assertEqual([call.args[2] for call in draw.call_args_list],
                         [(23, 24, 211, 53), (17, 14, 204, 52),
                          (25, 91, 212, 124), (17, 18, 207, 60),
                          (19, 21, 207, 52)])
        for name, layer in layers.items():
            with self.subTest(name=name):
                self.assertIn("sha256=", visual.assert_title_logo_golden(name, layer))

    def test_blank_and_shrunk_logos_fail(self):
        layer = title.make_part2_index_layer()
        blank = Image.new("L", layer.size)
        with self.assertRaisesRegex(AssertionError, "blank"):
            visual.assert_title_logo_golden("part2", blank)
        tiny = Image.new("L", layer.size)
        tiny.paste(layer.crop((20, 23, 207, 53)).resize((91, 16)), (70, 26))
        with self.assertRaisesRegex(AssertionError, "height"):
            visual.assert_title_logo_golden("part2", tiny)

    def test_wrong_font_sha_fails_closed(self):
        with mock.patch.object(aw_fonts, "OKDANDAN", Path(__file__)):
            with self.assertRaisesRegex(AssertionError, "unexpected OkDanDan-Bold SHA-256"):
                title.make_title_index_layer()


if __name__ == "__main__":
    unittest.main()
