#!/usr/bin/env python3
"""Focused final-ROM B-team drift gate tests."""
import json
import struct
import tempfile
import unittest
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qa_bteam_drift import (check, check_rom, compact_glyph_map, decode_compact,
                            display_equivalent, round2_width_equivalent,
                            classify_round2_issues,
                            authorized_dcf_a8c_reflow,
                            reviewed_seam_variants,
                            matches_alignment_composite, matches_reviewed_bteam_spacing,
                            DEFERRED_ADDRESSES, COMPACT_GLYPH_ADDRESSES,
                            NEW_STRICT_ADDRESSES, PINNED_CORE_DIGEST, core_digest)
from qa_bteam_drift import round2_issue_bucket
from qa_bteam_drift import co_breaks_as_spaces
from build_korean_full import validate_co_reflow_spans
from repoint_source_rows import row_bytes as source_row_bytes
import qa_part2_co_panel_width as co_panel_width


ROOT = Path(__file__).resolve().parents[1]
CODE = json.loads((ROOT / 'data/syllable_to_code_2350.json').read_text())['가']
CODE = int(CODE, 0) if isinstance(CODE, str) else CODE
GLYPH = CODE.to_bytes(2, 'big')


class RomDriftTest(unittest.TestCase):
    def test_renderer_aliases_do_not_inherit_semantic_substitutions(self):
        address = 0xB83C70
        self.assertEqual(display_equivalent('1,2.', address), '１、２。')
        for source, substituted in (('*', '＋'), ('=', '―'), ('@', '＃')):
            self.assertNotEqual(display_equivalent(source, address), substituted)

    def test_profile_punctuation_mutations_are_exact_address_bound(self):
        address = 0xB83C70  # protected source contains both comma and period
        self.assertEqual(display_equivalent('가,나.', address), '가、나。')
        # A different row in the same renderer cannot inherit this exception.
        self.assertEqual(display_equivalent('가,나.', 0xB83C71), '가，나．')
        # No protected source row at this address contains these characters.
        for source, forbidden in (('가:나', '가；나'), ('가[나]', '가（나）'),
                                  ('가{나}', '가（나）')):
            self.assertNotEqual(display_equivalent(source, address), forbidden)

    def test_co_source_rows_reconstruct_split_and_merged_fragments(self):
        from qa_integrity_map import decode_enc, load_syl
        # The ROM and manifest must come from the same build: relocation targets
        # move between candidates (b24 shifted the CO pages).
        import os
        rom_path = Path(os.environ.get('AW_TEST_ROM') or ROOT / 'output/game_wars_korean_candidate_20261012_b11.gba')
        manifest_path = Path(os.environ.get('AW_TEST_MANIFEST') or ROOT / 'temp/repoint_manifest.json')
        if not rom_path.is_file():
            self.skipTest('candidate ROM required')
        rom = rom_path.read_bytes()
        manifest = json.loads(manifest_path.read_text())
        rows = {
            '0xA2AAD3': '호이프와　사실　좋은　콤비。',  # split across two display rows
            '0xA2AAEE': '고양이　좋아',              # merged with the next source row
            '0xA2AAFB': '쥐　싫어',
        }
        for key, wanted in rows.items():
            with self.subTest(key=key):
                message = next(m for m in manifest if key in m.get('line_spans', {}))
                actual = decode_enc(source_row_bytes(rom, message, key), load_syl())
                self.assertEqual(actual, wanted)

    def test_co_span_rejects_stale_row_and_split_pair(self):
        payload = b'\x81\x40\x72\x81\x72\x00'
        validate_co_reflow_spans(payload, [[0, 2], [3, 2]])
        for stale in ([0, 4], [3, 1]):
            with self.subTest(stale=stale), self.assertRaises(AssertionError):
                validate_co_reflow_spans(payload, [stale])

    def test_co_break_is_token_aware(self):
        self.assertEqual(co_breaks_as_spaces(b'\x81\x72\x72'), b'\x81\x72\x81\x40')

    def test_co_census_rejects_unknown_control_and_reports_limits(self):
        rom = bytearray(256)
        struct.pack_into('<H', rom, 0, 2421)
        struct.pack_into('<I', rom, 4, 0x08000020)
        with mock.patch.object(co_panel_width, 'CO_COUNT', 1), \
                mock.patch.object(co_panel_width, 'PAGES', 1), \
                mock.patch.object(co_panel_width, 'CO_TABLE', 0), \
                mock.patch.object(co_panel_width, 'MESSAGE_TABLE', -9680):
            rom[32:34] = b'\x71\x00'
            with self.assertRaisesRegex(ValueError, 'unsupported control'):
                co_panel_width.census(rom)
            rom[32:61] = b'\x81\x40' * 14 + b'\x00'
            self.assertGreater(co_panel_width.census(rom)[0]['cells'], co_panel_width.LIMIT)
            rom[32:46] = b'\x72' * 6 + b'\x81\x40\x00' + b'\x00' * 5
            rows = co_panel_width.census(rom)
            self.assertEqual(len(rows), 7)

    def test_authorized_reflow_requires_bounded_adjacent_spans_and_native_newline(self):
        rom = bytearray(b'\x00' * 64)
        rom[20:29] = b'ABC\x72\x0a\x09DEF'
        message = {'msg': '0xDCFA8C', 'new_addr': '0x14', 'new_len': 9,
                   'line_spans': {'0xDCFA8E': [0, 3], '0xDCFABB': [6, 3]}}
        self.assertTrue(authorized_dcf_a8c_reflow(rom, message))
        for first, continuation, length in (
                ([1, 3], [6, 3], 9),    # displaced first row
                ([0, 3], [7, 2], 9),    # displaced continuation
                ([0, 3], [6, 4], 9),    # continuation exceeds new_len
                ([0, 3], [6, 3], 8),    # continuation exceeds shortened message
                ([-1, 4], [6, 3], 9),   # first row starts outside message
                ([0, 3], [6, 3], 50)): # message exceeds ROM
            with self.subTest(first=first, continuation=continuation, length=length):
                changed = json.loads(json.dumps(message))
                changed['line_spans']['0xDCFA8E'] = first
                changed['line_spans']['0xDCFABB'] = continuation
                changed['new_len'] = length
                self.assertFalse(authorized_dcf_a8c_reflow(rom, changed))
        for control in (b'\x72\x0a\x00', b'\x72\x09\x09', b'\x00\x0a\x09'):
            with self.subTest(control=control):
                changed = bytearray(rom)
                changed[23:26] = control
                self.assertFalse(authorized_dcf_a8c_reflow(changed, message))

    def test_m29_title_approved_exception_is_exact(self):
        from qa_bteam_drift import APPROVED_EXCEPTIONS, exception_errors
        baseline = json.loads((ROOT / 'data/bteam_baseline.json').read_text())
        self.assertEqual(APPROVED_EXCEPTIONS['0x00A2D814'], ('결전 전', '최종결전!'))
        self.assertEqual(exception_errors(baseline, baseline['overrides']), [])
        changed = json.loads(json.dumps(baseline))
        changed['overrides']['0x00A2D814'] = '결전 전'
        self.assertIn('0x00A2D814: baseline differs from the approved exception text',
                      exception_errors(changed, changed['overrides']))

    def test_m29_title_uses_pair_writer_glyphs_only(self):
        from qa_bteam_drift import original_glyph_encoding
        self.assertEqual(original_glyph_encoding('최종결전!'), '최종결전！')
        self.assertNotEqual(original_glyph_encoding('최종결전!'), '결전　전')

    def test_name_boundary_spacing_exception_is_exact_and_address_bound(self):
        self.assertTrue(matches_reviewed_bteam_spacing(
            0xDC3C63, '사령관님,료!', '　사령관님、　료！'))
        self.assertFalse(matches_reviewed_bteam_spacing(
            0xDC3C64, '사령관님,료!', '　사령관님、　료！'))
        self.assertFalse(matches_reviewed_bteam_spacing(
            0xDC3C63, '사령관님,료!', '　사령관님、　맥스！'))
        self.assertFalse(matches_reviewed_bteam_spacing(
            0xDC3C63, '사령관님,료!', '사령관님、　료！'))
        self.assertTrue(matches_reviewed_bteam_spacing(
            0xDEECDE, '해상유닛.지상 유닛을', '해상　유닛。지상　유닛을'))
        self.assertFalse(matches_reviewed_bteam_spacing(
            0xDEECDE, '해상유닛.지상 유닛을', '해상　유닛。공중　유닛을'))

    def test_source_drift_only_accepts_exact_surrender_pair(self):
        from qa_bteam_drift import BTEAM_SCRIPT_SPACING_REPAIRS
        baseline = json.loads((ROOT / 'data/bteam_baseline.json').read_text())
        original = baseline['overrides']
        for address, (before, after) in BTEAM_SCRIPT_SPACING_REPAIRS.items():
            key = f'0x{address:08X}'
            self.assertEqual(original[key], before)
            overrides = dict(original)
            overrides[key] = after
            self.assertEqual(check(baseline, overrides)['drift'],
                             [(key, before, after)])
        key = '0x00DEECDE'
        overrides = dict(original)
        overrides[key] = '해상　유닛。지상　유닛을'
        self.assertEqual(check(baseline, overrides)['drift'],
                         [(key, original[key], overrides[key])])
        key = '0x00A34B6C'
        overrides = dict(original)
        overrides[key] = '　예　　　아뇨'
        self.assertEqual(check(baseline, overrides)['drift'], [])
        for near_miss in ('예　　　아뇨', '　예　　　아뇨　', '　예　　 아뇨'):
            with self.subTest(near_miss=near_miss):
                overrides[key] = near_miss
                self.assertEqual(check(baseline, overrides)['drift'],
                                 [(key, original[key], near_miss)])

    def test_consensus_sets_and_baseline_pin(self):
        baseline = json.loads((ROOT / 'data/bteam_baseline.json').read_text())
        addresses = {int(x, 16) for x in baseline['overrides']}
        self.assertTrue(DEFERRED_ADDRESSES | COMPACT_GLYPH_ADDRESSES |
                        NEW_STRICT_ADDRESSES <= addresses)
        self.assertEqual(len(DEFERRED_ADDRESSES), 11)
        self.assertEqual(len(COMPACT_GLYPH_ADDRESSES), 21)
        self.assertEqual(core_digest(baseline), PINNED_CORE_DIGEST)
        self.assertNotIn('0x00A19324', baseline['overrides'])
        self.assertNotIn('0x00A1B3EC', baseline['overrides'])
        self.assertEqual(baseline['overrides']['0x00A19300'], '이걸로 좀조용해지겠지.')
        self.assertEqual(baseline['overrides']['0x00A1B3C8'], '어떡할까요?')

    def test_alignment_legacy_alias_must_match_exact_text(self):
        baseline = json.loads((ROOT / 'data/bteam_baseline.json').read_text())
        overrides = {'0x00A19324': '이걸로 좀조용해지겠지.',
                     '0x00A1B3EC': '어떡할까요?'}
        focused = {'overrides': {k: baseline['overrides'][k]
                                 for k in ('0x00A19300', '0x00A1B3C8')},
                   '_user_approved_exceptions': baseline['_user_approved_exceptions']}
        self.assertEqual(check(focused, overrides, pinned=core_digest(focused))['missing'], [])
        overrides['0x00A19324'] = '다른 문구'
        self.assertEqual(check(focused, overrides, pinned=core_digest(focused))['missing'],
                         [('0x00A19300', '이걸로 좀조용해지겠지.')])

    def test_alignment_composite_is_exact_and_address_bound(self):
        address = 0xA19300
        wanted = display_equivalent('이걸로 좀조용해지겠지.', address)
        self.assertTrue(matches_alignment_composite(
            wanted, '이걸로　좀', '조용해지겠지。', b'\x72', address))
        self.assertFalse(matches_alignment_composite(
            wanted, '이걸로　조금은', '조용해지겠지。', b'\x72', address))
        self.assertFalse(matches_alignment_composite(
            wanted, '이걸로　좀', '조용해지겠지。', b'\x00', address))
        self.assertFalse(matches_alignment_composite(
            wanted, '이걸로　좀', '조용해지겠지。', b'\x72', address + 1))

    def test_display_equivalence_preserves_spaces_and_punctuation(self):
        address = 0xA05868
        self.assertEqual(display_equivalent('가 나-!...', address),
                         display_equivalent('가　나ー！・・・', address, actual=True))
        self.assertNotEqual(display_equivalent('가 나-!', address),
                            display_equivalent('가 나ー！', address, actual=True))
        self.assertNotEqual(display_equivalent('가 나-!', address),
                            display_equivalent('가　나-！', address, actual=True))
        self.assertEqual(display_equivalent('AB', address), 'ＡＢ')
        self.assertNotEqual(display_equivalent('A B', address),
                            display_equivalent('AB', address))
        self.assertNotEqual(display_equivalent('A  B', address),
                            display_equivalent('A B', address))
        self.assertNotEqual(display_equivalent('A・B', address),
                            display_equivalent('A B', address))
        self.assertNotEqual(display_equivalent('A!B', address),
                            display_equivalent('AB', address))
        self.assertNotEqual(display_equivalent('・・・・', address),
                            display_equivalent('・・・', address, actual=True))

    def test_round2_width_alias_is_address_bound_and_keeps_every_character(self):
        address = 0xA2D55C
        self.assertTrue(round2_width_equivalent('레드스타 진군!', '레드스타　진군！', address))
        self.assertFalse(round2_width_equivalent('레드스타 진군!', '레드스타진군！', address))
        self.assertFalse(round2_width_equivalent('레드스타 진군!', '레드스타　진군', address))
        self.assertFalse(round2_width_equivalent('레드스타 진군!', '레드스타　진군！', address + 1))
        self.assertFalse(round2_width_equivalent('이 몸의 2회 행동을,견뎌낼 수 있겠느냐!?',
                         '이 몸의 2회 행동을、견뎌낼 수 있겠느냐！？', 0xB83A98))

    def test_round2_classification_rejects_structural_issues(self):
        address = 0xDD010A
        listed = {address}
        for cause in ('repoint pointer mismatch', 'repoint line mapping missing',
                      'repoint line mapping invalid',
                      'protected address has no final text write evidence'):
            self.assertEqual(round2_issue_bucket(
                {'address': f'0x{address:08X}', 'cause': cause}, listed), 'unlisted')
        self.assertEqual(round2_issue_bucket(
            {'address': f'0x{address:08X}',
             'cause': 'relocated row differs from protected baseline'}, listed), 'residual')
        self.assertEqual(round2_issue_bucket(
            {'address': f'0x{address:08X}', 'cause': 'final in-place writer differs'},
            listed), 'residual')
        self.assertEqual(round2_issue_bucket(
            {'address': '0x00000001', 'cause': 'relocated row differs from protected baseline'},
            listed), 'unlisted')

    def round2_fixture(self):
        """Self-contained ROM + manifest: listed residual bytes in place and every
        active pin relocated into free space with a pointer and line spans."""
        import csv
        original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        rom = bytearray(original)
        rows = {int(r['address'], 16): r for r in csv.DictReader(
            (ROOT / 'data/bteam_round2_residuals.tsv').open(encoding='utf-8'), delimiter='\t')}
        for address, row in rows.items():
            payload = bytes.fromhex(row['payload_hex'])
            rom[address:address + len(payload)] = payload
        pins = json.loads((ROOT / 'data/bteam_round2_active_pins.json').read_text(encoding='utf-8'))
        manifest = []
        for index, (key, hexdata) in enumerate(sorted(pins.items())):
            address = int(key, 16)
            data = bytes.fromhex(hexdata)
            target, site = 0xA3D000 + index * 0x100, 0xA3F000 + index * 4
            self.assertTrue(all(b == 0xFF for b in original[target:target + len(data)]))
            rom[target:target + len(data)] = data
            rom[site:site + 4] = (0x08000000 + target).to_bytes(4, 'little')
            active = rows[address].get('active_payload_hex')
            spans = {f'0x{address:06X}': [data.index(bytes.fromhex(active)), len(bytes.fromhex(active))]
                     if active else [0, 1]}
            follow = rows[address].get('active_follow_hex')
            if follow:
                spans['0xA2BC57'] = [data.index(bytes.fromhex(follow)), len(bytes.fromhex(follow))]
            manifest.append({'msg': f'0x{address:06X}', 'status': 'relocated', 'new_addr': f'0x{target:06X}',
                             'new_len': len(data), 'line_spans': spans, 'ptr_sites': [hex(site)]})
        return rom, manifest

    def test_round2_byte_pointer_mapping_mutations(self):
        base = json.loads((ROOT / 'data/bteam_baseline.json').read_text(encoding='utf-8'))
        rom, manifest = self.round2_fixture()
        deferred = [{'address': f'0x{address:08X}', 'cause': 'reviewed deferral'}
                    for address in DEFERRED_ADDRESSES]
        addr = 0xDD010A
        issue = {'address': f'0x{addr:08X}', 'cause': 'relocated row differs from protected baseline'}
        message = next(m for m in manifest if f'0x{addr:06X}' in m['line_spans'])
        target = int(message['new_addr'], 16)
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            rom_path, map_path = Path(tmp) / 'rom.gba', Path(tmp) / 'manifest.json'

            def classify(data, mapping):
                rom_path.write_bytes(bytes(data))
                map_path.write_text(json.dumps(mapping))
                return classify_round2_issues([issue] + deferred, base, str(rom_path), str(map_path))

            listed, _, unlisted = classify(rom, manifest)
            self.assertEqual((len(listed), unlisted), (1, []))
            for cause in ('repoint pointer mismatch', 'repoint line mapping missing',
                          'repoint line mapping invalid'):
                rom_path.write_bytes(bytes(rom)); map_path.write_text(json.dumps(manifest))
                _, _, unlisted = classify_round2_issues([dict(issue, cause=cause)] + deferred, base,
                                                        str(rom_path), str(map_path))
                self.assertEqual(len(unlisted), 1, cause)
            missing = json.loads(json.dumps(manifest))
            del next(m for m in missing if m['msg'] == message['msg'])['line_spans'][f'0x{addr:06X}']
            with self.assertRaisesRegex(ValueError, 'mapping or byte pin missing'):
                classify(rom, missing)
            for position, pattern in ((target + 2, 'message bytes or span changed'),
                                      (target + message['new_len'] - 1, 'message bytes or span changed'),
                                      (int(message['ptr_sites'][0], 16), 'pointer changed'),
                                      (addr, 'listed residual metadata or source bytes changed')):
                changed = bytearray(rom)
                changed[position] ^= 1
                with self.assertRaisesRegex(ValueError, pattern):
                    classify(changed, manifest)
            # Active line bytes and the A2BC3C continuation are pinned too.
            for key, pattern in (('0x00D82218', 'message bytes or span changed'),
                                 ('0x00A2BC3C', 'message bytes or span changed')):
                pinned = next(m for m in manifest if m['msg'] == f'0x{int(key, 16):06X}')
                changed = bytearray(rom)
                changed[int(pinned['new_addr'], 16)] ^= 1
                with self.assertRaisesRegex(ValueError, pattern):
                    classify(changed, manifest)

    def test_reviewed_seam_only(self):
        rows = {0xA00000: [('몸에', '혹시')]}
        self.assertIn('몸에　혹시', reviewed_seam_variants('몸에혹시', 0xA00000, rows))
        self.assertNotIn('몸에혹시', reviewed_seam_variants('몸에　혹시', 0xA00000, rows))
        self.assertEqual(reviewed_seam_variants('다른공백', 0xA00000, rows), {'다른공백'})
        self.assertEqual(reviewed_seam_variants('몸에혹시', 0xA00010, rows), {'몸에혹시'})

    def test_compact_decoder_and_trailing_padding(self):
        glyphs = compact_glyph_map()
        self.assertEqual(glyphs['魯'], '기')
        self.assertEqual(decode_compact('魯'.encode('shift_jis') + b'\x00\x00', {}, glyphs), '기')
        self.assertNotEqual(decode_compact('魯'.encode('shift_jis'), {}, {}), '기')
        self.assertIn('▯', decode_compact('魯'.encode('shift_jis') + b'\x00A', {}, glyphs))

    def test_compact_writer_is_used_by_rom_gate(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            folder = Path(tmp)
            rom = bytearray(64)
            payload = '魯'.encode('shift_jis') + b'\x00\x00'
            rom[0x20:0x24] = payload
            paths = [folder / name for name in ('rom.gba', 'map.json', 'manifest.json')]
            paths[0].write_bytes(rom)
            paths[1].write_text(json.dumps([[0x20, 4, 4, payload.hex(), None,
                                             '기', 0, 'part1-compact-ui']]))
            paths[2].write_text('[]')
            with mock.patch('qa_bteam_drift.verify_compact_font') as verify:
                self.assertEqual(check_rom({'overrides': {'0x00000020': '기'}},
                                           *map(str, paths)), [])
                verify.assert_called_once()
                self.assertEqual(len(check_rom({'overrides': {'0x00000020': '관'}},
                                               *map(str, paths))), 1)
            with mock.patch('qa_bteam_drift.verify_compact_font',
                            side_effect=ValueError('tile mismatch')):
                with self.assertRaisesRegex(ValueError, 'tile mismatch'):
                    check_rom({'overrides': {'0x00000020': '기'}}, *map(str, paths))

    def test_deferred_row_remains_failure(self):
        addr = min(DEFERRED_ADDRESSES)
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            folder = Path(tmp)
            rom = bytearray(addr + 16)
            rom[addr:addr + 2] = b'AB'
            paths = [folder / name for name in ('rom.gba', 'map.json', 'manifest.json')]
            paths[0].write_bytes(rom)
            paths[1].write_text(json.dumps([[addr, 2, 2, b'AB'.hex(), None,
                                             'AB', 0, 'test']]))
            paths[2].write_text('[]')
            issues = check_rom({'overrides': {f'0x{addr:08X}': 'AB'}}, *map(str, paths))
            self.assertEqual([x['decision'] for x in issues], ['DEFER'])

    def test_empty_row_cannot_borrow_adjacent_text(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            folder = Path(tmp)
            rom = bytearray(64)
            rom[0x22:0x24] = b'AB'
            writes = [[0x20, 2, 0, '', 0, '', 0, 'test'],
                      [0x22, 2, 2, b'AB'.hex(), None, 'AB', 0, 'test']]
            paths = [folder / name for name in ('rom.gba', 'map.json', 'manifest.json')]
            paths[0].write_bytes(rom)
            paths[1].write_text(json.dumps(writes))
            paths[2].write_text('[]')
            self.assertEqual(len(check_rom({'overrides': {'0x00000020': 'AB'}},
                                           *map(str, paths))), 1)

    def test_empty_relocated_row_cannot_borrow_next_span(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            folder = Path(tmp)
            rom = bytearray(256)
            rom[0x10:0x14] = (0x08000080).to_bytes(4, 'little')
            rom[0x80:0x84] = b'  AB'
            manifest = [{'msg': '0x40', 'old_len': 8, 'status': 'relocated',
                         'ptr_sites': ['0x10'], 'new_addr': '0x80', 'new_len': 4,
                         'line_spans': {'0x000040': [0, 2], '0x000042': [2, 2]}}]
            paths = [folder / name for name in ('rom.gba', 'map.json', 'manifest.json')]
            paths[0].write_bytes(rom)
            paths[1].write_text('[]')
            paths[2].write_text(json.dumps(manifest))
            self.assertEqual(len(check_rom({'overrides': {'0x00000040': 'AB'}},
                                           *map(str, paths))), 1)

    def test_wrapped_and_adjacent_rows(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            folder = Path(tmp)
            rom = bytearray(256)
            rom[0x20:0x22] = b'AB'
            rom[0x23:0x25] = b'CD'
            rom[0x80:0x87] = b'AB\x72\x0a\x09CD'
            rom[0x10:0x14] = (0x08000080).to_bytes(4, 'little')
            writes = [[0x20, 2, 2, b'AB'.hex(), None, 'AB', 0, 'test'],
                      [0x23, 2, 2, b'CD'.hex(), None, 'CD', 0, 'test']]
            paths = [folder / name for name in ('rom.gba', 'map.json', 'manifest.json')]
            paths[0].write_bytes(rom)
            paths[1].write_text(json.dumps(writes))
            paths[2].write_text('[]')
            self.assertEqual(len(check_rom({'overrides': {'0x00000020': 'ABCD'}},
                                           *map(str, paths))), 1)
            self.assertEqual(len(check_rom({'overrides': {'0x00000020': 'CD'}},
                                           *map(str, paths))), 1)
            self.assertEqual(len(check_rom({'overrides': {'0x00000020': 'A BCD'}},
                                           *map(str, paths))), 1)
            manifest = [{'msg': '0x40', 'old_len': 8, 'status': 'relocated',
                         'ptr_off': '0x10', 'ptr_sites': ['0x10'],
                         'new_addr': '0x80', 'new_len': 7,
                         'line_spans': {'0x000040': [0, 7]}}]
            paths[2].write_text(json.dumps(manifest))
            self.assertEqual(check_rom({'overrides': {'0x00000040': 'AB　CD'}},
                                       *map(str, paths)), [])
            self.assertEqual(check_rom({'overrides': {'0x00000040': 'ABCD'}},
                                       *map(str, paths)), [])
            self.assertEqual(len(check_rom({'overrides': {'0x00000040': 'A BCD'}},
                                           *map(str, paths))), 1)

    def test_middle_dot_ellipsis_is_not_empty(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            folder = Path(tmp)
            rom = bytearray(64)
            paths = [folder / name for name in ('rom.gba', 'map.json', 'manifest.json')]
            paths[2].write_text('[]')
            base = {'overrides': {'0x00000020': '・・・・・・'}}
            rom[0x20:0x26] = b'      '
            paths[0].write_bytes(rom)
            paths[1].write_text(json.dumps([[0x20, 6, 6, b'      '.hex(), None,
                                             '      ', 0, 'test']]))
            self.assertEqual(len(check_rom(base, *map(str, paths))), 1)
            rom[0x20:0x26] = b'......'
            paths[0].write_bytes(rom)
            paths[1].write_text(json.dumps([[0x20, 6, 6, b'......'.hex(), None,
                                             '......', 0, 'test']]))
            self.assertEqual(len(check_rom(base, *map(str, paths))), 1)

    def test_direct_and_repointed_bytes(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            folder = Path(tmp)
            rom = bytearray(256)
            rom[0x20:0x22] = GLYPH
            rom[0x80:0x82] = GLYPH
            rom[0x82] = 0
            rom[0x10:0x14] = (0x08000080).to_bytes(4, 'little')
            writes = [[0x20, 2, 2, GLYPH.hex(), None, '가', 0, 'test']]
            manifest = [{'msg': '0x40', 'old_len': 8, 'status': 'relocated',
                         'ptr_off': '0x10', 'ptr_sites': ['0x10'],
                         'new_addr': '0x80', 'new_len': 3,
                         'line_spans': {'0x000040': [0, 2]}}]
            base = {'overrides': {'0x00000020': '가', '0x00000040': '가'}}
            paths = [folder / name for name in ('rom.gba', 'map.json', 'manifest.json')]
            paths[0].write_bytes(rom)
            paths[1].write_text(json.dumps(writes))
            paths[2].write_text(json.dumps(manifest))
            self.assertEqual(check_rom(base, *map(str, paths)), [])

            rom[0x20:0x22] = b'AB'
            rom[0x80:0x82] = b'CD'
            writes[0][3] = b'AB'.hex()
            paths[0].write_bytes(rom)
            paths[1].write_text(json.dumps(writes))
            issues = check_rom(base, *map(str, paths))
            self.assertEqual({x['address'] for x in issues}, set(base['overrides']))
            self.assertEqual(issues[0]['rom_text'], 'AB')
            self.assertEqual(issues[1]['rom_text'], 'CD')

            # Finding the protected word elsewhere in the message is not a pass.
            rom[0x83:0x85] = GLYPH
            manifest[0]['new_len'] = 5
            paths[0].write_bytes(rom)
            paths[2].write_text(json.dumps(manifest))
            issues = check_rom(base, *map(str, paths))
            self.assertEqual(issues[1]['rom_text'], 'CD')

            rom[0x10:0x14] = (0x08000040).to_bytes(4, 'little')
            paths[0].write_bytes(rom)
            issues = check_rom(base, *map(str, paths))
            self.assertEqual(issues[1]['cause'], 'repoint pointer mismatch')

            rom[0x10:0x14] = (0x08000080).to_bytes(4, 'little')
            rom[0x20:0x22] = GLYPH
            paths[0].write_bytes(rom)
            with self.assertRaisesRegex(ValueError, 'integrity map does not match ROM'):
                check_rom(base, *map(str, paths))

            writes[0][3] = GLYPH.hex()
            paths[1].write_text(json.dumps(writes))
            manifest[0]['ptr_sites'] = ['0x10', '0x14']
            paths[2].write_text(json.dumps(manifest))
            issues = check_rom(base, *map(str, paths))
            self.assertEqual(issues[0]['cause'], 'repoint pointer mismatch')

            manifest[0]['ptr_sites'] = ['0x10']
            paths[2].write_text(json.dumps(manifest))
            map_rom = folder / 'map_rom.gba'
            map_rom.write_bytes(rom)
            rom[0x20:0x22] = b'AB'
            paths[0].write_bytes(rom)
            with self.assertRaisesRegex(ValueError, 'overlay changed protected in-place slot'):
                check_rom(base, *map(str, paths), str(map_rom))


if __name__ == '__main__':
    unittest.main()
