"""The host audit must resolve protected script writers like the builder."""
import unittest
import json
import hashlib
from pathlib import Path
import tempfile
from unittest.mock import patch

import audit_address_text_overrides as audit
import build_korean_full as builder
import qa_text_fit
import build_korean_poc as P


class ProtectedScriptAuditTests(unittest.TestCase):
    def _semantic_fixture(self, root, *, omit_span=False, omit_record=False,
                          foreign_owner=False, bad_sha=False):
        rom_path, manifest_path, original_path = (root/'rom.gba', root/'repoint.json', root/'original.gba')
        original = bytearray(0x100)
        original[0x20:0x24] = (0x08000040).to_bytes(4, 'little')
        original[0x24:0x28] = (0x08000060).to_bytes(4, 'little')
        original_path.write_bytes(original)
        rom = bytearray(original)
        rom[0x20:0x24] = (0x08000080).to_bytes(4, 'little')
        rom[0x24:0x28] = (0x08000090).to_bytes(4, 'little')
        rom[0x42:0x44] = b'OK'  # stale in-place copy must never authorize a pass
        rom[0x82:0x84] = b'OK'
        rom[0x92:0x94] = b'OK'
        rom_path.write_bytes(rom)
        messages = [] if omit_record else [{
            'msg': '0x000060' if foreign_owner else '0x000040',
            'status': 'relocated', 'new_addr': '0x000090' if foreign_owner else '0x000080',
            'old_len': 8, 'new_len': 8,
            'ptr_sites': ['0x000024'] if foreign_owner else ['0x000020'],
            'line_spans': {} if omit_span else {'0x000042': [2, 2]},
        }]
        manifest_path.write_text(json.dumps(messages))
        Path(str(rom_path) + '.build.json').write_text(json.dumps({
            'rom_sha256': hashlib.sha256(rom).hexdigest(),
            'source_sha256': hashlib.sha256(original).hexdigest(),
            'build_metadata': {'temp/repoint_manifest.json':
                               '0' * 64 if bad_sha else hashlib.sha256(manifest_path.read_bytes()).hexdigest()},
        }))
        return rom_path, manifest_path, original_path, rom

    def test_semantic_audit_reads_live_repoint_and_rejects_stale_manifest(self):
        with tempfile.TemporaryDirectory(dir=audit.ROOT/'temp') as directory:
            root = Path(directory)
            rom_path, manifest_path, original_path, rom = self._semantic_fixture(root)
            with patch.object(audit, 'SEMANTIC_REGRESSION_ADDRESSES', frozenset({0x42})), \
                 patch.object(qa_text_fit, 'load_direct_patch_texts',
                              return_value={0x42: (0x44, 'OK', 'patch_script_row')}), \
                 patch.object(P, 'ROM', str(original_path)):
                report = audit.audit_rom_semantics(rom_path, manifest_path, {0x42: 'OK'})
                self.assertEqual((report['semantic_relocated_count'], report['semantic_mismatch_count']), (1, 0))
                rom[0x20:0x24] = (0x08000090).to_bytes(4, 'little')
                rom_path.write_bytes(rom)
                with self.assertRaisesRegex(ValueError, 'receipt ROM/source/manifest mismatch'):
                    audit.audit_rom_semantics(rom_path, manifest_path, {0x42: 'OK'})

    def test_semantic_audit_reconstructs_split_source_row(self):
        with tempfile.TemporaryDirectory(dir=audit.ROOT/'temp') as directory:
            rom_path, manifest_path, original_path, rom = self._semantic_fixture(Path(directory))
            rom[0x86:0x88] = b'AB'
            rom_path.write_bytes(rom)
            manifest = json.loads(manifest_path.read_text())
            manifest[0]['new_len'] = 10
            manifest[0]['source_line_fragments'] = {'0x000042': [[2, 2], [6, 2]]}
            manifest_path.write_text(json.dumps(manifest))
            Path(str(rom_path) + '.build.json').write_text(json.dumps({
                'rom_sha256': hashlib.sha256(rom).hexdigest(),
                'source_sha256': hashlib.sha256(original_path.read_bytes()).hexdigest(),
                'build_metadata': {'temp/repoint_manifest.json':
                                   hashlib.sha256(manifest_path.read_bytes()).hexdigest()},
            }))
            with patch.object(audit, 'SEMANTIC_REGRESSION_ADDRESSES', frozenset({0x42})), \
                 patch.object(qa_text_fit, 'load_direct_patch_texts',
                              return_value={0x42: (0x44, 'OK', 'patch_script_row')}), \
                 patch.object(P, 'ROM', str(original_path)):
                report = audit.audit_rom_semantics(rom_path, manifest_path, {0x42: 'OK　AB'})
                self.assertEqual(report['semantic_mismatch_count'], 0)

    def test_approved_dacafe7_final_text_is_exact(self):
        # Exercise the actual semantic-audit exception on its protected address.
        address = 0xDCAFE7
        with tempfile.TemporaryDirectory(dir=audit.ROOT/'temp') as directory:
            root = Path(directory)
            original_path, rom_path, manifest_path = (root/'original.gba', root/'rom.gba', root/'repoint.json')
            original = bytes((address + 67) & ~3)
            rom = bytearray(original)
            rom[address:address + 2] = b'OK'
            original_path.write_bytes(original)
            rom_path.write_bytes(rom)
            manifest_path.write_text('[]')
            Path(str(rom_path) + '.build.json').write_text(json.dumps({
                'rom_sha256': hashlib.sha256(rom).hexdigest(),
                'source_sha256': hashlib.sha256(original).hexdigest(),
                'build_metadata': {'temp/repoint_manifest.json':
                                   hashlib.sha256(manifest_path.read_bytes()).hexdigest()},
            }))
            for actual, expected_mismatches in (
                ('먼저　１２　거점　점령하는　거야！', 0),
                ('먼저　１２거점　점령하는　거야！', 1),
                ('먼저　１２　거점　지키는　거야！', 1),
            ):
                with self.subTest(actual=actual), \
                     patch.object(audit, 'SEMANTIC_REGRESSION_ADDRESSES', frozenset({address})), \
                     patch.object(qa_text_fit, 'load_direct_patch_texts',
                                  return_value={address: (address + 2, 'old source', 'patch_script_row')}), \
                     patch('qa_integrity_map.decode_enc', return_value=actual), \
                     patch.object(P, 'ROM', str(original_path)):
                    report = audit.audit_rom_semantics(
                        rom_path, manifest_path, {address: '먼저 12거점 점령하는 거야!'})
                self.assertEqual(report['semantic_mismatch_count'], expected_mismatches, report)

    def test_semantic_audit_rejects_missing_and_foreign_relocation_evidence(self):
        for name, options, reason in (
            ('omitted span', {'omit_span': True}, 'missing relocated line span'),
            ('omitted record', {'omit_record': True}, 'missing relocated line span'),
            ('foreign owner with matching text', {'foreign_owner': True}, 'source ownership mismatch'),
            ('manifest sha mismatch', {'bad_sha': True}, 'receipt ROM/source/manifest mismatch'),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory(dir=audit.ROOT/'temp') as directory:
                rom_path, manifest_path, original_path, _rom = self._semantic_fixture(Path(directory), **options)
                with patch.object(audit, 'SEMANTIC_REGRESSION_ADDRESSES', frozenset({0x42})), \
                     patch.object(qa_text_fit, 'load_direct_patch_texts',
                                  return_value={0x42: (0x44, 'OK', 'patch_script_row')}), \
                     patch.object(P, 'ROM', str(original_path)), \
                     self.assertRaisesRegex(ValueError, reason):
                    audit.audit_rom_semantics(rom_path, manifest_path, {0x42: 'OK'})

    def test_two_real_addresses_use_current_authority_not_dead_call_literals(self):
        addresses = (0xD90250, 0xD902DC)
        raw = {a: builder.ADDRESS_TEXT_OVERRIDES[a] for a in addresses}
        extracted = qa_text_fit.load_direct_patch_texts()
        self.assertEqual(extracted[0xD90250][1], '취소 키로 메뉴 닫아')
        self.assertEqual(extracted[0xD902DC][1], '이제 유닛은 다 움직였으니 종료해')
        effective, stats = audit.load_effective_protected_texts(raw)
        self.assertEqual(effective, {
            0xD90250: 'B 버튼으로 메뉴를 닫을 수 있어.',
            0xD902DC: '이미 모든 유닛이 움직였으니 종료해 줘。',
        })
        self.assertEqual(stats['direct_patch_collision_count'], 2)
        self.assertEqual(stats['direct_patch_divergent_count'], 0)

    def test_explicit_empty_plain_and_whole_rows_do_not_resurrect_literals(self):
        raw = {0xD90250: '', 0xD902DC: ''}
        with patch.dict(builder.ADDRESS_TEXT_OVERRIDES, raw):
            effective, stats = audit.load_effective_protected_texts(raw)
        self.assertEqual(effective, raw)
        self.assertEqual(stats['direct_patch_divergent_count'], 0)

    def test_separate_prologue_writer_keeps_its_literal_policy(self):
        address, (literal, size) = next(iter(builder.INTRO_DIRECT_TEXT.items()))
        self.assertNotIn(address, builder.SCRIPT_OPERAND_SPANS)
        with patch.object(qa_text_fit, 'load_direct_patch_texts',
                          return_value={address: (address + size, literal, 'INTRO_DIRECT_TEXT')}), \
             patch.dict(builder.ADDRESS_TEXT_OVERRIDES, {address: 'earlier import'}), \
             patch.object(builder, 'direct_script_override_text',
                          side_effect=AssertionError('not a script writer')):
            effective, _ = audit.load_effective_protected_texts({address: 'earlier import'})
        self.assertEqual(effective[address], literal)

    def test_absent_script_override_retains_literal_fallback(self):
        address = 0xD90250
        with patch.object(qa_text_fit, 'load_direct_patch_texts',
                          return_value={address: (0xD90274, 'literal fallback', 'patch_script_row')}), \
             patch.dict(builder.ADDRESS_TEXT_OVERRIDES, {address: 'earlier import'}), \
             patch.object(builder, 'direct_script_override_text', return_value=None):
            effective, _ = audit.load_effective_protected_texts({address: 'earlier import'})
        self.assertEqual(effective[address], 'literal fallback')

    def test_wrong_merged_owner_end_is_rejected_like_the_actual_writer(self):
        address = 0xD902DC
        with patch.object(qa_text_fit, 'load_direct_patch_texts',
                          return_value={address: (0xD90320, 'wrong span', 'patch_script_row')}):
            with self.assertRaisesRegex(AssertionError, 'merged script row boundary mismatch'):
                audit.load_effective_protected_texts({address: builder.ADDRESS_TEXT_OVERRIDES[address]})

    def test_undeclared_real_script_call_still_uses_the_actual_resolver(self):
        address = 0xD9028B
        self.assertNotIn(address, builder.SCRIPT_OPERAND_SPANS)
        self.assertNotIn(address, builder.WHOLE_SCRIPT_ROWS)
        end, literal, writer = qa_text_fit.load_direct_patch_texts(include_writer=True)[address]
        self.assertEqual(writer, 'patch_script_row')
        _, members = builder.load_direct_script_metadata()
        overrides = builder.load_dialogue_overrides(audit.DIALOGUE_OVERRIDES)
        selected = builder.direct_script_override_text(address, end, members, overrides)
        with patch.object(builder, 'direct_script_override_text',
                          wraps=builder.direct_script_override_text) as resolver:
            effective, _ = audit.load_effective_protected_texts({address: builder.ADDRESS_TEXT_OVERRIDES[address]})
        resolver.assert_called_once_with(address, end, members, overrides)
        self.assertEqual(effective[address], literal if selected is None else selected)

    def test_dialogue_loader_normalizes_keys_and_rejects_invalid_inputs(self):
        address = 0xD9028B
        with tempfile.TemporaryDirectory(dir=audit.ROOT/'temp') as directory:
            source = Path(directory)/'overrides.json'
            source.write_text('{"d9028b": "편집"}')
            with patch.object(audit, 'DIALOGUE_OVERRIDES', source), \
                 patch.object(builder, 'direct_script_override_text',
                              wraps=builder.direct_script_override_text) as resolver:
                audit.load_effective_protected_texts({address: builder.ADDRESS_TEXT_OVERRIDES[address]})
                self.assertEqual(resolver.call_args.args[3], {'0x00D9028B': '편집'})
            for invalid in ('{"d9028b": 3}', '{"d9028b":"x","0x00D9028B":"y"}',
                            '{"d9028b":"x","d9028b":"y"}'):
                source.write_text(invalid)
                with patch.object(audit, 'DIALOGUE_OVERRIDES', source), self.assertRaises(ValueError):
                    audit.load_effective_protected_texts({address: builder.ADDRESS_TEXT_OVERRIDES[address]})

    def test_stale_authority_snapshot_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'snapshot differs'):
            audit.load_effective_protected_texts({0xD90250: 'foreign text'})

    def test_extractor_provenance_keeps_default_api_and_final_writer_order(self):
        with tempfile.TemporaryDirectory(dir=audit.ROOT/'temp') as directory:
            root = Path(directory);(root/'tools').mkdir()
            (root/'tools/build_korean_full.py').write_text('''
INTRO_DIRECT_TEXT = {0x300: ('소개', 8)}
for address, end, text, label in [(0x100, 0x108, '대사', 'row')]:
    patch_script_row(address, end, encode_text(text))
patch_script_row(0x200, 0x208, encode_text('대사'))
fixed_text_patch(0x200, 8, encode_text('별도'))
from part1_ship_help import ROWS as SHIP_HELP_ROWS
from part1_submarine_help import ROWS as SUBMARINE_HELP_ROWS
from part2_ending_qa_rows import ROWS as PART2_ENDING_QA_ROWS
for start, end, source_text in SHIP_HELP_ROWS:
    patch_script_row(start, end, source_text=source_text)
for start, end, source_text in SUBMARINE_HELP_ROWS:
    patch_script_row(start, end, source_text=source_text)
for start, end, source_text in PART2_ENDING_QA_ROWS:
    patch_script_row(start, end, source_text=source_text)
''')
            with patch.object(qa_text_fit, 'BASE', str(root)):
                default = qa_text_fit.load_direct_patch_texts()
                detailed = qa_text_fit.load_direct_patch_texts(include_writer=True)
        self.assertEqual(default, {a: value[:2] for a, value in detailed.items()})
        self.assertEqual(detailed[0x100][2], 'patch_script_row')
        self.assertEqual(detailed[0x200], (0x208, '별도', 'fixed_text_patch'))
        self.assertEqual(detailed[0x300][2], 'INTRO_DIRECT_TEXT')


if __name__ == '__main__':
    unittest.main()
