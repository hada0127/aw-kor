"""Reject provenance/capture claims that could silently reuse the wrong save."""
import json
from pathlib import Path
import tempfile
import unittest

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


if __name__ == '__main__':
    unittest.main()
