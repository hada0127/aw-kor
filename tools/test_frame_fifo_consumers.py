"""Small FIFO-proof consumer regressions; no native emulator is launched.

Run staged verification in a fresh process with FRAME_FIFO_RECORDER_TEST_PATH.
After production integration run without that variable to check real imports.
"""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

staged = os.environ.get('FRAME_FIFO_RECORDER_TEST_PATH')
if staged:
    spec = importlib.util.spec_from_file_location('playthrough_capture', staged)
    P = importlib.util.module_from_spec(spec)
    sys.modules['playthrough_capture'] = P
    spec.loader.exec_module(P)
else:
    import playthrough_capture as P
import game_save_evidence as G
import replay_campaign_qa as R
import recompress_closed_frames as C
import frame_png
import frame_transport

ROOT = Path(__file__).resolve().parents[1]


class ConsumerProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        library = G.LIBMGBA.resolve()
        if not library.is_file():
            raise RuntimeError('Consumer export fixture requires this project libmgba installation')
        cls.lib_sha = P.sha(library)
        print(json.dumps({'consumer_test_module': str(Path(P.__file__).resolve()), 'module_sha256': P.sha(Path(P.__file__))}), flush=True)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / 'temp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sequence = 0

    def fixture(self, fifo=True):
        self.sequence += 1
        run = self.root / 'output/qa' / ('fixture_' + str(self.sequence))
        run.mkdir(parents=True); (run / 'frames').mkdir()
        im = Image.new('RGB', (240, 160), (37, 91, 143))
        rgb = hashlib.sha256(im.tobytes()).hexdigest()
        image = run / 'frames' / (rgb + '.png'); im.save(image, compress_level=0)
        ledger = json.dumps({'core_frame': 1, 'keys': 'NONE', 'image': 'frames/' + image.name, 'rgb_sha256': rgb}) + '\n'
        (run / 'frames.jsonl').write_text(ledger); (run / 'actions.jsonl').write_text('')
        (run / 'baseline.gba').write_bytes(b'fixture ROM')
        (run / 'resume.ss0').write_bytes(b'fixture recorded state')
        harness = self.root / 'fixture-harness'; harness.write_bytes(b'not executable')
        modules = {name: {'path': str(Path(module.__file__).resolve()), 'sha256': P.sha(Path(module.__file__))}
                   for module, name in ((frame_png, 'frame_png.py'), (frame_transport, 'frame_transport.py'))}
        baseline = {'schema_version': 4, 'initial_core_frame': 0,
                    'rom_sha256': P.sha(run / 'baseline.gba'), 'harness_sha256': P.sha(harness),
                    'libmgba_sha256': self.lib_sha}
        if fifo:
            baseline['frame_transport'] = {'format': 'bounded-shot-fifo-v1', 'modules': modules,
                'module_sha256': modules['frame_transport.py']['sha256'],
                'initial_verification': 'frame_transport_verification.json'}
        (run / 'baseline.json').write_text(json.dumps(baseline))
        cp = {'core_frame': 1, 'baseline_sha256': P.sha(run / 'baseline.json'),
              'rom_sha256': baseline['rom_sha256'], 'harness_sha256': baseline['harness_sha256'],
              'libmgba_sha256': self.lib_sha, 'state': 'resume.ss0',
              'state_sha256': P.sha(run / 'resume.ss0'), 'ledger_bytes': len(ledger.encode()),
              'ledger_sha256': P.sha(run / 'frames.jsonl')}
        if fifo:
            raw = frame_transport.HEADER + im.convert('RGBA').tobytes()
            proof = {'schema': 1, 'core_frame': 1, 'counter_before': 1, 'counter_after_raw': 1,
                     'counter_after_fifo': 1, 'raw_bytes': len(raw), 'fifo_bytes': len(raw),
                     'raw_sha256': hashlib.sha256(raw).hexdigest(), 'fifo_sha256': hashlib.sha256(raw).hexdigest(),
                     'rgb_sha256': rgb, 'modules': modules, 'harness_sha256': baseline['harness_sha256'],
                     'rom_sha256': baseline['rom_sha256'], 'extra_emulated_frames': 0}
            (run / 'frame_transport_verification.json').write_text(json.dumps(proof))
            cp['frame_transport_verification_sha256'] = P.sha(run / 'frame_transport_verification.json')
        (run / 'resume.checkpoint.json').write_text(json.dumps(cp))
        (run / 'exit.json').write_text(json.dumps({'status': 'closed', 'emulator_exit_code': 0,
            'cleanup_errors': [], 'committed_core_frame': 1, 'last_observed_core_frame': 1}))
        saved = run / 'fixture.sav'; saved.write_bytes(bytes(range(256)) * 2)
        receipt = {k: cp[k] for k in ('rom_sha256', 'state_sha256', 'core_frame', 'libmgba_sha256')}
        receipt.update(kind='cartridge-save-from-recorded-checkpoint-v1', save=saved.name,
            save_sha256=P.sha(saved), source_checkpoint=str(run / 'resume.checkpoint.json'),
            source_checkpoint_sha256=P.sha(run / 'resume.checkpoint.json'),
            source_harness_sha256=cp['harness_sha256'])
        (run / 'fixture-save.json').write_text(json.dumps(receipt))
        return run, harness

    def mutate(self, run, kind):
        proof_path = run / 'frame_transport_verification.json'
        cp_path = run / 'resume.checkpoint.json'; cp = json.loads(cp_path.read_text())
        if kind == 'missing':
            proof_path.unlink()
        elif kind == 'hash':
            proof_path.write_text(proof_path.read_text() + ' ')
        elif kind == 'missing_checkpoint_hash':
            cp.pop('frame_transport_verification_sha256')
        else:
            proof = json.loads(proof_path.read_text())
            if kind == 'counter': proof['counter_after_fifo'] = 2
            elif kind == 'bool': proof['counter_before'] = True
            elif kind == 'rgb': proof['rgb_sha256'] = '0' * 64
            elif kind == 'modules': proof['modules'] = {}
            elif kind == 'different_raw_sha': proof['raw_sha256'] = '0' * 64
            elif kind == 'short_payload': proof['fifo_bytes'] -= 1
            elif kind == 'different_rom': proof['rom_sha256'] = '0' * 64
            elif kind == 'different_harness': proof['harness_sha256'] = '0' * 64
            elif kind == 'extra_frames': proof['extra_emulated_frames'] = 1
            elif kind == 'schema_bool': proof['schema'] = True
            elif kind in ('module_path', 'module_cross_sha', 'png_cross_sha'):
                baseline_path = run / 'baseline.json'; baseline = json.loads(baseline_path.read_text())
                if kind == 'module_path':
                    baseline['frame_transport']['modules']['frame_transport.py']['path'] = 'frame_transport.py'
                    proof['modules'] = baseline['frame_transport']['modules']
                elif kind == 'module_cross_sha':
                    baseline['frame_transport']['module_sha256'] = '0' * 64
                else:
                    baseline['frame_png_encoder_sha256'] = '0' * 64
                baseline_path.write_text(json.dumps(baseline)); cp['baseline_sha256'] = P.sha(baseline_path)
            else: raise AssertionError(kind)
            proof_path.write_text(json.dumps(proof))
            cp['frame_transport_verification_sha256'] = P.sha(proof_path)
        cp_path.write_text(json.dumps(cp))
        receipt_path = run / 'fixture-save.json'; receipt = json.loads(receipt_path.read_text())
        receipt['source_checkpoint_sha256'] = P.sha(cp_path); receipt_path.write_text(json.dumps(receipt))

    def consume(self, name, run, harness):
        if name == 'receipt': return G.verify_receipt(run / 'fixture-save.json')
        if name == 'replay': return R.verify_run(run)
        if name == 'export': return G.export(run / 'resume.checkpoint.json', harness, run / 'exported', announce=False)
        if name == 'recompress':
            work = run / 'work'; work.mkdir(exist_ok=True)
            with patch.object(C, 'ROOT', self.root), patch.object(C, 'unused'), patch.object(C, 'floor'), (self.root / 'test-receipts.jsonl').open('w') as receipt, (self.root / 'test-progress.jsonl').open('w') as progress:
                return C.process_run(run, work, 1, 1, receipt, progress)
        raise AssertionError(name)

    def test_consumers_bind_the_same_new_verifier(self):
        expected = Path(staged).resolve() if staged else ROOT / 'tools/playthrough_capture.py'
        self.assertEqual(Path(P.__file__).resolve(), expected)
        for module in (G, R, C):
            self.assertIs(module.verify_parent, P.verify_parent)

    def test_valid_fifo_and_legacy_proofs_accepted(self):
        for fifo in (False, True):
            for consumer in ('receipt', 'replay', 'recompress'):
                with self.subTest(fifo=fifo, consumer=consumer):
                    run, harness = self.fixture(fifo)
                    frame = next((run / 'frames').iterdir()); before = frame.read_bytes()
                    ledger = (run / 'frames.jsonl').read_bytes()
                    result = self.consume(consumer, run, harness)
                    if consumer == 'recompress':
                        self.assertEqual(result['replaced'], 1)
                        self.assertGreater(result['saved_bytes'], 0)
                        self.assertTrue(result['verify_parent_before_after'])
                        self.assertNotEqual(frame.read_bytes(), before)
                        with Image.open(frame) as image:
                            self.assertEqual(hashlib.sha256(image.convert('RGB').tobytes()).hexdigest(), frame.stem)
                        self.assertEqual((run / 'frames.jsonl').read_bytes(), ledger)
                    elif consumer == 'replay':
                        self.assertEqual(result['frames'], 1)
                    else:
                        self.assertEqual(result[1]['core_frame'], 1)

    def test_valid_export_reaches_mock_producer_only_after_proof(self):
        for fifo in (False, True):
            with self.subTest(fifo=fifo):
                run, harness = self.fixture(fifo)
                def producer(argv, **kwargs):
                    (run / 'exported/game.sav').write_bytes(bytes(range(256)) * 2)
                    return subprocess.CompletedProcess(argv, 0,
                        'OK loadstate ok=1\nOK framecounter 1\nOK dumpsave size=512\nOK framecounter 1\nOK quit\n', '')
                with patch.object(G.subprocess, 'run', side_effect=producer) as native:
                    receipt = self.consume('export', run, harness)
                    native.assert_called_once()
                self.assertTrue(receipt.is_file())
                G.verify_receipt(receipt)

    def test_invalid_proofs_rejected_before_consumer_writes_or_native(self):
        messages = {'missing': None, 'hash': 'proof hash', 'missing_checkpoint_hash': 'proof hash',
                    'counter': 'proof identity', 'bool': 'proof identity', 'rgb': 'first ledger frame',
                    'modules': 'module proof', 'different_raw_sha': 'proof identity',
                    'short_payload': 'proof identity', 'different_rom': 'proof identity',
                    'different_harness': 'proof identity', 'extra_frames': 'proof identity',
                    'schema_bool': 'proof identity', 'module_path': 'module identity malformed',
                    'module_cross_sha': 'module SHA differs', 'png_cross_sha': 'PNG module SHA differs'}
        for kind, message in messages.items():
            for consumer in ('receipt', 'replay', 'recompress', 'export'):
                with self.subTest(kind=kind, consumer=consumer):
                    run, harness = self.fixture()
                    self.mutate(run, kind)
                    frame = next((run / 'frames').iterdir()); before = frame.read_bytes()
                    protected = {p: p.read_bytes() for p in run.iterdir() if p.is_file()}
                    with patch.object(G.subprocess, 'run') as native, patch.object(C.os, 'replace') as replace:
                        error = self.assertRaises(FileNotFoundError) if kind == 'missing' else self.assertRaisesRegex(RuntimeError, message)
                        with error as caught:
                            self.consume(consumer, run, harness)
                        if kind == 'missing':
                            self.assertEqual(Path(caught.exception.filename), run / 'frame_transport_verification.json')
                        native.assert_not_called(); replace.assert_not_called()
                    self.assertEqual(frame.read_bytes(), before)
                    self.assertTrue(all(p.read_bytes() == raw for p, raw in protected.items()))
                    if consumer == 'recompress':
                        self.assertEqual((self.root / 'test-receipts.jsonl').read_bytes(), b'')
                        self.assertEqual((self.root / 'test-progress.jsonl').read_bytes(), b'')
                    self.assertFalse((run / 'exported').exists())
                    if (run / 'work').exists():
                        self.assertEqual(list((run / 'work').iterdir()), [])

    def test_initial_uncommitted_checkpoint_does_not_require_first_frame_probe(self):
        run, _ = self.fixture()
        cp = json.loads((run / 'resume.checkpoint.json').read_text())
        cp.update(core_frame=0, ledger_bytes=0, ledger_sha256=hashlib.sha256(b'').hexdigest())
        cp.pop('frame_transport_verification_sha256')
        (run / 'frame_transport_verification.json').unlink()
        P.verify_parent(run / 'initial.checkpoint.json', cp)

    def test_baseline_flag_deletion_breaks_checkpoint_hash_binding(self):
        run, _ = self.fixture()
        path = run / 'baseline.json'; baseline = json.loads(path.read_text())
        baseline.pop('frame_transport'); path.write_text(json.dumps(baseline))
        with self.assertRaisesRegex(RuntimeError, 'Parent baseline hash mismatch'):
            P.verify_parent(run / 'resume.checkpoint.json', json.loads((run / 'resume.checkpoint.json').read_text()))

if __name__ == '__main__':
    unittest.main()
