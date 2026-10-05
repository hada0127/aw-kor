"""Native-source regression for the observed artillery R-help punctuation loss."""
import collections
import json
from pathlib import Path
import struct
import unittest

import build_korean_full as B
from dialogue_regions import needs_safe_dialogue_punctuation
from dialogue_repoint import repoint_messages, text_segment_cells, _line_index, _read_table


class ArtilleryHelpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = Path(B.P.ROM).read_bytes()
        cls.codes = {k: int(v, 16) for k, v in json.loads(Path(B.SYLCODE).read_text()).items()}
        cls.rows = {0xA32278: (16, '차량계 유닛.'),
                    0xA32289: (26, '간접 공격 가능한 유닛의'),
                    0xA322A4: (22, '중에서는, 값도 싸다.')}

    def full(self, address):
        return B.encode_full_fidelity(self.rows[address][1], self.codes, collections.Counter(), address)

    def test_observed_source_boundaries_and_lossless_requirement(self):
        self.assertEqual(struct.unpack_from('<I', self.original, 0xA38798)[0], 0x08A32278)
        self.assertEqual(self.original[0xA322A4:0xA322BA].decode('shift_jis'), '中では、ねだんも安い。')
        self.assertEqual(self.original[0xA32288], 0x72)
        self.assertEqual(self.original[0xA322A3], 0x72)
        self.assertEqual(self.original[0xA322BA:0xA322BC], b'\0\0')
        for address in self.rows:
            self.assertTrue(needs_safe_dialogue_punctuation(address))
        for address in (0xA32277, 0xA322BA, 0xA322BC):
            self.assertFalse(needs_safe_dialogue_punctuation(address))
        address = 0xA322A4
        encoded, _ = B.encode_fit(self.rows[address][1], 22, self.codes, collections.Counter(), address)
        full = self.full(address)
        self.assertEqual(len(full), 24)
        self.assertIn(b'\x81\x41', full)
        self.assertTrue(full.endswith(b'\x81\x42'))
        self.assertTrue(B.story_requires_lossless_repoint(address, encoded, full))

    def test_real_message_repoint_preserves_controls_and_complete_words(self):
        rom = bytearray(self.original)
        lines = _line_index(B.FOUND)
        self.assertIn((0xA38798, 0xA32278), _read_table(self.original, 0xA357B4))
        for address, (size, _) in self.rows.items():
            self.assertEqual(lines[address][0], size)
        reverse = {v: k for k, v in self.codes.items()}

        def decode(raw):
            result, pos = [], 0
            while pos < len(raw):
                size = 2 if 0x81 <= raw[pos] <= 0xEF and pos + 1 < len(raw) else 1
                cell = raw[pos:pos + size]
                result.append(reverse.get(int.from_bytes(cell, 'big'), cell.decode('shift_jis', errors='replace')))
                pos += size
            return ''.join(result)

        manifest, stats = repoint_messages(
            rom, self.original, fixable=lambda a: a in self.rows,
            fixed_bytes=self.full, fit_level_dlg=lambda a: 6,
            decode_text=decode, cell_width=lambda a: text_segment_cells(self.full(a)),
            slots={a: n for a, (n, _) in self.rows.items()}, line_index=self.rows,
            table_offsets=[0xA357B4],
            free_start=0xA3D000, free_end=0xA3D100)
        self.assertEqual(stats['relocated'], 1, (manifest, stats))
        target = struct.unpack_from('<I', rom, 0xA38798)[0] - 0x08000000
        expected = b'\x72'.join(self.full(a) for a in self.rows) + b'\0\0'
        self.assertEqual(rom[target:target + len(expected)], expected)
        self.assertEqual(rom[0xA32278:0xA322BC], self.original[0xA32278:0xA322BC])
        self.assertLessEqual(max(text_segment_cells(self.full(a)) for a in self.rows), 50)

    def test_missing_required_relocation_is_fatal(self):
        import ast
        tree = ast.parse(Path(B.__file__).read_text())
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        assignment = next(n for n in ast.walk(main) if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'required_script_repoints' for t in n.targets))
        # The set also holds module constants (red_unit_intro / part1_m19_dialogue
        # ADDRESS names); keep only the literal artillery entry checked here.
        self.assertIsInstance(assignment.value, ast.Set)
        required = {ast.literal_eval(e) for e in assignment.value.elts if isinstance(e, ast.Constant)}
        self.assertIn(0xA322A4, required)
        with self.assertRaisesRegex(AssertionError, '0x00A322A4'):
            B.verify_required_script_repoints(required, set())
        B.verify_required_script_repoints(required, {0xA322A4})


if __name__ == '__main__':
    unittest.main()
