"""The bomber card's native NUL label is independent of OBJ captions."""
import ast
from collections import Counter
import json
from pathlib import Path
import struct
import unittest

import build_korean_full as B
import build_dialogue_map as M
import qa_text_fit


class BomberWeaponLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = Path(B.P.ROM).read_bytes()
        cls.codes = {s: int(c, 16) for s, c in json.loads(Path(B.SYLCODE).read_text()).items()}
        tree = ast.parse(Path(B.__file__).read_text())
        cls.writer = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'fixed_zero_text_patch')
        cls.rows = [ast.literal_eval(n) for n in ast.walk(tree)
                    if isinstance(n, ast.Tuple) and len(n.elts) == 3
                    and isinstance(n.elts[0], ast.Constant) and n.elts[0].value == 0xA294C4]

    def context(self, original=None):
        original = self.original if original is None else original
        env = dict(vars(B), orig=original, rom=bytearray(original), syl_to_code=self.codes,
                   unmapped=Counter(), WRITE_LOG=[])
        exec(compile(ast.Module(body=[self.writer], type_ignores=[]), B.__file__, 'exec'), env)
        return env

    def test_native_source_table_and_only_four_payload_bytes_change(self):
        self.assertEqual(self.rows, [(0xA294C4, 4, '폭탄')])
        self.assertEqual(struct.unpack_from('<I', self.original, 0xA357B4 + 0x8D7 * 4)[0], 0x08A294C4)
        self.assertEqual(self.original[0xA294C4:0xA294C8].decode('shift_jis'), '爆弾')
        env = self.context()
        env['fixed_zero_text_patch'](*self.rows[0])
        expected = bytes(B.encode_text('폭탄', self.codes, Counter()))
        self.assertEqual(env['rom'][:0xA294C4], self.original[:0xA294C4])
        self.assertEqual(env['rom'][0xA294C4:0xA294C8], expected)
        self.assertEqual(env['rom'][0xA294C8:], self.original[0xA294C8:])
        self.assertEqual(env['rom'][0xA294C8:0xA294CC], bytes(4))
        self.assertEqual(env['rom'][0xB81924:0xB81928], '爆弾'.encode('shift_jis'))
        self.assertFalse(env['unmapped'])
        self.assertEqual(env['WRITE_LOG'], [[0xA294C4, 4, 4, expected.hex(), 0, '폭탄', None, 'fixed_zero_text']])

    def test_part1_native_weapon_copy_has_independent_guarded_writer(self):
        env = self.context()
        env['fixed_zero_text_patch'](0xB81924, 4, '폭탄')
        expected = bytes(B.encode_text('폭탄', self.codes, Counter()))
        self.assertEqual(env['rom'][:0xB81924], self.original[:0xB81924])
        self.assertEqual(env['rom'][0xB81924:0xB81928], expected)
        self.assertEqual(env['rom'][0xB81928:], self.original[0xB81928:])
        self.assertEqual(struct.unpack_from('<I', env['rom'], 0xD850FC)[0], 0x08B81924)
        self.assertEqual(B.ADDRESS_TEXT_OVERRIDES[0xB81924], '폭탄')
        self.assertEqual(qa_text_fit.load_direct_patch_texts()[0xB81924], (0xB81928, '폭탄'))
        env['rom'][0xD850FC] ^= 1
        with self.assertRaises(AssertionError):
            env['fixed_zero_text_patch'](0xB81924, 4, '폭탄')

    def test_source_pointer_slot_and_overflow_rejected_before_write(self):
        for address, source in ((0xA294C4, True), (0xA294C8, True), (0xA37B10, True), (0xA37B10, False)):
            with self.subTest(address=hex(address), source=source):
                original = bytearray(self.original)
                if source:
                    original[address] ^= 1
                env = self.context(original)
                if not source:
                    env['rom'][address] ^= 1
                before = bytes(env['rom'])
                with self.assertRaises(AssertionError):
                    env['fixed_zero_text_patch'](*self.rows[0])
                self.assertEqual(env['rom'], before)
                self.assertFalse(env['WRITE_LOG'])
        for length, text in ((6, '폭탄'), (4, '폭격기')):
            env = self.context()
            with self.assertRaises(AssertionError):
                env['fixed_zero_text_patch'](0xA294C4, length, text)
            self.assertEqual(env['rom'], self.original)

    def test_missing_slot_cannot_repoint_native_nul_label(self):
        from dialogue_repoint import repoint_messages
        env = self.context()
        env['fixed_zero_text_patch'](*self.rows[0])
        before = bytes(env['rom'])
        tree = ast.parse(Path(B.__file__).read_text())
        call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name) and n.func.id == 'repoint_messages')
        skip_node = next(k.value for k in call.keywords if k.arg == 'skip_messages')
        scope = dict(vars(B), _rp_unsafe_messages=set())
        skip = eval(compile(ast.Expression(skip_node), B.__file__, 'eval'), scope)
        self.assertIn(0xA294C4, skip)
        manifest, stats = repoint_messages(
            env['rom'], self.original, fixable=lambda a: True,
            fixed_bytes=lambda a: bytes.fromhex('927891c4'), fit_level_dlg=lambda a: 99,
            decode_text=lambda b: '폭탄', cell_width=lambda a: 4,
            slots={}, line_index={0xA294C4: (4, '폭탄')}, table_offsets=[],
            extra_messages={0xA294C4: [0xA37B10]}, skip_messages=skip,
            free_start=0xA3D000, free_end=0xA3D010, min_level=1)
        self.assertEqual(env['rom'], before)
        self.assertEqual(manifest, [{'msg': '0xA294C4', 'status': 'skip_forced'}])
        self.assertEqual(stats.get('relocated', 0), 0)

    def test_final_guard_catches_late_payload_nul_or_pointer_damage(self):
        tree = ast.parse(Path(B.__file__).read_text())
        messages = {'bomber weapon fixed NUL label or native pointer overwritten',
                    'part1 bomber weapon fixed NUL label or native pointer overwritten'}
        guards = [n for n in ast.walk(tree) if isinstance(n, ast.If)
                  and any(isinstance(c, ast.Constant) and c.value in messages
                          for c in ast.walk(n) if isinstance(c, ast.Constant)
                          and isinstance(c.value, str))]
        self.assertEqual(len(guards), 2)
        code = compile(ast.Module(body=guards, type_ignores=[]), B.__file__, 'exec')
        env = self.context()
        env['fixed_zero_text_patch'](*self.rows[0])
        env['fixed_zero_text_patch'](0xB81924, 4, '폭탄')
        # part1_compact_ui_strings (sweep C6) is the last writer of the Part 1 copy:
        # the compact unit-info bank preloads 爆弾 (glyphs 폭탄), not the reserved codes.
        import part1_compact_ui_strings as compact_ui
        row = next(r for r in compact_ui.STRINGS if r[0] == 0xB81924)
        env['rom'][0xB81924:0xB81928] = compact_ui.encode_spec(row[2], self.codes)
        exec(code, env)
        for address in (0xA294C4, 0xA294C8, 0xA37B10, 0xB81924, 0xB81928, 0xD850FC):
            env['rom'][address] ^= 1
            with self.assertRaises(AssertionError):
                exec(code, env)
            env['rom'][address] ^= 1

    def test_metadata_and_authority_resolve_same_fixed_label(self):
        direct = qa_text_fit.load_direct_patch_texts()
        self.assertEqual(direct[0xA294C4], (0xA294C8, '폭탄'))
        self.assertEqual(B.ADDRESS_TEXT_OVERRIDES[0xA294C4], '폭탄')
        text = M.display_ko_for(0xA294C4, '爆弾', '', '폭탄', B.ADDRESS_TEXT_OVERRIDES,
                                {}, {}, {a: t for a, (_, t) in direct.items()}, {}, {}, kind='fixed_zero_text')
        self.assertEqual(text, '폭탄')


if __name__ == '__main__':
    unittest.main()
