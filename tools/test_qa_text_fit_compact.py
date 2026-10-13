"""B-team compact-row exemption in qa_text_fit needs evidence from the inspected ROM.

Set AW_TEST_ROM, AW_TEST_MAP (the build's integrity_map.json) and AW_TEST_MANIFEST.
"""
import json
import os
import unittest
from pathlib import Path

import qa_text_fit as Q


@unittest.skipUnless(os.environ.get('AW_TEST_ROM') and os.environ.get('AW_TEST_MAP')
                     and os.environ.get('AW_TEST_MANIFEST'),
                     'needs AW_TEST_ROM + AW_TEST_MAP + AW_TEST_MANIFEST')
class CompactEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = Path(os.environ['AW_TEST_ROM']).read_bytes()
        cls.rows = json.loads(Path(os.environ['AW_TEST_MAP']).read_text(encoding='utf-8'))

    def test_every_compact_row_has_rom_bound_evidence(self):
        for address in sorted(Q.COMPACT_ROW_WRITERS):
            self.assertTrue(Q.compact_row_evidence(self.rom, self.rows, address), hex(address))

    def test_mutated_rom_row_fails(self):
        for address in (0xB81874, 0xB82D58, 0xDF8BBA):
            bad = bytearray(self.rom)
            bad[address] ^= 0x01
            self.assertFalse(Q.compact_row_evidence(bytes(bad), self.rows, address), hex(address))

    def test_membership_alone_never_exempts(self):
        address = 0xB82D36
        rows = [r for r in self.rows if int(r[0]) != address]
        self.assertFalse(Q.compact_row_evidence(self.rom, rows, address))
        foreign = [list(r) for r in self.rows]
        for r in foreign:
            if int(r[0]) == address and r[3]:
                r[7] = 'import-csv'
        self.assertFalse(Q.compact_row_evidence(self.rom, foreign, address))
        self.assertFalse(Q.compact_row_evidence(self.rom, self.rows, 0xA0A9B1))

    def test_cli_reports_mutated_compact_row(self):
        import subprocess, sys, tempfile
        root = Path(__file__).resolve().parents[1]
        bad = bytearray(self.rom)
        bad[0xB82D58] ^= 0x01
        with tempfile.TemporaryDirectory(dir=root / 'temp', prefix='qa-text-fit-') as tmp:
            path = Path(tmp) / 'mutated.gba'
            path.write_bytes(bad)
            cmd = [sys.executable, str(root / 'tools/qa_text_fit.py'), '--rom', str(path),
                   '--map', os.environ['AW_TEST_MAP'], '--manifest', os.environ['AW_TEST_MANIFEST'],
                   '--map-rom', os.environ['AW_TEST_ROM']]
            result = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
        # The upstream drift check or the evidence check must reject it; never exit 0.
        self.assertNotEqual(result.returncode, 0, result.stdout[-400:] + result.stderr[-400:])
        self.assertIn('B82D58', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
