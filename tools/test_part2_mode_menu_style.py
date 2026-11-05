"""Native plate geometry and palette regressions for mode-select graphics."""
import unittest
import os
import hashlib
from PIL import Image
import hangul_pixel_fit as fit
from pathlib import Path
from aw_fonts import obj_canvas, hadasans_path
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

    def test_large_plate_font_source(self):
        self.assertEqual(Path(hadasans_path()).name, 'HadaSans-Bold.otf')

    def test_original_plate_boundaries(self):
        for off in BIG + SMALL:
            big = off in BIG
            a = obj_canvas(lz77_decompress(self.original, off)[0], 2 if big else 4, 8 if big else 4, 4 if big else 2)
            live = fit.plate_address(self.rom, off) if big else off
            b = obj_canvas(lz77_decompress(self.rom, live)[0], 2 if big else 4, 8 if big else 4, 4 if big else 2)
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

    def test_mode_select_header_art_is_not_erased(self):
        """The shared 0x541BB8 alphabet supplies MODE★SELECT at screen top left.

        Traced b19: loader 0x08373DEC (literal 0x373E7C) decompresses the
        20-glyph alphabet; MODE*SELECT copies glyphs M,O,D,E,*,S,L,C,T to OBJ
        tiles 320.. Only the campaign callers may use a Korean copy.
        """
        import struct
        import part2_campaign_header_atlas as hdr
        rom = Path(os.environ['AW_TEST_ROM']).read_bytes() if os.environ.get('AW_TEST_ROM') else self.rom
        native, consumed = lz77_decompress(self.original, 0x541BB8)
        self.assertEqual(rom[0x541BB8:0x541BB8 + consumed], self.original[0x541BB8:0x541BB8 + consumed])
        self.assertEqual(struct.unpack_from('<I', rom, hdr.ATLAS_LITERAL)[0], 0x08541BB8)
        for tile in tuple(range(8, 16)) + tuple(range(72, 80)):
            start = tile * 32
            self.assertEqual(lz77_decompress(rom, 0x541BB8)[0][start:start + 32], native[start:start + 32], tile)
        if not os.environ.get('AW_TEST_ROM'):
            return
        # The string itself must stay ASCII from the alphabet (b11..b18 wrote
        # SJIS Korean here, which the OBJ header renderer cannot draw).
        self.assertEqual(rom[0x8FC2AC:0x8FC2B8], b'MODE*SELECT\0')
        # Final ROM: campaign callers use the Korean copy, nobody else does.
        self.assertEqual(rom.count(struct.pack('<I', 0x08000000 + hdr.ATLAS_DEST)), 1)
        copy = lz77_decompress(rom, hdr.ATLAS_DEST)[0]
        for ch in 'CMPIGN':
            at = hdr.glyph_index(self.original, ch) * hdr.GLYPH
            self.assertNotEqual(copy[at:at + hdr.GLYPH], native[at:at + hdr.GLYPH], ch)
        for ch in 'AHRD*':
            at = hdr.glyph_index(self.original, ch) * hdr.GLYPH
            self.assertEqual(copy[at:at + hdr.GLYPH], native[at:at + hdr.GLYPH], ch)
        for src in hdr.CALLS:
            self.assertEqual(hdr._bl_target(rom, src), 0x08000000 + hdr.LOADER_DEST)
        callers = [a for a in range(0, len(rom) - 4, 2)
                   if (struct.unpack_from('<H', rom, a)[0] >> 11) == 0x1E
                   and (struct.unpack_from('<H', rom, a + 2)[0] >> 11) == 0x1F
                   and hdr._bl_target(rom, a) == 0x08000000 + hdr.LOADER_DEST]
        self.assertEqual(sorted(callers), sorted(hdr.CALLS))

    def test_header_drawer_strings_stay_in_ascii_alphabet(self):
        """All 19 header-loader callers draw ASCII alphabet strings (JP text)."""
        import part2_campaign_header_atlas as hdr
        hdr.verify_header_strings(self.original)
        rom = bytearray(Path(os.environ['AW_TEST_ROM']).read_bytes()) if os.environ.get('AW_TEST_ROM') else bytearray(self.original)
        self.assertEqual(hdr.verify_header_strings(rom), 19)
        expected = {0x332B26: b'NOW*LOADING', 0x333F96: b'LINK*MODE', 0x3490EC: b'WARS*SHOP',
                    0x365482: b'RULE*SETTING', 0x365BAE: b'TEAM*SETTING', 0x36F76C: b'SOUND*ROOM',
                    0x37D74A: b'SYOGUN*SELECT', 0x382122: b'MODE*SELECT', 0x386866: b'MAP*SELECT',
                    0x388A34: b'COLOR*EDIT'}
        strings = hdr.header_strings(rom)
        for caller, text in expected.items():
            self.assertEqual(strings[caller][1], text, hex(caller))
        # Mutation: an SJIS Korean header (b11..b19 defect) is rejected.
        bad = bytearray(rom)
        bad[0x8FC2C8:0x8FC2D0] = '통신모드'.encode('cp949')
        with self.assertRaises(AssertionError):
            hdr.verify_header_strings(bad)

    def test_unselected_small_bars_match_r4_goldens(self):
        golden = {
            0x5B8E44: 'f2c62f60e53031fac83a6a327898eb533cb5f6f5a72400b6982c4c701f507c86',
            0x5B9050: 'e19bc09129e956a33fce9c4339113b4f8f80a677ad4082a06839e97af2cdb6ff',
            0x5B9378: '88c34a4d6e7390265f0552d947e8c1f16a78ecf6e6ff30b828cd373149bad5e7',
            0x5B8F48: '424bd02a8131033fb5b2d0a7c04b0a12d2112d1b7aced2b517034372c8fe18e4',
            0x5B917C: 'fac8249a533cfad896d31a21d45b86d5aac52869f4507885cd60b22a5b25f071',
            0x5B9280: '0de621b3b2b81968dfb645e78db22bd6fe8c039819f11dab9940b61d20fa0ff6',
        }
        for off, digest in golden.items():
            raw = lz77_decompress(self.rom, off)[0]
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest, hex(off))

    def test_selected_plate_subtitle_has_text_width_white_box(self):
        golden = {
            0x5B7930: '10245baded86a2a2afb7ea69b301f22af61020f028ea0113f8045bc0c3a45146',
            0x5B7CB0: 'a50dbe7732faf01100ceeea3923200fe9476969e9edbd1a25528f586d038cf6a',
            0x5B7F38: '5b7c03ebb017da4813ebbd748ff5d856be90bc82afd44a015ff555eed63624e2',
            0x5B82B4: 'fb3c5c431a20d183b1d3546bfc3d675ed4753ce69b2c0880bcb8601ed752ee93',
            0x5B8564: '400049a16ddee8c9dc5760164f26d8d7fa066acabba1dc228bd207fefb9c898a',
            0x5B8850: 'fb4bb23e94198eee4914d007d7ff63769d12689e3a266e66ad5575da3238d411',
            0x5B8B20: 'f58aba6e1ed5e267125ed2785807f6c85953e5c5fe3bc2823f402e1bb055f46c',
        }
        for off in BIG:
            live = fit.plate_address(self.rom, off)
            raw = lz77_decompress(self.rom, live)[0]
            self.assertEqual(hashlib.sha256(raw).hexdigest(), golden[off], hex(off))
            p = obj_canvas(raw, 2, 8, 4)
            cols = [x for x in range(4, 124) if any(p[y][x] == 1 for y in range(23, 30))]
            self.assertTrue(cols, hex(off))
            left, right = min(cols), max(cols)
            self.assertTrue(all(p[y][x] == 5 for y in range(23, 30) for x in (left-1, right+1, 4, 123)), hex(off))
            self.assertTrue(any(p[y][x] == 5 for y in range(23, 30) for x in range(left, right+1)), hex(off))
            self.assertLess(right-left+1, 120, hex(off))

    def test_large_ink_clears_lower_band(self):
        for off in BIG:
            p = obj_canvas(lz77_decompress(self.rom, fit.plate_address(self.rom, off))[0], 2, 8, 4)
            ys = [y for y in range(2, 22) if any(5 <= v <= 12 for v in p[y][4:124])]
            self.assertGreater(max(ys) - min(ys) + 1, 16, hex(off))
            self.assertEqual(set(p[22][3:125]), {1})

    def test_complete_ink_on_shared_baseline_in_final_rom(self):
        rom = Path(os.environ['AW_TEST_ROM']).read_bytes() if os.environ.get('AW_TEST_ROM') else self.rom
        for off, text in zip(BIG, fit.PLATE_LABELS):
            grid = obj_canvas(lz77_decompress(rom, fit.plate_address(rom, off))[0], 2, 8, 4)
            layer = Image.new('L', (128, 32)); layer.putdata([v for row in grid for v in row])
            records = fit.verify_plate_ink(layer, text)
            ox, oy = fit.PLATE_ORIGIN
            for ch, (a, b, c, d) in records:
                self.assertEqual((b, d), (0, 20), (text, ch))
                ref = fit.plate_glyph(ch, fit.plate_width_scale(text))
                # Match all rows, including 받침, against an oversized render.
                unclipped = Image.new('L', (160, 64)); unclipped.paste(ref, (20, 20))
                self.assertEqual(layer.crop((a+ox,b+oy,c+ox,d+oy)).point(lambda v:255 if v in fit.PLATE_BODY_INDICES else 0).tobytes(), unclipped.crop((20,20,20+ref.width,40)).tobytes())
            # JP treatment: body uses the x-band indices 5..12, edges only 2/3.
            used = {grid[y][x] for y in range(2, 22) for x in range(4, 124)}
            self.assertTrue(used <= {1, 2, 3} | set(fit.PLATE_BODY_INDICES), (text, used))
            idx = fit.plate_syllable_indices(text)
            self.assertEqual(idx, sorted(idx), text)
            self.assertEqual(len(set(idx)), len(text), text)
            self.assertEqual(used & set(fit.PLATE_BODY_INDICES), set(idx), text)
            self.assertTrue(all(grid[22][x] == 1 for x in range(4,124)))
            self.assertTrue(any(grid[y][x] == 1 for y in range(23,30) for x in range(4,124)))
            self.assertTrue(all(grid[y][x] in (1, 2, 3, 5) for y in range(23,30) for x in range(4,124)))

    def test_clipped_or_shifted_syllable_rejected(self):
        for text in ('편집', '통신'):
            good = Image.new('L', (128,32), 1)
            fit.paint_plate(good, text)
            fit.verify_plate_ink(good, text)
            mask, records = fit.plate_line(text)
            ox, oy = fit.PLATE_ORIGIN
            for ch, (a,b,c,d) in records:
                bad = good.copy()
                for x in range(a+ox,c+ox): bad.putpixel((x,d+oy-1),1)
                with self.assertRaises(AssertionError): fit.verify_plate_ink(bad,text)
            shifted = Image.new('L',(128,32),1); shifted.paste(good.crop((0,0,128,31)),(0,1))
            with self.assertRaises(AssertionError): fit.verify_plate_ink(shifted,text)
            flat = good.point(lambda v: 5 if v in fit.PLATE_BODY_INDICES else v)
            with self.assertRaises(AssertionError): fit.verify_plate_ink(flat,text)

    def test_heavy_stems_and_open_dense_counters(self):
        # Each syllable retains a solid 2x2 stem and the outline's own jamo
        # components/counters at the final 20px band (no merged jamo).
        for text in fit.PLATE_LABELS:
            scale = fit.plate_width_scale(text)
            self.assertLessEqual(scale, fit.PLATE_MAX_WIDTH_SCALE)
            for ch in text:
                m = fit.plate_glyph(ch, scale)
                self.assertEqual(m.height, fit.PLATE_HEIGHT)
                self.assertTrue(any(all(m.getpixel((x+dx,y+dy)) for dx in (0,1) for dy in (0,1)) for y in range(m.height-1) for x in range(m.width-1)),ch)
                self.assertEqual(fit.plate_topology(m), fit.plate_outline_topology(ch), ch)

    def test_plates_fill_the_jp_cap_band(self):
        # JP words fill x=4..123, y=2..21; Korean fills the 20px cap band and
        # most of the width allowed by natural Hangul proportions (declared scale).
        for off, text in zip(BIG, fit.PLATE_LABELS):
            grid = obj_canvas(lz77_decompress(self.rom, fit.plate_address(self.rom, off))[0], 2, 8, 4)
            pts = [(x, y) for y in range(2, 22) for x in range(4, 124) if grid[y][x] in fit.PLATE_BODY_INDICES]
            ys = [y for _, y in pts]; xs = [x for x, _ in pts]
            self.assertEqual((min(ys), max(ys)), (2, 21), text)
            self.assertGreaterEqual(max(xs) - min(xs) + 1, 55, text)

    def test_only_declared_compressed_allocations_change(self):
        allowed = bytearray(len(self.rom))
        for off in BIG + SMALL + (0x5B9474,):
            original, capacity = lz77_decompress(self.original, off)
            result, used = lz77_decompress(self.rom, off)
            self.assertEqual(len(original), len(result))
            self.assertLessEqual(used, capacity)
            allowed[off:off + capacity] = b'\1' * capacity
        for off in BIG:
            live = fit.plate_address(self.rom, off)
            if live != off:
                raw, used = lz77_decompress(self.rom, live)
                self.assertEqual(len(raw), 2048)
                allowed[live:live + used] = b'\1' * used
                for loc in fit.PLATE_LOADERS[off]:
                    allowed[loc:loc + 4] = b'\1' * 4
        self.assertFalse(any(a != b and not permitted for a, b, permitted in zip(self.original, self.rom, allowed)))



