"""Opt-in omits only duplicate contact sheets, never frame evidence."""
import contextlib
import hashlib
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from PIL import Image
import test_playthrough_png_compression as fixtures


class NoContactSheetTests(fixtures.PngCaptureTests):
    def run_action(self, level, omit, key='A', count=2, hold=1):
        r = self.recorder(level)
        if omit is not None:
            r.no_contact_sheets = omit
        r.segment = 0
        r.last_checkpoint = None
        r.actions = io.StringIO()
        def checkpoint(tag):
            path = r.out / (tag + '.checkpoint.json')
            path.write_text(json.dumps({'core_frame': r.counter}))
            return path
        r.checkpoint = Mock(side_effect=checkpoint)
        with contextlib.redirect_stdout(io.StringIO()):
            r.action(key, count, hold)
        return r, [json.loads(line) for line in r.actions.getvalue().splitlines()]

    def test_omission_preserves_every_frame_endpoint_and_checkpoint(self):
        baseline, before = self.run_action(3, False)
        omitted, after = self.run_action(6, True)
        self.assertEqual(baseline.ledger.getvalue(), omitted.ledger.getvalue())
        self.assertEqual(baseline.counter, omitted.counter)
        self.assertEqual(omitted.counter, 3)
        self.assertEqual(before[0], after[0])
        self.assertIsNone(after[1]['sheet'])
        self.assertEqual(list(omitted.out.glob('*_sheet.png')), [])
        self.assertTrue(Path(before[1]['sheet']).is_file())
        self.assertTrue(Path(after[1]['checkpoint']).is_file())
        omitted.checkpoint.assert_called_once()
        with Image.open(after[1]['png']) as image:
            final = json.loads(omitted.ledger.getvalue().splitlines()[-1])
            self.assertEqual(hashlib.sha256(image.convert('RGB').tobytes()).hexdigest(), final['rgb_sha256'])
        self.assertEqual(len(list((omitted.out / 'frames').glob('*.png'))), 2)
        for row in map(json.loads, omitted.ledger.getvalue().splitlines()):
            with Image.open(omitted.out / row['image']) as image:
                self.assertEqual(hashlib.sha256(image.convert('RGB').tobytes()).hexdigest(), row['rgb_sha256'])

    def test_omission_does_not_copy_samples(self):
        original = fixtures.Recorder.capture
        def capture(recorder, key):
            image = original(recorder, key)
            proxy = Mock(wraps=image)
            proxy.copy.side_effect = AssertionError('sample copy forbidden')
            return proxy
        with patch.object(fixtures.Recorder, 'capture', capture):
            r, rows = self.run_action(3, True, 'NONE', 2, 0)
        self.assertEqual(r.committed, 2)
        self.assertIsNone(rows[-1]['sheet'])

    def test_absent_option_preserves_default_sheet(self):
        r, rows = self.run_action(3, None)
        self.assertTrue(Path(rows[-1]['sheet']).is_file())
        with Image.open(rows[-1]['sheet']) as image:
            self.assertEqual(image.size, (960, 180))

    def test_cli_exposes_opt_in_without_starting_native(self):
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('playthrough_capture.py')), '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--no-contact-sheets', result.stdout)


if __name__ == '__main__':
    unittest.main()
