"""Missing plain-script source must remain editable after map/group regeneration."""
import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build_dialogue_map as dialogue_map
import build_dialogue_groups as dialogue_groups
import build_korean_full as builder


class PlainScriptSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Original assets stay local; no extracted ROM fixture is tracked.
        cls.original = Path(builder.P.ROM).read_bytes()

    def test_exact_canonical_operands_decode_without_adjacent_controls(self):
        for address, expected in ((0xA0CC61, 'この'), (0xA0CC6B, 'よ。')):
            with self.subTest(address=hex(address)):
                self.assertEqual(builder.SCRIPT_PLAIN_OPERAND_SPANS[address], address + 4)
                self.assertEqual(dialogue_map.plain_script_source_text(
                    self.original, address, 4, 'script:reef regression'), expected)
        self.assertEqual(self.original[0xA0CC65], 0x77)
        self.assertEqual(self.original[0xA0CC6A], 0x77)
        self.assertEqual(self.original[0xA0CC6F], 0x6B)

    def test_unknown_relocated_and_mismatched_rows_are_not_decoded(self):
        cases = [(0xA0CC61, 3, 'script:x'), (0xA0CC61, 5, 'script:x'),
                 (0xA0CC61, 0, 'script:x'), (0xA0CC61, -1, 'script:x'),
                 (0xA0CC61, '4', 'script:x'), (0xA0CC61, True, 'script:x'),
                 (0xA0CC62, 4, 'script:x'), (0xA75000, 4, 'script:x'),
                 (0xA0CC61, 4, 'repoint:x'), (0xA0CC61, 4, 'raw_replace'),
                 (0xA0CC61, 4, None), (-1, 4, 'script:x')]
        for address, slot, kind in cases:
            with self.subTest(address=address, slot=slot, kind=kind):
                self.assertEqual(dialogue_map.plain_script_source_text(
                    self.original, address, slot, kind), '')
        self.assertEqual(dialogue_map.plain_script_source_text(
            self.original[:0xA0CC63], 0xA0CC61, 4, 'script:x'), '')

    def test_control_bytes_and_invalid_sjis_cannot_be_promoted_to_source(self):
        for raw in (b'\x82\xb177', b'\x82\xb1\x77\x00', b'\x82\x7f\x82\xcc',
                    b'\x00\x00\x00\x00', b'ABCD'):
            original = bytearray(self.original)
            original[0xA0CC61:0xA0CC65] = raw
            with self.subTest(raw=raw.hex()):
                self.assertEqual(dialogue_map.plain_script_source_text(
                    original, 0xA0CC61, 4, 'script:x'), '')
        with patch.dict(builder.SCRIPT_PLAIN_OPERAND_SPANS, {0xA0CC61: 0xA0CC66}):
            self.assertEqual(dialogue_map.plain_script_source_text(
                self.original, 0xA0CC61, 5, 'script:x'), '')
        # 0x77 is legal as the second byte of an SJIS glyph; do not scan raw
        # bytes for controls without respecting glyph boundaries.
        original = bytearray(self.original)
        original[0xA0CC61:0xA0CC65] = '『』'.encode('shift_jis')
        self.assertEqual(dialogue_map.plain_script_source_text(
            original, 0xA0CC61, 4, 'script:x'), '『』')

    def regenerate_fixture(self, directory, existing_source=None, stale_span=False, fixed_collision=False):
        root = Path(directory)
        found, trans, integrity = (root / name for name in ('found.csv', 'trans.csv', 'integrity.json'))
        with found.open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['address', 'text', 'length'])
            writer.writerow(['0x00A0CC58', 'それは、', 8])
            if existing_source is not None:
                writer.writerow(['0x00A0CC61', existing_source, 4])
        trans.write_text('address,japanese,korean,length\n')
        entries = [(0xA0CC58, 8, '그건, ', 'script:reef introduction'),
                   (0xA0CC61, 4, '이 ', 'script:reef demonstrative'),
                   (0xA0CC66, 4, '암초', 'known-story-fragment'),
                   (0xA0CC6B, 4, '야.', 'script:reef ending')]
        integrity.write_text(json.dumps([[a, slot, 0, '', 32, ko, 0, kind]
                                        for a, slot, ko, kind in entries]))
        if stale_span:
            data = json.loads(integrity.read_text())
            data[1][1] = 14  # Historical writer crossed 77 and the next operand.
            data = [row for row in data if row[0] != 0xA0CC6B]
            integrity.write_text(json.dumps(data))
        output = root / 'map.json'
        overrides = {a: ko for a, _, ko, kind in entries if kind.startswith('script:')}
        with (patch.object(dialogue_map, 'load_build_text_overrides', return_value=(overrides, {}, {})),
              patch.object(dialogue_map, 'load_direct_patch_texts', return_value=(
                  {0xA0CC61: '이 ', 0xA0CC6B: '야.'} if stale_span else
                  {0xA0CC66: 'incorrect editable text'} if fixed_collision else {})),
              patch.object(dialogue_map, 'load_dialogue_overrides', return_value={}),
              patch.object(dialogue_map, 'load_display_overrides', return_value={}),
              patch('sys.argv', ['build_dialogue_map', '--found', str(found), '--trans', str(trans),
                                 '--integrity', str(integrity), '--out', str(output)]),
              contextlib.redirect_stdout(io.StringIO())):
            self.assertEqual(dialogue_map.main(), 0)
        return output

    def test_stale_or_missing_build_metadata_cannot_restore_merged_ownership(self):
        with tempfile.TemporaryDirectory(dir=Path(builder.BASE) / 'temp') as directory:
            output = self.regenerate_fixture(directory, stale_span=True)
            rows = {int(row['address'], 16): row for row in json.loads(output.read_text())['lines']}
            for address, ja, ko in ((0xA0CC61, 'この', '이 '), (0xA0CC6B, 'よ。', '야.')):
                self.assertEqual(rows[address]['slot'], 4)
                self.assertEqual(rows[address]['ja'], ja)
                self.assertEqual(rows[address]['ko'], ko)
                self.assertIsNone(rows[address]['ship_ko'])
                self.assertFalse(rows[address]['is_noise'])

    def test_fixed_fragment_keeps_its_writer_even_if_plain_declaration_overlaps(self):
        with (tempfile.TemporaryDirectory(dir=Path(builder.BASE) / 'temp') as directory,
              patch.dict(builder.SCRIPT_PLAIN_OPERAND_SPANS, {0xA0CC66:0xA0CC6A})):
            output = self.regenerate_fixture(directory, fixed_collision=True)
            row = next(r for r in json.loads(output.read_text())['lines'] if r['address']=='0x00A0CC66')
            self.assertEqual(row['kind'],'known-story-fragment')
            self.assertEqual(row['ko'],'암초')

    def test_regenerated_map_and_groups_include_both_missing_fragments(self):
        with tempfile.TemporaryDirectory(dir=Path(builder.BASE) / 'temp') as directory:
            output = self.regenerate_fixture(directory)
            lines = {int(row['address'], 16): row for row in json.loads(output.read_text())['lines']}
            self.assertEqual(lines[0xA0CC61]['ja'], 'この')
            self.assertEqual(lines[0xA0CC6B]['ja'], 'よ。')
            self.assertEqual(lines[0xA0CC66]['ja'], '岩礁')
            self.assertEqual(lines[0xA0CC66]['kind'], 'known-story-fragment')
            self.assertTrue(all(not row['is_noise'] for row in lines.values()))
            groups_path = Path(directory) / 'groups.json'
            with (patch.object(dialogue_groups, 'DMAP', str(output)),
                  patch.object(dialogue_groups, 'OUT', str(groups_path)),
                  patch.object(dialogue_groups, 'OVERRIDES', str(Path(directory) / 'no-overrides.json')),
                  contextlib.redirect_stdout(io.StringIO())):
                dialogue_groups.main()
            groups = json.loads(groups_path.read_text())['groups']
            self.assertEqual(len(groups), 1)
            group = groups[0]
            self.assertEqual([m['address'] for m in group['members']],
                             ['0x00A0CC58', '0x00A0CC61', '0x00A0CC66', '0x00A0CC6B'])
            self.assertEqual(group['assembled_ja'], 'それは、この岩礁よ。')
            self.assertEqual(group['assembled_ko'], '그건, 이 암초야.')
            self.assertEqual([(s['address'], s['raw']) for s in group['segments'] if s['kind'] == 'ctrl'],
                             [('0x00A0CC60', '77'), ('0x00A0CC65', '77'), ('0x00A0CC6A', '77')])

    def test_existing_nonempty_source_is_preserved(self):
        with tempfile.TemporaryDirectory(dir=Path(builder.BASE) / 'temp') as directory:
            output = self.regenerate_fixture(directory, existing_source='既存の原文')
            row = next(row for row in json.loads(output.read_text())['lines']
                       if row['address'] == '0x00A0CC61')
            self.assertEqual(row['ja'], '既存の原文')


if __name__ == '__main__':
    unittest.main()
