"""Capture evidence stays frame exact and lossless at cheaper PNG compression."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock, patch
from PIL import Image
from playthrough_capture import Recorder, ROOT


class PngCaptureTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'temp').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'temp')
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def recorder(self, level):
        r = object.__new__(Recorder)
        r.out = self.root / str(level)
        (r.out / 'frames').mkdir(parents=True)
        r.png_compress_level = level
        r.counter = r.committed = 0
        r.seen = set()
        r.pending_png = []
        r.ledger = io.StringIO()
        r.check_disk = Mock()
        r.read_counter = lambda: r.counter + 1
        # Two identical frames followed by a changed frame, with varied RGB pixels.
        first = bytes((i * 37 % 256 for i in range(240 * 160 * 4)))
        changed = bytes([123]) + first[1:]
        def cmd(command):
            if command.startswith('shot '):
                pixels = first if r.counter <= 2 else changed
                Path(command[5:]).write_bytes(struct.pack('<HHB', 240, 160, 4) + pixels)
            return 'OK'
        r.cmd = cmd
        return r

    def test_compression_preserves_all_frames_rgb_and_deduplication(self):
        ledgers = []
        for level in (0, 3, 6, 9):
            r = self.recorder(level)
            for key in (1, 0, 16):
                r.capture(key)
            rows = [json.loads(line) for line in r.ledger.getvalue().splitlines()]
            self.assertEqual([row['core_frame'] for row in rows], [1, 2, 3])
            self.assertEqual([row['keys'] for row in rows], [1, 0, 16])
            self.assertEqual(rows[0]['image'], rows[1]['image'])
            self.assertNotEqual(rows[1]['image'], rows[2]['image'])
            self.assertEqual(len(r.pending_png), 2)
            self.assertEqual(r.check_disk.call_count, 3)
            self.assertEqual(r.committed, 3)
            ledgers.append(rows)
        self.assertTrue(all(rows == ledgers[0] for rows in ledgers))

    def test_roundtrip_mismatch_cannot_commit_a_frame(self):
        r = self.recorder(3)
        original_save = Image.Image.save
        def corrupt(image, path, **kwargs):
            return original_save(Image.new('RGB', image.size), path, **kwargs)
        with patch.object(Image.Image, 'save', corrupt), self.assertRaisesRegex(RuntimeError, 'PNG roundtrip mismatch'):
            r.capture(1)
        self.assertEqual(r.committed, 0)
        self.assertEqual(r.ledger.getvalue(), '')
        self.assertEqual(r.seen, set())

    def test_action_applies_selected_level_to_frames_endpoint_and_sheet(self):
        r = self.recorder(1)
        r.segment = 0
        r.last_checkpoint = None
        r.actions = io.StringIO()
        r.checkpoint = Mock(return_value=r.out / 'checkpoint.json')
        writes = []
        original_save = Image.Image.save
        def save(image, path, **kwargs):
            writes.append((Path(path), kwargs.get('compress_level')))
            return original_save(image, path, **kwargs)
        with patch.object(Image.Image, 'save', save), contextlib.redirect_stdout(io.StringIO()):
            r.action('A', 2, 1)
        self.assertEqual(len(writes), 4)  # Two unique frames, endpoint, contact sheet.
        self.assertTrue(all(level == 1 for path, level in writes))
        self.assertEqual(sum(path.parent.name == 'frames' for path, level in writes), 2)
        self.assertEqual(sum(path.stem.endswith('_sheet') for path, level in writes), 1)
        self.assertEqual(r.committed, 3)
        r.checkpoint.assert_called_once()

    def test_invalid_compression_rejected_before_creating_output(self):
        for value in (-1, 10, True, 3.0, '3'):
            args = argparse.Namespace(out=self.root / 'unused', png_compress_level=value)
            with self.assertRaises(ValueError):
                Recorder(args)
            self.assertFalse(args.out.exists())


if __name__ == '__main__':
    unittest.main()
