import copy
import json
import struct
import unittest
from collections import Counter
from pathlib import Path

import build_korean_full as B
import part2_volcano_context as C
from test_part2_native_controls import HOOK_FIXTURE


class VolcanoContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = Path(B.P.ROM).read_bytes()
        cls.codes = json.loads(Path(B.SYLCODE).read_text())
        cls.codes = {k: int(v, 16) for k, v in cls.codes.items()}

    def fixture(self):
        rom = bytearray(self.original)
        for address, raw in HOOK_FIXTURE.items():
            rom[address:address + len(bytes.fromhex(raw))] = bytes.fromhex(raw)
        enc = lambda t: bytes(B.encode_full_fidelity(t, self.codes, Counter(), 0xA1D444))
        payloads = (
            enc('그렇군.') + b'\x57' + enc('결국은,') + b'\x57'
            + enc('자신을 위한 얘기인가.') + b'\x57\x57\x72'
            + enc('위험하다느니 어쩐다느니 걱정하는 척하면서.') + b'\x6b\0',
            enc('내 작전에 참견하고 싶다면,') + b'\x57' + enc('우선은') + b'\x72'
            + enc('주어진 전력으로 승리해 보여라.') + b'\x6b\0',
        )
        manifest = []
        for i, (source, pointer, size, _, _) in enumerate(C.CASES):
            target = 0xA3D000 if i == 0 else source
            rom[target:target + len(payloads[i])] = payloads[i]
            if i == 0:
                struct.pack_into('<I', rom, pointer, target + 0x08000000)
                manifest.append(dict(msg=hex(source), status='relocated', ptr_off=hex(pointer),
                                     new_addr=hex(target), old_len=size, new_len=len(payloads[i])))
        return rom, manifest

    def test_relocated_benefit_and_in_place_imperative(self):
        rom, manifest = self.fixture()
        report = C.verify(rom, self.original, manifest, self.codes)
        self.assertEqual(len(report['messages']), 2)
        self.assertFalse(report['native_consumer_verified'])
        self.assertFalse(report['pixels_verified'])

    def test_first_person_regression_rejected(self):
        rom, manifest = self.fixture()
        enc = lambda t: bytes(B.encode_full_fidelity(t, self.codes, Counter(), 0xA1D4BC))
        a = bytes(rom).index(enc('보여라'), 0xA1D4BC, 0xA1D50C)
        rom[a:a + 6] = enc('보겠다')
        with self.assertRaises(ValueError):
            C.verify(rom, self.original, manifest, self.codes)

    def test_control_and_pointer_corruption_rejected(self):
        rom, manifest = self.fixture()
        for offset in (C.CASES[0][1], 0xA3D000 + manifest[0]['new_len'] - 2):
            changed = bytearray(rom)
            changed[offset] ^= 1
            with self.assertRaises(ValueError):
                C.verify(changed, self.original, manifest, self.codes)
        original = bytearray(self.original)
        original[C.CASES[1][0]] ^= 1
        with self.assertRaises(ValueError):
            C.verify(rom, original, manifest, self.codes)

    def test_missing_duplicate_and_overlong_manifest_rejected(self):
        rom, manifest = self.fixture()
        bad = copy.deepcopy(manifest)
        bad[0]['new_len'] = 513
        for entries in ([], manifest + manifest, bad):
            with self.assertRaises(ValueError):
                C.verify(rom, self.original, entries, self.codes)

    def test_same_controls_but_shifted_wait_rejected(self):
        rom, manifest = self.fixture()
        start = 0xA3D000
        offset = bytes(rom[start:start + manifest[0]['new_len']]).index(b'\x57')
        rom[start + offset:start + offset + 3] = rom[start + offset + 1:start + offset + 3] + b'\x57'
        with self.assertRaisesRegex(ValueError, 'wait positions'):
            C.verify(rom, self.original, manifest, self.codes)

    def test_self_interest_meaning_regression_rejected(self):
        rom, manifest = self.fixture()
        enc = lambda t: bytes(B.encode_full_fidelity(t, self.codes, Counter(), 0xA1D444))
        pos = bytes(rom).index(enc('위한'), 0xA3D000, 0xA3D000 + manifest[0]['new_len'])
        rom[pos:pos + 4] = enc('하는')
        with self.assertRaises(ValueError):
            C.verify(rom, self.original, manifest, self.codes)


if __name__ == '__main__':
    unittest.main()
