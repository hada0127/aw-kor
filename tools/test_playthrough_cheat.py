"""Test-only RAM cheats are recorded per frame and taint every descendant (2026-10-07 user decision)."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import playthrough_capture as P
import game_save_evidence as G
from playthrough_cheat_status import status
from replay_campaign_qa import export_inputs, verify_run, compare_runs
from unittest.mock import patch as _patch
import os

FAKE = """#!%s
import json, os, struct, sys
rom, log = sys.argv[1], sys.argv[2]
open(log, 'w').close()
save = open(sys.argv[3], 'rb').read() if len(sys.argv) > 3 else bytes((i * 7 + 3) & 255 for i in range(32768))
frame = 0
writes = open(log + '.writes', 'a')
def reply(text):
    sys.stdout.write(text + '\\n'); sys.stdout.flush()
for line in sys.stdin:
    verb, _, arg = line.strip().partition(' ')
    if verb == 'framecounter': reply('OK framecounter %%d' %% frame)
    elif verb == 'frames': frame += int(arg); reply('OK frames ' + arg)
    elif verb == 'keys': reply('OK keys ' + arg)
    elif verb in ('w8', 'w16'):
        addr, data = arg.split()
        writes.write(json.dumps([frame, verb, addr, data]) + '\\n'); writes.flush()
        nwrites = globals().get('nwrites', 0) + 1; globals()['nwrites'] = nwrites
        if os.environ.get('FAKE_W_FAIL') == str(nwrites):
            reply('ERR w'); continue
        if os.environ.get('FAKE_W_HANG') == str(nwrites):
            import time; time.sleep(30); continue
        n = len(data) // (2 if verb == 'w8' else 4)
        reply('OK w8 %%d' %% n if verb == 'w8' else 'OK w16 %%d halfwords' %% n)
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


