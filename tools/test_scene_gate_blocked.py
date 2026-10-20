"""Current candidate scene gates must distinguish unresolved evidence from capture passes."""
import copy
from collections import Counter
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ROM = 'output/game_wars_korean_full.gba'
sys.path.insert(0, str(ROOT/'tools'))


class SceneGateBlockedTest(unittest.TestCase):
    def test_native_part2_titles_keep_game_scene_membership_and_pair_protection(self):
        from tools import build_scene_catalog as build
        groups = json.loads((ROOT/'data/dialogue_groups.json').read_text())['groups']
        native = {
            group['group_id']: int(group['members'][0]['address'], 16)
            for group in groups
            if int(group['members'][0]['address'], 16) in build.NATIVE_TITLE_SOURCES
        }
        self.assertEqual(len(native), 179)
        self.assertEqual(set(native.values()), build.NATIVE_TITLE_SOURCES)
        guards = build._load_build_guards()
        for group in groups:
            if group['group_id'] in native:
                self.assertEqual(build._member_build_status(group['members'][0], guards), 'pair')

        catalog = json.loads((ROOT/'data/scene_catalog.json').read_text())
        placements = {
            group_id: scene['id']
            for scene in catalog['scenes']
            for group_id in scene['dialogue_ids']
            if group_id in native
        }
        self.assertEqual(len(placements), len(native))
        self.assertEqual(placements, {
            group_id: ('23_part2_main_menu' if address < 0xA2D000
                       else '24_part2_campaign_map')
            for group_id, address in native.items()
        })

    def test_catalog_regeneration_preserves_current_evidence(self):
        from tools import build_scene_catalog as build
        source = json.loads((ROOT/'data/scene_entrypoints.json').read_text())['scenes']
        with TemporaryDirectory(dir=ROOT/'temp') as directory:
            generated_path = Path(directory)/'scene_catalog.json'
            with patch.object(build, 'OUT', generated_path), patch('builtins.print'):
                build.main()
            generated = json.loads(generated_path.read_text())
        registered = json.loads((ROOT/'data/scene_catalog.json').read_text())
        self.assertEqual(generated, registered)
        early = source['30a1_part2_redstar_story_early']
        current = next(cp for cp in json.loads((ROOT/'data/screen_checkpoints.json').read_text())['checkpoints']
                       if cp['name'] == early['checkpoint'])
        self.assertEqual(early['source_endpoint'], early['provenance_path'])
        self.assertEqual(current['recorder_endpoint']['checkpoint'], early['source_endpoint'])
        self.assertTrue(early['source_endpoint'].startswith('temp/release_C/canon10/runs/'))
        withdrawn = {'scene_30a1_part2_redstar_story_early_b', 'scene_80a_campaign_story_early'}
        for row in source.values():
            self.assertFalse(withdrawn & {x.get('checkpoint') if isinstance(x, dict) else x
                                            for x in row.get('extra_screenshots', [])})

    def test_current_candidate_reports_clean_scene_gates(self):
        source = json.loads((ROOT/'data/scene_entrypoints.json').read_text())['scenes']
        expected = {sid: row['status'].upper() for sid, row in source.items()
                    if row.get('status') in {'blocked', 'defect'}}
        commands = [
            (['python3', 'tools/audit_scene_semantics.py', '--strict', '--rom', ROM],
             ROOT/'temp/scene_semantic_audit/report.json'),
            (['python3', 'tools/qa_scene_screenshot_sanity.py', '--rom', ROM],
             ROOT/'temp/scene_screenshots_sanity/report.json'),
        ]
        measured = [Counter(), Counter()]
        for (command, report_path), expected_counts in zip(commands, measured):
            with self.subTest(command=command[1]):
                result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                report = json.loads(report_path.read_text())
                issues = report['issues']
                self.assertEqual(Counter(x['issue'] for x in issues), expected_counts)
                self.assertEqual({x.get('scene', x.get('scene_id')): x['issue'] for x in issues
                                  if x['issue'] == 'BLOCKED'}, expected)

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

    def test_active_registration_is_bound_to_b43_and_excludes_history(self):
        from tools.audit_scene_semantics import active_registration_records
        path = ROOT/'data/release_C_evidence_registration.json'
        reg = json.loads(path.read_text())
        b43 = '488094f77a823648907c48e1647d2f53f356c5d70dfd39a8d1c3b4419aa03e34'
        active = active_registration_records(path, b43)
        self.assertEqual(reg['target_candidate_sha256'], b43)
        self.assertEqual(reg['current_candidate_sha256'], b43)
        self.assertEqual(len(active), 34)
        self.assertTrue(all(r['replay']['candidate_sha256'] == b43 for r in active))
        self.assertEqual(len(reg['history']['records']), 446)
        self.assertFalse({r['key'] for r in active} &
                         {r['key'] for r in reg['history']['records']})
        self.assertEqual(sum(r['item_id'].startswith('26a-b30-') for r in active), 19)
        self.assertEqual(sum(r['item_id'].startswith('26a-b30-')
                             for r in reg['history']['records']), 152)
        self.assertFalse(any(r['item_id'].startswith('26a-b31-') for r in active))
        for r in active:
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
                 patch('sys.argv', ['audit_scene_semantics.py', '--strict', '--rom', ROM]), \
                 patch('builtins.print'):
                with self.assertRaises(SystemExit) as status:
                    audit.main()
                self.assertEqual(status.exception.code, 1)
            audit_issues = json.loads((work/'audit/report.json').read_text())['issues']
            self.assertEqual(sum(x.get('issue') == 'BLOCKED' for x in audit_issues), 0)
            self.assertEqual([x['scene'] for x in audit_issues if x['issue'] == 'DEFECT'], [scene_id])

            with patch('sys.argv', ['qa_scene_screenshot_sanity.py', '--rom', ROM,
                                    '--catalog', str(catalog), '--out', str(work/'qa')]), \
                 patch('builtins.print'):
                self.assertEqual(sanity.main(), 1)
            sanity_issues = json.loads((work/'qa/report.json').read_text())['issues']
            self.assertEqual(sum(x.get('issue') == 'BLOCKED' for x in sanity_issues), 0)
            self.assertEqual([x['scene_id'] for x in sanity_issues if x['issue'] == 'DEFECT'],
                             [scene_id])

    def test_synthetic_blocked_survives_generation_and_both_gates(self):
        from tools import audit_scene_semantics as audit
        from tools import build_scene_catalog as build
        from tools import qa_scene_screenshot_sanity as sanity
        with TemporaryDirectory(dir=ROOT/'temp') as directory:
            work = Path(directory)
            source = copy.deepcopy(json.loads((ROOT/'data/scene_entrypoints.json').read_text()))
            scene_id = '89b_common_battle_defeat_comm_messages'
            source['scenes'][scene_id] = {
                'status': 'blocked', 'note': 'synthetic missing current candidate capture',
                'diagnostic_probe': {'fixture': True}}
            entrypoints = work/'scene_entrypoints.json'
            entrypoints.write_text(json.dumps(source))
            catalog = work/'scene_catalog.json'
            with patch.object(build, 'ENTRYPOINTS', entrypoints), \
                 patch.object(build, 'OUT', catalog), patch('builtins.print'):
                build.main()
            scene = next(s for s in json.loads(catalog.read_text())['scenes'] if s['id'] == scene_id)
            self.assertEqual(scene['screenshot'], {'status': 'blocked', 'note': source['scenes'][scene_id]['note']})
            self.assertEqual(scene['diagnostic_probe'], {'fixture': True})

            with patch.object(audit, 'CAT', catalog), \
                 patch.object(audit, 'OUT_DIR', work/'audit'), \
                 patch('sys.argv', ['audit_scene_semantics.py', '--strict', '--rom', ROM]), \
                 patch('builtins.print'):
                with self.assertRaises(SystemExit) as status:
                    audit.main()
                self.assertEqual(status.exception.code, 1)
            audit_issues = json.loads((work/'audit/report.json').read_text())['issues']
            self.assertEqual([x['scene'] for x in audit_issues if x['issue'] == 'BLOCKED'], [scene_id])

            with patch('sys.argv', ['qa_scene_screenshot_sanity.py', '--rom', ROM,
                                    '--catalog', str(catalog), '--out', str(work/'qa')]), \
                 patch('builtins.print'):
                self.assertEqual(sanity.main(), 1)
            sanity_issues = json.loads((work/'qa/report.json').read_text())['issues']
            self.assertEqual([x['scene_id'] for x in sanity_issues if x['issue'] == 'BLOCKED'], [scene_id])

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
                 patch('sys.argv', ['audit_scene_semantics.py', '--strict', '--rom', ROM]), \
                 patch('builtins.print'):
                with self.assertRaises(SystemExit) as exit_status:
                    audit.main()
                self.assertEqual(exit_status.exception.code, 1)
            issues = json.loads((work/'audit/report.json').read_text())['issues']
            self.assertTrue(any(x.get('scene')=='89b_common_battle_defeat_comm_messages'
                                and x.get('issue')=='89b current candidate trace provenance 없음'
                                for x in issues))
