import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import contextlib
import io
from unittest.mock import patch

from PIL import Image
import prune_capture_sheets as prune
from playthrough_capture import ROOT


class SheetPruningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / 'temp')
        self.root = Path(self.tmp.name)
        self.run = self.root / 'output/qa/closed'
        (self.run / 'frames').mkdir(parents=True)
        (self.root / 'docs').mkdir()
        (self.root / 'data').mkdir()
        self.patch = patch.object(prune, 'ROOT', self.root)
        self.patch.start()
        image = Image.new('RGB', (240, 160), 'red')
        self.digest = hashlib.sha256(image.tobytes()).hexdigest()
        self.frame = self.run / f'frames/{self.digest}.png'
        image.save(self.frame)
        ledger, actions = [], []
        for frame in range(1, 42):
            tag = f'{frame:04d}_NONE_{frame:07d}'
            endpoint, sheet, cp = (self.run / (tag + suffix) for suffix in ('.png', '_sheet.png', '.checkpoint.json'))
            image.save(endpoint); cp.write_text('{}')
            samples = [{'frame': frame, 'image': str(self.frame), 'rgb_sha256': self.digest}]
            prune.reconstruct(samples).save(sheet)
            actions.extend([{'segment': frame, 'status': 'started', 'start_core_frame': frame,
                             'hold_frames': 0, 'release_frames': 1, 'key': 'NONE'},
                            {'segment': frame, 'status': 'captured', 'start_core_frame': frame,
                             'end_core_frame': frame, 'png': str(endpoint), 'sheet': str(sheet), 'checkpoint': str(cp)}])
            ledger.append({'core_frame': frame, 'image': f'frames/{self.digest}.png', 'rgb_sha256': self.digest})
        raw = ''.join(json.dumps(row) + '\n' for row in ledger).encode()
        (self.run / 'frames.jsonl').write_bytes(raw)
        (self.run / 'actions.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in actions))
        (self.run / 'resume.checkpoint.json').write_text(json.dumps({'core_frame': 41, 'ledger_bytes': len(raw), 'ledger_sha256': hashlib.sha256(raw).hexdigest()}))
        (self.run / 'exit.json').write_text(json.dumps({'status': 'closed', 'emulator_exit_code': 0, 'cleanup_errors': [], 'error': None, 'last_observed_core_frame': 41, 'committed_core_frame': 41}))

    def tearDown(self):
        prune.cached_pixels.cache_clear()
        self.patch.stop()
        self.tmp.cleanup()

    def test_prepare_preserves_boundaries_and_reconstructs_middle(self):
        plans = prune.prepare(self.run, 5)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]['samples'][0]['frame'], 21)
        with Image.open(plans[0]['sheet']) as original:
            self.assertEqual(prune.reconstruct(plans[0]['samples']).tobytes(), original.tobytes())

    def test_documented_reference_is_retained(self):
        (self.root / 'docs/evidence.md').write_text('0021_NONE_0000021_sheet.png')
        self.assertEqual(prune.prepare(self.run, 5), [])

    def test_changed_ledger_is_rejected(self):
        with (self.run / 'frames.jsonl').open('ab') as stream:
            stream.write(b'{}\n')
        with self.assertRaises((ValueError, KeyError)):
            prune.prepare(self.run, 5)

    def test_modified_frame_invalidates_cached_pixels(self):
        prune.frame_pixels(self.frame, self.digest)
        Image.new('RGB', (240, 160), 'blue').save(self.frame)
        with self.assertRaisesRegex(ValueError, 'RGB mismatch'):
            prune.frame_pixels(self.frame, self.digest)

    def test_symlink_frame_is_rejected(self):
        other = self.frame.with_suffix('.other')
        self.frame.rename(other); self.frame.symlink_to(other)
        with self.assertRaises(ValueError):
            prune.frame_pixels(self.frame, self.digest)

    def test_restore_preserves_pixels_and_refuses_overwrite(self):
        record = prune.prepare(self.run, 1)[0]
        pixels = prune.reconstruct(record['samples']).tobytes()
        record['rgb_sha256'] = hashlib.sha256(pixels).hexdigest()
        target = self.run / 'restored.png'
        prune.restore_sheet(record, target)
        with Image.open(target) as restored:
            self.assertEqual(restored.tobytes(), pixels)
        with self.assertRaises(FileExistsError):
            prune.restore_sheet(record, target)

    def test_sampling_matches_hold_and_release_boundaries(self):
        self.assertEqual(prune.sample_frames({'start_core_frame': 9, 'hold_frames': 2, 'release_frames': 3}), [9, 10, 11, 12, 13])

    def test_root_and_temp_references_are_retained(self):
        (self.root / 'todo.md').write_text('0021_NONE_0000021_sheet.png')
        self.assertEqual(prune.prepare(self.run, 5), [])
        (self.root / 'todo.md').unlink()
        (self.root / 'temp').mkdir()
        (self.root / 'temp/review.txt').write_text('0021_NONE_0000021_sheet.png')
        self.assertEqual(prune.prepare(self.run, 5), [])

    def test_restore_cli_handles_prepared_only_crash_receipt(self):
        record = prune.prepare(self.run, 1)[0]
        record['rgb_sha256'] = hashlib.sha256(prune.reconstruct(record['samples']).tobytes()).hexdigest()
        record['status'] = 'verified_original_present'
        work = self.root / 'temp/receipt'
        work.mkdir(parents=True)
        receipt = work / 'receipts.jsonl'
        receipt.write_text(json.dumps(record) + '\n')
        (work / 'plan.json').write_text(json.dumps({'font': prune.font_identity()}))
        Path(record['sheet']).unlink()
        with patch('sys.argv', ['prune', '--restore', str(receipt)]), contextlib.redirect_stdout(io.StringIO()):
            prune.main()
        with Image.open(record['sheet']) as restored:
            self.assertEqual(hashlib.sha256(restored.tobytes()).hexdigest(), record['rgb_sha256'])

    def test_no_sheet_action_is_skipped(self):
        path = self.run / 'actions.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for row in rows:
            if row['status'] == 'captured':
                row['sheet'] = None
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        self.assertEqual(prune.prepare(self.run, 1), [])

    def test_own_dry_run_receipt_does_not_protect_its_candidate(self):
        plans = prune.prepare(self.run, 1)
        work = self.root / 'temp/dry_run'
        work.mkdir(parents=True)
        (work / 'plan.json').write_text(json.dumps({'kind': 'capture-sheet-pruning-v1'}))
        (work / 'receipts.jsonl').write_text(json.dumps(plans[0]) + '\n')
        self.assertEqual(prune.prepare(self.run, 1), plans)
        (work / 'review.txt').write_text(Path(plans[0]['sheet']).name)
        self.assertEqual(prune.prepare(self.run, 1), [])


if __name__ == '__main__':
    unittest.main()
