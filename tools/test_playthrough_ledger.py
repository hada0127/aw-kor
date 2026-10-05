"""Incremental frame hashes preserve wire bytes and reject changed live ledgers."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from playthrough_capture import FrameLedger, Recorder, ROOT, sha, verify_parent


class FrameLedgerTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'temp').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'temp')
        self.root = Path(self.temp.name)
        self.path = self.root / 'frames.jsonl'
        self.ledger = FrameLedger(self.path)

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def test_exact_utf8_bytes_empty_and_multiple_checkpoints(self):
        self.assertEqual(self.ledger.snapshot(), (hashlib.sha256(b'').hexdigest(), 0))
        expected = b''
        for row in ({'core_frame': 1, 'keys': 0}, {'text': '한글🙂', 'core_frame': 2}):
            text = json.dumps(row, ensure_ascii=False) + '\n'
            self.assertEqual(self.ledger.write(text), len(text))
            expected += text.encode('utf-8')
            self.ledger.flush()
            os.fsync(self.ledger.fileno())
            self.assertEqual(self.path.read_bytes(), expected)
            self.assertEqual(self.ledger.snapshot(), (sha(self.path), len(expected)))

    def test_external_overwrite_even_with_restored_mtime_is_rejected(self):
        self.ledger.write('first line\n')
        before = self.path.stat()
        with self.path.open('r+b') as stream:
            stream.write(b'other line')
        os.utime(self.path, ns=(before.st_atime_ns, before.st_mtime_ns))
        with self.assertRaisesRegex(RuntimeError, 'changed outside'):
            self.ledger.snapshot()
        with self.assertRaisesRegex(RuntimeError, 'invalid after'):
            self.ledger.write('next\n')

    def test_external_append_is_rejected_before_overwriting_it(self):
        self.ledger.write('original\n')
        with self.path.open('ab') as stream:
            stream.write(b'external\n')
        before = self.path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'changed outside'):
            self.ledger.write('next\n')
        self.assertEqual(self.path.read_bytes(), before)

    def test_replacement_and_truncation_are_rejected(self):
        for operation in ('replace', 'truncate', 'symlink'):
            with self.subTest(operation=operation):
                path = self.root / (operation + '.jsonl')
                ledger = FrameLedger(path)
                try:
                    ledger.write('original\n')
                    if operation == 'truncate':
                        path.write_bytes(b'')
                    else:
                        moved = path.with_suffix('.moved')
                        path.rename(moved)
                        if operation == 'symlink':
                            path.symlink_to(moved)
                        else:
                            path.write_bytes(b'original\n')
                    with self.assertRaisesRegex(RuntimeError, 'changed outside'):
                        ledger.snapshot()
                finally:
                    ledger.close()

    def test_short_write_poisoning_prevents_checkpoint(self):
        stream = self.ledger.stream
        class ShortWriter:
            def fileno(self): return stream.fileno()
            def write(self, raw): return stream.write(raw[:2])
            def close(self): return stream.close()
        self.ledger.stream = ShortWriter()
        with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
            self.ledger.write('a full row\n')
        with self.assertRaisesRegex(RuntimeError, 'invalid after'):
            self.ledger.snapshot()

    def test_write_error_poisoning_prevents_checkpoint(self):
        with patch.object(self.ledger.stream, 'write', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                self.ledger.write('row\n')
        with self.assertRaisesRegex(RuntimeError, 'invalid after'):
            self.ledger.snapshot()

    def test_concurrent_append_during_write_rejects_size_change(self):
        original_write = self.ledger.stream.write
        def extra_write(raw):
            count = original_write(raw)
            with self.path.open('ab') as external:
                external.write(b'external\n')
            return count
        with patch.object(self.ledger.stream, 'write', side_effect=extra_write):
            with self.assertRaisesRegex(RuntimeError, 'size changed during write'):
                self.ledger.write('row\n')
        with self.assertRaisesRegex(RuntimeError, 'invalid after'):
            self.ledger.snapshot()

    def test_checkpoint_uses_incremental_digest_without_reading_ledger(self):
        recorder = object.__new__(Recorder)
        recorder.out = self.root
        recorder.pending_png = []
        (self.root / 'frames').mkdir()
        (self.root / 'baseline.json').write_text('{}')
        recorder.ledger = self.ledger
        recorder.committed = 1
        recorder.rom_sha = recorder.harness_sha = recorder.lib_sha = 'identity'
        self.ledger.write('{"core_frame": 1}\n')
        def cmd(command):
            Path(command.removeprefix('savestate ')).write_bytes(b'state')
            return 'OK savestate ok=1'
        recorder.cmd = cmd
        actual_sha = sha
        def guarded_sha(path):
            self.assertNotEqual(Path(path), self.path)
            return actual_sha(path)
        with patch('playthrough_capture.sha', guarded_sha):
            checkpoint = recorder.checkpoint('test')
        result = json.loads(checkpoint.read_text())
        self.assertEqual(result['ledger_sha256'], actual_sha(self.path))
        self.assertEqual(result['ledger_bytes'], self.path.stat().st_size)

    def test_resume_still_reads_and_rejects_changed_committed_prefix(self):
        baseline = {'schema_version': 2, 'initial_core_frame': 0}
        (self.root / 'baseline.json').write_text(json.dumps(baseline))
        self.ledger.write('{"core_frame": 1}\n')
        digest, size = self.ledger.snapshot()
        checkpoint = {'core_frame': 1, 'ledger_bytes': size, 'ledger_sha256': digest}
        self.path.write_bytes(b'{"core_frame": 2}\n')
        with self.assertRaisesRegex(RuntimeError, 'Parent ledger hash mismatch'):
            verify_parent(self.root / 'checkpoint.json', checkpoint)


if __name__ == '__main__':
    unittest.main()
