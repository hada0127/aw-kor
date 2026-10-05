import collections
import csv
import json
import struct
import unittest
from pathlib import Path

import build_korean_full as B
import red_unit_intro as R
from dialogue_repoint import repoint_messages
from dialogue_regions import needs_safe_dialogue_punctuation

ROOT = Path(__file__).resolve().parents[1]


class RedUnitIntroTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = Path(B.P.ROM).read_bytes()
        cls.codes = {s: int(c, 16) for s, c in json.loads(Path(B.SYLCODE).read_text()).items()}

    def encode(self, text, address):
        unknown = collections.Counter()
        result = B.encode_required_full_fidelity(text, self.codes, unknown, address)
        self.assertFalse(unknown)
        return result

    def relocate(self):
        rom = bytearray(self.original)
        rom[0xA3D000:0xA3D100] = b'\xff' * 256
        manifest, stats = repoint_messages(
            rom, self.original, fixable=lambda a: a == R.ADDRESS,
            fixed_bytes=lambda a: self.encode(R.TEXT, a), fit_level_dlg=lambda a: 6,
            decode_text=lambda b: R.TEXT, cell_width=lambda a: 34,
            slots={R.ADDRESS: 32}, line_index={R.ADDRESS: (32, 'original')},
            table_offsets=[], extra_messages={R.START: [R.POINTER]},
            free_start=0xA3D000, free_end=0xA3D100,
            valid_codes=frozenset(self.codes.values()) | {0x8140},
        )
        self.assertEqual(stats['relocated'], 1, manifest)
        B.verify_required_script_repoints({R.ADDRESS},
            {int(a, 16) for m in manifest if m.get('status') == 'relocated' for a in m.get('fixed', [])})
        return rom

    def test_real_repointer_preserves_approved_text_and_controls(self):
        rom = self.relocate()
        self.assertEqual(R.verify(rom, self.original, self.encode)['status'], 'PASS')
        payload = R.expected(self.original, self.encode)
        self.assertEqual(len(self.encode(R.TEXT, R.ADDRESS)), 34)
        self.assertEqual(payload[:2], b'\x0a\x09')
        self.assertTrue(needs_safe_dialogue_punctuation(R.START))
        self.assertEqual(payload[-6:], b'k\x0a\x00\x00\x00\x00')
        self.assertEqual(rom[R.START:R.END], self.original[R.START:R.END])
        self.assertEqual(rom[R.POINTER-4:R.POINTER], b'\x19\x00\x00\x00')

    def test_source_control_opcode_and_additional_reference_rejected(self):
        for offset in (R.START, R.TEXT_END, R.POINTER - 4, R.POINTER):
            original = bytearray(self.original)
            original[offset] ^= 1
            with self.assertRaises(ValueError):
                R.source_guard(original)
        for target in (R.START, R.ADDRESS):
            original = bytearray(self.original)
            struct.pack_into('<I', original, 0x100, target + 0x08000000)
            with self.assertRaises(ValueError):
                R.source_guard(original)

    def test_missing_relocation_and_corrupt_final_text_rejected(self):
        with self.assertRaises(ValueError):
            R.verify(self.original, self.original, self.encode)
        with self.assertRaises(AssertionError):
            B.verify_required_script_repoints({R.ADDRESS}, set())
        rom = self.relocate()
        for offset in (0xA3D000, 0xA3D004, 0xA3D025, R.POINTER, R.POINTER - 4):
            broken = bytearray(rom)
            broken[offset] ^= 1
            with self.assertRaises(ValueError):
                R.verify(broken, self.original, self.encode)

    def test_invalid_relocation_bounds_rejected(self):
        rom = self.relocate()
        for target in (0xA3CFFC, 0xA3D001, R.SPRITE_STORAGE_START - 4):
            broken = bytearray(rom)
            struct.pack_into('<I', broken, R.POINTER, target + 0x08000000)
            with self.assertRaises(ValueError):
                R.verify(broken, self.original, self.encode)

    def test_authoritative_sources_match_unchanged_protected_baseline(self):
        key = f'0x{R.ADDRESS:08X}'
        baseline = json.loads((ROOT / 'data/bteam_baseline.json').read_text())['overrides'][key]
        self.assertEqual(R.TEXT, baseline)
        self.assertEqual(json.loads((ROOT / 'data/dialogue_overrides.json').read_text())[key], baseline)
        with open(ROOT / 'data/translation_for_import.csv') as stream:
            rows = [r for r in csv.DictReader(stream) if r['address'] == key]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['korean'], baseline)


if __name__ == '__main__':
    unittest.main()
