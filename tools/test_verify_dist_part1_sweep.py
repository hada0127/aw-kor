"""Part1 map-label evidence must include both b39 save conditions."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import verify_dist_integrity as gate


class Part1SweepEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidate = Path(gate.BASE) / 'output/game_wars_korean_candidate_20261017_b39.gba'
        if not candidate.is_file():
            raise unittest.SkipTest(f'b39 candidate missing: {candidate}')
        cls.rom = candidate.read_bytes()
        cls.rom_sha = gate.sha256(cls.rom)

    def verify(self):
        return gate.verify_part1_map_label_hook(self.rom, self.rom_sha)

    def test_locked_and_unlocked_reports_pass_together(self):
        ok, message = self.verify()
        self.assertTrue(ok, message)
        self.assertIn('locked: sweep_steps=', message)
        self.assertIn('unlocked_cat0: sweep_steps=', message)

    def test_missing_locked_report_fails(self):
        with tempfile.TemporaryDirectory(dir=Path(gate.BASE) / 'temp') as folder:
            with patch.object(gate, 'PART1_MAP_LABEL_LOCKED_SWEEP_REPORT', str(Path(folder) / 'missing.json')):
                ok, message = self.verify()
        self.assertFalse(ok)
        self.assertIn('locked sweep report missing', message)

    def test_stale_locked_report_fails(self):
        report = json.loads(Path(gate.PART1_MAP_LABEL_LOCKED_SWEEP_REPORT).read_text())
        report['source_rom_sha256'] = '0' * 64
        with tempfile.TemporaryDirectory(dir=Path(gate.BASE) / 'temp') as folder:
            stale = Path(folder) / 'stale.json'
            stale.write_text(json.dumps(report))
            with patch.object(gate, 'PART1_MAP_LABEL_LOCKED_SWEEP_REPORT', str(stale)):
                ok, message = self.verify()
        self.assertFalse(ok)
        self.assertIn('locked sweep report SHA stale', message)

    def test_empty_contact_sheets_fail(self):
        report = json.loads(Path(gate.PART1_MAP_LABEL_LOCKED_SWEEP_REPORT).read_text())
        report['docs'] = {}
        with tempfile.TemporaryDirectory(dir=Path(gate.BASE) / 'temp') as folder:
            malformed = Path(folder) / 'malformed.json'
            malformed.write_text(json.dumps(report))
            with patch.object(gate, 'PART1_MAP_LABEL_LOCKED_SWEEP_REPORT', str(malformed)):
                ok, message = self.verify()
        self.assertFalse(ok)
        self.assertIn('locked sweep contact sheets missing', message)


if __name__ == '__main__':
    unittest.main()
