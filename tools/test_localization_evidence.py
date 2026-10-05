import copy
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

import localization_evidence as evidence
import prepare_patch_distribution as package
import run_release_qa as release


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        (evidence.ROOT / 'temp').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=evidence.ROOT / 'temp')
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(evidence, 'ROOT', self.root); self.root_patch.start()
        (self.root / 'temp').mkdir()
        for name in evidence.BUILD_METADATA:
            (self.root / name).write_text('[]')
        (self.root / 'data').mkdir()
        (self.root / 'data/text.json').write_text('{"ko":"원문"}')
        self.source = self.root / 'original.gba'; self.source.write_bytes(b'original   fixture')
        self.rom = self.root / 'patched.gba'; self.rom.write_bytes(b'translated fixture')
        self.fonts = patch.object(evidence, 'EXTERNAL_FONTS', []); self.fonts.start()
        self.inputs = evidence.snapshot_inputs(self.root)
        evidence.write_build_receipt(self.rom, self.source, self.inputs, self.inputs, evidence.sha(self.source))
        self.report = {'schema': 1, 'stage': 'prepackage_qa', 'rom_sha256': evidence.sha(self.rom),
                       'source_sha256': evidence.sha(self.source), 'inputs_before': self.inputs,
                       'inputs_after': self.inputs, 'failed_count': 0,
                       'results': [{'label': name, 'returncode': 0, 'timed_out': False}
                                   for name in release.REQUIRED_PREPACKAGE_GATES]}

    def tearDown(self):
        self.fonts.stop(); self.root_patch.stop(); self.temp.cleanup()

    def verify(self, report=None, current=None):
        return evidence.verify_prepackage_report(report or self.report, self.rom, self.source,
                                                  release.REQUIRED_PREPACKAGE_GATES,
                                                  current or evidence.snapshot_inputs(self.root))

    def test_current_complete_report_passes_but_missing_failed_duplicate_checks_do_not(self):
        self.assertEqual(self.verify()['rom_sha256'], evidence.sha(self.rom))
        for fault in ('missing', 'failed', 'timeout', 'duplicate', 'wrong_stage', 'boolean_code'):
            report = copy.deepcopy(self.report)
            if fault == 'missing': report['results'].pop()
            if fault == 'failed': report['results'][0]['returncode'] = 1
            if fault == 'timeout': report['results'][0]['timed_out'] = True
            if fault == 'duplicate': report['results'].append(report['results'][0])
            if fault == 'wrong_stage': report['stage'] = 'editor_only'
            if fault == 'boolean_code': report['results'][0]['returncode'] = False
            with self.subTest(fault=fault), self.assertRaises(ValueError): self.verify(report)

    def test_changed_translation_and_rom_invalidate_evidence(self):
        (self.root / 'data/text.json').write_text('{"ko":"바뀜"}')
        with self.assertRaisesRegex(ValueError, 'stale'): self.verify()
        self.rom.write_bytes(b'changed ROM')
        with self.assertRaisesRegex(ValueError, 'these ROMs'): self.verify()

    def test_generated_outputs_are_declared_but_do_not_allow_code_drift(self):
        (self.root / 'data/objlabel_sprites.json').write_text('{}')
        after = evidence.snapshot_inputs(self.root)
        evidence.stable_build_inputs(self.inputs, after)
        (self.root / 'tools').mkdir()
        (self.root / 'tools/writer.py').write_text('new implementation')
        with self.assertRaisesRegex(ValueError, 'changed during build'):
            evidence.stable_build_inputs(self.inputs, evidence.snapshot_inputs(self.root))

    def test_source_changed_during_build_cannot_get_a_receipt(self):
        with self.assertRaisesRegex(ValueError, 'Source ROM changed'):
            evidence.write_build_receipt(self.rom, self.source, self.inputs, self.inputs, 'wrong hash')

    def test_replaced_build_metadata_and_debug_receipts_are_rejected(self):
        (self.root / evidence.BUILD_METADATA[0]).write_text('[1]')
        with self.assertRaisesRegex(ValueError, 'metadata'): self.verify()
        evidence.write_build_receipt(self.rom, self.source, self.inputs, self.inputs,
                                     evidence.sha(self.source), repoint_enabled=False)
        with self.assertRaisesRegex(ValueError, 'Debug build'): self.verify()

    def test_packaging_refuses_before_writing_and_accepts_bound_fixture(self):
        report_path = self.root / 'qa.json'; dist = self.root / 'dist'
        with patch.object(package, 'SOURCE_ROM', self.source), patch.object(package, 'TARGET_ROM', self.rom), \
             patch.object(package, 'DIST', dist), patch.object(package, 'snapshot_inputs', lambda: self.inputs), \
             patch('sys.argv', ['prepare', '--qa-report', str(report_path), '--stem', 'fixture']):
            with self.assertRaisesRegex(SystemExit, 'before writing'): package.main()
            self.assertFalse(dist.exists())
            evidence.write_json(report_path, self.report)
            package.main()
        manifest = json.loads((dist / 'manifest.json').read_text())
        self.assertEqual(manifest['validation']['qa_evidence']['report_digest'], evidence.digest(self.report))
        self.assertTrue(manifest['validation']['bps_round_trip'])

    def test_failed_gate_never_runs_packaging_or_distribution_checks(self):
        labels = []
        def run(label, argv, timeout):
            labels.append(label)
            return {'label': label, 'returncode': 1 if label == 'fit' else 0, 'timed_out': False}
        with patch.object(release, 'snapshot_inputs', lambda: self.inputs), \
             patch.object(release, 'verify_build_receipt'), patch.object(release, 'sha', return_value='hash'), \
             patch.object(release, 'run_one', run), patch.object(release, 'BASE_GATES', [('fit', []), ('dist-integrity', [])]), \
             patch.object(release, 'PREPACKAGE_REPORT', self.root / 'prepackage.json'), \
             patch('sys.argv', ['qa', '--dist-date', '2026-09-21', '--report', str(self.root / 'report.json')]):
            self.assertEqual(release.main(), 1)
        self.assertEqual(labels, ['py-compile', 'fit'])

    def test_timeout_output_is_json_serializable_and_password_is_redacted(self):
        args = ['python', 'check.py', '--password', 'fixture-secret']
        error = subprocess.TimeoutExpired(args, 1, output=b'partial output', stderr=b'partial error')
        with patch.object(release.subprocess, 'run', side_effect=error):
            result = release.run_one('fixture', args, timeout=1)
        self.assertTrue(result['timed_out'])
        self.assertNotIn('fixture-secret', json.dumps(result))


if __name__ == '__main__': unittest.main()
