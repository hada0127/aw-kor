"""The new terrain atlas must not expose an old ROM's empty reserved space."""
from contextlib import ExitStack, contextmanager
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import part2_terrain_movement_labels as T

spec = importlib.util.spec_from_file_location('terrain_editor_test', T.ROOT / 'tools/sprite_editor/server.py')
SE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SE)
scene_spec = importlib.util.spec_from_file_location('terrain_scene_editor_test', T.ROOT / 'tools/scene_editor/server.py')
CE = importlib.util.module_from_spec(scene_spec)
scene_spec.loader.exec_module(CE)


class TerrainEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (T.ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        cls.sprite = next(s for s in json.loads((T.ROOT / 'data/objlabel_sprites.json').read_text())['sprites'] if s['id'] == T.ASSET_ID)
        cls.writes = T.expected_writes(cls.original)
        cls.installed = bytearray(cls.original)
        for a, data in cls.writes:
            cls.installed[a:a + len(data)] = data
        cls.generated = SE.decode_from_rom(cls.installed, cls.sprite)

    @contextmanager
    def editor(self, rom, record=None):
        with tempfile.TemporaryDirectory(dir=T.ROOT / 'temp', prefix='terrain_editor_') as directory:
            root = Path(directory)
            override = root / 'overrides.json'
            override.write_text(json.dumps({T.ASSET_ID: record} if record else {}))
            with ExitStack() as stack:
                for name, value in [('OVERRIDES_PATH', override), ('EDIT_DIR', root)]:
                    stack.enter_context(patch.object(SE, name, value))
                stack.enter_context(patch.object(SE, 'CMP_DIR', root / 'compare'))
                stack.enter_context(patch.object(SE, 'rom_bytes', return_value=self.original))
                stack.enter_context(patch.object(SE, 'patched_bytes', return_value=rom))
                stack.enter_context(patch.object(SE, 'sprite_by_id', return_value=self.sprite))
                stack.enter_context(patch.object(SE, 'get_layout', return_value=None))
                stack.enter_context(patch.object(SE, 'palette_for', return_value=[[i * 17] * 3 for i in range(16)]))
                yield object.__new__(SE.Handler), override

    def test_old_and_missing_rom_use_reviewed_generated_canvas(self):
        for rom in (self.original, b''):
            with self.editor(rom) as (handler, _):
                result = handler._tile({'id': [T.ASSET_ID]})
                self.assertTrue(result['ok'])
                self.assertEqual((result['width'], result['height']), (40, 112))
                self.assertEqual(result['indices'], self.generated[0])
                self.assertTrue(any(any(row) for row in result['indices']))

    def test_original_comparison_preserves_all_native_body_pixels_and_empty_tails(self):
        with self.editor(self.original):
            grid, w, h, _ = SE.decode_indices(self.sprite)
        self.assertEqual((w, h), (40, 112))
        native, _, _ = SE.ES.tiles_to_indices(self.original[0x454494:0x454494 + 7 * 256], 4)
        self.assertEqual([row[:32] for row in grid], native)
        self.assertTrue(all(row[32:] == [0] * 8 for row in grid))

    def test_installed_user_atlas_is_not_regenerated(self):
        rom = bytearray(self.installed)
        rom[T.ATLAS] ^= 1
        with self.editor(bytes(rom)):
            actual = SE.decode_current_indices(self.sprite)
        self.assertEqual(actual, SE.decode_from_rom(rom, self.sprite))
        self.assertNotEqual(actual, self.generated)

    def test_partial_installation_get_and_save_fail_without_writing(self):
        for address in (T.CAVE, T.ATLAS, T.SITES[0][0]):
            rom = bytearray(self.original)
            rom[address] ^= 1
            with self.editor(bytes(rom)) as (handler, override):
                before = override.read_bytes()
                result = handler._tile({'id': [T.ASSET_ID]})
                self.assertFalse(result['ok'])
                saved = handler._save({'id': T.ASSET_ID, 'indices': self.generated[0]})
                self.assertFalse(saved['ok'])
                self.assertIn('타일을 확인', saved['error'])
                self.assertEqual(override.read_bytes(), before)

    def test_explicit_saved_edit_survives_old_rom_get_and_resave(self):
        grid = copy.deepcopy(self.generated[0]); grid[0][0] ^= 1
        with self.editor(self.original, {'indices': grid}) as (handler, override):
            result = handler._tile({'id': [T.ASSET_ID]})
            self.assertTrue(result['edited']); self.assertEqual(result['indices'], grid)
            saved = handler._save({'id': T.ASSET_ID, 'indices': grid})
            self.assertTrue(saved['ok'], saved)
            self.assertEqual(json.loads(override.read_text())[T.ASSET_ID]['indices'], grid)

    def test_metadata_permutation_drift_is_not_silently_used(self):
        bad = copy.deepcopy(self.sprite)
        bad['labels'][0]['perm'][0] = 69
        with self.editor(self.original):
            self.assertIsNone(SE.decode_current_indices(bad))
            self.assertIsNone(SE.decode_indices(bad))

    def test_preview_uses_generated_current_and_real_native_but_not_fake_patched_image(self):
        with self.editor(self.original):
            self.assertEqual(SE.current_tiles(self.sprite), SE.encode_indices(self.generated[0], 40, 112))
            self.assertTrue(SE.render_compare_png(T.ASSET_ID, 'orig').startswith(b'\x89PNG'))
            self.assertIsNone(SE.render_compare_png(T.ASSET_ID, 'patched'))
        with self.editor(bytes(self.installed)):
            self.assertTrue(SE.render_compare_png(T.ASSET_ID, 'patched').startswith(b'\x89PNG'))

    def test_both_compare_apis_use_native_pixels_and_only_offer_installed_image(self):
        native_edit = bytearray(self.installed)
        native_edit[T.ATLAS:T.ATLAS + 2240] = self.original[0x454494:0x454494 + 7 * 256] + bytes(7 * 64)
        partial = bytearray(self.original); partial[T.CAVE] ^= 1
        cases = [('missing', b'', False, False),
                 ('old', self.original, False, False),
                 ('installed', bytes(self.installed), True, True),
                 ('native_edit', bytes(native_edit), True, False),
                 ('partial', bytes(partial), False, False)]
        for name, rom, available, changed in cases:
            with self.subTest(name=name), self.editor(rom) as (handler, _), patch.object(CE, 'SE', SE):
                responses = [handler._compare({'id': [T.ASSET_ID]}),
                             object.__new__(CE.Handler)._compare_data(T.ASSET_ID, self.sprite)]
                for response in responses:
                    self.assertTrue(response['ok'])
                    self.assertEqual(bool(response['patched_url']), available)
                    self.assertEqual(response['build_changed'], changed)
                    self.assertFalse(response['has_edit'])
                self.assertEqual(SE.render_compare_png(T.ASSET_ID, 'patched') is not None, available)


if __name__ == '__main__':
    unittest.main()