class CheatTests(unittest.TestCase):
    def setUp(self):
        (P.ROOT / 'temp').mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=P.ROOT / 'temp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rom = self.root / 'rom.gba'
        self.rom.write_bytes(b'\0' * 512 + b'SRAM_V113' + bytes(range(256)) * 4)
        self.harness = self.root / 'fake_harness'
        self.harness.write_text(FAKE)
        self.harness.chmod(0o755)

    def args(self, **kw):
        base = dict(out=self.root / 'run1', rom=self.rom, harness=self.harness, resume=None, game_save=None, min_free_gib=1,
                    timeout=10, png_compress_level=1, no_contact_sheets=True, game_save_source_rom_sha256=None)
        base.update(kw)
        return SimpleNamespace(**base)

    def record(self, script, **kw):
        """script: list of ('act', count) or ('cmd', 'freeze w16 02000010 6400')"""
        with patch('builtins.print'):
            recorder = P.Recorder(self.args(**kw))
            for kind, value in script:
                if kind == 'act':
                    recorder.action('NONE', value, 0)
                else:
                    recorder.cheat_command(value.split())
            result = recorder.close()
        recorder.proc.stdin.close()
        recorder.proc.stdout.close()
        self.assertEqual(result['status'], 'closed', result)
        return recorder.out, result

    def checkpoints(self, run):
        return {p.name: json.loads(p.read_text()) for p in run.glob('*.checkpoint.json')}

    def test_parse_cheat_write_limits(self):
        self.assertEqual(P.parse_cheat_write('w16', '0x0201A13C', '6400'),
                         {'op': 'w16', 'addr': '0201A13C', 'hex': '6400'})
        for args in (('w32', '02000000', '00'), ('w8', '08000000', '00'), ('w8', '02040000', '00'),
                     ('w16', '02000001', '0000'), ('w16', '02000000', '00'), ('w8', '02000000', 'zz'),
                     ('w8', '0203FFFF', '0000'), ('w8', '03000000', '00' * 65)):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    P.parse_cheat_write(*args)

    def test_normal_run_has_no_cheat_fields(self):
        run, result = self.record([('act', 3)])
        self.assertNotIn('cheat_tainted', result)
        self.assertNotIn('cheat_inherited', json.loads((run / 'baseline.json').read_text()))
        for cp in self.checkpoints(run).values():
            self.assertNotIn('cheat_tainted', cp)
        self.assertNotIn('cheat', (run / 'frames.jsonl').read_text())
        self.assertEqual(status(run / 'resume.checkpoint.json')['normal_play'], True)

    def test_freeze_and_oneshot_are_written_before_each_frame_and_ledgered(self):
        run, result = self.record([('act', 2), ('cmd', 'freeze w16 02000010 6400'), ('cmd', 'cheat w8 03000004 01'),
                                   ('act', 3), ('cmd', 'unfreeze all'), ('act', 2)])
        self.assertTrue(result['cheat_tainted'])
        rows = [json.loads(l) for l in (run / 'frames.jsonl').read_text().splitlines()]
        cheat_frames = [r['core_frame'] for r in rows if 'cheat' in r]
        self.assertEqual(cheat_frames, [4, 5, 6])
        self.assertEqual(len(rows[3]['cheat']), 2)          # one-shot + freeze on the first frame
        self.assertEqual(rows[4]['cheat'], [{'op': 'w16', 'addr': '02000010', 'hex': '6400'}])
        writes = [json.loads(l) for l in Path(str(run / 'emulator.log') + '.writes').read_text().splitlines()]
        self.assertEqual([w[0] for w in writes], [3, 3, 4, 5])  # applied at the frame boundary before emulation
        cps = self.checkpoints(run)
        self.assertNotIn('cheat_tainted', cps['initial.checkpoint.json'])
        self.assertTrue(cps['resume.checkpoint.json']['cheat_tainted'])
        later = [cp for name, cp in cps.items() if cp['core_frame'] >= 4]
        self.assertTrue(all(cp.get('cheat_tainted') for cp in later))
        events = [json.loads(l) for l in (run / 'actions.jsonl').read_text().splitlines() if 'cheat_event' in l]
        self.assertEqual([e['cheat_event'] for e in events], ['freeze', 'cheat', 'unfreeze'])
        st = status(run / 'resume.checkpoint.json')
        self.assertEqual((st['cheat_tainted'], st['normal_play']), (True, False))
        with self.assertRaisesRegex(ValueError, 'cheat-tainted'):
            export_inputs(run)

    def test_stripping_taint_from_checkpoint_is_rejected(self):
        run, _ = self.record([('cmd', 'freeze w8 02000000 FF'), ('act', 2)])
        cp_path = run / 'resume.checkpoint.json'
        cp = json.loads(cp_path.read_text())
        del cp['cheat_tainted']
        cp_path.write_text(json.dumps(cp))
        with self.assertRaisesRegex(RuntimeError, 'cheat-tainted checkpoint|dispatched cheat lost its taint'):
            P.verify_parent(cp_path, cp)
        cp['cheat_tainted'] = False
        with self.assertRaisesRegex(RuntimeError, 'Malformed cheat taint'):
            P.verify_parent(cp_path, cp)

    def test_resume_inherits_taint_and_cannot_clear_it(self):
        run1, _ = self.record([('cmd', 'cheat w8 02000000 01'), ('act', 1)])
        run2, result = self.record([('act', 2)], out=self.root / 'run2', resume=run1 / 'resume.checkpoint.json')
        self.assertTrue(result['cheat_tainted'])
        self.assertTrue(json.loads((run2 / 'baseline.json').read_text())['cheat_inherited'])
        self.assertTrue(all(cp.get('cheat_tainted') for cp in self.checkpoints(run2).values()))
        self.assertNotIn('cheat', (run2 / 'frames.jsonl').read_text())
        self.assertFalse(status(run2 / 'resume.checkpoint.json')['normal_play'])
        cp_path = run2 / 'resume.checkpoint.json'
        cp = json.loads(cp_path.read_text())
        del cp['cheat_tainted']
        with self.assertRaisesRegex(RuntimeError, 'lost its taint'):
            P.verify_parent(cp_path, cp)

    def test_game_saves_from_tainted_checkpoint_carry_taint_to_new_runs(self):
        run1, _ = self.record([('act', 1), ('cmd', 'freeze w16 0201A13C 6400'), ('act', 2)])
        cp = run1 / 'resume.checkpoint.json'
        with patch('builtins.print'):
            legacy = G.export(cp, self.harness, self.root / 'legacy')
            anchored = G.export_anchored(cp, self.harness, self.root / 'anchored', reason='cheat test')
        for receipt in (legacy, anchored):
            self.assertTrue(json.loads(receipt.read_text())['cheat_tainted'])
        run3, result = self.record([('act', 1)], out=self.root / 'run3', game_save=anchored)
        self.assertTrue(result['cheat_tainted'])
        self.assertTrue(json.loads((run3 / 'baseline.json').read_text())['cheat_inherited'])
        self.assertTrue(all(c.get('cheat_tainted') for c in self.checkpoints(run3).values()))
        # Stripping the flag from a receipt whose tainted source still exists is rejected.
        for receipt in (legacy, anchored):
            record = json.loads(receipt.read_text())
            del record['cheat_tainted']
            receipt.write_text(json.dumps(record))
            with self.subTest(kind=record['kind']):
                with self.assertRaisesRegex(ValueError, 'Cheat taint dropped'):
                    G.verify_receipt(receipt, verify_frames=False, expected_rom_sha256=P.sha(self.rom),
                                     expected_harness_sha256=P.sha(self.harness),
                                     expected_libmgba_sha256=P.sha(G.LIBMGBA.resolve()))

    def test_normal_checkpoint_before_first_cheat_stays_normal(self):
        run, _ = self.record([('act', 2), ('cmd', 'freeze w8 02000000 01'), ('act', 1)])
        cps = self.checkpoints(run)
        first = [name for name, cp in cps.items() if cp['core_frame'] == 3][0]
        self.assertTrue(status(run / first)['normal_play'])

    # ---- 2026-10-07 review regressions (codex_4fe9e18) -------------------------------------
    def verify_kwargs(self):
        return dict(expected_rom_sha256=P.sha(self.rom), expected_harness_sha256=P.sha(self.harness),
                    expected_libmgba_sha256=P.sha(G.LIBMGBA.resolve()))

    def tainted_anchor(self, name='anch'):
        run1, _ = self.record([('cmd', 'cheat w8 02000000 01'), ('act', 2)], out=self.root / (name + '_src'))
        with patch('builtins.print'):
            receipt = G.export_anchored(run1 / 'resume.checkpoint.json', self.harness, self.root / name,
                                        reason='cheat test')
        return run1, receipt

    def test_anchored_receipt_without_flag_and_without_source_is_tainted(self):
        run1, receipt = self.tainted_anchor()
        record = json.loads(receipt.read_text())
        self.assertEqual((record['cheat_tainted'], record['cheat_provenance']), (True, 'full-frame-chain'))
        del record['cheat_tainted']
        receipt.write_text(json.dumps(record))
        shutil.rmtree(run1)                                   # source provenance now unavailable
        G.verify_receipt(receipt, **self.verify_kwargs())     # bytes still verify ...
        self.assertEqual(G.receipt_cheat_status(record, P.sha(receipt)),
                         {'tainted': True, 'basis': 'unverifiable'})   # ... but never as normal play
        run3, result = self.record([('act', 1)], out=self.root / 'run3', game_save=receipt)
        baseline = json.loads((run3 / 'baseline.json').read_text())
        self.assertTrue(baseline['cheat_inherited'])
        self.assertEqual(baseline['initial_game_save']['cheat_provenance'], 'unverifiable')
        self.assertTrue(result['cheat_tainted'])
        self.assertFalse(status(run3 / 'resume.checkpoint.json')['normal_play'])
        # Removing the inheritance from that run is rejected by chain verification.
        cp_path = run3 / 'resume.checkpoint.json'
        base_path = run3 / 'baseline.json'
        del baseline['cheat_inherited']
        base_path.write_text(json.dumps(baseline))
        cp = json.loads(cp_path.read_text()); cp['baseline_sha256'] = P.sha(base_path)
        with self.assertRaisesRegex(RuntimeError, 'taint dropped|lost its taint'):
            P.verify_parent(cp_path, cp)

    def test_clean_anchor_with_attested_false_and_registry_fallback(self):
        run1, _ = self.record([('act', 2)], out=self.root / 'clean_src')
        with patch('builtins.print'):
            receipt = G.export_anchored(run1 / 'resume.checkpoint.json', self.harness, self.root / 'clean',
                                        reason='clean test')
        record = json.loads(receipt.read_text())
        self.assertIs(record['cheat_tainted'], False)
        shutil.rmtree(run1)
        self.assertFalse(G.receipt_cheat_status(record, P.sha(receipt))['tainted'])
        # A legacy-style receipt (no flag, source gone) is clean only via the reviewed registry.
        del record['cheat_tainted'], record['cheat_provenance']
        receipt.write_text(json.dumps(record))
        self.assertTrue(G.receipt_cheat_status(record, P.sha(receipt))['tainted'])
        registry = self.root / 'registry.json'
        registry.write_text(json.dumps({'receipts': {P.sha(receipt): {'cheat_tainted': False, 'basis': 'test'}}}))
        with patch.object(G, 'CHEAT_REGISTRY', registry):
            self.assertEqual(G.receipt_cheat_status(record, P.sha(receipt)), {'tainted': False, 'basis': 'registry'})
        # An explicit false without exporter provenance is malformed.
        record['cheat_tainted'] = False
        with self.assertRaisesRegex(ValueError, 'without exporter provenance'):
            G.receipt_cheat_status(record, P.sha(receipt))

    def test_skip_source_frame_check_fails_closed(self):
        run1, _ = self.record([('cmd', 'cheat w8 02000000 01'), ('act', 2)], out=self.root / 'skip_src')
        cp_path = run1 / 'resume.checkpoint.json'
        cp = json.loads(cp_path.read_text())
        del cp['cheat_tainted']
        cp_path.write_text(json.dumps(cp))                      # ledger still holds the cheat rows
        with patch('builtins.print'), self.assertRaisesRegex(ValueError, 'Cheat taint dropped'):
            G.export_anchored(cp_path, self.harness, self.root / 'skip1', reason='x', verify_source_frames=False)
        # Inherited run whose checkpoint lost its flag.
        run2, _ = self.record([('cmd', 'cheat w8 02000000 01'), ('act', 1)], out=self.root / 'inh_src')
        run3, _ = self.record([('act', 1)], out=self.root / 'inh', resume=run2 / 'resume.checkpoint.json')
        cp3_path = run3 / 'resume.checkpoint.json'
        cp3 = json.loads(cp3_path.read_text()); del cp3['cheat_tainted']; cp3_path.write_text(json.dumps(cp3))
        with patch('builtins.print'), self.assertRaisesRegex(ValueError, 'Cheat-inherited source checkpoint lost'):
            G.export_anchored(cp3_path, self.harness, self.root / 'skip2', reason='x', verify_source_frames=False)
        # Clean source whose ledger is gone: provenance unverifiable -> tainted receipt.
        run4, _ = self.record([('act', 2)], out=self.root / 'noledger_src')
        (run4 / 'frames.jsonl').unlink()
        with patch('builtins.print'):
            receipt = G.export_anchored(run4 / 'resume.checkpoint.json', self.harness, self.root / 'skip3',
                                        reason='x', verify_source_frames=False)
        record = json.loads(receipt.read_text())
        self.assertEqual((record['cheat_tainted'], record['cheat_provenance']), (True, 'unverifiable-source-ledger'))

    def test_changed_rom_migration_keeps_taint(self):
        _, receipt = self.tainted_anchor('mig')
        rom2 = self.root / 'rom2.gba'
        rom2.write_bytes(b'\1' * 512 + b'SRAM_V113' + bytes(range(256)) * 4)
        run, result = self.record([('act', 1)], out=self.root / 'migrated', rom=rom2, game_save=receipt,
                                  game_save_source_rom_sha256=P.sha(self.rom))
        baseline = json.loads((run / 'baseline.json').read_text())
        self.assertIn('migration', baseline['initial_game_save'])
        self.assertTrue(baseline['cheat_inherited'])
        self.assertTrue(result['cheat_tainted'])

    def failing_run(self, env, script):
        with patch.dict(os.environ, env), patch('builtins.print'):
            recorder = P.Recorder(self.args(out=self.root / ('fail_' + '_'.join(env)), timeout=2))
            error = None
            try:
                for kind, value in script:
                    if kind == 'act':
                        recorder.action('NONE', value, 0)
                    else:
                        recorder.cheat_command(value.split())
            except BaseException as exc:
                error = exc
            result = recorder.close(error)
        self.assertIsNotNone(error)
        return recorder.out, result

    def test_failed_or_timed_out_write_records_taint_and_partial_application(self):
        script = [('act', 1), ('cmd', 'cheat w8 02000000 01'), ('cmd', 'freeze w8 02000004 02'), ('act', 1)]
        for env, ack in (({'FAKE_W_FAIL': '2'}, 1), ({'FAKE_W_HANG': '1'}, 0)):
            with self.subTest(env=env):
                run, result = self.failing_run(env, script)
                self.assertEqual(result['status'], 'failed')
                self.assertTrue(result['cheat_tainted'])
                partial = result['cheat_partial_application']
                self.assertEqual(len(partial['acknowledged']), ack)
                self.assertEqual(len(partial['uncertain']), 2 - ack)
                self.assertTrue((run / P.CHEAT_MARKER).exists())
                rows = [json.loads(l) for l in (run / 'actions.jsonl').read_text().splitlines()]
                dispatch = [r['cheat_dispatch'] for r in rows if 'cheat_dispatch' in r]
                self.assertEqual(dispatch, ['started', 'failed'])
                # No checkpoint was published at or after the dispatched frame.
                first = json.loads((run / P.CHEAT_MARKER).read_text())['first_dispatch_core_frame']
                self.assertTrue(all(json.loads(p.read_text())['core_frame'] < first
                                    for p in run.glob('*.checkpoint.json')))

    def test_exit_flag_stripping_does_not_make_a_normal_route(self):
        run, _ = self.record([('cmd', 'cheat w8 02000000 01'), ('act', 2)])
        exit_path = run / 'exit.json'
        closed = json.loads(exit_path.read_text()); del closed['cheat_tainted']
        exit_path.write_text(json.dumps(closed))
        with self.assertRaisesRegex(ValueError, 'cheat-tainted'):
            export_inputs(run)
        verified = verify_run(run)['cheat']
        self.assertTrue(verified['cheat_tainted'])
        self.assertFalse(verified['exit_flag_consistent'])

    def test_comparison_carries_cheat_classification(self):
        normal, _ = self.record([('act', 3)], out=self.root / 'cmp_normal')
        cheated, _ = self.record([('cmd', 'freeze w8 02000000 01'), ('act', 3)], out=self.root / 'cmp_cheat')
        result = compare_runs(normal, cheated)
        self.assertEqual(result['status'], 'cheat_tainted_identical_to_reference')
        self.assertEqual(result['pixel_status'], 'identical_to_reference')
        self.assertFalse(result['normal_play_evidence'])
        self.assertTrue(result['candidate_cheat']['cheat_tainted'])
        self.assertFalse(result['reference_cheat']['cheat_tainted'])
        clean = compare_runs(normal, self.record([('act', 3)], out=self.root / 'cmp_normal2')[0])
        self.assertEqual((clean['status'], clean['normal_play_evidence']), ('identical_to_reference', True))

    def test_contact_sheets_and_segment_results_are_labelled(self):
        with patch('builtins.print'):
            recorder = P.Recorder(self.args(out=self.root / 'sheets', no_contact_sheets=False))
            recorder.action('NONE', 2, 0)
            recorder.cheat_command('cheat w8 02000000 01'.split())
            recorder.action('NONE', 2, 0)
            recorder.close()
        rows = [json.loads(l) for l in (recorder.out / 'actions.jsonl').read_text().splitlines()]
        captured = [r for r in rows if r.get('status') == 'captured']
        self.assertNotIn('cheat_tainted', captured[-2])
        self.assertEqual((captured[-1]['cheat_tainted'], captured[-1]['classification']),
                         (True, 'cheat_tainted_not_normal_play'))
        from PIL import Image
        with Image.open(captured[-1]['sheet']) as sheet:
            self.assertIn((200, 0, 0), sheet.convert('RGB').getdata())
        with Image.open(captured[-2]['sheet']) as sheet:
            self.assertNotIn((200, 0, 0), sheet.convert('RGB').getdata())



if __name__ == '__main__':
    unittest.main()
