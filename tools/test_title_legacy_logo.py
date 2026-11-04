"""Legacy 「게임보이 워즈 어드밴스」 title logo regression checks.

2026-11-04 user decision: the Part 1 / Part 2 / shared 1+2 / select title
logos go back to the pre-b32 art (f94e690 reverse-applied), including the
「한글판」 badge and the shared-title TM erase.
"""
import hashlib
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aw_fonts
import build_title_hangul as title

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_ROM = ROOT / "original/Game Boy Wars Advance 1+2 (Japan).gba"
LEGACY_TEXT = "게임보이 워즈 어드밴스"

# sha256 of Image.tobytes() for each generated 240x160 index layer.
LAYER_GOLDENS = {
    "shared": "6fb82b5b0e0f01dd2de4a17ac9e4f0085c67bfeed21df9085416dfdd6682906b",
    "select": "2740bcb8feec9f2e36b6a365b06be9d0f5e949049ee7198213c50dbb59af965c",
    "part1": "bbca9ed2b3012e7acc51aeeda0f58d3d308bf4094fc2fddf0e0925ff76fd53d7",
    "part2": "7d14f9aab71d4ecef633dbaa449190d706633d9240dcb4b00503c11b364bf0c7",
    "badge": "10677554f954f7283f450df74dedb1ca3b33c9735bc0e608b51c1175b093a121",
}

LAYER_FACTORIES = {
    "shared": "make_title_index_layer",
    "select": "make_select_index_layer",
    "part1": "make_part1_index_layer",
    "part2": "make_part2_index_layer",
    "badge": "make_title_residual_overlay_layer",
}

# The four OBJ LZ77 blocks the logo layers are written into (select holds the
# top and bottom logos).
LOGO_BLOCKS = {
    "shared": "TITLE_OBJ_LZ77_OFF",
    "select": "SELECT_OBJ_LZ77_OFF",
    "part1": "PART1_TITLE_OBJ_LZ77_OFF",
    "part2": "PART2_TITLE_OBJ_LZ77_OFF",
}


def sprite_pixel(tile_data, sprites, x, y, tile_subtract=0):
    for sprite in sprites:
        _idx, sx, sy, w, h, base, _pal = sprite
        if sx <= x < sx + w and sy <= y < sy + h:
            lx, ly = x - sx, y - sy
            tile = base - tile_subtract + (ly // 8) * (w // 8) + lx // 8
            value = tile_data[tile * 32 + (ly % 8) * 4 + (lx % 8) // 2]
            return (value >> (4 if lx & 1 else 0)) & 0xF
    return None


class LegacyTitleLogoTests(unittest.TestCase):
    def test_font_is_okdandan(self):
        self.assertEqual(hashlib.sha256(Path(aw_fonts.okdandan_path()).read_bytes()).hexdigest(),
                         aw_fonts.OKDANDAN_SHA256)

    def test_layer_goldens(self):
        for name, factory in LAYER_FACTORIES.items():
            with self.subTest(name=name):
                layer = getattr(title, factory)()
                self.assertEqual(layer.size, (240, 160))
                self.assertIsNotNone(layer.getbbox(), name)
                self.assertEqual(hashlib.sha256(layer.tobytes()).hexdigest(), LAYER_GOLDENS[name])

    def test_logo_text_is_legacy_wording(self):
        self.assertFalse(hasattr(title, "draw_mock_a_logo"))
        with mock.patch.object(title, "draw_index_text", wraps=title.draw_index_text) as index_text, \
                mock.patch.object(title, "draw_select_logo_text", wraps=title.draw_select_logo_text) as select_text:
            title.make_title_index_layer()
            title.make_select_index_layer()
            title.make_part1_index_layer()
            title.make_part2_index_layer()
        texts = [c.args[1] for c in index_text.call_args_list] + [c.args[1] for c in select_text.call_args_list]
        # shared + part1 via draw_index_text; select top/bottom + part2 via draw_select_logo_text
        self.assertEqual(index_text.call_count, 2)
        self.assertEqual(select_text.call_count, 3)
        self.assertEqual(texts, [LEGACY_TEXT] * 5)

    def test_logo_blocks_decode_and_accept_layers(self):
        rom = ORIGINAL_ROM.read_bytes()
        for name, attr in LOGO_BLOCKS.items():
            with self.subTest(name=name):
                dec = title.lz77_decompress(rom, getattr(title, attr))
                self.assertIsNotNone(dec, name)
        tile_data = bytearray(title.lz77_decompress(rom, title.TITLE_OBJ_LZ77_OFF)[0])
        layer = title.make_title_index_layer()
        title.patch_sprite_index_layer(tile_data, layer, title.TEXT_SPRITES)
        written = 0
        for y in range(160):
            for x in range(240):
                px = sprite_pixel(tile_data, title.TEXT_SPRITES, x, y)
                if px is not None:
                    self.assertEqual(px, layer.getpixel((x, y)), (x, y))
                    written += px != 0
        self.assertGreater(written, 500)

    def test_shared_title_badge_present_and_tm_erased(self):
        rom = ORIGINAL_ROM.read_bytes()
        tile_data = bytearray(title.lz77_decompress(rom, title.TITLE_OBJ_LZ77_OFF)[0])
        title.patch_title_residual_tiles(tile_data)
        badge = title.make_title_residual_overlay_layer()
        badge_pixels = 0
        for y in range(9, 28):
            for x in range(52, 191):
                want = badge.getpixel((x, y))
                if want == 0:
                    continue
                got = sprite_pixel(tile_data, title.TITLE_BACKDROP_SPRITES, x, y)
                if got is not None:
                    self.assertEqual(got, want, (x, y))
                    badge_pixels += 1
        self.assertGreater(badge_pixels, 1000)
        for y in range(40, 55):  # rect (208, 40, 230, 55) is end-exclusive
            for x in range(208, 230):
                got = sprite_pixel(tile_data, title.TITLE_BACKDROP_SPRITES, x, y)
                if got is not None:
                    self.assertEqual(got, 0, (x, y))

    def test_select_residual_band_without_b32_tm_exception(self):
        rom = ORIGINAL_ROM.read_bytes()
        original = title.lz77_decompress(rom, title.SELECT_OBJ_LZ77_OFF)[0]
        patched = bytearray(original)
        title.patch_select_residual_tiles(patched)
        for _idx, sx, sy, w, h, base, _pal in title.SELECT_RESIDUAL_SPRITES:
            for ly in range(h):
                for lx in range(w):
                    x, y = sx + lx, sy + ly
                    tile = base + (ly // 8) * (w // 8) + lx // 8
                    offset = tile * 32 + (ly % 8) * 4 + (lx % 8) // 2
                    shift = 4 if lx & 1 else 0
                    after = (patched[offset] >> shift) & 15
                    before = (original[offset] >> shift) & 15
                    if (200 <= x < 221 and 28 <= y < 36) or (56 <= x < 184 and 124 <= y < 141):
                        self.assertEqual(after, 0, (x, y))
                    else:
                        self.assertEqual(after, before, (x, y))

    def test_wrong_font_sha_fails_closed(self):
        with mock.patch.object(aw_fonts, "OKDANDAN", Path(__file__)):
            with self.assertRaisesRegex(AssertionError, "unexpected OkDanDan-Bold SHA-256"):
                title.make_title_index_layer()


if __name__ == "__main__":
    unittest.main()
