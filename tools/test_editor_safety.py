"""Regression tests for editor path, storage and renderer save gates."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def load_editor(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / name / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SE = load_editor("sprite_editor")
DE = load_editor("dialogue_editor")
CE = load_editor("scene_editor")
import editor_storage
import preview_capture


class EditorSafetyTests(unittest.TestCase):
    def test_known_story_fragment_is_readonly_and_ignores_stale_override(self):
        from build_dialogue_map import display_ko_for
        self.assertEqual(display_ko_for(0xA078A0, 'あ、', '과거 CSV', '아、',
                                       {}, {}, {}, {}, {0xA078A0: '과거 편집'}, {},
                                       kind='known-story-fragment'), '아、')
        self.assertEqual(display_ko_for(0xA0283C, 'まだ', '과거 CSV', None,
                                       {}, {}, {}, {}, {}, {}, kind='known-story-fragment'), '')
        member = {'address': '0x00A078A0', 'ko': '아、', 'ja': 'あ、', 'kind': 'known-story-fragment'}
        snapshot = {'data': {'lines': [member]}, 'by_addr': {member['address']: member},
                    'overrides': {member['address']: '과거 편집'}}
        with patch.object(DE, 'known_fragment_addresses', return_value=frozenset([member['address']])), \
             patch.object(CE.DE, 'known_fragment_addresses', return_value=frozenset([member['address']])):
            self.assertEqual(DE.current_ko(member['address'], snapshot=snapshot), member['ko'])
            self.assertEqual(CE.effective_member_ko(member, snapshot['overrides']), member['ko'])
            budget = CE.line_budget(member)
            self.assertFalse(budget['editable'])
            self.assertIn('고정 문구', budget['reason'])
            with patch.object(DE, 'load_groups', return_value={'groups': [{'members': [member]}]}), \
                 patch.object(DE, 'load_json', return_value=snapshot['data']), \
                 patch.object(DE.B, 'load_dialogue_overrides', return_value=snapshot['overrides']):
                group = object.__new__(DE.Handler)._groups({})['lines'][0]
                self.assertEqual(group['members'][0]['ko'], member['ko'])
                self.assertFalse(group['members'][0]['editable'])
            for module in (DE, CE):
                result = object.__new__(module.Handler)._save_line(
                    {'address': member['address'], 'ko': '변경'}, snapshot=snapshot)
                self.assertFalse(result['ok'])
                self.assertIn('고정 문구', result['error'])

    def test_structured_command_rows_reject_fragment_saves_without_writes(self):
        member = {'address': '0x00D8FD5A', 'ko': '메뉴에 공격 명령이'}
        self.assertEqual(DE.current_ko(member['address'], member), member['ko'])
        self.assertEqual(CE.effective_member_ko(member, {}), member['ko'])
        from qa_text_fit import load_direct_patch_texts
        self.assertEqual(load_direct_patch_texts()[0xD8FD5A], (0xD8FD80, '메뉴에 공격 명령이'))
        self.assertEqual(load_direct_patch_texts()[0xD8FBF6], (0xD8FC16, '이 보병으로 공격'))
        self.assertEqual(load_direct_patch_texts()[0xD8FC46], (0xD8FC6A, '이 보병을 골라 줘'))
        for address in ('0x00D8FD5A', '0x00D8FD6E', '0x00D8FBF6', '0x00D8FC46'):
            self.assertFalse(CE.line_budget({'address': address})['editable'])
            for module in (DE, CE):
                result = object.__new__(module.Handler)._save_line({'address': address, 'ko': '바뀐 문구'})
                self.assertFalse(result['ok'])
                self.assertIn('복합 대사', result['error'])

    def test_whole_row_assembly_keeps_command_once_and_following_newline(self):
        from build_dialogue_groups import decode_gap, korean_segments
        source = bytes.fromhex('338d558c8230720a09')
        gap = decode_gap(source, 0, len(source))
        self.assertEqual([s['address'] for s in gap], ['0x00000000', '0x00000006', '0x00000007', '0x00000008'])
        segments = [{'kind': 'frag', 'address': '0x00D8FD5A'},
                    {'kind': 'var', 'address': '0x00D8FD66', 'default': '攻撃'},
                    {'kind': 'frag', 'address': '0x00D8FD6E'},
                    {'kind': 'newline', 'address': '0x00D8FD81'},
                    {'kind': 'frag', 'address': '0x00D8FD83'}]
        members = [{'address': '0x00D8FD5A'}, {'address': '0x00D8FD6E'}, {'address': '0x00D8FD83'}]
        self.assertEqual(korean_segments(segments, members), [segments[0], segments[3], segments[4]])

    def test_extracted_script_text_uses_tsv_but_keeps_separate_prologue_writer(self):
        from build_dialogue_map import display_ko_for
        address = 0xD902DC
        args = (address, '原文', 'CSV', '실제 빌드', {address: '보호 문구'}, {}, {},
                {address: '기본 문구'}, {address: '과거 편집'}, {})
        self.assertEqual(display_ko_for(*args, kind='script:turn end advice row'), '보호 문구')
        self.assertEqual(display_ko_for(*args, kind='part2-prologue-inline-renderer'), '기본 문구')
        self.assertEqual(display_ko_for(*args[:-1], {address: '전용 표시'}, kind='script:row'), '전용 표시')
        legacy = 0xD8FD5A
        self.assertEqual(display_ko_for(legacy, '', '', None, {legacy: '메뉴에'}, {}, {},
                                       {legacy: '메뉴에 공격 명령이'}, {}, {}, kind='script:attack menu row'),
                         '메뉴에 공격 명령이')

    def setUp(self):
        directory = tempfile.TemporaryDirectory(dir=ROOT / 'temp')
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / 'data').mkdir()
        (root / 'temp').mkdir()
        storage_root = patch.object(editor_storage, 'ROOT', root)
        storage_root.start()
        self.addCleanup(storage_root.stop)
        for module in (DE, CE.DE):
            intent_path = patch.object(module, 'EDITOR_INTENTS_PATH', root / 'data/editor_override_intents.json')
            intent_path.start()
            self.addCleanup(intent_path.stop)

    def test_display_authority_is_visible_and_rejects_both_save_endpoints(self):
        addr = '0x00A2C1B8'
        expected = DE.B.load_display_overrides()[int(addr, 16)]
        self.assertEqual(DE.current_ko(addr), expected)
        self.assertEqual(CE.effective_member_ko({'address': addr, 'ko': '다른 문구'}, {}), expected)
        self.assertFalse(CE.line_budget({'address': addr})['editable'])
        for module in (DE, CE):
            result = object.__new__(module.Handler)._save_line({'address': addr, 'ko': expected})
            self.assertFalse(result['ok'])
            self.assertIn('전용 표시', result['error'])
        with patch.object(DE, 'atomic_write_group', side_effect=AssertionError('unexpected write')):
            result = object.__new__(DE.Handler)._save_lines({'lines': [
                {'address': addr, 'ko': expected, 'confirm_current': True}]})
            self.assertFalse(result['ok'])
            self.assertIn('전용 표시', result['error'])

    def test_empty_and_nonstring_edits_fail_before_any_write(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as directory:
            root = Path(directory)
            path = root / 'dialogue.json'
            path.write_text('{"lines":[{"address":"0x00A07528","ko":"기존"}]}')
            before = path.read_bytes()
            for module in (DE, CE):
                authority = DE if module is DE else CE.DE
                with patch.object(authority, 'DIALOGUE_PATH', path), patch.object(authority, 'atomic_write_group', side_effect=AssertionError('unexpected write')):
                    for value in ('', '　 ', None, 42):
                        result = object.__new__(module.Handler)._save_line({'address': '0x00A07528', 'ko': value})
                        self.assertFalse(result['ok'], result)
                        self.assertIn('빈 문구' if isinstance(value, str) else '문자열', result['error'])
                        self.assertEqual(path.read_bytes(), before)

    def test_existing_override_confirmation_writes_only_receipt_once(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as directory:
            root = Path(directory)
            paths = {name: root / name for name in ('DIALOGUE_PATH', 'GROUPS_PATH', 'OVERRIDES_PATH', 'ADDRESS_TEXT_OVERRIDES_TSV', 'EDITOR_INTENTS_PATH')}
            paths['DIALOGUE_PATH'].write_text('{"lines":[{"address":"0x00A07528","ko":"기존"}]}')
            paths['GROUPS_PATH'].write_text('{"groups":[]}')
            paths['OVERRIDES_PATH'].write_text('{"0x00A07528":"기존"}')
            paths['ADDRESS_TEXT_OVERRIDES_TSV'].write_text('address\ttext\n0x00AFF123\t보호\n')
            before = {p: p.read_bytes() for name,p in paths.items() if name != 'EDITOR_INTENTS_PATH'}
            handler = object.__new__(DE.Handler)
            with patch.multiple(DE, **paths):
                self.assertEqual(handler._save_lines({'lines': [{'address': '0x00A07528', 'ko': '기존'}]}), {'ok': True, 'saved': 0, 'confirmed': 0, 'unchanged': 1, 'warnings': []})
                self.assertEqual(handler._save_lines({'lines': [{'address': '0x00A07528', 'ko': '기존', 'confirm_current': True}]}), {'ok': True, 'saved': 0, 'confirmed': 1, 'unchanged': 0, 'warnings': []})
                self.assertEqual(handler._save_lines({'lines': [{'address': '0x00A07528', 'ko': '기존', 'confirm_current': True}]}), {'ok': True, 'saved': 0, 'confirmed': 0, 'unchanged': 1, 'warnings': []})
                self.assertEqual(before, {p: p.read_bytes() for p in before})
                self.assertEqual(DE.B.load_editor_override_intents(paths['EDITOR_INTENTS_PATH']), {'0x00A07528': DE.B.editor_text_digest('기존')})

                paths['OVERRIDES_PATH'].write_text('{}')
                paths['EDITOR_INTENTS_PATH'].unlink()
                result = handler._save_lines({'lines': [{'address': '0x00A07528', 'ko': '기존'}]})
                self.assertEqual(result, {'ok': True, 'saved': 0, 'confirmed': 0, 'unchanged': 1, 'warnings': []})
                self.assertEqual(paths['OVERRIDES_PATH'].read_text(), '{}')
                self.assertFalse(paths['EDITOR_INTENTS_PATH'].exists())
                result = handler._save_lines({'lines': [{'address': '0x00A07528', 'ko': '기존', 'confirm_current': True}]})
                self.assertEqual(result, {'ok': True, 'saved': 1, 'confirmed': 0, 'unchanged': 0, 'warnings': []})
                self.assertEqual(json.loads(paths['OVERRIDES_PATH'].read_text())['0x00A07528'], '기존')

    def test_bteam_unchanged_confirmation_does_not_create_receipt(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as directory:
            root = Path(directory)
            dialogue = root / 'dialogue.json'
            overrides = root / 'overrides.json'
            dialogue.write_text('{"lines":[{"address":"0x00A29390","ko":"바주카병"}]}')
            overrides.write_text('{"0x00A29390":"바주카병"}')
            with patch.object(DE, 'DIALOGUE_PATH', dialogue), patch.object(DE, 'OVERRIDES_PATH', overrides), patch.object(DE, 'atomic_write_group', side_effect=AssertionError('Bteam no-op wrote data')):
                result = object.__new__(DE.Handler)._save_lines({'lines': [{'address': '0x00A29390', 'ko': '바주카병', 'confirm_current': True}]})
                self.assertEqual(result, {'ok': True, 'saved': 0, 'confirmed': 0, 'unchanged': 1, 'warnings': []})

    def test_unchanged_group_preserves_distinct_source_authority_byte_for_byte(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as directory:
            root = Path(directory)
            paths = {name: root / name for name in ('DIALOGUE_PATH', 'GROUPS_PATH', 'OVERRIDES_PATH', 'ADDRESS_TEXT_OVERRIDES_TSV')}
            paths['DIALOGUE_PATH'].write_text('{"lines":[{"address":"0x00AFF123","ko":"표시"}]}')
            paths['GROUPS_PATH'].write_text('{"groups":[]}')
            paths['OVERRIDES_PATH'].write_text('{"0x00AFF123":"원래 긴 번역"}')
            paths['ADDRESS_TEXT_OVERRIDES_TSV'].write_text('address\ttext\n0x00AFF123\t표시\n')
            before = {p: p.read_bytes() for p in paths.values()}
            handler = object.__new__(DE.Handler)
            with patch.multiple(DE, **paths), patch.object(handler, '_save_line', return_value={'ok': True, 'address': '0x00AFF123', 'ko': '표시'}):
                result = handler._save_lines({'lines': [{}]})
            self.assertEqual(result, {'ok': True, 'saved': 0, 'confirmed': 0, 'unchanged': 1, 'warnings': []})
            self.assertEqual(before, {p: p.read_bytes() for p in paths.values()})

    def test_authority_snapshot_refreshes_and_cannot_be_mutated(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as directory:
            path = Path(directory) / 'authority.tsv'
            path.write_text('address\ttext\n0x00AFF123\t전\n')
            with patch.object(DE.B, 'load_address_text_overrides_tsv', wraps=DE.B.load_address_text_overrides_tsv) as reader:
                for _ in range(10):
                    snapshot = DE.address_text_snapshot(path)
                    self.assertEqual(snapshot[2]['0x00AFF123'], '전')
                self.assertEqual(reader.call_count, 1)
                with self.assertRaises(TypeError):
                    snapshot[2]['0x00AFF123'] = '오염'
                replacement = path.with_suffix('.new')
                replacement.write_text('address\ttext\n0x00AFF123\t후\n')
                replacement.replace(path)
                self.assertEqual(DE.address_text_snapshot(path)[2]['0x00AFF123'], '후')
                self.assertEqual(reader.call_count, 2)

    def test_bteam_noop_compares_current_value_not_baseline(self):
        address = '0x00A29390'
        baseline = DE.load_json(ROOT / 'data/bteam_baseline.json', {})['overrides'][address]
        for module, authority in [(DE, DE), (CE, CE.DE)]:
            handler = object.__new__(module.Handler)
            with patch.object(authority, 'current_ko', return_value='다름'):
                same = handler._save_line({'address': address, 'ko': '다름', 'dry_run': True})
                self.assertTrue(same.get('ok'), same)
                changed = handler._save_line({'address': address, 'ko': baseline, 'dry_run': True})
                self.assertTrue(changed.get('bteam_confirm_required'), changed)
                self.assertEqual(changed['bteam_baseline'], baseline)

    def test_data_validation_failure_returns_json_error(self):
        class Handler:
            def _send(self, status, body): return status, body
            @editor_storage.editor_request
            def request(self): raise ValueError('authority.tsv:3: duplicate address')
        status, body = Handler().request()
        self.assertEqual(status, 500)
        self.assertFalse(body['ok'])
        self.assertIn('authority.tsv:3: duplicate address', body['error'])

    def test_editor_tsv_readers_refuse_invalid_rows_without_rewriting(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as directory:
            path = Path(directory) / 'authority.tsv'
            for tail in ['bad-address\t값\n', '\t값\n', '0xAFF123\t중복\n']:
                source = 'address\ttext\n0x00AFF123\t정상\n' + tail
                path.write_text(source)
                for editor in (DE, CE):
                    with self.subTest(editor=editor.__name__, tail=tail), patch.object(editor, 'ADDRESS_TEXT_OVERRIDES_TSV', path):
                        with self.assertRaises(ValueError):
                            editor.address_text_overrides()
                        self.assertEqual(path.read_text(), source)

    def test_result_score_patch_changes_only_owned_atlas_entries(self):
        original = preview_capture.ORIG_ROM.read_bytes()
        rom = bytearray(original)
        with patch.object(DE.B, 'rec_objlabel'), patch.object(DE.B, 'rec_label_layout'):
            self.assertEqual(DE.B.patch_part1_result_score_labels(rom), 3)
            self.assertEqual(rom[:0xBEAF5C], original[:0xBEAF5C])
            self.assertEqual(rom[0xBEB0FC:], original[0xBEB0FC:])
            for start, end in [(0xBEAF5C, 0xBEAFDC), (0xBEAFDC, 0xBEB05C), (0xBEB05C, 0xBEB0FC)]:
                self.assertNotEqual(rom[start:end], original[start:end])
            with self.assertRaisesRegex(AssertionError, 'atlas source changed'):
                DE.B.patch_part1_result_score_labels(rom)

    def test_group_save_validates_all_before_writing_and_rolls_back_io_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as directory:
            root = Path(directory)
            paths = {name: root / name for name in ('DIALOGUE_PATH', 'GROUPS_PATH', 'OVERRIDES_PATH', 'ADDRESS_TEXT_OVERRIDES_TSV', 'EDITOR_INTENTS_PATH')}
            paths['DIALOGUE_PATH'].write_text('{"lines":[{"address":"0x00AFF123","ko":"전"}]}')
            paths['GROUPS_PATH'].write_text('{"groups":[{"members":[{"address":"0x00AFF123","ko":"전"}]}]}')
            paths['OVERRIDES_PATH'].write_text('{}')
            paths['EDITOR_INTENTS_PATH'].write_text('{}')
            paths['ADDRESS_TEXT_OVERRIDES_TSV'].write_text('address\ttext\n0x00AFF123\t전\n0x00AFF200\t" 인용 ""보존"" "\n')
            before = {path: path.read_bytes() for path in paths.values()}
            handler = object.__new__(DE.Handler)
            ok = {'ok': True, 'address': '0x00AFF123', 'ko': '후'}
            with patch.multiple(DE, **paths), patch.object(DE, '_GROUPS_CACHE', None), \
                 patch.object(DE, '_LOCK', threading.RLock()):
                with patch.object(handler, '_save_line', side_effect=[ok, {'ok': False, 'error': 'invalid'}]):
                    result = handler._save_lines({'lines': [{}, {}]})
                self.assertFalse(result['ok'])
                self.assertEqual(before, {path: path.read_bytes() for path in paths.values()})
                replace = editor_storage.os.replace
                calls = []
                def fail_second(source, target):
                    calls.append(source)
                    if str(source).endswith('.new') and len(calls) >= 2:
                        raise OSError('injected publication failure')
                    return replace(source, target)
                with patch.object(handler, '_save_line', return_value=ok), patch.object(editor_storage.os, 'replace', side_effect=fail_second):
                    with self.assertRaisesRegex(OSError, 'injected publication'):
                        handler._save_lines({'lines': [{}]})
                self.assertEqual(before, {path: path.read_bytes() for path in paths.values()})
                with patch.object(handler, '_save_line', return_value=ok):
                    self.assertEqual(handler._save_lines({'lines': [{}]})['saved'], 1)
                self.assertEqual(json.loads(paths['OVERRIDES_PATH'].read_text())['0x00AFF123'], '후')
                self.assertEqual(DE.B.load_editor_override_intents(DE.EDITOR_INTENTS_PATH)['0x00AFF123'], DE.B.editor_text_digest('후'))
                self.assertEqual(DE.address_text_overrides()['0x00AFF123'], '후')
                self.assertEqual(DE.address_text_overrides()['0x00AFF200'], ' 인용 "보존" ')
                self.assertEqual(json.loads(paths['GROUPS_PATH'].read_text())['groups'][0]['members'][0]['ko'], '후')
                with patch.object(handler, '_save_line', return_value={**ok, 'ko': ''}):
                    cleared = handler._save_lines({'lines': [{}]})
                self.assertEqual(cleared['saved'], 1)
                self.assertEqual(DE.address_text_overrides()['0x00AFF123'], '')

    def test_preview_rejects_unknown_navigation(self):
        with self.assertRaisesRegex(ValueError, 'unknown preview navigation'):
            preview_capture._nav(Mock(), [['pres', 'A', 1]])

    def test_preview_named_cache_tracks_text_and_keeps_requested_sweep_frames(self):
        import qa_visual_regions
        from PIL import Image
        class Driver:
            def __init__(self, rom, directory, harness):
                self.directory = directory
            def shot(self, stem):
                im = Image.new('RGB', (240, 160), 'white')
                im.putpixel((0, 0), (0, 0, 0))
                im.save(self.directory / (stem + '.png'))
                return im
            def frames(self, count): pass
            def close(self): pass
        cv = {**preview_capture.CANVASES['part2_menu'], 'nav': [],
              'sweep': {'frames': [1, 2], 'score_box': [0, 0, 8, 8], 'keep_all': True}}
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as directory, \
             patch.object(preview_capture, 'CACHE', Path(directory)), \
             patch.dict(preview_capture.CANVASES, {'test': cv}), \
             patch.object(qa_visual_regions, 'MGBADriver', Driver):
            first = preview_capture.capture('가', canvas='test', out_name='named.png')
            second = preview_capture.capture('나', canvas='test', out_name='named.png')
            self.assertNotEqual(first['png'], second['png'])
            self.assertFalse(second['cached'])
            self.assertTrue(preview_capture.capture('나', canvas='test', out_name='named.png')['cached'])
            for item in first['sweep']['candidates']:
                self.assertTrue(Path(item['png']).is_file())
            self.assertEqual(list(Path(directory).glob('run_*')), [])

    def test_delayed_group_reader_cannot_pair_old_data_with_new_stamp(self):
        old_read = threading.Event()
        release_old = threading.Event()
        stamp = [1]
        errors = []
        def read_groups(*args):
            value = stamp[0]
            if value == 1:
                old_read.set()
                if not release_old.wait(5):
                    raise TimeoutError('reader was not released')
            return {'version': value}
        def delayed_read():
            try:
                self.assertEqual(DE.load_groups(), {'version': 1})
            except BaseException as exc:
                errors.append(exc)
        with patch.object(DE, '_GROUPS_CACHE', None), \
             patch.object(DE, 'file_stamp', side_effect=lambda path: stamp[0]), \
             patch.object(DE, 'load_json', side_effect=read_groups):
            worker = threading.Thread(target=delayed_read)
            worker.start()
            try:
                self.assertTrue(old_read.wait(5))
                stamp[0] = 2
                self.assertEqual(DE.load_groups(), {'version': 2})
            finally:
                release_old.set()
                worker.join(5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(DE.load_groups(), {'version': 2})
            self.assertEqual(DE._GROUPS_CACHE, (2, {'version': 2}))

    def test_preview_partial_rom_write_failure_cleans_its_directory(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "temp") as directory:
            cache = Path(directory)
            write = Path.write_bytes
            def fail_rom(path, data):
                if path.name == 'preview.gba':
                    write(path, data[:128])
                    raise OSError('injected disk write failure')
                return write(path, data)
            with patch.object(preview_capture, 'CACHE', cache), patch.object(Path, 'write_bytes', fail_rom):
                with self.assertRaisesRegex(OSError, 'injected disk write'):
                    preview_capture.capture('검증', canvas='part1_welcome', use_cache=False)
            self.assertEqual(list(cache.iterdir()), [])

    def test_group_and_slot_caches_refresh_after_external_replace(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "temp") as directory:
            groups = Path(directory) / 'groups.json'
            dialogue = Path(directory) / 'dialogue.json'
            dialogue.write_text('{"lines": []}')
            def publish(slot):
                staging = Path(directory) / 'new.json'
                staging.write_text(json.dumps({'groups': [{'members': [{'address': '0x00AFF123', 'slot': slot}]}]}))
                staging.replace(groups)
            publish(4)
            with patch.object(DE, 'GROUPS_PATH', groups), patch.object(DE, 'DIALOGUE_PATH', dialogue), \
                 patch.object(DE, '_GROUPS_CACHE', None), patch.object(DE, '_FALLBACK_SLOTS_CACHE', None):
                self.assertEqual(DE.fallback_slots()['0x00AFF123'], 4)
                publish(8)
                self.assertEqual(DE.load_groups()['groups'][0]['members'][0]['slot'], 8)
                self.assertEqual(DE.fallback_slots()['0x00AFF123'], 8)

    def test_icon_layout_gate_follows_relocated_pointer(self):
        import struct
        original = preview_capture.ORIG_ROM.read_bytes()
        rom = bytearray(original)
        DE.B.verify_editor_icon_layout(original, rom)
        address = 0xA2CA50
        pointer = DE.B.PART2_EDITOR_ICON_POINTERS[address]
        live = 0xF00000
        struct.pack_into('<I', rom, pointer, live + 0x08000000)
        rom[live:live + 4] = DE.B.PART2_EDITOR_ICON_PREFIX
        DE.B.verify_editor_icon_layout(original, rom)
        rom[live] = 0
        with self.assertRaisesRegex(AssertionError, 'live editor icon prefix'):
            DE.B.verify_editor_icon_layout(original, rom)

    def test_icon_menu_layout_prefix_is_not_translated_or_counted_as_free_space(self):
        import collections
        original = preview_capture.ORIG_ROM.read_bytes()
        for address, slot in DE.B.PART2_EDITOR_ICON_LABEL_SLOTS.items():
            self.assertEqual(original[address:address + 4], DE.B.PART2_EDITOR_ICON_PREFIX)
            budget = CE.line_budget({'address': hex(address), 'slot': slot})
            self.assertEqual(budget['content_slot'], slot - 4)
            self.assertEqual(budget['max_syllables'], (slot - 4) // 2)
            good = '가' * ((slot - 4) // 2)
            encoded, level = DE.B.encode_fit(good, slot, DE.syl_to_code_ints(),
                                            collections.Counter(), address)
            self.assertEqual(level, 0)
            self.assertEqual(encoded[:4], DE.B.PART2_EDITOR_ICON_PREFIX)
            self.assertEqual(len(encoded), slot)
            self.assertEqual(DE.B.encode_full_fidelity(good, DE.syl_to_code_ints(),
                                                     collections.Counter(), address), encoded)
            self.assertEqual(DE.B.encode_text('　　' + good, DE.syl_to_code_ints(),
                                             collections.Counter(), address), encoded)
            for module, function, key in ((DE, DE.validate_build_fit, 'ok'),
                                           (CE, CE.build_fit_budget, 'fits')):
                self.assertFalse(function(good + '가', slot, hex(address))[key])

    def test_part2_mode_help_punctuation_keeps_two_byte_alignment(self):
        import collections
        for address, text, slot in ((0xA2C144, '컴퓨터와 대전하여,점수가 기록됩니다', 40),
                                    (0xA2C25C, '친구와 연결해 대전/지도 교환 가능', 48)):
            encoded, level = DE.B.encode_fit(text, slot, DE.syl_to_code_ints(),
                                            collections.Counter(), address)
            self.assertEqual(level, 0)
            self.assertEqual(len(encoded) % 2, 0)
            self.assertNotIn(b',', encoded)
            self.assertNotIn(b'/', encoded)
            self.assertLessEqual(len(encoded), slot)

    def test_invalid_pixel_data_rejected_without_masking_or_truncating(self):
        valid = [[0] * 8 for _ in range(8)]
        self.assertEqual(SE.encode_indices(valid, 8, 8), bytes(32))
        for grid, w, h in [([[0] * 9 for _ in range(8)], 9, 8),
                           (valid[:-1], 8, 8), ([None] * 8, 8, 8)]:
            with self.subTest(w=w, h=h), self.assertRaises(ValueError):
                SE.encode_indices(grid, w, h)
        for value in (-1, 16, 1.5, True, "1", None):
            grid = [row[:] for row in valid]
            grid[4][3] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                SE.encode_indices(grid, 8, 8)

    def test_revert_unknown_ids_cannot_delete_files(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "temp") as directory:
            root = Path(directory)
            sentinel = root / "keep.png"
            sentinel.write_bytes(b"keep")
            edits = root / "edits"
            edits.mkdir()
            for module, method in ((SE, "_revert"), (CE, "_sprite_revert")):
                handler = object.__new__(module.Handler)
                helper = module if module is SE else module.SE
                with patch.object(helper, "EDIT_DIR", edits):
                    for sid in ("../keep", str(sentinel.with_suffix("")), "unknown"):
                        self.assertFalse(getattr(handler, method)({"id": sid})["ok"])
                        self.assertEqual(sentinel.read_bytes(), b"keep")

    def test_static_rejects_absolute_traversal_and_symlink(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "temp") as directory:
            root = Path(directory)
            private = root / "private.txt"
            private.write_text("private")
            static = root / "static"
            static.mkdir()
            (static / "escape.txt").symlink_to(private)
            (static / "ok.txt").write_text("public")
            for module, method in ((SE, "_static"), (DE, "_serve_static")):
                handler = object.__new__(module.Handler)
                handler._send = lambda code, body, *args: (code, body)
                with patch.object(module, "STATIC", static):
                    for rel in ("../private.txt", str(private), "escape.txt"):
                        self.assertEqual(getattr(handler, method)(rel)[0], 403)
                    self.assertEqual(getattr(handler, method)("missing.txt")[0], 404)

    def test_merged_children_rejected_before_any_save(self):
        address = "0x00D8FFF9"
        for module in (DE, CE):
            handler = object.__new__(module.Handler)
            with patch.object(module, "load_json", return_value={"lines": [{"address": address}]}):
                result = handler._save_line({"address": address, "ko": "변경"})
            self.assertFalse(result["ok"])
            self.assertEqual(result["owner_address"], "0x00D8FFE3")

    def test_actual_renderer_width_and_merged_owner_slot(self):
        # Part 1 converts alphanumerics to two-byte fullwidth glyphs.
        for module, function, ok_key in ((DE, DE.validate_build_fit, "ok"),
                                         (CE, CE.build_fit_budget, "fits")):
            result = function("A1", 4, "0x00D8FFE3")
            self.assertTrue(result[ok_key])
            self.assertEqual(result["encoded_len"], 4)
            self.assertEqual(module.member_slot("0x00D8FFE3"), 57)

    def test_unsupported_part2_quotes_return_actionable_validation_error(self):
        for function, ok_key in ((DE.validate_build_fit, 'ok'), (CE.build_fit_budget, 'fits')):
            for text in ('"브레이크"', "'브레이크'", '‘브레이크’'):
                result = function(text, 32, '0x00A0A014')
                self.assertFalse(result[ok_key])
                self.assertEqual(result['fit_level'], 99)
                self.assertIn('「 」', result['error'])
            result = function('「브레이크」', 32, '0x00A0A014')
            self.assertTrue(result[ok_key])

    def test_level_zero_punctuation_loss_is_exposed_by_both_editors(self):
        for function in (DE.validate_build_fit, CE.build_fit_budget):
            result = function('이번엔 거점 건설,', 18, '0x00A01BA9')
            self.assertEqual(result['fit_level'], 0)
            self.assertIn('부호', result['warning'])

    def test_unknown_scene_address_is_not_saved(self):
        handler = object.__new__(CE.Handler)
        with patch.object(CE, "member_slot", return_value=None), patch.object(CE.DE, "save_json") as save:
            result = handler._save_line({"address": "0x00AFF123", "ko": "검증"})
        self.assertFalse(result["ok"])
        save.assert_not_called()

    def test_palette_and_actual_geometry_are_validated(self):
        for palette in ([], [[0, 0, 0]] * 15, [[0, 0, 256]] * 16, [[True, 0, 0]] * 16):
            with self.assertRaises(ValueError):
                SE.validate_palette(palette)
        grid = [[0] * 8 for _ in range(8)]
        with patch.object(SE, "decode_current_indices", return_value=(grid, 16, 8, 2)):
            with self.assertRaisesRegex(ValueError, "타일 크기"):
                SE.validate_sprite_edit({'type': 'raw'}, grid, None)

    def test_external_rom_replace_invalidates_cache(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "temp") as directory:
            rom = Path(directory) / "test.gba"
            rom.write_bytes(b"old")
            with patch.object(SE, "PATCHED_ROM_PATH", rom), patch.object(SE, "_PATCHED", None):
                self.assertEqual(SE.patched_bytes(), b"old")
                replacement = rom.with_suffix('.new')
                replacement.write_bytes(b"new")
                replacement.replace(rom)
                self.assertEqual(SE.patched_bytes(), b"new")

    def test_late_writer_conflict_fails_with_evidence(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "temp") as directory:
            report = Path(directory) / "report.json"
            report.write_text('{"ok": true}')
            result = {'report': str(report), 'expected_writes': [('font', 2, b'ab')]}
            CE.B.verify_sprite_override_final_bytes(bytearray(b'00ab00'), result)
            with self.assertRaisesRegex(AssertionError, "font"):
                CE.B.verify_sprite_override_final_bytes(bytearray(b'00ac00'), result)
            saved = json.loads(report.read_text())
            self.assertFalse(saved['ok'])
            self.assertEqual(saved['final_byte_conflicts'][0]['offset'], '0x2')

    def test_preview_encoder_preserves_complete_sjis_characters(self):
        payload, truncated = preview_capture.encode_payload('가나', 'ko', 4)
        self.assertTrue(truncated)
        self.assertEqual(payload[2:], bytes(2))
        payload, truncated = preview_capture.encode_payload('A1!', 'ko', 8,
                                                             address=0xDF8E16)
        expected = DE.B.encode_text('A1!', DE.syl_to_code_ints(), __import__('collections').Counter(), 0xDF8E16)
        self.assertFalse(truncated)
        self.assertEqual(payload[:len(expected)], expected)

    def test_preview_follows_actual_pointer_and_preserves_control(self):
        for path in (preview_capture.ORIG_ROM, preview_capture.PATCHED_ROM):
            rom = path.read_bytes()
            canvas = preview_capture.CANVASES['part1_welcome']
            slot = preview_capture._resolve_slot(canvas, rom)
            self.assertEqual(rom[slot + canvas['len']:slot + canvas['len'] + 2], b'k\n')
            payload, _ = preview_capture.encode_payload('검증 A1!', 'ko', canvas['len'],
                                                        add_terminator=False, pad_byte=32,
                                                        address=0xDF8E16)
            changed = bytearray(rom)
            changed[slot:slot + canvas['len']] = payload
            self.assertEqual(changed[slot + canvas['len']:], rom[slot + canvas['len']:])

    def test_busy_lock_returns_http_error_within_deadline(self):
        program = """
