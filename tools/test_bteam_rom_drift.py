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
from qa_bteam_drift import script_format_bytes
from build_korean_full import validate_co_reflow_spans
from repoint_source_rows import row_bytes as source_row_bytes
from part2_prologue_punctuation import PUNCTUATION
import qa_part2_co_panel_width as co_panel_width


ROOT = Path(__file__).resolve().parents[1]
CODE = json.loads((ROOT / 'data/syllable_to_code_2350.json').read_text())['가']
CODE = int(CODE, 0) if isinstance(CODE, str) else CODE
GLYPH = CODE.to_bytes(2, 'big')


class RomDriftTest(unittest.TestCase):
    def test_all_approved_prologue_rows_decode_exactly_from_final_rom(self):
        import os
        from qa_integrity_map import decode_enc, load_syl
        rom_path = Path(os.environ.get('AW_TEST_ROM') or ROOT / 'output/game_wars_korean_p2_reviewfix3.gba')
        map_path = Path(os.environ.get('AW_TEST_MAP') or ROOT / 'temp/integrity_map.json')
        manifest_path = Path(os.environ.get('AW_TEST_MANIFEST') or ROOT / 'temp/repoint_manifest.json')
        if not rom_path.is_file():
            self.skipTest('matching candidate ROM required')
        rom = rom_path.read_bytes()
        writes = json.loads(map_path.read_text())
        manifest = json.loads(manifest_path.read_text())
        exceptions = json.loads((ROOT / 'data/bteam_baseline.json').read_text())['_user_approved_exceptions']
        # plan_C B-pin (2026-11-04 user): rows of the reviewed A01A0C/A01C10 messages ship the
        # reviewed wording with the same approved 、。->，． glyphs (bpin_contract).
        import bpin_contract
        reviewed = {'0x00A01A1A': '헬보우즈님．', '0x00A01C10': '그\u3000점은，',
                    '0x00A01C1B': '염려\u3000마십시오．', '0x00A01C2A': '사령관들에게\u3000명했습니다．',
                    '0x00A01C59': '곧\u3000모일\u3000겁니다．'}
        self.assertIn(0xA01C10, bpin_contract.MESSAGES)
        self.assertEqual(len(PUNCTUATION), 21)
        for address, _, _, relocated in PUNCTUATION:
            key = f'0x{address:08X}'
            with self.subTest(address=key):
                self.assertIn(key, exceptions)
                if relocated:
                    message = next(m for m in manifest if m.get('status') == 'relocated'
                                   and f'0x{address:06X}' in m.get('line_spans', {}))
                    payload = source_row_bytes(rom, message, f'0x{address:06X}')
                else:
                    owner = next((row for row in reversed(writes)
                                  if row[7] in ('part2-prologue-drawn-comma-space',
                                                bpin_contract.NATIVE_WRITER)
                                  and len(row) > 8 and f'0x{address:06X}' in
                                  row[8].get('source_line_fragments', {})), None)
                    if owner:
                        offset, length = owner[8]['source_line_fragments'][f'0x{address:06X}']
                        payload = rom[owner[0] + offset:owner[0] + offset + length]
                    else:
                        inline = next((row for row in writes
                                       if row[7] == 'part2-prologue-inline-renderer'
                                       and row[0] == address), None)
                        if inline:
                            payload = rom[address:address + inline[2]].split(b'\x77\x72', 1)[0]
                        else:
                            row = next(row for row in writes if row[0] == address and row[3])
                            payload = rom[address:address + row[2]]
                actual = decode_enc(script_format_bytes(payload, address), load_syl()).rstrip(' \u3000')
                if key in reviewed:
                    self.assertEqual(actual.lstrip('\u3000'), reviewed[key])
                    continue
                self.assertEqual(actual, exceptions[key]['to'])

    def test_prologue_final_rom_gate_rejects_unapproved_word_mutation(self):
        import os
        rom_path = Path(os.environ.get('AW_TEST_ROM') or ROOT / 'output/game_wars_korean_p2_reviewfix3.gba')
        map_path = Path(os.environ.get('AW_TEST_MAP') or ROOT / 'temp/integrity_map.json')
        manifest_path = Path(os.environ.get('AW_TEST_MANIFEST') or ROOT / 'temp/repoint_manifest.json')
        if not rom_path.is_file():
            self.skipTest('matching candidate ROM required')
        base = json.loads((ROOT / 'data/bteam_baseline.json').read_text())
        rom = bytearray(rom_path.read_bytes())
        writes = json.loads(map_path.read_text())
        address = 0xA01A94  # protected and owned by the final whole-message write
        from qa_integrity_map import load_syl
        codes = load_syl()
        old = bytes(rom[address:address + 2])
        replacement = next(code.to_bytes(2, 'big') for code, syllable in codes.items()
                           if syllable == '각')
        self.assertNotEqual(old, replacement)
        rom[address:address + 2] = replacement
        for row in writes:
            if row[3] and row[0] <= address and address + 2 <= row[0] + len(bytes.fromhex(row[3])):
                encoded = bytearray.fromhex(row[3])
                offset = address - row[0]
                encoded[offset:offset + 2] = replacement
                row[3] = encoded.hex()
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as temporary:
            candidate = Path(temporary) / 'mutated.gba'
            mapping = Path(temporary) / 'integrity_map.json'
            candidate.write_bytes(rom)
            mapping.write_text(json.dumps(writes))
            issues = check_rom(base, str(candidate), str(mapping), str(manifest_path))
        self.assertTrue(any(item['address'] == '0x00A01A94' and
                            '각' in item['rom_text'] for item in issues))

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
        rom_path = Path(os.environ.get('AW_TEST_ROM') or ROOT / 'output/game_wars_korean_full.gba')
        manifest_path = Path(os.environ.get('AW_TEST_MANIFEST') or ROOT / 'temp/repoint_manifest.json')
        if not rom_path.is_file():
            self.skipTest('candidate ROM required')
        rom = rom_path.read_bytes()
        manifest = json.loads(manifest_path.read_text())
        # plan_C B-pin reviewed CO page (0xA2AA90, bpin_contract): A2AAD3 still spans two
        # display rows; A2AAEE/A2AAFB share the last row.
        rows = {
            '0xA2AAD3': '실은　손발이　잘　맞는다。　좋아함　고양이',  # split across two display rows
            '0xA2AAEE': '싫어함',
            '0xA2AAFB': '　쥐',
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
        self.assertEqual(APPROVED_EXCEPTIONS['0x00A34F70'],
                         ('엔트리 중이야,잠시 기다려 줘!!', '엔트리 중이야, 잠시 기다려 줘!!'))
        self.assertEqual(APPROVED_EXCEPTIONS['0x00A34F98'],
                         ('친구가 모이면,스타트를 눌러 줘!!', '친구가 모이면, 스타트를 눌러 줘!!'))
        link_spacing = {
            '0x00A3508C': ('맵을 송신 중이야,잠시 기다려 줘!!', '맵을 송신 중이야, 잠시 기다려 줘!!'),
            '0x00A350B4': ('맵을 수신 중이야,잠시 기다려 줘!!', '맵을 수신 중이야, 잠시 기다려 줘!!'),
            '0x00A350DC': ('종료했어.시작한다!!', '종료했어. 시작한다!!'),
            '0x00A350F8': ('종료했어.메뉴로 돌아갈게.', '종료했어. 메뉴로 돌아갈게.'),
            '0x00A3511C': ('맵을 저장 중이야,전원을 끄지 말아 줘!!', '맵을 저장 중이야, 전원을 끄지 말아 줘!!'),
            '0x00A3514C': ('다운로드 준비 중이야.잠시 기다려 줘!!', '다운로드 준비 중이야. 잠시 기다려 줘!!'),
            '0x00A3517C': ('접속이 안 되네,메뉴로 돌아갈게.', '접속이 안 되네, 메뉴로 돌아갈게.'),
        }
        for address, pair in link_spacing.items():
            with self.subTest(address=address):
                self.assertEqual(APPROVED_EXCEPTIONS[address], pair)
        self.assertEqual(APPROVED_EXCEPTIONS['0x00A2D814'], ('결전 전', '최종결전!'))
        self.assertEqual(APPROVED_EXCEPTIONS['0x00DF8E16'],
                         ('게임보이 워즈에 오신 걸 환영해요!', '게임보이 워즈 어드밴스에 어서 와!'))
        self.assertEqual(APPROVED_EXCEPTIONS['0x00DF948E'],
                         ('그렇다면, 간단하게 게임보이 워즈에', '그렇다면, 게임보이 워즈 어드밴스에'))
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
            self.assertEqual(check(baseline, overrides, rewrites=EMPTY_OVERLAY, ledger_bytes=_EMPTY_LEDGER)['drift'],
                             [(key, before, after)])
        key = '0x00DEECDE'
        overrides = dict(original)
        overrides[key] = '해상　유닛。지상　유닛을'
        self.assertEqual(check(baseline, overrides, rewrites=EMPTY_OVERLAY, ledger_bytes=_EMPTY_LEDGER)['drift'],
                         [(key, original[key], overrides[key])])
        key = '0x00A34B6C'
        overrides = dict(original)
        overrides[key] = '　예　　　아뇨'
        self.assertEqual(check(baseline, overrides, rewrites=EMPTY_OVERLAY, ledger_bytes=_EMPTY_LEDGER)['drift'], [])
        for near_miss in ('예　　　아뇨', '　예　　　아뇨　', '　예　　 아뇨'):
            with self.subTest(near_miss=near_miss):
                overrides[key] = near_miss
                self.assertEqual(check(baseline, overrides, rewrites=EMPTY_OVERLAY, ledger_bytes=_EMPTY_LEDGER)['drift'],
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

    def test_editor_display_approvals_keep_source_protected(self):
        baseline = json.loads((ROOT / 'data/bteam_baseline.json').read_text())
        self.assertEqual(core_digest(baseline), PINNED_CORE_DIGEST)
        self.assertEqual(check(baseline, baseline['overrides'])['errors'], [])
        changed = dict(baseline['overrides'])
        changed['0x00D82498'] = '채움'
        self.assertIn(('0x00D82498', '정보', '채움'), check(baseline, changed)['drift'])
        self.assertTrue(check(baseline, changed)['errors'])
        tampered = json.loads(json.dumps(baseline, ensure_ascii=False))
        tampered['_user_approved_exceptions']['0x00D8246A']['display_only'] = False
        self.assertTrue(check(tampered, tampered['overrides'])['errors'])

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
        # fixB J (E3): 3-5 dots ship as one 「…」 (0x8163); 1-2 stay middle dots.
        self.assertEqual(display_equivalent('・・・・', address),
                         display_equivalent('…', address, actual=True))
        self.assertEqual(display_equivalent('가...나', address),
                         display_equivalent('가…나', address, actual=True))
        self.assertEqual(display_equivalent('・・・・・・', address),
                         display_equivalent('……', address, actual=True))
        self.assertNotEqual(display_equivalent('・・', address),
                            display_equivalent('…', address, actual=True))
        self.assertNotEqual(display_equivalent('・・・', address),
                            display_equivalent('……', address, actual=True))

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

    def test_dd0108_repointer_full_sources_pass_drift_and_mutations_fail(self):
        from test_dialogue_script_safety import ScriptSafetyTests
        _, rom, message, _, _ = ScriptSafetyTests().dd0108_fixture()
        base = {'overrides': {'0x00DD010A': '이 녀석이 모든 것을,조종하고 있었던 거로군!',
                              '0x00DD0137': '용서 못 해!'}}
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            paths = [Path(tmp) / name for name in ('fixture.gba', 'map.json', 'manifest.json')]
            paths[1].write_text('[]')
            def check(data, record):
                paths[0].write_bytes(data)
                paths[2].write_text(json.dumps([record]))
                # Baseline-only fixture: the committed ledger now owns 0xDD010A.
                return check_rom(base, *map(str, paths), ledger_bytes=_EMPTY_LEDGER,
                                 ledger_pinned=_sha(_EMPTY_LEDGER))
            self.assertEqual(check(rom, message), [])
            target = int(message['new_addr'], 16)
            for off in (target + 24, target + 55, target + 71, target + 4):
                changed = bytearray(rom)
                changed[off:off+2] = b'\x81\x49' if off == target + 4 else b'\x81\x40'  # comma, both !, or word separator loss
                self.assertTrue(check(changed, message))
            changed = bytearray(rom)
            changed[0xDE705C] ^= 1
            self.assertTrue(all(r['cause'] == 'repoint pointer mismatch' for r in check(changed, message)))
            wrong = json.loads(json.dumps(message))
            wrong['source_line_fragments']['0xDD010A'][1] = [33, 26]
            self.assertTrue(check(rom, wrong))
            wrong = json.loads(json.dumps(message))
            wrong['source_fragment_joiners']['0xDD010A'] = ['8140']
            self.assertTrue(check(rom, wrong))

    def test_bpin_rows_leave_the_round2_byte_pins(self):
        # plan_C B-pin: listed residual rows the B-pin writer rewrites are not
        # byte-pinned any more; check_rom requires their approved `to` instead.
        import bpin_contract
        base = json.loads((ROOT / 'data/bteam_baseline.json').read_text(encoding='utf-8'))
        rom, manifest = self.round2_fixture()
        deferred = [{'address': f'0x{address:08X}', 'cause': 'reviewed deferral'}
                    for address in DEFERRED_ADDRESSES]
        self.assertIn('0x00D82218', bpin_contract.bteam_approvals())
        changed = bytearray(rom)
        changed[0xD82218] ^= 1
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            rom_path, map_path = Path(tmp) / 'rom.gba', Path(tmp) / 'manifest.json'
            rom_path.write_bytes(bytes(changed))
            map_path.write_text(json.dumps(manifest))
            classify_round2_issues(deferred, base, str(rom_path), str(map_path))

    def test_round2_byte_pointer_mapping_mutations(self):
        base = json.loads((ROOT / 'data/bteam_baseline.json').read_text(encoding='utf-8'))
        rom, manifest = self.round2_fixture()
        deferred = [{'address': f'0x{address:08X}', 'cause': 'reviewed deferral'}
                    for address in DEFERRED_ADDRESSES]
        # 0xD82218 (the former example) is a plan_C B-pin row now; A2C804 keeps an active pin.
        addr = 0xA2C804
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
            for key, pattern in (('0x00A2C804', 'message bytes or span changed'),
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



def _ledger_bytes(entries, approved='2026-11-04 user (test)'):
    data = {'_doc': 'test', 'approved': approved, 'entries': entries}
    return (json.dumps(data, sort_keys=True, ensure_ascii=False, indent=1) + '\n').encode()


def _sha(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


# Synthetic ledgers are checked against an empty W3 overlay: the committed
# data/dialogue_rewrites.json is filled wave by wave and has its own ledger.
EMPTY_OVERLAY = {'_doc': 'x', 'schema': 1, 'messages': {}}
_EMPTY_LEDGER = json.dumps({'_doc': 'x', 'approved': 'x', 'entries': {}}).encode()


class ApprovedRewriteLedgerTest(unittest.TestCase):
    """data/bteam_approved_rewrites.json bulk approval ledger (plan A T0)."""

    def setUp(self):
        from qa_bteam_drift import APPROVED_EXCEPTIONS
        self.baseline = json.loads((ROOT / 'data/bteam_baseline.json').read_text())
        exceptions = set(APPROVED_EXCEPTIONS) | set(self.baseline['_user_approved_exceptions'])
        self.key = next(k for k in sorted(self.baseline['overrides']) if k not in exceptions)
        self.before = self.baseline['overrides'][self.key]
        self.after = self.before + ' 재작성'
        self.overrides = dict(self.baseline['overrides'])
        self.overrides[self.key] = self.after
        self.entry = {'from': self.before, 'to': self.after, 'batch': 'p2-b00',
                      'reviewed_by': 'harness-review/test',
                      'review_ref': 'temp/fix_20261104/humanizer/batches/p2-b00/review.json',
                      'message': self.key.lower()}

    def test_committed_ledger_is_pinned_and_empty_ledger_passes(self):
        from qa_bteam_drift import (APPROVED_REWRITE_LEDGER, APPROVED_REWRITE_LEDGER_DIGEST,
                                    ledger_entries, load_ledger_bytes)
        raw = load_ledger_bytes()
        self.assertEqual(Path(APPROVED_REWRITE_LEDGER), ROOT / 'data/bteam_approved_rewrites.json')
        self.assertEqual(_sha(raw), APPROVED_REWRITE_LEDGER_DIGEST)
        data = json.loads(raw)
        self.assertEqual(raw.decode(), json.dumps(data, sort_keys=True, ensure_ascii=False,
                                                  indent=1) + '\n')
        result = check(self.baseline, self.baseline['overrides'])
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['drift'], [])
        if not ledger_entries(raw):
            # An empty ledger approves nothing: a B-team change is still drift.
            self.assertEqual(check(self.baseline, self.overrides)['drift'],
                             [(self.key, self.before, self.after)])

    def test_exact_ledger_entry_clears_drift(self):
        raw = _ledger_bytes({self.key: self.entry})
        result = check(self.baseline, self.overrides, rewrites=EMPTY_OVERLAY, ledger_bytes=raw, ledger_pinned=_sha(raw))
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['drift'], [])
        self.assertEqual(result['missing'], [])

    def test_digest_mismatch_fails(self):
        raw = _ledger_bytes({self.key: self.entry})
        result = check(self.baseline, self.overrides, rewrites=EMPTY_OVERLAY, ledger_bytes=raw)
        self.assertTrue(any('digest mismatch' in e for e in result['errors']))
        edited = raw.replace(b'p2-b00', b'p2-b01')
        result = check(self.baseline, self.overrides, ledger_bytes=edited, ledger_pinned=_sha(raw))
        self.assertTrue(any('digest mismatch' in e for e in result['errors']))

    def test_overlap_with_individual_exceptions_fails(self):
        from qa_bteam_drift import APPROVED_EXCEPTIONS
        recorded = self.baseline['_user_approved_exceptions']
        for key in ('0x00DD0D1A', next(k for k in recorded if k not in APPROVED_EXCEPTIONS)):
            with self.subTest(key=key):
                entry = dict(self.entry, **{'from': self.baseline['overrides'].get(key, 'x'),
                                            'to': self.baseline['overrides'].get(key, 'x') + '!'})
                raw = _ledger_bytes({key: entry})
                errors = check(self.baseline, self.baseline['overrides'], ledger_bytes=raw,
                               ledger_pinned=_sha(raw))['errors']
                self.assertTrue(any(key in e and 'overlaps' in e for e in errors), errors)

    def test_from_to_and_metadata_must_be_exact(self):
        cases = {
            'from': dict(self.entry, **{'from': self.before + '.'}),
            'to': dict(self.entry, to=self.after + '.'),
            'noop': dict(self.entry, to=self.before),
            'batch': dict(self.entry, batch=''),
            'reviewed_by': {k: v for k, v in self.entry.items() if k != 'reviewed_by'},
            'review_ref': dict(self.entry, review_ref=None),
        }
        for name, entry in cases.items():
            with self.subTest(case=name):
                raw = _ledger_bytes({self.key: entry})
                result = check(self.baseline, self.overrides, rewrites=EMPTY_OVERLAY, ledger_bytes=raw,
                               ledger_pinned=_sha(raw))
                self.assertTrue(result['errors'], name)
        raw = _ledger_bytes({self.key: self.entry}, approved='')
        self.assertTrue(check(self.baseline, self.overrides, rewrites=EMPTY_OVERLAY, ledger_bytes=raw,
                              ledger_pinned=_sha(raw))['errors'])
        raw = _ledger_bytes({self.key: dict(self.entry, approved='2026-11-04 user')}, approved='')
        self.assertEqual(check(self.baseline, self.overrides, rewrites=EMPTY_OVERLAY, ledger_bytes=raw,
                               ledger_pinned=_sha(raw))['errors'], [])
        raw = _ledger_bytes({self.key.lower(): self.entry})
        self.assertTrue(check(self.baseline, self.overrides, rewrites=EMPTY_OVERLAY, ledger_bytes=raw,
                              ledger_pinned=_sha(raw))['errors'])
        raw = _ledger_bytes({'0x00FFFFF0': dict(self.entry)})
        self.assertTrue(check(self.baseline, self.overrides, rewrites=EMPTY_OVERLAY, ledger_bytes=raw,
                              ledger_pinned=_sha(raw))['errors'])
        # An unlisted B-team change next to a listed one is still drift.
        raw = _ledger_bytes({self.key: self.entry})
        other = next(k for k in sorted(self.baseline['overrides'])
                     if k > self.key and k not in self.baseline['_user_approved_exceptions'])
        overrides = dict(self.overrides)
        overrides[other] = overrides[other] + '?'
        self.assertEqual([d[0] for d in check(self.baseline, overrides, rewrites=EMPTY_OVERLAY, ledger_bytes=raw,
                                              ledger_pinned=_sha(raw))['drift']], [other])

    def test_accept_keeps_baseline_for_ledger_addresses(self):
        from qa_bteam_drift import accept
        raw = _ledger_bytes({self.key: self.entry})
        new = accept(self.baseline, self.overrides, ledger_bytes=raw)
        self.assertEqual(new['overrides'][self.key], self.before)
        self.assertEqual(core_digest(new), PINNED_CORE_DIGEST)
        with self.assertRaisesRegex(ValueError, 'outside the approved exceptions'):
            accept(self.baseline, self.overrides, ledger_bytes=_ledger_bytes({}))

    def test_final_rom_gate_matches_only_ledger_to_text(self):
        na = json.loads((ROOT / 'data/syllable_to_code_2350.json').read_text())['나']
        na = (int(na, 0) if isinstance(na, str) else na).to_bytes(2, 'big')
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            folder = Path(tmp)
            rom = bytearray(256)
            rom[0x20:0x22] = na
            writes = [[0x20, 2, 2, na.hex(), None, '나', 0, 'test']]
            base = {'overrides': {'0x00000020': '가'}}
            paths = [folder / name for name in ('rom.gba', 'map.json', 'manifest.json')]
            paths[0].write_bytes(rom)
            paths[1].write_text(json.dumps(writes))
            paths[2].write_text('[]')
            empty = _ledger_bytes({})
            self.assertEqual(len(check_rom(base, *map(str, paths), ledger_bytes=empty,
                                           ledger_pinned=_sha(empty))), 1)
            entry = dict(self.entry, **{'from': '가', 'to': '나'})
            raw = _ledger_bytes({'0x00000020': entry})
            self.assertEqual(check_rom(base, *map(str, paths), ledger_bytes=raw,
                                       ledger_pinned=_sha(raw)), [])
            wrong = _ledger_bytes({'0x00000020': dict(entry, to='다')})
            self.assertEqual(len(check_rom(base, *map(str, paths), ledger_bytes=wrong,
                                           ledger_pinned=_sha(wrong))), 1)
            stale = _ledger_bytes({'0x00000020': dict(entry, **{'from': '라'})})
            self.assertEqual(len(check_rom(base, *map(str, paths), ledger_bytes=stale,
                                           ledger_pinned=_sha(stale))), 1)
            with self.assertRaisesRegex(ValueError, 'ledger digest mismatch'):
                check_rom(base, *map(str, paths), ledger_bytes=raw)

    def test_final_rom_gate_rejects_old_wording_for_valid_ledger(self):
        """A valid ledger entry makes its row require "to": old wording is a hard issue."""
        from qa_bteam_drift import round2_issue_bucket
        na = json.loads((ROOT / 'data/syllable_to_code_2350.json').read_text())['나']
        na = (int(na, 0) if isinstance(na, str) else na).to_bytes(2, 'big')
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            folder = Path(tmp)
            paths = [folder / name for name in ('rom.gba', 'map.json', 'manifest.json')]
            base = {'overrides': {'0x00000020': '가'}}
            entry = dict(self.entry, **{'from': '가', 'to': '나'})
            raw = _ledger_bytes({'0x00000020': entry})

            def issues(glyph):
                rom = bytearray(256)
                rom[0x20:0x22] = glyph
                paths[0].write_bytes(rom)
                paths[1].write_text(json.dumps([[0x20, 2, 2, glyph.hex(), None, 'x', 0, 'test']]))
                paths[2].write_text('[]')
                return check_rom(base, *map(str, paths), ledger_bytes=raw, ledger_pinned=_sha(raw))

            self.assertEqual(issues(na), [])
            old = issues(GLYPH)  # ROM still shows the baseline ("from") wording
            self.assertEqual([(x['address'], x['rom_text'], x['decision']) for x in old],
                             [('0x00000020', '가', 'APPLY_LEDGER_REWRITE')])
            self.assertEqual(old[0]['cause'], 'ledger-owned row differs from approved rewrite "to"')
            # Never absorbed as a listed round-2 residual, even at a listed address.
            self.assertEqual(round2_issue_bucket(old[0], {0x20}), 'unlisted')
            # Baseline-only equivalences (width alias here) must not rescue it either.
            with mock.patch('qa_bteam_drift.round2_width_equivalent', return_value=True), \
                    mock.patch('qa_bteam_drift.matches_reviewed_bteam_spacing', return_value=True):
                self.assertEqual(len(issues(GLYPH)), 1)
                self.assertEqual(issues(na), [])
            # An entry whose "from" is not the baseline binds nothing: both readings fail.
            stale = _ledger_bytes({'0x00000020': dict(entry, **{'from': '라'})})
            raw = stale
            self.assertEqual([x['cause'] for x in issues(na)],
                             ['ledger entry not bound to the B-team baseline'])
            self.assertEqual(len(issues(GLYPH)), 1)

    def test_builder_final_gate_rejects_old_wording_of_ledger_restore_row(self):
        """The builder's final check_rom call (committed ledger) fails a ledger row left unchanged."""
        import re
        import build_korean_full as builder
        from qa_bteam_drift import ledger_entries, load_ledger_bytes
        source = (ROOT / 'tools/build_korean_full.py').read_text(encoding='utf-8')
        # The builder relies on the committed, pinned ledger (no override arguments).
        self.assertRegex(source, r'_check_bteam_rom\(_bteam_baseline, staged_rom, intg_path, staged_manifest\)')
        ledger = ledger_entries(load_ledger_bytes())
        accounted = (set(builder.BTEAM_PREVIOUS_KOREAN_TEXT) | set(builder.BTEAM_ROUND2_RESIDUALS)
                     | set(builder.BTEAM_SCRIPT_SPACING_REPAIRS) | {0xA34B6C})
        rows = [k for k in sorted(ledger) if int(k, 16) in builder.BTEAM_RESTORE_BASELINE_ROWS
                and int(k, 16) not in accounted]
        if not rows:
            self.skipTest('no ledger-owned builder restoration row')
        syl = {s: int(c, 16) for s, c in json.loads(
            (ROOT / 'data/syllable_to_code_2350.json').read_text()).items()}
        key, address = rows[0], int(rows[0], 16)
        base = {'overrides': {key: self.baseline['overrides'][key]}}
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            folder = Path(tmp)
            paths = [folder / name for name in ('rom.gba', 'map.json', 'manifest.json')]

            def issues(text):
                # Rendered form as the overlay writes it (fullwidth spaces/punctuation).
                enc = b''.join(syl[ch].to_bytes(2, 'big') if ch in syl
                               else b'\x81\x40' if ch == '\u3000' else ch.encode('shift_jis')
                               for ch in display_equivalent(text, address))
                rom = bytearray(address + len(enc) + 16)
                rom[address:address + len(enc)] = enc
                paths[0].write_bytes(rom)
                paths[1].write_text(json.dumps([[address, len(enc), len(enc), enc.hex(),
                                                 None, text, 0, 'test']]))
                paths[2].write_text('[]')
                return check_rom(base, *map(str, paths))  # same call shape as the builder

            self.assertEqual(issues(ledger[key]['to']), [])
            old = issues(ledger[key]['from'])
            self.assertEqual([(x['address'], x['decision']) for x in old],
                             [(key, 'APPLY_LEDGER_REWRITE')])
        # The builder raises when a restoration issue is outside its expected
        # residual set; this row is not in any expected-residual source.
        self.assertNotIn(address, accounted)


class DialogueRewriteOverlayDriftTest(unittest.TestCase):
    """W3 rewrites (data/dialogue_rewrites.json owner_texts) feed both drift gates."""

    def setUp(self):
        from qa_bteam_drift import APPROVED_EXCEPTIONS
        self.baseline = json.loads((ROOT / 'data/bteam_baseline.json').read_text())
        exceptions = set(APPROVED_EXCEPTIONS) | set(self.baseline['_user_approved_exceptions'])
        self.key = next(k for k in sorted(self.baseline['overrides']) if k not in exceptions)
        self.other = next(k for k in sorted(self.baseline['overrides'])
                          if k > self.key and k not in exceptions)
        self.before = self.baseline['overrides'][self.key]
        self.after = self.before + ' 재작성'
        self.row = f'0x{int(self.key, 16):06X}'
        self.overrides = dict(self.baseline['overrides'])

    def rewrites(self, owner_texts):
        entry = {'source': self.row, 'game': 'p2', 'before_sha256': 'a', 'after_sha256': 'b',
                 'ko': self.after, 'batch': 'p2-b00', 'reviewed_by': 'harness-review/test',
                 'review_ref': 'temp/test/review.json'}
        if owner_texts is not None:
            entry['owner_texts'] = owner_texts
        return {'_doc': 'test', 'schema': 1, 'messages': {self.row: entry}}

    def entry(self, **change):
        entry = {'from': self.before, 'to': self.after, 'batch': 'p2-b00',
                 'reviewed_by': 'harness-review/test', 'review_ref': 'temp/test/review.json',
                 'message': self.row}
        entry.update(change)
        return entry

    def run_check(self, rewrites, entries):
        raw = _ledger_bytes(entries)
        return check(self.baseline, self.overrides, rewrites=rewrites,
                     ledger_bytes=raw, ledger_pinned=_sha(raw))

    def test_empty_overlay_is_a_no_op(self):
        result = self.run_check(EMPTY_OVERLAY, {})
        self.assertEqual((result['drift'], result['errors']), ([], []))
        # The committed overlay (None = load data/dialogue_rewrites.json) is
        # covered by the committed ledger, so it is drift-free as well.
        result = check(self.baseline, self.overrides)
        self.assertEqual((result['drift'], result['errors']), ([], []))

    def test_ledgered_rewrite_passes(self):
        result = self.run_check(self.rewrites({self.row: self.after}), {self.key: self.entry()})
        self.assertEqual((result['drift'], result['missing'], result['errors']), ([], [], []))
        # Non-B-team rows of the same message never need a ledger entry.
        result = self.run_check(self.rewrites({self.row: self.after, '0xFFFFF0': 'x'}),
                                {self.key: self.entry()})
        self.assertEqual((result['drift'], result['errors']), ([], []))

    def test_unlisted_rewrite_is_drift(self):
        result = self.run_check(self.rewrites({self.row: self.after}), {})
        self.assertEqual(result['drift'], [(self.key, self.before, self.after)])
        # A listed row does not cover another rewritten B-team row of the message.
        other_row = f'0x{int(self.other, 16):06X}'
        other_text = self.baseline['overrides'][self.other] + '?'
        result = self.run_check(self.rewrites({self.row: self.after, other_row: other_text}),
                                {self.key: self.entry()})
        self.assertEqual([d[0] for d in result['drift']], [self.other])

    def test_ledger_to_or_from_mismatch_fails(self):
        for name, entry in {'to': self.entry(to=self.after + '.'),
                            'from': self.entry(**{'from': self.before + '.'})}.items():
            with self.subTest(case=name):
                result = self.run_check(self.rewrites({self.row: self.after}), {self.key: entry})
                self.assertTrue(any(self.key in e for e in result['errors']), result['errors'])
        # The override alone (without the rewrite) no longer matches the ledger "to".
        result = self.run_check({'_doc': 'x', 'schema': 1, 'messages': {}}, {self.key: self.entry()})
        self.assertTrue(any('override differs from the ledger' in e for e in result['errors']))

    def test_rewrite_without_owner_texts_or_bad_overlay_fails(self):
        result = self.run_check(self.rewrites(None), {})
        self.assertTrue(any('owner_texts' in e for e in result['errors']), result['errors'])
        doc = self.rewrites({self.row: self.after})
        second = dict(doc['messages'][self.row], source='0xFFFFF0')
        doc['messages']['0xFFFFF0'] = second
        result = self.run_check(doc, {self.key: self.entry()})
        self.assertTrue(any('two dialogue rewrites' in e for e in result['errors']))
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            bad = Path(tmp) / 'rewrites.json'
            bad.write_text(json.dumps({'schema': 9, 'messages': {}}))
            from qa_bteam_drift import rewrite_owner_texts
            self.assertTrue(rewrite_owner_texts(path=str(bad))[1])

    def test_rewrite_of_individual_exception_row_fails(self):
        key = '0x00DD0D1A'
        row = f'0x{int(key, 16):06X}'
        doc = self.rewrites({row: '다른 문장'})
        doc['messages'] = {row: dict(doc['messages'][self.row], source=row)}
        result = self.run_check(doc, {})
        self.assertTrue(any(key in e for e in result['errors']), result['errors'])

    def test_rom_gate_reads_relocated_overlay_message(self):
        na = json.loads((ROOT / 'data/syllable_to_code_2350.json').read_text())['나']
        na = (int(na, 0) if isinstance(na, str) else na).to_bytes(2, 'big')
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            folder = Path(tmp)
            rom = bytearray(256)
            # Native message keeps its old bytes; the overlay copy lives at 0xA0.
            rom[0x40:0x42] = GLYPH
            rom[0xA0:0xA2] = na
            rom[0xA2] = 0
            rom[0x10:0x14] = (0x080000A0).to_bytes(4, 'little')
            writes = [[0x40, 2, 2, GLYPH.hex(), None, '가', 0, 'native'],
                      [0xA0, 3, 3, (na + b'\0').hex(), None, None, None, 'dialogue-rewrite-final'],
                      [0x10, 4, 4, (0x080000A0).to_bytes(4, 'little').hex(), None, None, None,
                       'dialogue-rewrite-pointer']]
            manifest = [{'msg': '0x40', 'old_len': 3, 'status': 'relocated', 'ptr_off': '0x10',
                         'ptr_sites': ['0x10'], 'new_addr': '0xA0', 'new_len': 3,
                         'line_spans': {'0x000040': [0, 2]},
                         'source_line_fragments': {'0x000040': [[0, 2]]},
                         'rewrite': {'previous_target': '0x000040', 'previous_status': 'native'}}]
            base = {'overrides': {'0x00000040': '가'}}
            paths = [folder / name for name in ('rom.gba', 'map.json', 'manifest.json')]
            paths[0].write_bytes(rom)
            paths[1].write_text(json.dumps(writes))
            paths[2].write_text(json.dumps(manifest))
            entry = self.entry(**{'from': '가', 'to': '나', 'message': '0x000040'})

            def issues(entries):
                raw = _ledger_bytes(entries)
                return check_rom(base, *map(str, paths), ledger_bytes=raw, ledger_pinned=_sha(raw))

            self.assertEqual(issues({'0x00000040': entry}), [])
            missing = issues({})
            self.assertEqual([(x['address'], x['rom_text']) for x in missing],
                             [('0x00000040', '나')])
            self.assertEqual(len(issues({'0x00000040': dict(entry, to='다')})), 1)
            # The old native bytes still read '가', but the gate follows the
            # pointer: a stale pointer to the native slot is a hard mismatch.
            rom[0x10:0x14] = (0x08000040).to_bytes(4, 'little')
            writes[2][3] = rom[0x10:0x14].hex()
            paths[0].write_bytes(rom)
            paths[1].write_text(json.dumps(writes))
            stale = issues({'0x00000040': entry})
            self.assertEqual([x['cause'] for x in stale], ['repoint pointer mismatch'])


if __name__ == '__main__':
    unittest.main()
