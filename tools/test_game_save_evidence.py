"""Reject provenance/capture claims that could silently reuse the wrong save."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import game_save_evidence as G
import playthrough_capture as P
from game_save_evidence import verify_receipt, verify_recorded_seed, verify_migration_storage
from playthrough_capture import sha
from replay_campaign_qa import export_inputs


class GameSaveEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'temp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'baseline.gba').write_bytes(b'original captured ROM')
        (self.source / 'state.ss0').write_bytes(b'recorded state')
        self.cp = self.source / 'frame.checkpoint.json'
        meta = {'rom_sha256': sha(self.source / 'baseline.gba'), 'state': 'state.ss0',
                'state_sha256': sha(self.source / 'state.ss0'), 'core_frame': 120,
                'libmgba_sha256': 'a' * 64, 'harness_sha256': 'b' * 64}
        self.cp.write_text(json.dumps(meta))
        (self.root / 'game.sav').write_bytes(bytes(range(256)) * 2)
        self.record = {k: meta[k] for k in ('rom_sha256', 'state_sha256', 'core_frame', 'libmgba_sha256')}
        self.record.update(kind='cartridge-save-from-recorded-checkpoint-v1', save='game.sav',
                           save_sha256=sha(self.root / 'game.sav'), source_checkpoint=str(self.cp),
                           source_checkpoint_sha256=sha(self.cp), source_harness_sha256='b' * 64)
        self.receipt = self.root / 'game_save.json'
        self.receipt.write_text(json.dumps(self.record))

    def test_unchanged_save_is_bound_to_recorded_rom_state_and_frame(self):
        saved, record = verify_receipt(self.receipt, verify_frames=False)
        self.assertEqual(saved, self.root / 'game.sav')
        self.assertEqual(record['core_frame'], 120)

    def test_legacy_receipt_ignores_new_anchored_identity_arguments(self):
        # Backward compatibility: legacy receipts keep their old checks only.
        verify_receipt(self.receipt, verify_frames=False, expected_harness_sha256='e' * 64,
                       expected_libmgba_sha256='e' * 64)

    def test_game_save_cannot_boot_on_a_different_rom(self):
        with self.assertRaisesRegex(ValueError, 'does not match target ROM'):
            verify_receipt(self.receipt, verify_frames=False, expected_rom_sha256='f' * 64)

    def test_explicit_save_migration_requires_exact_source_and_distinct_target(self):
        source = self.record['rom_sha256']
        verify_receipt(self.receipt, verify_frames=False, expected_rom_sha256='f' * 64,
                       migration_source_sha256=source)
        for target, declared in [('f' * 64, 'e' * 64), (source, source), (None, source)]:
            with self.subTest(target=target, declared=declared), self.assertRaises(ValueError):
                verify_receipt(self.receipt, verify_frames=False, expected_rom_sha256=target,
                               migration_source_sha256=declared)

    def test_save_migration_rejects_wrong_target_storage_and_size(self):
        source = self.root / 'source.gba'; target = self.root / 'target.gba'
        source.write_bytes(b'FLASH1M_V102'); target.write_bytes(b'FLASH1M_V103')
        verify_migration_storage(source, target, 131072)
        with self.assertRaisesRegex(ValueError, 'size'):
            verify_migration_storage(source, target, 65536)
        for blob in (b'SRAM_V110', b'unknown', b'FLASH1M_V102 SRAM_V110'):
            target.write_bytes(blob)
            with self.assertRaisesRegex(ValueError, 'storage types'):
                verify_migration_storage(source, target, 131072)

    def test_changed_save_is_rejected_even_with_same_size(self):
        (self.root / 'game.sav').write_bytes(bytes(reversed(range(256))) * 2)
        with self.assertRaisesRegex(ValueError, 'bytes do not match'):
            verify_receipt(self.receipt, verify_frames=False)

    def test_changed_source_state_or_rom_is_rejected(self):
        for name in ('state.ss0', 'baseline.gba'):
            with self.subTest(name=name):
                path = self.source / name
                original = path.read_bytes()
                path.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'source binary changed'):
                    verify_receipt(self.receipt, verify_frames=False)
                path.write_bytes(original)

    def test_receipt_cannot_redirect_save_outside_its_directory(self):
        self.record['save'] = '../outside.sav'
        self.receipt.write_text(json.dumps(self.record))
        with self.assertRaisesRegex(ValueError, 'escapes'):
            verify_receipt(self.receipt, verify_frames=False)

    def test_loaded_seed_copy_must_match_source_bytes(self):
        seed = {'save': 'game.sav', 'save_sha256': sha(self.root / 'game.sav'),
                'receipt': 'game_save.json', 'receipt_sha256': sha(self.receipt),
                'loaded_copy': 'loaded.sav'}
        (self.root / 'loaded.sav').write_bytes((self.root / 'game.sav').read_bytes())
        baseline = {'initial_game_save': seed}
        verify_recorded_seed(self.root, baseline)
        baseline['rom_sha256'] = 'f' * 64
        baseline['schema_version'] = 3
        verify_recorded_seed(self.root, baseline)
        baseline['schema_version'] = 4
        with self.assertRaisesRegex(ValueError, 'migration is missing'):
            verify_recorded_seed(self.root, baseline)
        seed['migration'] = {'source_rom_sha256': self.record['rom_sha256'],
                             'target_rom_sha256': baseline['rom_sha256']}
        verify_recorded_seed(self.root, baseline)
        seed['migration']['source_rom_sha256'] = 'e' * 64
        with self.assertRaisesRegex(ValueError, 'migration is missing'):
            verify_recorded_seed(self.root, baseline)
        seed['migration']['source_rom_sha256'] = self.record['rom_sha256']
        (self.root / 'loaded.sav').write_bytes(b'wrong loaded save')
        with self.assertRaisesRegex(ValueError, 'seed changed'):
            verify_recorded_seed(self.root, baseline)

    def test_invalid_save_size_is_rejected_even_with_matching_hash(self):
        (self.root / 'game.sav').write_bytes(b'bad')
        self.record['save_sha256'] = sha(self.root / 'game.sav')
        self.receipt.write_text(json.dumps(self.record))
        with self.assertRaisesRegex(ValueError, 'bytes do not match'):
            verify_receipt(self.receipt, verify_frames=False)

    def test_missing_save_key_is_value_error(self):
        self.record.pop('save')
        self.receipt.write_text(json.dumps(self.record))
        with self.assertRaisesRegex(ValueError, 'malformed: save'):
            verify_receipt(self.receipt, verify_frames=False)

    def test_unknown_receipt_kind_is_rejected(self):
        self.record['kind'] = 'unknown'
        self.receipt.write_text(json.dumps(self.record))
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            verify_receipt(self.receipt, verify_frames=False)

    def test_source_harness_identity_is_checked(self):
        self.record['source_harness_sha256'] = 'wrong'
        self.receipt.write_text(json.dumps(self.record))
        with self.assertRaisesRegex(ValueError, 'harness mismatch'):
            verify_receipt(self.receipt, verify_frames=False)

    def test_seeded_boot_cannot_masquerade_as_empty_save_route(self):
        (self.root / 'baseline.json').write_text(json.dumps({'initial_core_frame': 0, 'initial_game_save': {'save': 'game.sav'}}))
        with self.assertRaisesRegex(ValueError, 'empty-save cold route'):
            export_inputs(self.root)


FAKE_HARNESS = """#!%s
import json, struct, sys
rom, log = sys.argv[1], sys.argv[2]
open(log, 'w').close()
save = open(sys.argv[3], 'rb').read() if len(sys.argv) > 3 else bytes((i * 7 + 3) & 255 for i in range(32768))
frame = 0
def reply(text):
    sys.stdout.write(text + '\\n'); sys.stdout.flush()
