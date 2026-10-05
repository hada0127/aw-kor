import copy
import ast
import json
from pathlib import Path
import struct
import unittest
from collections import Counter

import build_korean_full as B
import part2_dialogue_layout_contracts as L
from test_part2_native_controls import HOOK_FIXTURE


class DialogueLayoutContractsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = Path(B.P.ROM).read_bytes()
        cls.codes = {k: int(v, 16) for k, v in json.loads(Path(B.SYLCODE).read_text()).items()}

    def fixture(self):
        rom = bytearray(self.original)
        for address, raw in HOOK_FIXTURE.items():
            rom[address:address + len(bytes.fromhex(raw))] = bytes.fromhex(raw)
        encode = lambda s: bytes(B.encode_full_fidelity(s, self.codes, Counter(), 0xA1F944))
        records = []
        for index, (source, c) in enumerate(L.CONTRACTS.items()):
            target = 0xA3D000 + index * 512
            prefix = encode('검사') + b'\x77' + encode('자료') + b'\x77\x72' + encode('준비') + b'\x6b'
            # Original A1F944 has two same-row waits on its second page;
            # A1F9D8 has one. Neither wait may disappear during repair.
            first = encode(c['rows'][0])
            if source == 0xA1F944:
                first = first[:14] + b'\x77' + first[14:]
            payload = prefix + first + b'\x77\x72' + encode(c['rows'][1]) + b'\x6b\0'
            rom[target:target + len(payload)] = payload
            struct.pack_into('<I', rom, c['pointer'], target + 0x08000000)
            records.append({'msg': f'0x{source:X}', 'status': 'relocated',
                            'ptr_off': f"0x{c['pointer']:X}", 'new_addr': f'0x{target:X}',
                            'old_len': c['old_len'], 'new_len': len(payload)})
        return rom, records

    def test_both_complete_text_contracts_pass_with_native_controls(self):
        rom, records = self.fixture()
        self.assertEqual([r['row_half_cells'] for r in L.verify(rom, self.original, records, self.codes)],
                         [[32, 36], [36, 34]])

    def test_missing_duplicate_or_skipped_relocation_is_blocked(self):
        rom, records = self.fixture()
        for changed in [records[1:], records + [records[0]],
                        [{**records[0], 'status': 'skip_control_changed'}, records[1]]]:
            with self.assertRaises(ValueError):
                L.verify(rom, self.original, changed, self.codes)

    def test_wrong_source_pointer_target_and_truncation_are_blocked(self):
        rom, records = self.fixture()
        for address in [0xA37170, 0xA37178]:
            changed = bytearray(rom)
            changed[address] ^= 1
            with self.assertRaises(ValueError):
                L.verify(changed, self.original, records, self.codes)
        changed_records = copy.deepcopy(records)
        changed_records[0]['new_addr'] = '0xA3D004'
        with self.assertRaises(ValueError):
            L.verify(rom, self.original, changed_records, self.codes)
        for index, source in enumerate(L.CONTRACTS):
            original = bytearray(self.original)
            original[source] ^= 1
            with self.assertRaises(ValueError):
                L.verify(rom, original, records, self.codes)
            changed = copy.deepcopy(records)
            changed[index]['new_len'] -= 1
            with self.assertRaises(ValueError):
                L.verify(rom, self.original, changed, self.codes)

    def test_late_text_or_wait_corruption_is_blocked(self):
        rom, records = self.fixture()
        from qa_part2_physical_rows import tokenize
        for record in records:
            target = int(record['new_addr'], 16)
            tokens = tokenize(rom[target:target + record['new_len']])
            for kind in ['text', 'same_row', 'newline']:
                token = next(t for t in tokens if t['kind'] == kind)
                changed = bytearray(rom)
                changed[target + token['offset']] = 0x20
                with self.assertRaises(ValueError):
                    L.verify(changed, self.original, records, self.codes)

    def test_native_consumer_changes_are_blocked(self):
        rom, records = self.fixture()
        rom[0x314596] ^= 1
        with self.assertRaises(ValueError):
            L.verify(rom, self.original, records, self.codes)

    def test_wait_moved_inside_text_is_blocked_even_with_same_control_count(self):
        rom, records = self.fixture()
        from qa_part2_physical_rows import tokenize
        target = int(records[0]['new_addr'], 16)
        payload = bytes(rom[target:target + records[0]['new_len']])
        waits = [t['offset'] for t in tokenize(payload) if t['kind'] == 'same_row']
        position = waits[-2]
        changed = payload[:position] + payload[position + 1:position + 3] + b'\x77' + payload[position + 3:]
        rom[target:target + len(changed)] = changed
        with self.assertRaises(ValueError):
            L.verify(rom, self.original, records, self.codes)

    def test_numeric_first_row_reaches_real_script_owner_without_truncation(self):
        address, end = 0xA1FA14, 0xA1FA2A
        text = '사령관이 3명 있으면 상황에 따른'
        self.assertEqual(B.ADDRESS_TEXT_OVERRIDES[address], text)
        overrides = json.loads(Path(B.BASE, 'data/dialogue_overrides.json').read_text())
        self.assertEqual(overrides['0x00A1FA14'], text)
        tree = ast.parse(Path(B.__file__).read_text())
        script_rows = [ast.literal_eval(n) for n in ast.walk(tree)
                       if isinstance(n, ast.Tuple) and len(n.elts) == 4
                       and isinstance(n.elts[0], ast.Constant) and n.elts[0].value == address]
        self.assertEqual(script_rows, [(address, end, text, 'part2 three commanders row')])
        writer = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                      and n.name == 'patch_script_row')
        env = dict(vars(B), orig=self.original, rom=bytearray(self.original),
                   syl_to_code=self.codes, unmapped=Counter(), direct_script_members={},
                   _dlg_ov=overrides, required_script_repoints=set(), WRITE_LOG=[])
        exec(compile(ast.Module(body=[writer], type_ignores=[]), B.__file__, 'exec'), env)
        payload = B.encode_text(text, self.codes, Counter(), address)
        env['patch_script_row'](address, end, payload, 'part2 three commanders row', source_text=text)
        self.assertEqual(env['required_script_repoints'], {address})
        self.assertEqual(env['WRITE_LOG'][-1][5], text)
        self.assertEqual(env['rom'][address:end], self.original[address:end])


if __name__ == '__main__':
    unittest.main()
