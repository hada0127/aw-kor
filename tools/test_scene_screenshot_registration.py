"""Regression checks for required recorder scene captures and provenance."""
import copy
import hashlib
import json
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
NAME = 'scene_85_ui_common'


class SceneRegistrationTest(unittest.TestCase):
    def test_b32r5_fifteen_reconciled_scenes_are_captured(self):
        expected = {
            'scene_19a2_part1_heavy_tank_advice_story',
            'scene_19b1_part1_hoip_ambush_weather_story',
            'scene_19b2_part1_hoip_landing_setup_story',
            'scene_19c1_part1_mid_campaign_radio_story',
            'scene_19c2_part1_mid_fog_map_story',
            'scene_19e7_part1_hoip_co_weather_help',
            'scene_26_part2_battle_labels',
            'scene_28_part2_result_status',
            'scene_30e3_part2_blackhole_yellowcomet_supply_briefing_story',
            'scene_30e4_part2_blackhole_yellowcomet_fortress_story',
            'scene_30g1_part2_green_earth_volcano_sortie_story',
            'scene_30g2_part2_green_earth_volcano_lava_story',
            'scene_80a_campaign_story_early',
            'scene_80b_campaign_story_mid',
            'scene_80c_campaign_story_late',
        }
        manifest = json.loads((ROOT/'temp/scene_screenshots/manifest.json').read_text())
        self.assertEqual(len(expected), 15)
        self.assertEqual(set(manifest['captured'][55:]), expected)
        self.assertEqual(manifest['skipped'], [])
        checkpoints = {x['name']: x for x in json.loads(
            (ROOT/'data/screen_checkpoints.json').read_text())['checkpoints']}
        for name in expected:
            self.assertIn(name, checkpoints)
            self.assertEqual(checkpoints[name]['grade'], 'recorded_b32r5')

    def test_legacy_save_taint_requires_pinned_receipt(self):
        from tools.capture_scene_screenshots import initial_save_valid, source_taint
        run = ROOT/'temp/release_C/H_p1_supply'
        baseline = json.loads((run/'baseline.json').read_text())
        state = json.loads((run/'0038_A_0004010.checkpoint.json').read_text())
        self.assertFalse(source_taint(state, baseline))
        self.assertTrue(initial_save_valid(run, baseline))
        missing = copy.deepcopy(baseline)
        missing['initial_game_save']['receipt_sha256'] = '0' * 64
        self.assertIsNone(source_taint(state, missing))
        self.assertFalse(initial_save_valid(run, missing))
        tainted = copy.deepcopy(state)
        tainted['cheat_tainted'] = True
        self.assertTrue(source_taint(tainted, baseline))
        inherited = copy.deepcopy(baseline)
        inherited['cheat_inherited'] = True
        self.assertTrue(source_taint(tainted, inherited))
        with self.assertRaises(ValueError):
            source_taint({'cheat_tainted': False}, inherited)
        with self.assertRaises(ValueError):
            source_taint({'cheat_tainted': 'false'}, baseline)

    def test_import_and_cache_share_ledger_core_frame_validation(self):
        from tools import capture_scene_screenshots as capture
        digest = lambda data: hashlib.sha256(data).hexdigest()
        with TemporaryDirectory(dir=ROOT/'temp') as d:
            fake_root = Path(d)
            run = fake_root/'run'
            run.mkdir()
            (fake_root/'data').mkdir()
            (fake_root/'data/game_save_cheat_provenance.json').write_text('{"receipts":{}}')
            image = Image.new('RGB', (240, 160), (10, 20, 30))
            source = run/'source.png'; image.save(source)
            baseline = run/'baseline.json'; baseline.write_text(json.dumps({'rom_sha256':'a'*64}))
            row = {'core_frame': 42, 'image': 'source.png', 'rgb_sha256': digest(image.tobytes())}
            ledger = (json.dumps(row)+'\n').encode()
            ledger_path = run/'frames.jsonl'; ledger_path.write_bytes(ledger)
            (run/'actions.jsonl').write_text('')
            state = run/'source.checkpoint.json'
            state.write_text(json.dumps({'rom_sha256':'a'*64,'baseline_sha256':capture.sha256(baseline),
                                         'ledger_bytes':len(ledger),'ledger_sha256':digest(ledger),
                                         'core_frame':42,'cheat_tainted':False}))
            endpoint = {'checkpoint':'run/source.checkpoint.json','frame':'run/source.png',
                        'frame_sha256':capture.sha256(source),'core_frame':42}
            cp = {'name':'fixture','mode':'recorder_endpoint','scene_id':'fixture_scene',
                  'cheat_tainted':False,'recorder_endpoint':endpoint}
            cached = fake_root/'cached/frame.png'
            with patch.object(capture, 'ROOT', fake_root):
                capture.import_recorder_endpoint(cp, cached, 'a'*64)
                self.assertTrue(capture.current_capture(cached,cp,'a'*64)[0])
                (fake_root/'data/game_save_cheat_provenance.json').write_text(
                    '{"receipts":{"receipt-true":{"cheat_tainted":true}}}')
                with self.assertRaises(ValueError):
                    capture.source_taint({'cheat_tainted':False},
                                         {'initial_game_save':{'receipt_sha256':'receipt-true'}})
                endpoint['core_frame'] = 43
                self.assertFalse(capture.current_capture(cached,cp,'a'*64)[0])
                endpoint['core_frame'] = 42
                ledger_path.write_bytes(b'corrupt\n')
                self.assertFalse(capture.current_capture(cached,cp,'a'*64)[0])

    def test_local_cheat_evidence_taints_missing_flag_and_rejects_false(self):
        from tools import capture_scene_screenshots as capture
        with TemporaryDirectory(dir=ROOT/'temp') as d:
            run = Path(d)
            (run/'baseline.json').write_text('{"cheat_inherited":false}')
            (run/'actions.jsonl').write_text('')
            row = {'core_frame':42,'cheat':{'op':'w8'}}
            ledger = (json.dumps(row)+'\n').encode()
            (run/'frames.jsonl').write_bytes(ledger)
            state = {'core_frame':42,'ledger_bytes':len(ledger),
                     'ledger_sha256':hashlib.sha256(ledger).hexdigest()}
            baseline = {'cheat_inherited':False}
            self.assertTrue(capture.source_taint(state,baseline,run))
            with self.assertRaisesRegex(ValueError,'contradicts'):
                capture.source_taint({**state,'cheat_tainted':False},baseline,run)
            (run/'frames.jsonl').write_text('{"core_frame":42}\n')
            clean_ledger = (run/'frames.jsonl').read_bytes()
            clean = {**state,'ledger_bytes':len(clean_ledger),
                     'ledger_sha256':hashlib.sha256(clean_ledger).hexdigest()}
            (run/'cheat_taint.json').write_text('{"first_dispatch_core_frame":42}')
            self.assertTrue(capture.source_taint(clean,baseline,run))
            (run/'cheat_taint.json').unlink()
            (run/'actions.jsonl').write_text('{"cheat_dispatch":{},"core_frame":42}\n')
            self.assertTrue(capture.source_taint(clean,baseline,run))
            with self.assertRaisesRegex(ValueError,'contradicts'):
                capture.source_taint({**clean,'cheat_tainted':False},baseline,run)

    def test_two_checkpoint_comparison_has_two_original_panels(self):
        from tools import build_comparison_sheet as comparison
        from unittest.mock import patch
        manifest = json.loads((ROOT/'data/screen_checkpoints.json').read_text())
        pair = [next(c for c in manifest['checkpoints'] if c['name']==name)
                for name in ('01_coldboot_nintendo','02_common_title')]
        self.assertTrue(all(c.get('orig_nav') for c in pair))
        with TemporaryDirectory(dir=ROOT/'temp') as d:
            work = Path(d)
            (work/'manifest.json').write_text(json.dumps({'checkpoints':pair}))
            calls=[]
            def fake_capture(rom, ck, out, harness, side, **kwargs):
                calls.append((ck['name'],side))
                folder=out/f"{ck['name']}_{side}"; folder.mkdir(parents=True,exist_ok=True)
                image=Image.new('RGB',(240,160),(20,30,40) if side=='orig' else (60,70,80))
                image.save(folder/'frame.png')
                return image
            argv=['build_comparison_sheet.py','--manifest',str(work/'manifest.json'),
                  '--compare','--out',str(work/'out')]
            with patch('sys.argv',argv), patch.object(comparison,'capture',side_effect=fake_capture):
                comparison.main()
            self.assertEqual([name for name,side in calls if side=='orig'],
                             ['01_coldboot_nintendo','02_common_title'])
            self.assertTrue(all((work/'out'/f"{c['name']}_orig"/'frame.png').exists() for c in pair))
            self.assertTrue((work/'out'/'sheet_compare.png').exists())

    def test_missing_stale_endpoint_and_taint_mutations(self):
        from tools.capture_scene_screenshots import current_capture
        work = ROOT/'temp/w1_scene_registration_test'
        work.mkdir(parents=True, exist_ok=True)
        source = ROOT/'temp/scene_screenshots'/f'{NAME}_patched'
        if not (source/'frame.png').exists():
            self.skipTest('release C scene import unavailable')
        dest = work/f'{NAME}_patched'
        dest.mkdir(exist_ok=True)
        checkpoint = next(x for x in json.loads((ROOT/'data/screen_checkpoints.json').read_text())['checkpoints']
                          if x['name'] == NAME)
        catalog = {'scenes':[{'id':'85_ui_common','capture_required':True,'screenshot':{'checkpoint':NAME}}]}
        (work/'catalog.json').write_text(json.dumps(catalog))
        def run(names, cp, provenance):
            shutil.copyfile(source/'frame.png', dest/'frame.png')
            (dest/'provenance.json').write_text(json.dumps(provenance))
            (work/'manifest.json').write_text(json.dumps({'captured':names,'skipped':[]}))
            (work/'checkpoints.json').write_text(json.dumps({'checkpoints':[cp]}))
            subprocess.run(['python3','tools/qa_scene_screenshot_sanity.py','--rom',
                            'temp/release_C/F_help_sweep/baseline.gba', '--shot-dir',str(work),
                            '--manifest',str(work/'manifest.json'),'--catalog',str(work/'catalog.json'),
                            '--checkpoints',str(work/'checkpoints.json'),'--out',str(work/'out')],
                           cwd=ROOT,capture_output=True,text=True,check=False)
            return {x['issue'] for x in json.loads((work/'out/report.json').read_text())['issues']}
        original=json.loads((source/'provenance.json').read_text())
        self.assertIn('missing_scene',run([],checkpoint,original))
        self.assertIn('duplicate_checkpoint',run([NAME,NAME],checkpoint,original))
        stale=copy.deepcopy(original);stale['rom_sha256']='0'*64
        self.assertIn('stale_provenance',run([NAME],checkpoint,stale))
        broken=copy.deepcopy(checkpoint);broken['recorder_endpoint']['frame_sha256']='0'*64
        self.assertIn('invalid_cached_capture',run([NAME],broken,original))
        lost=copy.deepcopy(original);lost['cheat_tainted']=False
        self.assertIn('invalid_cached_capture',run([NAME],checkpoint,lost))
        withdrawn=copy.deepcopy(checkpoint);withdrawn['grade']='blocked_legacy_note_only'
        self.assertFalse(current_capture(dest/'frame.png', withdrawn, original['rom_sha256'])[0])
        self.assertIn('withdrawn_checkpoint_required',run([NAME],withdrawn,original))
        (work/'catalog.json').write_text(json.dumps({'scenes':[{'id':'missing','capture_required':True,
                                                                'screenshot':{}}]}))
        subprocess.run(['python3','tools/qa_scene_screenshot_sanity.py','--rom',
                        'temp/release_C/F_help_sweep/baseline.gba','--shot-dir',str(work),
                        '--manifest',str(work/'manifest.json'),'--catalog',str(work/'catalog.json'),
                        '--checkpoints',str(work/'checkpoints.json'),'--out',str(work/'out')],
                       cwd=ROOT,capture_output=True,text=True,check=False)
        issues={x['issue'] for x in json.loads((work/'out/report.json').read_text())['issues']}
        self.assertIn('required_scene_missing_checkpoint',issues)


if __name__=='__main__':
    unittest.main()
