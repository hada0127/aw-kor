"""Recorder integration; optional staged-module path during a live source freeze."""
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import frame_transport
from frame_transport import FrameFIFO, FRAME_SIZE, HEADER

ROOT = Path(__file__).resolve().parents[1]
MODULE = Path(os.environ.get('FRAME_FIFO_RECORDER_TEST_PATH', ROOT / 'tools/playthrough_capture.py'))
spec = importlib.util.spec_from_file_location('frame_fifo_recorder_under_test', MODULE)
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)
FRAME = HEADER + bytes(range(256)) * 600


class CaptureIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / 'temp')
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def recorder(self, name, fifo=False, payload=FRAME):
        r = P.Recorder.__new__(P.Recorder)
        r.out = self.root / name; r.out.mkdir(); (r.out / 'frames').mkdir()
        r.counter = 0; r.committed = 0; r.protocol_failed = False
        r.seen = set(); r.pending_png = []; r.png_compress_level = 3
        r.lossless_palette_frames = True; r.ledger = io.StringIO()
        r.harness_sha = 'harness'; r.rom_sha = 'rom'; r.native_counter = 0
        r.frame_transport_modules = {name: {'path': str(Path(module.__file__).resolve()), 'sha256': P.sha(Path(module.__file__))}
            for module, name in ((P.frame_png, 'frame_png.py'), (frame_transport, 'frame_transport.py'))}
        r.check_disk = lambda: None
        r.read_counter = lambda: r.native_counter
        def cmd(command):
            if command == 'frames 1':
                r.native_counter += 1
            if command.startswith('shot '):
                with Path(command[5:]).open('wb') as writer:
                    writer.write(payload)
            return 'OK'
        r.cmd = cmd
        r.frame_transport = FrameFIFO(r.out / 'frame.fifo', .2) if fifo else None
        if fifo:
            self.addCleanup(r.frame_transport.close)
        return r

    def test_png_rgb_ledger_counter_equal_to_regular_transport(self):
        regular = self.recorder('regular')
        fifo = self.recorder('fifo', True)
        for key in ('NONE', 'A', 'LEFT'):
            self.assertEqual(regular.capture(key).tobytes(), fifo.capture(key).tobytes())
        self.assertEqual(regular.ledger.getvalue(), fifo.ledger.getvalue())
        self.assertEqual(regular.counter, fifo.counter)
        self.assertEqual(regular.committed, fifo.committed)
        for name in regular.seen:
            self.assertEqual((regular.out / 'frames' / (name + '.png')).read_bytes(),
                             (fifo.out / 'frames' / (name + '.png')).read_bytes())
        self.assertTrue((regular.out / 'current.raw').exists())
        self.assertFalse((fifo.out / 'current.raw').exists())
        self.assertFalse((fifo.out / 'frame_transport_probe.raw').exists())
        proof = json.loads((fifo.out / 'frame_transport_verification.json').read_text())
        self.assertEqual(proof['raw_sha256'], proof['fifo_sha256'])
        self.assertEqual(proof['counter_before'], 1)
        self.assertEqual(proof['counter_after_raw'], 1)
        self.assertEqual(proof['counter_after_fifo'], 1)
        self.assertEqual(proof['extra_emulated_frames'], 0)

    def test_failed_fifo_frame_not_committed_or_written(self):
        r = self.recorder('bad', True, FRAME[:-1])
        with self.assertRaises(RuntimeError):
            r.capture('NONE')
        self.assertTrue(r.protocol_failed)
        self.assertEqual(r.counter, 1)
        self.assertEqual(r.committed, 0)
        self.assertEqual(r.ledger.getvalue(), '')
        self.assertEqual(list((r.out / 'frames').iterdir()), [])

    def test_command_error_poisoned_even_after_complete_bytes(self):
        r = self.recorder('bad_reply', True)
        cmd = r.cmd
        def failed(command):
            reply = cmd(command)
            if command.startswith('shot '):
                raise RuntimeError('Native shot response failed')
            return reply
        r.cmd = failed
        with self.assertRaisesRegex(RuntimeError, 'response failed'):
            r.capture('NONE')
        self.assertTrue(r.protocol_failed)
        self.assertEqual(r.committed, 0)
        self.assertEqual(r.ledger.getvalue(), '')

    def test_initial_probe_byte_mismatch_not_committed(self):
        r = self.recorder('mismatch', True)
        original = r.cmd
        def cmd(command):
            if command == 'shot ' + str(r.frame_transport.path):
                with r.frame_transport.path.open('wb') as writer:
                    writer.write(FRAME[:-1] + bytes([FRAME[-1] ^ 1]))
                return 'OK'
            return original(command)
        r.cmd = cmd
        with self.assertRaisesRegex(RuntimeError, 'identity differs'):
            r.capture('NONE')
        self.assertEqual(r.committed, 0)
        self.assertTrue(r.protocol_failed)
        self.assertFalse((r.out / 'frame_transport_verification.json').exists())

    def test_initial_probe_counter_change_not_committed(self):
        r = self.recorder('counter_mismatch', True)
        original = r.cmd
        def cmd(command):
            result = original(command)
            if command.startswith('shot '):
                r.native_counter += 1
            return result
        r.cmd = cmd
        with self.assertRaisesRegex(RuntimeError, 'identity differs'):
            r.capture('NONE')
        self.assertEqual(r.committed, 0)
        self.assertTrue(r.protocol_failed)

    def test_module_import_source_cannot_be_shadowed(self):
        self.assertEqual(P.ROOT, ROOT)
        self.assertEqual(P.frame_module_source(P.frame_png, 'frame_png.py'), ROOT / 'tools/frame_png.py')
        with self.assertRaisesRegex(RuntimeError, 'provenance'):
            P.frame_module_source(SimpleNamespace(__file__=str(self.root / 'frame_png.py')), 'frame_png.py')

    def test_parent_proof_hash_and_counter_are_verified(self):
        r = self.recorder('parent_proof', True)
        r.capture('NONE')
        (r.out / 'frames.jsonl').write_text(r.ledger.getvalue())
        baseline = {'schema_version': 4, 'initial_core_frame': 0, 'rom_sha256': r.rom_sha,
                    'harness_sha256': r.harness_sha, 'frame_transport': {'format': 'bounded-shot-fifo-v1', 'modules': r.frame_transport_modules,
                    'module_sha256': r.frame_transport_modules['frame_transport.py']['sha256']}}
        (r.out / 'baseline.json').write_text(json.dumps(baseline))
        cp = {'core_frame': 1, 'baseline_sha256': P.sha(r.out / 'baseline.json'),
              'rom_sha256': r.rom_sha, 'harness_sha256': r.harness_sha,
              'ledger_bytes': (r.out / 'frames.jsonl').stat().st_size,
              'ledger_sha256': P.sha(r.out / 'frames.jsonl'),
              'frame_transport_verification_sha256': r.frame_transport_proof_sha}
        P.verify_parent(r.out / 'resume.checkpoint.json', cp)
        proof = r.out / 'frame_transport_verification.json'
        original_proof = proof.read_text()
        for key, value, message in [('schema', True, 'proof identity'), ('counter_before', True, 'proof identity'), ('modules', {}, 'module proof')]:
            changed = json.loads(original_proof); changed[key] = value
            proof.write_text(json.dumps(changed)); cp['frame_transport_verification_sha256'] = P.sha(proof)
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, message):
                P.verify_parent(r.out / 'resume.checkpoint.json', cp)
        proof.write_text(original_proof); cp['frame_transport_verification_sha256'] = P.sha(proof)
        doc = json.loads(proof.read_text()); doc['counter_after_fifo'] = 2
        proof.write_text(json.dumps(doc))
        with self.assertRaisesRegex(RuntimeError, 'proof hash'):
            P.verify_parent(r.out / 'resume.checkpoint.json', cp)
        cp['frame_transport_verification_sha256'] = P.sha(proof)
        with self.assertRaisesRegex(RuntimeError, 'proof identity'):
            P.verify_parent(r.out / 'resume.checkpoint.json', cp)
        doc['counter_after_fifo'] = 1; doc['rgb_sha256'] = '0' * 64
        proof.write_text(json.dumps(doc)); cp['frame_transport_verification_sha256'] = P.sha(proof)
        with self.assertRaisesRegex(RuntimeError, 'first ledger frame'):
            P.verify_parent(r.out / 'resume.checkpoint.json', cp)

if __name__ == '__main__':
    unittest.main()
