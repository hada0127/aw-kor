"""Current candidate scene gates must distinguish unresolved evidence from capture passes."""
import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ROM = json.loads((ROOT/'temp/scene_screenshots/manifest.json').read_text())['rom']
sys.path.insert(0, str(ROOT/'tools'))


class SceneGateBlockedTest(unittest.TestCase):
    def test_catalog_regeneration_preserves_blockers_and_evidence(self):
        from tools import build_scene_catalog as build
        source = json.loads((ROOT/'data/scene_entrypoints.json').read_text())['scenes']
        with TemporaryDirectory(dir=ROOT/'temp') as directory:
            generated_path = Path(directory)/'scene_catalog.json'
            with patch.object(build, 'OUT', generated_path), patch('builtins.print'):
                build.main()
            generated = json.loads(generated_path.read_text())
        registered = json.loads((ROOT/'data/scene_catalog.json').read_text())
        self.assertEqual(generated, registered)
        by_id = {scene['id']: scene for scene in generated['scenes']}
        blockers = {sid: row for sid, row in source.items()
                    if row.get('status') in {'blocked', 'defect'}}
        self.assertEqual((sum(v['status']=='blocked' for v in blockers.values()),
                          sum(v['status']=='defect' for v in blockers.values())), (15, 0))
        for sid, row in blockers.items():
            self.assertEqual(by_id[sid]['screenshot'],
                             {'status': row['status'], 'note': row['note']})
            for key in ('diagnostic_probe', 'evidence'):
                if key in row:
                    self.assertEqual(by_id[sid][key], row[key])
        early = source['30a1_part2_redstar_story_early']
        current = next(cp for cp in json.loads((ROOT/'data/screen_checkpoints.json').read_text())['checkpoints']
                       if cp['name'] == early['checkpoint'])
        self.assertEqual(early['source_endpoint'], current['recorder_endpoint']['checkpoint'])
        self.assertEqual(early['source_endpoint'], early['provenance_path'])
        withdrawn = {'scene_30a1_part2_redstar_story_early_b', 'scene_80a_campaign_story_early'}
        for row in source.values():
            self.assertFalse(withdrawn & {x.get('checkpoint') if isinstance(x, dict) else x
                                            for x in row.get('extra_screenshots', [])})

    def test_current_candidate_has_only_declared_blockers(self):
        source = json.loads((ROOT/'data/scene_entrypoints.json').read_text())['scenes']
        expected = {sid: row['status'].upper() for sid, row in source.items()
                    if row.get('status') in {'blocked', 'defect'}}
        commands = [
            (['python3', 'tools/audit_scene_semantics.py', '--strict'],
             ROOT/'temp/scene_semantic_audit/report.json'),
            (['python3', 'tools/qa_scene_screenshot_sanity.py', '--rom', ROM],
             ROOT/'temp/scene_screenshots_sanity/report.json'),
        ]
        for command, report_path in commands:
            with self.subTest(command=command[1]):
                result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                report = json.loads(report_path.read_text())
                issues = report['issues']
                self.assertEqual(len(issues), len(expected), issues)
                self.assertEqual({x.get('scene', x.get('scene_id')): x['issue'] for x in issues},
                                 expected)
                self.assertFalse(any('89b' in str(x.get('scene', x.get('scene_id', '')))
                                     for x in issues))

    def test_probes_and_defect_never_registered_as_pass(self):
        reg = json.loads((ROOT/'data/release_C_evidence_registration.json').read_text())
        records = {r['item_id']: r for r in reg['history']['records'] if r['key'].endswith('|batch4')}
        self.assertEqual(records['26a-P2-DEFECT']['replay']['status'], 'DEFECT')
        source = json.loads((ROOT/'data/scene_entrypoints.json').read_text())['scenes']
        history = source['26a_part2_battle_start_overlays']['evidence']['b28_defect_history']
        self.assertEqual(history['status'], 'defect')
        self.assertEqual(history['evidence']['candidate_sha256'],
                         'e00646e63eff4ff9828f12595675e3a10ee93e4d7da88b7c4a8e5f9921497067')
        for item in ('B-30e3', 'B-19c1', 'B-80b', 'B-80c'):
            self.assertEqual(records[item]['replay']['status'], 'BLOCKED')
        self.assertTrue(records['B-19f']['replay']['cheat_tainted'])
        self.assertTrue(records['C-89b-trace']['replay']['cheat_tainted'])

    def test_active_registration_is_bound_to_b31_and_excludes_history(self):
        from tools.audit_scene_semantics import active_registration_records
        path = ROOT/'data/release_C_evidence_registration.json'
        reg = json.loads(path.read_text())
        b31 = '416a1c50d048b4f21b9defa023e11df701e7bcd3a81cecaeb2c9518245a384c2'
        active = active_registration_records(path, b31)
        self.assertEqual(reg['target_candidate_sha256'], b31)
        self.assertEqual(len(active), 69)
        self.assertTrue(all(r['replay']['candidate_sha256'] == b31 for r in active))
        self.assertEqual(len(reg['history']['records']), 139)
        self.assertFalse({r['key'] for r in active} &
                         {r['key'] for r in reg['history']['records']})
        self.assertFalse(any(r['item_id'].startswith('26a-b30-') for r in active))
        self.assertEqual(sum(r['item_id'].startswith('26a-b30-')
                             for r in reg['history']['records']), 19)
        for r in active:
            if r['item_id'].startswith('26a-b31-'):
                self.assertEqual(r['key'].split('|', 1)[1], r['input_route'])

    def test_synthetic_defect_survives_generation_and_both_gates(self):
        from tools import audit_scene_semantics as audit
        from tools import build_scene_catalog as build
        from tools import qa_scene_screenshot_sanity as sanity
        with TemporaryDirectory(dir=ROOT/'temp') as directory:
            work = Path(directory)
            source = copy.deepcopy(json.loads((ROOT/'data/scene_entrypoints.json').read_text()))
            scene_id = '89b_common_battle_defeat_comm_messages'
            source['scenes'][scene_id] = {
                'status': 'defect', 'note': 'synthetic current candidate defect',
                'evidence': {'fixture': True}}
            entrypoints = work/'scene_entrypoints.json'
            entrypoints.write_text(json.dumps(source))
            catalog = work/'scene_catalog.json'
            with patch.object(build, 'ENTRYPOINTS', entrypoints), \
                 patch.object(build, 'OUT', catalog), patch('builtins.print'):
                build.main()
            generated = json.loads(catalog.read_text())
            scene = next(s for s in generated['scenes'] if s['id'] == scene_id)
            self.assertEqual(scene['screenshot']['status'], 'defect')
            self.assertEqual(scene['evidence'], {'fixture': True})

            with patch.object(audit, 'CAT', catalog), \
                 patch.object(audit, 'OUT_DIR', work/'audit'), \
                 patch('sys.argv', ['audit_scene_semantics.py', '--strict']), \
                 patch('builtins.print'):
                with self.assertRaises(SystemExit) as status:
                    audit.main()
                self.assertEqual(status.exception.code, 1)
            audit_issues = json.loads((work/'audit/report.json').read_text())['issues']
            self.assertEqual(sum(x.get('issue') == 'BLOCKED' for x in audit_issues), 15)
            self.assertEqual([x['scene'] for x in audit_issues if x['issue'] == 'DEFECT'], [scene_id])

            with patch('sys.argv', ['qa_scene_screenshot_sanity.py', '--rom', ROM,
                                    '--catalog', str(catalog), '--out', str(work/'qa')]), \
                 patch('builtins.print'):
                self.assertEqual(sanity.main(), 1)
            sanity_issues = json.loads((work/'qa/report.json').read_text())['issues']
            self.assertEqual(sum(x.get('issue') == 'BLOCKED' for x in sanity_issues), 15)
            self.assertEqual([x['scene_id'] for x in sanity_issues if x['issue'] == 'DEFECT'],
                             [scene_id])

    def test_89b_mismatched_receipt_rom_sha_is_rejected(self):
        from tools import audit_scene_semantics as audit
        with TemporaryDirectory(dir=ROOT/'temp') as directory:
            work = Path(directory)
            receipt_path = ROOT/audit.RUNTIME_WATCH_REQUIREMENTS[
                '89b_common_battle_defeat_comm_messages']['receipt']
            receipt = json.loads(receipt_path.read_text())
            receipt['rom_sha256'] = '0' * 64
            changed = work/'wrong_89b_receipt.json'
            changed.write_text(json.dumps(receipt))
            requirement = dict(audit.RUNTIME_WATCH_REQUIREMENTS[
                '89b_common_battle_defeat_comm_messages'])
            requirement['receipt'] = str(changed)
            requirements = dict(audit.RUNTIME_WATCH_REQUIREMENTS)
            requirements['89b_common_battle_defeat_comm_messages'] = requirement
            with patch.object(audit, 'RUNTIME_WATCH_REQUIREMENTS', requirements), \
                 patch.object(audit, 'OUT_DIR', work/'audit'), \
                 patch('sys.argv', ['audit_scene_semantics.py', '--strict']), \
                 patch('builtins.print'):
                with self.assertRaises(SystemExit) as exit_status:
                    audit.main()
                self.assertEqual(exit_status.exception.code, 1)
            issues = json.loads((work/'audit/report.json').read_text())['issues']
            self.assertTrue(any(x.get('scene')=='89b_common_battle_defeat_comm_messages'
                                and x.get('issue')=='89b current candidate trace provenance 없음'
                                for x in issues))
