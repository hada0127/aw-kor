import collections
import json
import struct
import unittest
from unittest.mock import patch
from pathlib import Path

import build_korean_full as B
import part1_m19_dialogue as M
from dialogue_repoint import repoint_messages


class M19DialogueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = Path(B.P.ROM).read_bytes()
        cls.codes = {s: int(c, 16) for s, c in json.loads(Path(B.SYLCODE).read_text()).items()}

    def encode(self, text, address):
        unknown = collections.Counter()
        raw = B.encode_required_full_fidelity(text, self.codes, unknown, address)
        self.assertFalse(unknown)
        return raw

    def fixture(self):
        rom = bytearray(self.original)
        for address, length in M.SPANS:
            if address in M.APPROVED_NEIGHBORS:
                encoded = self.encode(M.APPROVED_NEIGHBORS[address], address)
                self.assertLessEqual(len(encoded), length)
                rom[address:address + length] = encoded.ljust(length, b' ')
        return rom

    def relocate(self):
        rom = self.fixture()
        expected = M.expected_before_repoint(rom, self.original, self.encode)
        rom[0xA3D000:0xA3D200] = b'\xff' * 512
        manifest, stats = repoint_messages(
            rom, self.original, fixable=lambda a: a == M.ADDRESS,
            fixed_bytes=lambda a: self.encode(M.TEXT, a), fit_level_dlg=lambda a: 6,
            decode_text=lambda raw: raw.decode('shift_jis', errors='replace'),
            cell_width=lambda a: 50, slots=dict(M.SPANS),
            line_index={a: (n, self.original[a:a+n].decode('shift_jis')) for a, n in M.SPANS},
            table_offsets=[], extra_messages={M.START: [M.POINTER]},
            line_layouts=M.layout(self.original, self.encode),
            free_start=0xA3D000, free_end=0xA3D200)
        self.assertEqual(stats['relocated'], 1, manifest)
        B.verify_required_script_repoints({M.ADDRESS},
            {int(a, 16) for m in manifest if m.get('status') == 'relocated' for a in m.get('fixed', [])})
        return rom, expected

    def test_real_repointer_exact_text_pages_following_row_and_width(self):
        rom, expected = self.relocate()
        result = M.verify(rom, self.original, expected, self.encode)
        self.assertEqual(result['row_pixels'], [104, 88])
        self.assertEqual(len(expected), 159)
        self.assertEqual(' '.join(M.ROWS), M.TEXT)
        self.assertEqual(rom[M.START:M.END], self.fixture()[M.START:M.END])
        self.assertEqual(expected.count(b'\x72\x0a\x09'), 2)
        self.assertEqual(expected.count(b'\x6b\x0a\x09\x0a\x09'), 2)

    def test_final_pointer_opcode_pages_and_neighbor_mutations_rejected(self):
        rom, expected = self.relocate()
        for offset in (M.POINTER, M.POINTER - 4, 0xA3D000, 0xA3D005,
                       0xA3D000 + expected.index(b'\x6b\x0a\x09\x0a\x09'),
                       0xA3D000 + len(expected) - 10):
            broken = bytearray(rom); broken[offset] ^= 1
            with self.assertRaises(ValueError):
                M.verify(broken, self.original, expected, self.encode)
        for target in (0xA3CFFC, 0xA3D001, M.SPRITE_STORAGE_START - 4):
            broken = bytearray(rom); struct.pack_into('<I', broken, M.POINTER, target + 0x08000000)
            with self.assertRaises(ValueError):
                M.verify(broken, self.original, expected, self.encode)

    def test_missing_repoint_and_source_or_preexisting_control_changes_rejected(self):
        rom = self.fixture()
        expected = M.expected_before_repoint(rom, self.original, self.encode)
        with self.assertRaises(ValueError): M.verify(rom, self.original, expected, self.encode)
        with self.assertRaises(AssertionError): B.verify_required_script_repoints({M.ADDRESS}, set())
        for offset in (M.START, 0xDCF632, M.POINTER - 4, M.POINTER):
            broken = bytearray(self.original); broken[offset] ^= 1
            with self.assertRaises(ValueError): M.source_guard(broken)
        for offset in (0xDCF60A, 0xDCF632, 0xDCF635, 0xDCF651, 0xDCF683, 0xDCF697):
            broken = bytearray(rom); broken[offset] ^= 1
            with self.assertRaises(ValueError): M.expected_before_repoint(broken, self.original, self.encode)

    def test_duplicate_reference_width_and_wording_changes_rejected(self):
        broken = bytearray(self.original)
        struct.pack_into('<I', broken, 0x100, M.START + 0x08000000)
        with self.assertRaises(ValueError): M.source_guard(broken)
        with self.assertRaises(ValueError):
            M.layout(self.original, lambda text, address: b'\x81\x40' * 23)
        with patch.object(M, 'ROWS', ('누군지는 모르겠지만,', '화났어!')):
            with self.assertRaises(ValueError): M.layout(self.original, self.encode)

    def test_required_encoder_rejects_missing_glyph_without_old_warning_false_positive(self):
        missing = dict(self.codes); missing.pop('끝')
        unknown = collections.Counter({'historical': 9})
        with self.assertRaises(KeyError):
            B.encode_required_full_fidelity(M.TEXT, missing, unknown, M.ADDRESS)
        with self.assertRaises(ValueError):
            B.encode_required_full_fidelity(M.TEXT + '☃', self.codes, unknown, M.ADDRESS)
        self.assertEqual(unknown['☃'], 1)
        expected = self.encode(M.TEXT, M.ADDRESS)
        self.assertEqual(B.encode_required_full_fidelity(M.TEXT, self.codes, unknown, M.ADDRESS), expected)


if __name__ == '__main__':
    unittest.main()
