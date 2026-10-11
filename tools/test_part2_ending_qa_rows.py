"""Part 2 ending-QA fragment repairs and recap labels (2026-10-08)."""
import collections
import json
import os
import struct
import unittest
from pathlib import Path
from unittest import mock

import part2_ending_qa_rows as R
import part2_recap_labels as recap
from dialogue_repoint import PORTRAIT_ROW_HALF_CELLS

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
CANDIDATE = ROOT / 'output/game_wars_korean_candidate_part2_20261008_v9.gba'


class EndingRowTests(unittest.TestCase):
    def test_rows_are_unprotected_whole_fragments(self):
        import build_korean_full as builder
        protected = set(json.loads((ROOT / 'data/bteam_baseline.json').read_text())['overrides'])
        protected |= set(json.loads((ROOT / 'data/bteam_addresses.json').read_text())['addresses'])
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        starts = [s for s, _, _ in R.ROWS]
        self.assertEqual(len(starts), len(set(starts)))
        for start, end, text in R.ROWS:
            with self.subTest(address=hex(start)):
                self.assertNotIn(f'0x{start:08X}', protected)
                body = ORIGINAL[start:end]
                self.assertTrue(body and all(len(ch.encode('shift_jis')) == 2 for ch in body.decode('shift_jis')))
                self.assertLess(ORIGINAL[end], 0x81)     # ends at a control byte
                self.assertIn(start, builder.PLAYTHROUGH_REPAIR_ROWS)   # forced relocation
                self.assertEqual(builder.SCRIPT_PLAIN_OPERAND_SPANS[start], end)
                self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[start], text)
                builder.encode_full_fidelity(text, codes, collections.Counter(), start)

    @unittest.skipUnless(CANDIDATE.is_file(), 'v9 candidate ROM required for native parser fixture')
    def test_composed_row_gate_rejects_wide_rows(self):
        import build_korean_full as builder
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        start = R.ROWS[0][0]
        source_record = next(m for m in json.loads((ROOT / 'temp/repoint_manifest.json').read_text())
                             if f'0x{start:06X}' in m.get('line_spans', {}))

        def message(cells):
            glyph = codes['가'].to_bytes(2, 'big')
            return glyph * (cells // 2) + b'\x57' + glyph * (cells - cells // 2) + b'\x6b\x00'

        for cells, ok in ((PORTRAIT_ROW_HALF_CELLS // 2, True), (PORTRAIT_ROW_HALF_CELLS // 2 + 1, False)):
            data = message(cells)
            rom = bytearray(CANDIDATE.read_bytes())
            rom[0xA49FC0:0xA49FC0 + len(data)] = data
            struct.pack_into('<I', rom, int(source_record['ptr_off'], 16), 0x08A49FC0)
            manifest = [{**source_record, 'new_addr': '0xA49FC0', 'new_len': len(data),
                         'line_spans': {f'0x{start:06X}': [0, 2]}}]
            with mock.patch.object(R, 'ROWS', ((start, 0, '가'),)):
                if ok:
                    self.assertEqual(R.check_composed_rows(rom, manifest)[start], 2 * cells)
                else:
                    with self.assertRaisesRegex(AssertionError, 'assembled width'):
                        R.check_composed_rows(rom, manifest)
        with self.assertRaisesRegex(AssertionError, 'not relocated'):
            R.check_composed_rows(rom, [])

    @unittest.skipUnless(CANDIDATE.is_file(), 'v9 candidate ROM required for native parser fixture')
    def test_consume_only_and_bad_payload_or_manifest_fail_closed(self):
        import build_korean_full as builder
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        glyph = codes['가'].to_bytes(2, 'big')
        start = R.ROWS[0][0]
        source_record = next(m for m in json.loads((ROOT / 'temp/repoint_manifest.json').read_text())
                             if f'0x{start:06X}' in m.get('line_spans', {}))
        base = CANDIDATE.read_bytes()

        def check(data, span=(0, 2)):
            rom = bytearray(base)
            rom[0xA49FC0:0xA49FC0 + len(data)] = data
            struct.pack_into('<I', rom, int(source_record['ptr_off'], 16), 0x08A49FC0)
            manifest = [{**source_record, 'new_addr': '0xA49FC0', 'new_len': len(data),
                         'line_spans': {f'0x{start:06X}': list(span)}}]
            with mock.patch.object(R, 'ROWS', ((start, 0, '가'),)):
                return R.check_composed_rows(rom, manifest)

        for control in (b'\x09', b'\x0a'):
            with self.subTest(control=control), self.assertRaisesRegex(AssertionError, 'assembled width.*48>44'):
                check(glyph * 12 + control + glyph * 12 + b'\x6b\x00')
        with self.assertRaisesRegex(AssertionError, 'unknown control'):
            check(glyph + b'\x11' + glyph + b'\x00')
        with self.assertRaisesRegex(AssertionError, 'malformed'):
            check(glyph + b'\x81\x00')
        with self.assertRaisesRegex(AssertionError, 'invalid.*span'):
            check(glyph + b'\x00', (2, 4))

    @unittest.skipUnless(os.environ.get('AW_TEST_ROM') and os.environ.get('AW_TEST_MANIFEST'),
                         'set AW_TEST_ROM/AW_TEST_MANIFEST to the candidate and its repoint manifest')
    def test_candidate_rows_fit_the_portrait_box(self):
        rom = Path(os.environ['AW_TEST_ROM']).read_bytes()
        manifest_path = Path(os.environ['AW_TEST_MANIFEST'])
        manifest_raw = manifest_path.read_bytes()
        receipt = json.loads(Path(os.environ['AW_TEST_ROM'] + '.build.json').read_text())
        from qa_part2_physical_rows import bind_artifacts
        codes = (ROOT / 'data/syllable_to_code_2350.json').read_bytes()
        bind_artifacts(ORIGINAL, rom, manifest_raw, receipt, codes)
        manifest = json.loads(manifest_raw)
        widths = R.check_composed_rows(rom, manifest)
        self.assertLessEqual(max(widths.values()), PORTRAIT_ROW_HALF_CELLS)
        self.assertLessEqual(widths[0xA1A399], 42)   # 전멸 전까진 무슨 일이 생길지 모른다.


class RecapLabelTests(unittest.TestCase):
    def test_labels_change_only_label_tiles_and_fit(self):
        native = recap.source_guard(ORIGINAL)
        data = recap.render(ORIGINAL)
        self.assertEqual(data[20 * 32:], native[20 * 32:])      # digits 0-9 untouched
        self.assertNotEqual(data[:20 * 32], native[:20 * 32])
        values = {v for b in data[:20 * 32] for v in (b & 15, b >> 4)}
        self.assertLessEqual(values, {0, recap.FILL, recap.SHADOW})
        self.assertEqual(len(recap.expected_region(ORIGINAL)), recap.CAPACITY)
        broken = bytearray(ORIGINAL)
        broken[recap.POINTER] ^= 1
        with self.assertRaises(AssertionError):
            recap.source_guard(bytes(broken))

    @unittest.skipUnless(os.environ.get('AW_TEST_ROM'), 'set AW_TEST_ROM to the candidate under test')
    def test_candidate_carries_the_labels(self):
        recap.verify(Path(os.environ['AW_TEST_ROM']).read_bytes(), ORIGINAL)


if __name__ == '__main__':
    unittest.main()
