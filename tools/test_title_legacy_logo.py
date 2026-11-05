"""Legacy 「게임보이 워즈 어드밴스」 title logo regression checks.

2026-11-04 user decision: the Part 1 / Part 2 / shared 1+2 / select title
logos go back to the pre-b32 art (f94e690 reverse-applied), including the
「한글판」 badge and the shared-title TM erase.
"""
import hashlib
import json
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
    "shared": "aa689821c9d8cda3b00dc09c3d15e953bf03a6372aa7c8ee5cec586a4f4c913b",
    "select": "242845a62624df9551c3d0410b82076e902f95ddcc4fa0d40cb677606a943c3a",
    "part1": "bbca9ed2b3012e7acc51aeeda0f58d3d308bf4094fc2fddf0e0925ff76fd53d7",
    "part2": "e1445f5ebd7376af28cc9ec87ee3f2f1fdb4f065dc05ad7ff225dca55d097968",
    "badge": "10677554f954f7283f450df74dedb1ca3b33c9735bc0e608b51c1175b093a121",
}

# These are the occupied-pixel masks of the restored fixB layers. Edge shades
# may change, but the lettering, badge and prompt silhouettes must not move.
OCCUPANCY_GOLDENS = {
    "shared": "2b5d2d271ff758d941d6a9e7f05466418d50edcde587a95a82ad2015df2768ca",
    "select": "229abfaa58b1e69d120b6013001eb1f1a1e2db7c30d8d2d3e52d7f3bf11abbeb",
    "part1": "ee67fdd46bfd28183b0752dcd70e2f26ec56c38c328244d94470af0a3eee9eb2",
    "part2": "23be974b65037f66569f067905a8032114dcb2a940074d217dc8e15c9a85c5d5",
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
    def test_part1_header_ink_and_protected_english(self):
        for _, offset, text, size in (title.PART1_MAIN_HEADER_BLOCKS +
                                      title.PART1_SUBMENU_LOGO_BLOCKS):
            with self.subTest(offset=hex(offset)):
                layer = title.make_part1_header_with_footer(offset, text, size)
                footer_y = title.part1_footer_y(offset)
                korean = layer.crop((0, 0, 80, footer_y)).getbbox()
                # gfx T5: Galmuri header family (no edge-to-edge proof for the
                # 64/16 OBJ pair): ink stays inside the first 64 px cell.
                self.assertTrue(title.PART1_HEADER_FAMILY_GALMURI)
                self.assertGreaterEqual(korean[3] - korean[1], 12)
                self.assertLess(korean[2], 64)
                native_footer = title.original_part1_footer(offset)
                self.assertEqual(layer.crop((0, footer_y, 80, 32)).tobytes(),
                                 native_footer.crop((0, footer_y, 80, 32)).tobytes())

    def test_part1_authoritative_option_overrides_match_generator(self):
        from export_sprites import tiles_to_indices
        overrides = json.loads((ROOT / 'data/sprites_overrides.json').read_text())
        for sid in ('lz77_00C03880', 'lz77_00C03AF0'):
            with self.subTest(sid=sid):
                record = overrides[sid]
                offset = int(sid[5:], 16)
                _, _, label, size = next(row for row in title.PART1_MODE_OPTION_BLOCKS if row[1] == offset)
                raw = title.option_layer_to_tiles(title.make_part1_option_block(label, size))
                grid, width, height = tiles_to_indices(raw, record['width'] // 8)
                self.assertEqual((width, height), (record['width'], record['height']))
                self.assertEqual(grid, record['indices'])
                self.assertLessEqual(len(title.lz77_compress_optimal(raw, vram_safe=True)),
                                     title.PART1_MODE_OPTION_BLOCK_CAPACITY[offset])

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
                if name in OCCUPANCY_GOLDENS:
                    occupied = bytes(bool(index) for index in layer.tobytes())
                    self.assertEqual(hashlib.sha256(occupied).hexdigest(), OCCUPANCY_GOLDENS[name])

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
