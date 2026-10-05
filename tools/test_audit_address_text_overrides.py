"""The host audit must resolve protected script writers like the builder."""
import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

import audit_address_text_overrides as audit
import build_korean_full as builder
import qa_text_fit


class ProtectedScriptAuditTests(unittest.TestCase):
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