for line in sys.stdin:
    verb, _, arg = line.strip().partition(' ')
    if verb == 'framecounter': reply('OK framecounter %%d' %% frame)
    elif verb == 'frames': frame += int(arg); reply('OK frames ' + arg)
    elif verb == 'keys': reply('OK keys ' + arg)
    elif verb == 'shot':
        open(arg, 'wb').write(struct.pack('<HHB', 240, 160, 4) + bytes([frame & 255, 40, 80, 0]) * (240 * 160))
        reply('OK shot 240 160')
    elif verb == 'savestate':
        open(arg, 'w').write(json.dumps({'frame': frame, 'save': save.hex()})); reply('OK savestate ok=1')
    elif verb == 'loadstate':
        state = json.load(open(arg)); frame = state['frame']; save = bytes.fromhex(state['save'])
        reply('OK loadstate ok=1')
    elif verb == 'dumpsave':
        open(arg, 'wb').write(save); reply('OK dumpsave size=%%d' %% len(save))
    elif verb == 'quit':
        reply('OK quit'); break
    else:
        reply('ERR ' + verb)
""" % sys.executable


class AnchoredGameSaveTests(unittest.TestCase):
    """2026-10-06 evidence-chain cut: an anchored receipt is a self-contained chain root."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=P.ROOT / 'temp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rom = self.root / 'rom.gba'
        self.rom.write_bytes(b'\0' * 512 + b'SRAM_V113' + bytes(range(256)) * 4)
        self.harness = self.root / 'fake_harness'
        self.harness.write_text(FAKE_HARNESS)
        self.harness.chmod(0o755)
        self.lib = sha(G.LIBMGBA.resolve())
        self.source = self.root / 'source'
        self.record(out=self.source, actions=[3])
        self.cp = self.source / 'resume.checkpoint.json'

    def args(self, **kw):
        base = dict(rom=self.rom, harness=self.harness, resume=None, game_save=None, min_free_gib=1,
                    timeout=10, png_compress_level=1, no_contact_sheets=True, game_save_source_rom_sha256=None)
        base.update(kw)
        return SimpleNamespace(**base)

    def record(self, actions, **kw):
        with patch('builtins.print'):
            recorder = P.Recorder(self.args(**kw))
            for count in actions:
                recorder.action('NONE', count, 0)
            result = recorder.close()
        recorder.proc.stdin.close()
        recorder.proc.stdout.close()
        self.assertEqual(result['status'], 'closed', result)
        return recorder.out

    def anchor(self, name='anchor', **kw):
        with patch('builtins.print'):
            return G.export_anchored(self.cp, self.harness, self.root / name, reason='unit test cut', **kw)

    def verify(self, receipt, **kw):
        base = dict(expected_rom_sha256=sha(self.rom), expected_harness_sha256=sha(self.harness),
                    expected_libmgba_sha256=self.lib)
        base.update(kw)
        return verify_receipt(receipt, **base)

    def test_anchored_receipt_verifies_after_source_run_is_deleted(self):
        receipt = self.anchor()
        with patch('builtins.print'):
            legacy = G.export(self.cp, self.harness, self.root / 'legacy')
        record = json.loads(receipt.read_text())
        self.assertEqual((record['kind'], record['source_chain_verification'], record['reason']),
                         ('cartridge-save-anchored-v1', 'full-frame-chain', 'unit test cut'))
        self.assertEqual((record['save_storage'], record['source_core_frame']), (['SRAM'], 4))
        shutil.rmtree(self.source)
        saved, _ = self.verify(receipt)
        self.assertEqual(saved, receipt.parent / 'game.sav')
        with self.assertRaises((OSError, ValueError)):  # legacy kind still depends on its source run
            verify_receipt(legacy, verify_frames=False)

    def test_new_run_and_its_resume_verify_only_back_to_anchored_root(self):
        receipt = self.anchor()
        shutil.rmtree(self.source)
        run1 = self.record(out=self.root / 'run1', game_save=receipt, actions=[2])
        baseline = json.loads((run1 / 'baseline.json').read_text())
        self.assertIsNone(baseline['parent_checkpoint'])
        self.assertEqual(baseline['initial_core_frame'], 0)
        self.assertEqual(json.loads((run1 / 'game_save.json').read_text())['kind'], 'cartridge-save-anchored-v1')
        run2 = self.record(out=self.root / 'run2', resume=run1 / 'resume.checkpoint.json', actions=[1])
        cp2 = run2 / 'resume.checkpoint.json'
        P.verify_parent(cp2, json.loads(cp2.read_text()))
        # The root's local copies are still bound: tampering is detected on resume.
        for name in ('game.sav', 'game_save.json'):
            with self.subTest(name=name):
                path = run1 / name
                original = path.read_bytes()
                path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
                with self.assertRaisesRegex(ValueError, 'seed changed'):
                    P.verify_parent(cp2, json.loads(cp2.read_text()))
                path.write_bytes(original)

    def test_tampering_and_identity_mismatch_are_rejected(self):
        receipt = self.anchor()
        shutil.rmtree(self.source)
        saved = receipt.parent / 'game.sav'
        outside = self.root / 'outside.sav'
        outside.write_bytes(saved.read_bytes())
        record = json.loads(receipt.read_text())
        receipt.write_text(json.dumps({**record, 'save': '../outside.sav'}))
        with self.assertRaisesRegex(ValueError, 'escapes'):
            self.verify(receipt)
        receipt.write_text(json.dumps(record))
        link = receipt.parent / 'link.sav'
        link.symlink_to(outside)
        receipt.write_text(json.dumps({**record, 'save': 'link.sav'}))
        with self.assertRaisesRegex(ValueError, 'escapes'):
            self.verify(receipt)
        receipt.write_text(json.dumps(record))
        original = saved.read_bytes()
        saved.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        with self.assertRaisesRegex(ValueError, 'bytes do not match'):
            self.verify(receipt)
        saved.write_bytes(original)
        cases = [({'expected_rom_sha256': 'f' * 64}, 'does not match target ROM'),
                 ({'expected_harness_sha256': 'e' * 64}, 'harness mismatch'),
                 ({'expected_libmgba_sha256': 'e' * 64}, 'library mismatch'),
                 ({'expected_harness_sha256': None}, 'requires harness')]
        for kw, message in cases:
            with self.subTest(kw=kw), self.assertRaisesRegex(ValueError, message):
                self.verify(receipt, **kw)
        record = json.loads(receipt.read_text())
        for key, value, message in [('reason', ' ', 'malformed'), ('save_storage', ['SRAM', 'FLASH'], 'malformed'),
                                    ('save_size', 65536, 'bytes do not match'), ('schema', 2, 'malformed')]:
            with self.subTest(key=key):
                receipt.write_text(json.dumps({**record, key: value}))
                with self.assertRaisesRegex(ValueError, message):
                    self.verify(receipt)
        saved.write_bytes(b'\xff' * 32768)
        receipt.write_text(json.dumps({**record, 'save_sha256': sha(saved)}))
        with self.assertRaisesRegex(ValueError, 'uniform'):
            self.verify(receipt)
        saved.write_bytes(original)
        receipt.write_text(json.dumps(record))
        other = self.root / 'other_harness'
        other.write_text(FAKE_HARNESS + '# different build\n')
        other.chmod(0o755)
        with patch.object(P.subprocess, 'Popen', side_effect=AssertionError('must fail before launch')), \
                self.assertRaisesRegex(ValueError, 'harness mismatch'), patch('builtins.print'):
            P.Recorder(self.args(out=self.root / 'bad_harness', harness=other, game_save=receipt))

    def test_anchored_migration_uses_recorded_storage_type(self):
        receipt = self.anchor()
        shutil.rmtree(self.source)
        source = json.loads(receipt.read_text())['rom_sha256']
        self.verify(receipt, expected_rom_sha256='f' * 64, migration_source_sha256=source)
        with self.assertRaisesRegex(ValueError, 'migration source'):
            self.verify(receipt, expected_rom_sha256='f' * 64, migration_source_sha256='e' * 64)
        target = self.root / 'target.gba'
        target.write_bytes(b'SRAM_V110')
        verify_migration_storage(None, target, 32768, source_types={b'SRAM'})
        target.write_bytes(b'FLASH1M_V103')
        with self.assertRaisesRegex(ValueError, 'storage types'):
            verify_migration_storage(None, target, 32768, source_types={b'SRAM'})

    def test_export_source_checks_and_explicit_binaries_only_mode(self):
        other = self.root / 'other_harness'
        other.write_text(FAKE_HARNESS + '# different build\n')
        other.chmod(0o755)
        with self.assertRaisesRegex(ValueError, 'checkpoint harness'):
            G.export_anchored(self.cp, other, self.root / 'x', reason='r')
        with self.assertRaisesRegex(ValueError, 'reason'):
            G.export_anchored(self.cp, self.harness, self.root / 'y', reason=' ')
        next((self.source / 'frames').iterdir()).unlink()  # simulate pruned bulk frames
        with self.assertRaises(Exception):
            self.anchor('full')
        receipt = self.anchor('lite', verify_source_frames=False)
        self.assertEqual(json.loads(receipt.read_text())['source_chain_verification'], 'checkpoint-binaries-only')
        self.verify(receipt)
        # Skip mode still binds schema>=3 baselines, even if the checkpoint drops the field.
        baseline = self.source / 'baseline.json'
        original = baseline.read_bytes()
        baseline.write_bytes(original + b' ')
        with self.assertRaisesRegex(ValueError, 'baseline changed'):
            self.anchor('lite2', verify_source_frames=False)
        baseline.write_bytes(original)
        checkpoint = json.loads(self.cp.read_text())
        checkpoint.pop('baseline_sha256')
        self.cp.write_text(json.dumps(checkpoint))
        with self.assertRaisesRegex(ValueError, 'baseline changed'):
            self.anchor('lite3', verify_source_frames=False)

    def test_cli_anchored_export(self):
        script = Path(G.__file__).resolve()
        base = [sys.executable, str(script), '--checkpoint', str(self.cp), '--harness', str(self.harness)]
        env = {**os.environ, 'PYTHONPATH': str(script.parent)}
        bad = subprocess.run(base + ['--out', str(self.root / 'cli_bad'), '--anchored'],
                             capture_output=True, text=True, env=env)
        self.assertEqual(bad.returncode, 2)
        bad = subprocess.run(base + ['--out', str(self.root / 'cli_bad'), '--reason', 'x'],
                             capture_output=True, text=True, env=env)
        self.assertEqual(bad.returncode, 2)
        self.assertFalse((self.root / 'cli_bad').exists())
        ok = subprocess.run(base + ['--out', str(self.root / 'cli'), '--anchored', '--reason', 'cli cut'],
                            capture_output=True, text=True, env=env)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(ok.stdout.strip(), str((self.root / 'cli' / 'game_save.json').resolve()))
        self.verify(self.root / 'cli' / 'game_save.json')


if __name__ == '__main__':
    unittest.main()
