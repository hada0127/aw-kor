"""Cross-process read/modify/write stays serialized after storage extraction."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AtomicDataTests(unittest.TestCase):
    def test_cross_process_read_modify_write_preserves_all_updates(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as directory:
            root = Path(directory)
            target = root / 'counter.json'
            (root / 'data').mkdir()
            target.write_text('{"n": 0}')
            program = """
import json, sys, time
from pathlib import Path
import atomic_data
from atomic_data import DATA_LOCK, save_json
p = Path(sys.argv[1])
atomic_data.ROOT = p.parent
for _ in range(20):
    with DATA_LOCK:
        value = json.loads(p.read_text())
        time.sleep(.002)
        value['n'] += 1
        save_json(p, value)
"""
            children = [subprocess.Popen([sys.executable, '-c', program, str(target)],
                                         cwd=ROOT / 'tools') for _ in range(3)]
            for child in children:
                self.assertEqual(child.wait(timeout=30), 0)
            self.assertEqual(json.loads(target.read_text()), {'n': 60})


if __name__ == '__main__':
    unittest.main()
