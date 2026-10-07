#!/usr/bin/env python3
"""Focused final-ROM B-team drift gate tests."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from qa_bteam_drift import (check, check_rom, compact_glyph_map, decode_compact,
                            display_equivalent, reviewed_seam_variants,
                            matches_alignment_composite, matches_reviewed_bteam_spacing,
                            DEFERRED_ADDRESSES, COMPACT_GLYPH_ADDRESSES,
                            NEW_STRICT_ADDRESSES, PINNED_CORE_DIGEST, core_digest)


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
        self.assertEqual(len(DEFERRED_ADDRESSES), 25)
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
