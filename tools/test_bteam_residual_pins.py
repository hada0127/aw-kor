"""Bounded manifest gate regression; no ROM/census or builder execution."""
import csv
import hashlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qa_bteam_drift as qa


class ResidualPinsTest(unittest.TestCase):
    def setUp(self):
        self.payload = Path(qa.BASE, 'data/bteam_round2_residuals.tsv').read_bytes()

    def gate(self, payload):
        # Stop immediately after the real digest/count gates, before ROM QA.
        def read_bytes(path):
            if path.name == 'bteam_round2_residuals.tsv':
                return payload
            raise RuntimeError('reached active pins')

        with patch.object(Path, 'read_bytes', read_bytes), patch.object(
                Path, 'open', lambda *a, **kw: io.StringIO(payload.decode('utf-8'))):
            qa.classify_round2_issues([], {}, 'unused-rom', 'unused-manifest')

    def test_approved_manifest_passes_digest_and_count(self):
        self.assertEqual(hashlib.sha256(self.payload).hexdigest(),
                         '7d3c76b92b4d6ce30fd79331d54c65468988daa0e16fed07c4de1fd5261d01e1')
        rows = list(csv.DictReader(io.StringIO(self.payload.decode()), delimiter='\t'))
        self.assertEqual(len(rows), 87)
        listed = {int(row['address'], 16) for row in rows}
        self.assertEqual(len(listed), 87)
        self.assertNotIn(0xB830AC, listed)
        self.assertNotIn(0xB82FAC, listed)
        self.assertNotIn(0xEC312E, listed)
        self.assertNotIn(0xD821F0, listed)
        self.assertEqual(qa.round2_issue_bucket({
            'address': '0xB830AC', 'cause': 'final in-place writer test'}, listed), 'unlisted')
        with self.assertRaisesRegex(RuntimeError, '^reached active pins$'):
            self.gate(self.payload)

    def test_unrelated_tsv_changes_fail_digest(self):
        lines = self.payload.splitlines(keepends=True)
        variants = {
            'metadata': self.payload.replace(b'\t', b'\tX', 1),
            'reorder': b''.join([lines[0], lines[2], lines[1], *lines[3:]]),
            'delete': b''.join(lines[:-1]),
            'duplicate': self.payload + lines[-1],
        }
        for name, payload in variants.items():
            with self.subTest(name=name), self.assertRaisesRegex(
                    ValueError, '^B-team residual manifest digest changed$'):
                self.gate(payload)


if __name__ == '__main__':
    unittest.main()