import os, fcntl, time
fd = os.open('data', os.O_RDONLY)
fcntl.flock(fd, fcntl.LOCK_EX)
print('locked', flush=True)
time.sleep(10)
"""
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as directory, \
             patch.object(editor_storage, 'ROOT', Path(directory)):
            (Path(directory) / 'data').mkdir()
            child = subprocess.Popen([sys.executable, '-c', program], cwd=directory,
                                     stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), 'locked')
                class Handler:
                    def _send(self, code, body):
                        return code, body

                    @editor_storage.editor_request
                    def request(self):
                        with editor_storage.EDITOR_LOCK:
                            raise AssertionError('lock should be unavailable')

                started = time.monotonic()
                code, body = Handler().request()
                self.assertEqual(code, 503)
                self.assertTrue(body['busy'])
                self.assertLess(time.monotonic() - started, 4)
            finally:
                child.terminate()
                child.wait(timeout=5)
                child.stdout.close()

    def test_cross_process_read_modify_write_preserves_all_updates(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "temp") as directory:
            target = Path(directory) / "counter.json"
            (Path(directory) / "data").mkdir()
            (Path(directory) / "temp").mkdir()
            target.write_text('{"n": 0}')
            program = """
import json, sys, time
from pathlib import Path
import editor_storage
from editor_storage import EDITOR_LOCK, save_json
p = Path(sys.argv[1])
editor_storage.ROOT = p.parent
for _ in range(20):
    with EDITOR_LOCK:
        value = json.loads(p.read_text())
        time.sleep(.002)
        value['n'] += 1
        save_json(p, value)
"""
            children = [subprocess.Popen([sys.executable, "-c", program, str(target)],
                                         cwd=ROOT / "tools") for _ in range(3)]
            for child in children:
                self.assertEqual(child.wait(timeout=30), 0)
            self.assertEqual(json.loads(target.read_text()), {"n": 60})


if __name__ == "__main__":
    unittest.main()
