#!/usr/bin/env python3
"""Focused final-ROM B-team drift gate tests."""
import json
import tempfile
import unittest
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qa_bteam_drift import (check, check_rom, compact_glyph_map, decode_compact,
                            display_equivalent, round2_width_equivalent,
                            classify_round2_issues,
                            reviewed_seam_variants,
                            matches_alignment_composite, matches_reviewed_bteam_spacing,
                            DEFERRED_ADDRESSES, COMPACT_GLYPH_ADDRESSES,
                            NEW_STRICT_ADDRESSES, PINNED_CORE_DIGEST, core_digest)
from qa_bteam_drift import round2_issue_bucket


ROOT = Path(__file__).resolve().parents[1]
CODE = json.loads((ROOT / 'data/syllable_to_code_2350.json').read_text())['가']
CODE = int(CODE, 0) if isinstance(CODE, str) else CODE
GLYPH = CODE.to_bytes(2, 'big')


class RomDriftTest(unittest.TestCase):
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