class CampaignHeaderEditorTest(unittest.TestCase):
    """Sprite editor edits the Korean copy; the JP alphabet is read-only."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location('sprite_editor_hdr_test', ROOT / 'tools/sprite_editor/server.py')
        cls.SE = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.SE)
        cls.original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_editor_table_points_at_korean_copy(self):
        import part2_campaign_header_atlas as hdr
        self.assertEqual(self.SE.PART2_CAMPAIGN_HEADER_OFFSETS, {hdr.ATLAS_DEST})
        self.assertEqual(self.SE.PART2_CAMPAIGN_HEADER_COPY_ID, hdr.EDITOR_ID)
        self.assertIn(hdr.ATLAS, self.SE.PART2_HEADER_ALPHABET_READONLY_OFFSETS)
        layout = self.SE.build_layout_cells({'offset_int': hdr.ATLAS_DEST, 'type': 'lz77', 'tile_cols': 32})
        self.assertEqual(layout['fallback'], 'part2_campaign_header_oam')
        with self.assertRaisesRegex(ValueError, '읽기 전용'):
            self.SE.validate_sprite_edit({'offset_int': hdr.ATLAS, 'type': 'lz77'}, [[0] * 256] * 40, None)

    def test_editor_rejects_invalid_copy_edits_before_saving(self):
        import part2_campaign_header_atlas as hdr
        from build_korean_full import patch_part2_campaign_header_obj
        from export_sprites import tiles_to_indices
        rom = bytearray(self.original)
        patch_part2_campaign_header_obj(rom, self.original)
        raw = lz77_decompress(rom, hdr.ATLAS_DEST)[0]
        sprite = {'id': hdr.EDITOR_ID, 'offset_int': hdr.ATLAS_DEST, 'type': 'lz77',
                  'tile_cols': 32, 'comp_size': hdr.REGION[1] - hdr.ATLAS_DEST}

        def edited(glyph):
            grid, _, _ = tiles_to_indices(raw, 32)
            tile = hdr.glyph_index(self.original, glyph) * 8
            y, x = (tile // 32) * 8 + 3, (tile % 32) * 8 + 3
            grid[y][x] = (grid[y][x] + 1) % 16
            return grid
        for glyph in ('A', 'Y', 'S'):
            with self.subTest(glyph=glyph):
                with self.assertRaisesRegex(ValueError, '캠페인 헤더 사본 편집 거부'):
                    self.SE.validate_sprite_edit(sprite, edited(glyph), None, rom_snapshot=bytes(rom))
        enc, w, h = self.SE.validate_sprite_edit(sprite, edited('C'), None, rom_snapshot=bytes(rom))
        self.assertEqual((w, h), (256, 40))
        # The save endpoint must not persist a rejected edit.
        import json, tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp', prefix='hdr-save-') as tmp:
            ov = Path(tmp) / 'ov.json'
            ov.write_text('{}')
            with patch.object(self.SE, 'OVERRIDES_PATH', ov), \
                 patch.object(self.SE, 'sprite_by_id', lambda sid: sprite), \
                 patch.object(self.SE, 'decode_current_indices', lambda sp: self.SE.decode_from_rom(bytes(rom), sp)):
                handler = self.SE.Handler.__new__(self.SE.Handler)
                result = handler._save({'id': hdr.EDITOR_ID, 'indices': edited('A'), 'palette': None})
            self.assertFalse(result['ok'])
            self.assertEqual(json.loads(ov.read_text()), {})

    def test_one_override_snapshot_feeds_both_passes(self):
        import json, tempfile
        import part2_campaign_header_atlas as hdr
        from build_korean_full import OverrideSnapshot, apply_sprite_overrides, patch_part2_campaign_header_obj
        from export_sprites import tiles_to_indices
        rom = bytearray(self.original)
        patch_part2_campaign_header_obj(rom, self.original)
        raw = lz77_decompress(rom, hdr.ATLAS_DEST)[0]

        def grid_for(glyph):
            grid, _, _ = tiles_to_indices(raw, 32)
            tile = hdr.glyph_index(self.original, glyph) * 8
            y, x = (tile // 32) * 8 + 3, (tile % 32) * 8 + 3
            grid[y][x] = (grid[y][x] + 1) % 16
            return grid
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp', prefix='hdr-snap-') as tmp:
            path = Path(tmp) / 'ov.json'
            path.write_text(json.dumps({hdr.EDITOR_ID: {'indices': grid_for('C')}}))
            snap = OverrideSnapshot(str(path))
            # An editor save lands mid-build: invalid A edit.
            path.write_text(json.dumps({hdr.EDITOR_ID: {'indices': grid_for('A')}}))
            built = bytearray(self.original)
            patch_part2_campaign_header_obj(built, self.original, override_snapshot=snap)
            self.assertNotEqual(lz77_decompress(built, hdr.ATLAS_DEST)[0], raw)
            report = Path(tmp) / 'report.json'
            apply_sprite_overrides(built, ov_path=str(path), report_path=str(report), ov_snapshot=snap)
            self.assertEqual(json.loads(report.read_text())['override_sha256'], snap.sha256)
            with self.assertRaisesRegex(AssertionError, 'changed during the build'):
                snap.verify_unchanged()

    def test_build_applies_copy_edit_and_rejects_jp_glyph_edit(self):
        import json, tempfile
        import part2_campaign_header_atlas as hdr
        from build_korean_full import patch_part2_campaign_header_obj
        from export_sprites import tiles_to_indices
        rom = bytearray(self.original)
        patch_part2_campaign_header_obj(rom, self.original)
        raw = lz77_decompress(rom, hdr.ATLAS_DEST)[0]
        grid, _, _ = tiles_to_indices(raw, 32)
        def pixel(glyph):
            tile = hdr.glyph_index(self.original, glyph) * 8
            return (tile // 32) * 8 + 3, (tile % 32) * 8 + 3
        y, x = pixel('C')
        grid[y][x] = (grid[y][x] + 1) % 16
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp', prefix='hdr-editor-') as tmp:
            path = Path(tmp) / 'ov.json'
            path.write_text(json.dumps({hdr.EDITOR_ID: {'indices': grid}}))
            edited = bytearray(self.original)
            patch_part2_campaign_header_obj(edited, self.original, override_path=str(path))
            self.assertNotEqual(lz77_decompress(edited, hdr.ATLAS_DEST)[0], raw)
            self.assertEqual(edited[0x541BB8:0x541BB8 + 1125], self.original[0x541BB8:0x541BB8 + 1125])
            grid2, _, _ = tiles_to_indices(raw, 32)
            y, x = pixel('A')
            grid2[y][x] = (grid2[y][x] + 1) % 16
            path.write_text(json.dumps({hdr.EDITOR_ID: {'indices': grid2}}))
            with self.assertRaisesRegex(AssertionError, "JP glyph 'A'"):
                patch_part2_campaign_header_obj(bytearray(self.original), self.original, override_path=str(path))


if __name__ == '__main__':
    unittest.main()
