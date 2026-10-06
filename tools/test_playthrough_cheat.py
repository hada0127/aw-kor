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
from replay_campaign_qa import export_inputs

FAKE = """#!%s
import json, struct, sys
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
        with self.assertRaisesRegex(RuntimeError, 'cheat-tainted checkpoint'):
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


if __name__ == '__main__':
    unittest.main()
