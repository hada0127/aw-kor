import json
import hashlib
import argparse
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
from PIL import Image, UnidentifiedImageError
import replay_campaign_qa as replay

from replay_campaign_qa import ROOT, compare_ledgers, compare_runs, export_inputs, parse_inputs, verify_run
from playthrough_capture import Recorder, parse_action


class ReplayTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'temp').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'temp')
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def ledger(self, name, hashes, keys=None):
        path = self.root / name
        path.write_text(''.join(json.dumps({'core_frame': i + 1, 'keys': (keys or [0] * len(hashes))[i],
                                            'rgb_sha256': digest, 'image': f'frames/{digest}.png'}) + '\n'
                                for i, digest in enumerate(hashes)))
        return path

    def test_only_explicit_supported_commands(self):
        self.assertEqual(parse_inputs('# route\nNONE 120\nA 60\n'), [('NONE', 120), ('A', 60)])
        for text in ('', 'quit', 'w8 100', 'A 0', 'A 1801', 'A 2 extra'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_inputs(text)

    def test_held_inputs_preserve_duration_and_normalize_defaults(self):
        self.assertEqual(parse_inputs('RIGHT 60 30\nA 60 2\nNONE 30 0\n'),
                         [('RIGHT', 60, 30), ('A', 60), ('NONE', 30)])
        self.assertEqual(parse_action(['a']), ('A', 120, 2))
        self.assertEqual(parse_inputs('right 60 30\na 60\n'), [('RIGHT', 60, 30), ('A', 60)])
        for text in ('A 60 0', 'A 60 121', 'NONE 60 2', 'A 60 -1', 'A 60 3 4'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_inputs(text)

    def test_invalid_hold_does_not_touch_recorder(self):
        recorder = object.__new__(Recorder)
        for key, count, hold in [('A', 60, 0), ('A', 60, 121), ('NONE', 60, 1)]:
            with self.subTest(key=key, hold=hold), self.assertRaises(ValueError):
                recorder.action(key, count, hold)

    def test_export_round_trips_held_inputs_and_checks_total_frames(self):
        (self.root / 'baseline.json').write_text(json.dumps({'initial_core_frame': 0, 'parent_checkpoint': None}))
        (self.root / 'exit.json').write_text(json.dumps({'status': 'closed', 'emulator_exit_code': 0}))
        actions = [{'status': 'started', 'segment': 1, 'key': 'RIGHT', 'hold_frames': 30,
                    'release_frames': 60, 'start_core_frame': 1},
                   {'status': 'captured', 'segment': 1, 'end_core_frame': 90}]
        path = self.root / 'actions.jsonl'
        path.write_text(''.join(json.dumps(row) + '\n' for row in actions))
        self.assertEqual(parse_inputs(export_inputs(self.root)), [('RIGHT', 60, 30)])
        actions[1]['end_core_frame'] = 62
        path.write_text(''.join(json.dumps(row) + '\n' for row in actions))
        with self.assertRaisesRegex(ValueError, 'Action frame count mismatch'):
            export_inputs(self.root)
        del actions[0]['hold_frames']
        path.write_text(''.join(json.dumps(row) + '\n' for row in actions))
        with self.assertRaisesRegex(ValueError, 'hold duration is missing'):
            export_inputs(self.root)

    def test_every_frame_difference_is_grouped_not_silently_sampled(self):
        old = self.ledger('old', ['a'] * 6)
        new = self.ledger('new', ['a', 'b', 'c', 'a', 'd', 'a'])
        result = compare_ledgers(old, new)
        self.assertEqual(result['changed_frames'], 3)
        self.assertEqual([(r['first_frame'], r['last_frame']) for r in result['changed_ranges']], [(2, 3), (5, 5)])
        self.assertEqual(compare_ledgers(old, old)['status'], 'identical_to_reference')

    def test_missing_or_differently_keyed_frames_cannot_pass(self):
        old = self.ledger('old', ['a', 'a'])
        for new in (self.ledger('short', ['a']), self.ledger('keys', ['a', 'a'], [0, 1])):
            with self.assertRaises(ValueError):
                compare_ledgers(old, new)

    def test_export_rejects_incomplete_action_and_resumed_suffix(self):
        baseline = self.root / 'baseline.json'
        baseline.write_text(json.dumps({'initial_core_frame': 0, 'parent_checkpoint': None}))
        (self.root / 'exit.json').write_text(json.dumps({'status': 'closed', 'emulator_exit_code': 0}))
        actions = [{'status': 'started', 'segment': 1, 'key': 'A', 'hold_frames': 2,
                    'release_frames': 60, 'start_core_frame': 1},
                   {'status': 'captured', 'segment': 1, 'end_core_frame': 62},
                   {'status': 'started', 'segment': 2, 'key': 'B', 'hold_frames': 2,
                    'release_frames': 60, 'start_core_frame': 63}]
        (self.root / 'actions.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in actions))
        with self.assertRaisesRegex(ValueError, 'Incomplete action'):
            export_inputs(self.root)
        (self.root / 'actions.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in actions[:-1]))
        self.assertEqual(export_inputs(self.root), 'A 60\n')
        baseline.write_text(json.dumps({'initial_core_frame': 62, 'parent_checkpoint': 'parent'}))
        with self.assertRaisesRegex(ValueError, 'cold-boot'):
            export_inputs(self.root)

    def fixture(self, name):
        run = self.root / name
        (run / 'frames').mkdir(parents=True)
        digest = lambda data: hashlib.sha256(data).hexdigest()
        rom = b'fixture ROM'; state = b'fixture state'
        (run / 'baseline.gba').write_bytes(rom)
        (run / 'resume.ss0').write_bytes(state)
        im = Image.new('RGB', (240, 160), 'black'); rgb = digest(im.tobytes())
        im.save(run / 'frames' / (rgb + '.png'))
        ledger = (json.dumps({'core_frame': 1, 'keys': 0, 'image': f'frames/{rgb}.png', 'rgb_sha256': rgb}) + '\n').encode()
        (run / 'frames.jsonl').write_bytes(ledger)
        identity = {'rom_sha256': digest(rom), 'harness_sha256': 'harness', 'libmgba_sha256': 'library'}
        (run / 'baseline.json').write_text(json.dumps({**identity, 'schema_version': 2,
                                                      'initial_core_frame': 0, 'parent_checkpoint': None}))
        checkpoint = {**identity, 'core_frame': 1, 'ledger_bytes': len(ledger),
                      'ledger_sha256': digest(ledger), 'state': 'resume.ss0', 'state_sha256': digest(state)}
        (run / 'resume.checkpoint.json').write_text(json.dumps(checkpoint))
        (run / 'exit.json').write_text(json.dumps({'status': 'closed', 'emulator_exit_code': 0,
                                                  'committed_core_frame': 1, 'last_observed_core_frame': 1}))
        return run

    def change_json(self, path, **changes):
        row = json.loads(path.read_text()); row.update(changes); path.write_text(json.dumps(row))

    def test_verified_capture_rejects_corruption_and_uncommitted_data(self):
        failures = {'rom': (ValueError, 'ROM hash'), 'png': (UnidentifiedImageError, 'identify image'),
                    'state': (ValueError, 'state mismatch'), 'identity': (ValueError, 'identity mismatch'),
                    'exit': (ValueError, 'did not close'), 'suffix': (ValueError, 'Uncommitted'),
                    'escape': (ValueError, 'state mismatch'), 'ledger_hash': (RuntimeError, 'ledger hash'),
                    'frame_gap': (RuntimeError, 'frame discontinuity')}
        for fault, (exception, message) in failures.items():
            with self.subTest(fault=fault):
                run = self.fixture(fault)
                self.assertEqual(verify_run(run)['frames'], 1)
                if fault in ('rom', 'state'):
                    (run / ('baseline.gba' if fault == 'rom' else 'resume.ss0')).write_bytes(b'damaged')
                elif fault == 'png':
                    next((run / 'frames').glob('*.png')).write_bytes(b'damaged')
                elif fault == 'identity':
                    self.change_json(run / 'resume.checkpoint.json', harness_sha256='other')
                elif fault == 'exit':
                    self.change_json(run / 'exit.json', emulator_exit_code=1)
                elif fault == 'suffix':
                    with (run / 'frames.jsonl').open('ab') as stream: stream.write(b'{}\n')
                elif fault == 'escape':
                    self.change_json(run / 'resume.checkpoint.json', state='../outside.ss0')
                elif fault == 'ledger_hash':
                    p = run / 'frames.jsonl'; p.write_bytes(p.read_bytes().replace(b'"keys": 0', b'"keys": 1'))
                elif fault == 'frame_gap':
                    p = run / 'frames.jsonl'; p.write_bytes(p.read_bytes().replace(b'"core_frame": 1', b'"core_frame": 2'))
                    self.change_json(run / 'resume.checkpoint.json', ledger_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                with self.assertRaisesRegex(exception, message):
                    verify_run(run)

    def test_parent_chain_and_baseline_identity_are_rechecked(self):
        from playthrough_capture import verify_parent, sha
        parent, child = self.fixture('parent'), self.fixture('child')
        cp = parent / 'resume.checkpoint.json'
        self.change_json(child / 'baseline.json', initial_core_frame=1,
                         parent_checkpoint=str(cp), parent_checkpoint_sha256=sha(cp))
        (child / 'frames.jsonl').write_bytes(b'')
        child_cp = child / 'resume.checkpoint.json'
        self.change_json(child_cp, ledger_bytes=0, ledger_sha256=hashlib.sha256(b'').hexdigest())
        verify_parent(child_cp, json.loads(child_cp.read_text()))
        self.change_json(parent / 'baseline.json', harness_sha256='changed')
        with self.assertRaisesRegex(RuntimeError, 'baseline identity mismatch'):
            verify_parent(child_cp, json.loads(child_cp.read_text()))
        self.change_json(parent / 'baseline.json', harness_sha256='harness')
        self.change_json(cp, core_frame=2)
        with self.assertRaisesRegex(RuntimeError, 'checkpoint hash mismatch'):
            verify_parent(child_cp, json.loads(child_cp.read_text()))

    def test_baseline_digest_and_orphan_seed_are_rejected(self):
        from playthrough_capture import verify_parent, sha
        run = self.fixture('metadata')
        cp = run / 'resume.checkpoint.json'
        self.change_json(run / 'baseline.json', schema_version=3)
        self.change_json(cp, baseline_sha256=sha(run / 'baseline.json'))
        verify_parent(cp, json.loads(cp.read_text()))
        self.change_json(run / 'baseline.json', initial_core_frame=1)
        with self.assertRaisesRegex(RuntimeError, 'baseline hash mismatch'):
            verify_parent(cp, json.loads(cp.read_text()))
        self.change_json(cp, baseline_sha256=sha(run / 'baseline.json'))
        with self.assertRaisesRegex(RuntimeError, 'requires a parent'):
            verify_parent(cp, json.loads(cp.read_text()))
        self.change_json(run / 'baseline.json', initial_core_frame=0)
        self.change_json(cp, baseline_sha256=sha(run / 'baseline.json'))
        (run / 'game.sav').write_bytes(b'orphaned seed')
        with self.assertRaisesRegex(RuntimeError, 'seed metadata missing'):
            verify_parent(cp, json.loads(cp.read_text()))

    def test_self_comparison_and_incompatible_histories_are_rejected(self):
        old, new = self.fixture('old_run'), self.fixture('new_run')
        self.assertEqual(compare_runs(old, new)['status'], 'identical_to_reference')
        with self.assertRaisesRegex(ValueError, 'distinct'):
            compare_runs(old, old)
        self.change_json(new / 'baseline.json', parent_checkpoint='different_parent')
        with self.assertRaisesRegex(ValueError, 'cold-boot'):
            compare_runs(old, new)

    def test_changed_harness_or_library_cannot_be_a_matching_reference(self):
        old = self.fixture('reference')
        for key in ('harness_sha256', 'libmgba_sha256'):
            with self.subTest(key=key):
                new = self.fixture(key)
                for name in ('baseline.json', 'resume.checkpoint.json'):
                    self.change_json(new / name, **{key: 'changed'})
                with self.assertRaisesRegex(ValueError, 'Incompatible reference'):
                    compare_runs(old, new)

    def test_real_hung_child_is_killed_and_timeout_is_recorded(self):
        (self.root / 'tools').mkdir()
        (self.root / 'tools/playthrough_capture.py').write_text(
            'import signal,time\nsignal.signal(signal.SIGINT, signal.SIG_IGN)\ntime.sleep(60)\n')
        rom = self.root / 'rom.gba'; rom.write_bytes(b'rom')
        harness = self.root / 'harness'; harness.write_bytes(b'harness')
        inputs = self.root / 'inputs.txt'; inputs.write_text('NONE 1\n')
        args = argparse.Namespace(rom=rom, harness=harness, inputs=inputs, out=self.root / 'job',
                                  reference=None, repeat=1, min_free_gib=15, run_timeout_seconds=1)
        actual_sha = replay.sha
        def fixture_sha(path):
            return 'library' if str(path).endswith('libmgba.dylib') else actual_sha(path)
        children = []
        class Child(subprocess.Popen):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs); children.append(self)
            def wait(self, timeout=None):
                return super().wait(timeout=min(timeout, .2) if timeout is not None else None)
        with patch.object(replay, 'ROOT', self.root), patch.object(replay, 'sha', fixture_sha), patch.object(replay.subprocess, 'Popen', Child):
            with self.assertRaises(subprocess.TimeoutExpired):
                replay.run_replays(args)
        result = json.loads((args.out / 'summary.json').read_text())
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['error_type'], 'TimeoutExpired')
        self.assertIsNone(result['active_process_group'])
        self.assertEqual(len(children), 1)
        with self.assertRaises(ProcessLookupError):
            os.killpg(children[0].pid, 0)

    def test_usage_error_is_not_the_visual_difference_exit_code(self):
        parser = replay.UsageParser()
        with patch('sys.stderr'), self.assertRaises(SystemExit) as raised:
            parser.error('incomplete captures')
        self.assertEqual(raised.exception.code, 64)


if __name__ == '__main__':
    unittest.main()
