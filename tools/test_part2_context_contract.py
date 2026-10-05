import ast
import copy
import json
import struct
import unittest
from collections import Counter
from pathlib import Path

import build_korean_full as B
import part2_context_contract as C
from test_part2_native_controls import HOOK_FIXTURE


class ContextContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = Path(B.P.ROM).read_bytes()
        cls.codes = {k: int(v, 16) for k, v in json.loads(Path(B.SYLCODE).read_text()).items()}

    def fixture(self):
        rom = bytearray(self.original)
        for address, raw in HOOK_FIXTURE.items():
            rom[address:address + len(bytes.fromhex(raw))] = bytes.fromhex(raw)
        parts = ['근데,', '공중전의 이글,', '해상전의 나에게',
                 '지상전의 한나가 합류하면,', '두려울 게 없다.',
                 '자,', '우리 나라를,', '되찾자!']
        controls = [b'\x57', b'\x57', b'\x72', b'\x57', b'\x6b', b'\x57', b'\x57', b'\x6b\0']
        payload = b''.join(bytes(B.encode_full_fidelity(t, self.codes, Counter(), C.SOURCE)) + c
                           for t, c in zip(parts, controls))
        target = 0xA3D000
        rom[target:target + len(payload)] = payload
        struct.pack_into('<I', rom, C.POINTER, target + 0x08000000)
        manifest = [{'msg': hex(C.SOURCE), 'status': 'relocated', 'ptr_off': hex(C.POINTER),
                     'new_addr': hex(target), 'old_len': C.OLD_LEN, 'new_len': len(payload)}]
        return rom, manifest

    def test_complete_context_accepts_unobserved_46_cell_row(self):
        rom, manifest = self.fixture()
        report = C.verify(rom, self.original, manifest, self.codes)
        self.assertIn('31424c interpretation', report['scope'])
        self.assertFalse(report['native_consumer_verified'])
        self.assertFalse(report['pixels_verified'])

    def test_pointer_source_missing_duplicate_and_truncation_fail(self):
        rom, manifest = self.fixture()
        for changed in [[], manifest + manifest, [{**manifest[0], 'new_len': manifest[0]['new_len'] - 1}],
                        [{**manifest[0], 'new_addr': '0xA3D004'}]]:
            with self.assertRaises(ValueError):
                C.verify(rom, self.original, changed, self.codes)
        for address in [C.POINTER, 0xA3D000 + 12]:
            changed = bytearray(rom); changed[address] ^= 1
            with self.assertRaises(ValueError):
                C.verify(changed, self.original, manifest, self.codes)
        original = bytearray(self.original); original[C.SOURCE] ^= 1
        with self.assertRaises(ValueError):
            C.verify(rom, original, manifest, self.codes)

    def test_same_control_count_but_moved_wait_fails(self):
        rom, manifest = self.fixture()
        start = 0xA3D000
        position = bytes(rom[start:start + manifest[0]['new_len']]).index(b'\x57')
        rom[start + position:start + position + 3] = rom[start + position + 1:start + position + 3] + b'\x57'
        with self.assertRaises(ValueError):
            C.verify(rom, self.original, manifest, self.codes)

    def test_actual_script_owner_preserves_overlength_subject_until_repoint(self):
        address, end, text = 0xA199CA, 0xA199D8, '해상전의 나에게'
        self.assertEqual(B.ADDRESS_TEXT_OVERRIDES[address], text)
        overrides = json.loads(Path(B.BASE, 'data/dialogue_overrides.json').read_text())
        self.assertEqual(overrides['0x00A199CA'], text)
        tree = ast.parse(Path(B.__file__).read_text())
        rows = [ast.literal_eval(n) for n in ast.walk(tree) if isinstance(n, ast.Tuple)
                and len(n.elts) == 4 and isinstance(n.elts[0], ast.Constant)
                and n.elts[0].value == address]
        self.assertEqual(rows, [(address, end, text, 'part2 sea commander subject row')])
        writer = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'patch_script_row')
        env = dict(vars(B), orig=self.original, rom=bytearray(self.original),
                   syl_to_code=self.codes, unmapped=Counter(), direct_script_members={},
                   _dlg_ov=overrides, required_script_repoints=set(), WRITE_LOG=[])
        exec(compile(ast.Module(body=[writer], type_ignores=[]), B.__file__, 'exec'), env)
        env['patch_script_row'](address, end, b'', 'part2 sea commander subject row', source_text=text)
        self.assertEqual(env['required_script_repoints'], {address})
        self.assertEqual(env['rom'][address:end], self.original[address:end])
        self.assertEqual(env['WRITE_LOG'][-1][5], text)

    def teacher_fixture(self):
        rom = bytearray(self.original)
        for address, raw in HOOK_FIXTURE.items():
            rom[address:address + len(bytes.fromhex(raw))] = bytes.fromhex(raw)
        manifest = []
        for i, (source, pointer, old_len, _, _) in enumerate(C.TEACHER_SOURCES):
            first = (bytes(B.encode_full_fidelity('그렇지 않습니다,', self.codes, Counter(), source))
                     + b'\x77' + bytes(B.encode_full_fidelity('선생님!', self.codes, Counter(), source)) + b'\x6b')
            payload = first + self.original[source + 34:source + old_len]
            target = 0xA3D000 + i * 512
            rom[target:target + len(payload)] = payload
            struct.pack_into('<I', rom, pointer, target + 0x08000000)
            manifest.append({'msg': hex(source), 'status': 'relocated', 'ptr_off': hex(pointer),
                             'new_addr': hex(target), 'old_len': old_len, 'new_len': len(payload)})
        return rom, manifest

    def test_teacher_first_page_keeps_wait_and_polite_reassurance(self):
        rom, manifest = self.teacher_fixture()
        result = C.verify_teacher_context(rom, self.original, manifest, self.codes)
        self.assertEqual(len(result['messages']), 2)
        self.assertFalse(result['native_consumer_verified'])
        self.assertFalse(result['pixels_verified'])
        for teacher in (0xA2185B, 0xA219AB):
            self.assertGreater(len(B.encode_full_fidelity('선생님!', self.codes, Counter(), teacher)), 6)
            self.assertIn(teacher, B.PLAYTHROUGH_REPAIR_ROWS)

    def test_teacher_pointer_source_text_and_wait_mutations_fail(self):
        rom, manifest = self.teacher_fixture()
        for address in (0xA37310, 0xA3D000, 0xA2185B, 0xA3731C, 0xA3D200, 0xA219AB):
            changed = bytearray(rom); changed[address] ^= 1
            with self.assertRaises(ValueError):
                C.verify_teacher_context(changed, self.original, manifest, self.codes)
        changed = bytearray(rom)
        position = bytes(changed[0xA3D000:0xA3D100]).index(b'\x77')
        changed[0xA3D000+position:0xA3D000+position+3] = changed[0xA3D000+position+1:0xA3D000+position+3] + b'\x77'
        with self.assertRaises(ValueError):
            C.verify_teacher_context(changed, self.original, manifest, self.codes)
        for index in range(2):
            for key, value in [('status', 'inplace'), ('old_len', 1), ('ptr_off', '0xA37300'),
                               ('new_addr', '0xA3D001'), ('new_addr', '0xA3C000'), ('new_len', 513)]:
                changed = copy.deepcopy(manifest); changed[index][key] = value
                with self.subTest(index=index, key=key, value=value), self.assertRaises(ValueError):
                    C.verify_teacher_context(rom, self.original, changed, self.codes)
        for changed in ([], manifest[:1], manifest[1:], manifest + manifest[:1]):
            with self.assertRaises(ValueError):
                C.verify_teacher_context(rom, self.original, changed, self.codes)
        for source, _, _, _, _ in C.TEACHER_SOURCES:
            original = bytearray(self.original); original[source] ^= 1
            with self.assertRaises(ValueError):
                C.verify_teacher_context(rom, original, manifest, self.codes)

    def test_teacher_import_and_regenerated_editor_map_match_authority(self):
        import csv
        with Path(B.BASE, 'data/translation_for_import.csv').open() as stream:
            imported = {int(r['address'], 16): r['korean'] for r in csv.DictReader(stream)}
        for address in (0xA21840, 0xA21990):
            self.assertEqual(imported[address], '그렇지 않습니다,')
        mapped = json.loads(Path(B.BASE, 'data/dialogue_map.json').read_text())['lines']
        for address, text in ((0xA21840, '그렇지 않습니다,'), (0xA2185B, '선생님!'),
                              (0xA21990, '그렇지 않습니다,'), (0xA219AB, '선생님!')):
            rows = [r for r in mapped if r.get('address') == f'0x{address:08X}']
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['ko'], text)
            self.assertEqual(rows[0]['ship_ko'], text)

    def test_teacher_source_owners_require_repoint_without_shortening(self):
        tree = ast.parse(Path(B.__file__).read_text())
        writer = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'patch_script_row')
        overrides = json.loads(Path(B.BASE, 'data/dialogue_overrides.json').read_text())
        for address in (0xA2185B, 0xA219AB):
            env = dict(vars(B), orig=self.original, rom=bytearray(self.original), syl_to_code=self.codes,
                       unmapped=Counter(), direct_script_members={}, _dlg_ov=overrides,
                       required_script_repoints=set(), WRITE_LOG=[])
            exec(compile(ast.Module(body=[writer], type_ignores=[]), B.__file__, 'exec'), env)
            env['patch_script_row'](address, address+6, b'', 'teacher', source_text='선생님!')
            self.assertEqual(env['required_script_repoints'], {address})
            self.assertEqual(env['rom'][address:address+6], self.original[address:address+6])
            self.assertEqual(env['WRITE_LOG'][-1][5], '선생님!')


if __name__ == '__main__':
    unittest.main()
