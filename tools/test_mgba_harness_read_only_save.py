"""Integration check for the diagnostic harness's read-only save option."""
import hashlib
import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReadOnlySaveTest(unittest.TestCase):
    def test_probe_does_not_write_back_to_source_save(self):
        rom = ROOT / 'temp/release_C/OJ1_soundroom/baseline.gba'
        seed = ROOT / 'temp/release_C/OJ1_soundroom/loaded_game.sav'
        pre_save_state = ROOT / 'temp/release_C/OJ1_soundroom/0033_B_0005938.ss0'
        if not rom.exists() or not seed.exists() or not pre_save_state.exists():
            self.skipTest('release C ROM/save/state unavailable')
        work = ROOT / 'temp/w1_harness_read_only_test'
        work.mkdir(parents=True, exist_ok=True)
        binary = work / 'mgbah'
        source = work / 'seed.sav'
        shutil.copyfile(seed, source)
        subprocess.run(['gcc', '-O2', '-I/usr/include', str(ROOT/'tools/mgba_harness.c'), '-lmgba', '-o', str(binary)],
                       check=True, cwd=ROOT)
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        for name in ('before.sav','after.sav'):
            (work/name).unlink(missing_ok=True)
        commands = [f'loadstate {pre_save_state}', f'dumpsave {work}/before.sav']
        def press(key, hold):
            commands.extend([f'keys {key}',f'frames {hold}','keys 0','frames 1'])
        press(1,240)
        commands.extend(['frames 200',f'dumpsave {work}/after.sav','quit'])
        result = subprocess.run([str(binary), str(rom), str(work/'log.txt'), str(source)],
                                input='\n'.join(commands)+'\n', text=True, capture_output=True, cwd=ROOT, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('OK quit', result.stdout)
        self.assertIn('OK dumpsave', result.stdout)
        self.assertNotEqual(hashlib.sha256((work/'before.sav').read_bytes()).hexdigest(),
                            hashlib.sha256((work/'after.sav').read_bytes()).hexdigest(),
                            'in-game save did not change SRAM; route needs correction')
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
        self.assertFalse(list((ROOT/'temp').glob('mgbah_probe_save_*')))


if __name__ == '__main__':
    unittest.main()
