"""Both editor endpoints preserve title-art ownership across dictionary changes."""
from contextlib import ExitStack, contextmanager
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import part2_power_title_glyphs as titles
import test_part2_power_title_glyphs as glyph_tests
from export_sprites import tiles_to_indices


def load_editor(name):
    spec = importlib.util.spec_from_file_location('power_test_' + name, titles.ROOT / 'tools' / name / 'server.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SE = load_editor('sprite_editor')
CE = load_editor('scene_editor')


class PowerTitleEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        glyph_tests.PowerTitleTests.setUpClass()
        cls.fixture = glyph_tests.PowerTitleTests
        cls.sprite = {'id': titles.ASSET_ID, 'offset_int': titles.OFFSET,
                      'offset': hex(titles.OFFSET), 'type': 'lz77', 'tile_cols': 32,
                      'size': titles.RAW_SIZE, 'comp_size': titles.SLOT_SIZE, 'source': 'scan_lz77'}
        cls.palette = [[i * 17] * 3 for i in range(16)]
        cls.grid = tiles_to_indices(cls.fixture.rendered, 32)[0]

    @contextmanager
    def editor(self, kind, record=None):
        api = SE if kind == 'sprite' else CE
        shared = SE if kind == 'sprite' else CE.SE
        state = {'rom': bytes(self.fixture.patched), 'names': dict(self.fixture.names)}
        with tempfile.TemporaryDirectory(dir=titles.ROOT / 'temp', prefix='power_binding_') as directory:
            root = Path(directory)
            override = root / 'overrides.json'
            override.write_text(json.dumps({titles.ASSET_ID: record} if record else {}))
            edit_dir = root / 'edits'
            edit_dir.mkdir()
            original_art = edit_dir / (titles.ASSET_ID + '.png')
            original_art.write_bytes(b'preserve-personal-png')
            with ExitStack() as stack:
                for name, value in [('OVERRIDES_PATH', override), ('EDIT_DIR', edit_dir)]:
                    stack.enter_context(patch.object(shared, name, value))
                stack.enter_context(patch.object(shared, 'patched_bytes', side_effect=lambda: state['rom']))
                stack.enter_context(patch.object(shared, 'rom_bytes', return_value=self.fixture.original))
                stack.enter_context(patch.object(shared, '_power_title_context', side_effect=lambda: (state['names'], self.fixture.codes)))
                stack.enter_context(patch.object(shared, 'sprite_by_id', return_value=self.sprite))
                stack.enter_context(patch.object(shared, 'get_layout', return_value=None))
                stack.enter_context(patch.object(shared, 'palette_for', return_value=self.palette))
                handler = object.__new__(api.Handler)
                get = (lambda: handler._tile({'id': [titles.ASSET_ID]})) if kind == 'sprite' else (
                    lambda: handler._tile_data(titles.ASSET_ID, self.sprite, {}))
                save = handler._save if kind == 'sprite' else handler._sprite_save
                yield state, shared, get, save, override, original_art

    def changed_name_state(self, state):
        # All glyphs/order stay identical, but one full name changes. A digest
        # of just the glyph count or dictionary bytes would miss this change.
        names = dict(state['names'])
        address = max(names)
        names[address] = '흑파도'
        rom = bytearray(state['rom'])
        payload = b''.join(self.fixture.codes[ch].to_bytes(2, 'big') for ch in names[address])
        rom[address:titles.NAMES_END] = payload.ljust(titles.NAMES_END - address, b'\0')
        state.update(names=names, rom=bytes(rom))

    def test_both_editors_load_echo_save_binding_and_reload_unbuilt_personal_edit(self):
        for kind in ('sprite', 'scene'):
            with self.subTest(kind=kind), self.editor(kind) as (state, shared, get, save, override, art):
                view = get()
                self.assertTrue(view['ok'], view)
                token = view[titles.BINDING_KEY]
                user_grid = [row[:] for row in view['indices']]
                user_grid[255][255] = 1
                result = save({'id': titles.ASSET_ID, 'indices': user_grid, 'palette': self.palette,
                               titles.BINDING_KEY: token})
                self.assertTrue(result['ok'], result)
                stored = json.loads(override.read_text())[titles.ASSET_ID]
                self.assertEqual(stored[titles.BINDING_KEY], token)
                self.assertEqual(stored['indices'], user_grid)
                self.assertNotEqual(art.read_bytes(), b'preserve-personal-png')
                # The ROM has not been built since save. The correctly bound
                # personal record is still the authoritative editable artwork.
                fresh = get()
                self.assertTrue(fresh['ok'], fresh)
                self.assertTrue(fresh['edited'])
                self.assertEqual(fresh['indices'], user_grid)

    def test_load_then_dictionary_or_name_build_change_rejects_save_without_touching_files(self):
        for kind in ('sprite', 'scene'):
            with self.subTest(kind=kind), self.editor(kind) as (state, shared, get, save, override, art):
                view = get()
                old_token = view[titles.BINDING_KEY]
                before = (override.read_bytes(), art.read_bytes())
                self.changed_name_state(state)
                self.assertNotEqual(old_token, titles.dictionary_binding(state['rom'], state['names'], self.fixture.codes))
                with patch.object(shared, 'validate_sprite_edit', side_effect=AssertionError('stale request reached compression')):
                    result = save({'id': titles.ASSET_ID, 'indices': view['indices'], 'palette': self.palette,
                                   titles.BINDING_KEY: old_token})
                self.assertFalse(result['ok'])
                self.assertIn('보존', result['error'])
                self.assertEqual(before, (override.read_bytes(), art.read_bytes()))

    def test_dictionary_change_during_validation_is_checked_again_before_write(self):
        for kind in ('sprite', 'scene'):
            with self.subTest(kind=kind), self.editor(kind) as (state, shared, get, save, override, art):
                view = get()
                before = (override.read_bytes(), art.read_bytes())
                def changed_during_compression(*args, **kwargs):
                    self.changed_name_state(state)
                    return self.fixture.rendered, 256, 256
                with patch.object(shared, 'validate_sprite_edit', side_effect=changed_during_compression):
                    result = save({'id': titles.ASSET_ID, 'indices': view['indices'], 'palette': self.palette,
                                   titles.BINDING_KEY: view[titles.BINDING_KEY]})
                self.assertFalse(result['ok'])
                self.assertIn('저장 중', result['error'])
                self.assertEqual(before, (override.read_bytes(), art.read_bytes()))

    def test_legacy_or_stale_saved_art_is_not_relabelled_or_removed_by_either_endpoint(self):
        valid = titles.dictionary_binding(self.fixture.patched, self.fixture.names, self.fixture.codes)
        for kind in ('sprite', 'scene'):
            for binding in (None, 'v1:' + '0' * 64):
                record = {'indices': self.grid}
                if binding is not None:
                    record[titles.BINDING_KEY] = binding
                with self.subTest(kind=kind, binding=binding), self.editor(kind, record) as (state, shared, get, save, override, art):
                    before = (override.read_bytes(), art.read_bytes())
                    self.assertFalse(get()['ok'])
                    result = save({'id': titles.ASSET_ID, 'indices': self.grid, 'palette': self.palette,
                                   titles.BINDING_KEY: valid})
                    self.assertFalse(result['ok'])
                    self.assertIn('보존', result['error'])
                    self.assertEqual(before, (override.read_bytes(), art.read_bytes()))

    def test_missing_build_and_old_japanese_atlas_never_receive_a_new_binding(self):
        for kind in ('sprite', 'scene'):
            for rom in (b'', bytes(self.fixture.base), self.fixture.original):
                with self.subTest(kind=kind, rom=sha256(rom).hexdigest()), self.editor(kind) as (state, shared, get, save, override, art):
                    state['rom'] = rom
                    before = (override.read_bytes(), art.read_bytes())
                    view = get()
                    self.assertFalse(view['ok'])
                    self.assertNotIn(titles.BINDING_KEY, view)
                    self.assertEqual(before, (override.read_bytes(), art.read_bytes()))

    def test_binding_includes_same_count_order_changes_and_every_name(self):
        original = titles.dictionary_binding(self.fixture.patched, self.fixture.names, self.fixture.codes)
        state = {'rom': bytes(self.fixture.patched), 'names': dict(self.fixture.names)}
        self.changed_name_state(state)
        same_order = titles.bind_dictionary(state['rom'], state['names'], self.fixture.codes)
        self.assertEqual(same_order, self.fixture.dictionary)
        self.assertNotEqual(original, titles.dictionary_binding(state['rom'], state['names'], self.fixture.codes))
        names = dict(self.fixture.names)
        names[titles.NAMES_START] = '적기'
        dictionary = ''.join(dict.fromkeys(''.join(names.values())))
        rom = bytearray(self.fixture.patched)
        first_end = list(names)[1]
        encode = lambda s: b''.join(self.fixture.codes[ch].to_bytes(2, 'big') for ch in s)
        rom[titles.NAMES_START:first_end] = encode('적기').ljust(first_end - titles.NAMES_START, b'\0')
        rom[titles.DICTIONARY:titles.DICTIONARY + titles.DICTIONARY_SIZE] = encode(dictionary).ljust(titles.DICTIONARY_SIZE, b'\0')
        self.assertEqual(len(dictionary), 57)
        self.assertNotEqual(original, titles.dictionary_binding(rom, names, self.fixture.codes))

    def test_builder_rejects_stale_or_missing_binding_before_any_asset_write(self):
        from build_korean_full import apply_sprite_overrides
        for binding in (None, 'v1:' + '0' * 64):
            with self.subTest(binding=binding), tempfile.TemporaryDirectory(dir=titles.ROOT / 'temp', prefix='power_stale_build_') as directory:
                directory = Path(directory)
                record = {'indices': self.grid}
                if binding is not None:
                    record[titles.BINDING_KEY] = binding
                override = directory / 'overrides.json'
                override.write_text(json.dumps({titles.ASSET_ID: record}))
                before = override.read_bytes()
                rom = bytearray(self.fixture.patched)
                result = apply_sprite_overrides(rom, ov_path=str(override), report_path=str(directory / 'report.json'),
                                               power_title_context=(self.fixture.names, self.fixture.codes))
                self.assertEqual((result['applied'], result['skipped']), (0, 1))
                self.assertEqual(rom, self.fixture.patched)
                self.assertEqual(override.read_bytes(), before)
                self.assertIn('보존', json.loads((directory / 'report.json').read_text())['records'][0]['reason'])

    def test_capture_checks_binding_even_when_applied_bytes_equal_automatic_output(self):
        payload = bytes(self.fixture.patched[titles.OFFSET:titles.OFFSET + titles.SLOT_SIZE])
        result = {'expected_writes': [(titles.ASSET_ID, titles.OFFSET, payload)]}
        with self.assertRaisesRegex(AssertionError, 'dictionary binding'):
            titles.capture_regions(self.fixture.patched, self.fixture.original, self.fixture.names, self.fixture.codes,
                                   editor_result=result)
        result['dictionary_bindings'] = {titles.ASSET_ID: titles.dictionary_binding(
            self.fixture.patched, self.fixture.names, self.fixture.codes)}
        result['expected_writes'][0] = (titles.ASSET_ID, titles.OFFSET, payload[:-1] + b'\1')
        with self.assertRaisesRegex(AssertionError, 'byte extent'):
            titles.capture_regions(self.fixture.patched, self.fixture.original, self.fixture.names, self.fixture.codes,
                                   editor_result=result)

    def test_unrelated_sprite_save_does_not_require_title_binding(self):
        other = {'id': 'raw_test', 'offset_int': 0x20, 'offset': '0x20', 'type': 'raw4bpp',
                 'tile_cols': 1, 'size': 32, 'source': 'test'}
        for kind in ('sprite', 'scene'):
            with self.subTest(kind=kind), self.editor(kind) as (state, shared, get, save, override, art):
                with patch.object(shared, 'sprite_by_id', return_value=other):
                    result = save({'id': other['id'], 'indices': [[1] * 8 for _ in range(8)], 'palette': self.palette})
                self.assertTrue(result['ok'], result)
                self.assertNotIn(titles.BINDING_KEY, json.loads(override.read_text())[other['id']])

    def test_actual_frontend_functions_echo_loaded_binding(self):
        script = Path(__file__).with_name('test_power_title_editor_transport.js')
        result = subprocess.run(['node', str(script)], cwd=titles.ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('5 transport checks PASS', result.stdout)


if __name__ == '__main__':
    unittest.main()
