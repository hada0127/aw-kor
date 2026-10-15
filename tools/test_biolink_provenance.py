"""Clean link receipts must not silently accept state or command injection."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scene_routes.verify4_link import biolink, bios_nav


class FakeProcess:
    def __init__(self):
        self.stdin = io.StringIO()
        self.stdout = io.StringIO('OK command\n' * 8)


class LinkProvenanceTest(unittest.TestCase):
    def test_host_save_cannot_bypass_provenance(self):
        with self.assertRaises(TypeError):
            biolink.Link(Path('temp/unused'), host_save='untracked.sav')

    def make_link(self, folder):
        link = biolink.Link.__new__(biolink.Link)
        link.proc = FakeProcess()
        link.out = folder
        link.transcript = []
        link.cheat_tainted = False
        link.state_loads = []
        link.saved_states = []
        return link

    def test_unknown_and_mismatched_state(self):
        with tempfile.TemporaryDirectory(dir=biolink.ROOT / 'temp') as raw:
            folder = Path(raw)
            state = folder / 'state.ss0'
            state.write_bytes(b'state')
            link = self.make_link(folder)
            link.cmd(f'loadstate 0 {state}')
            self.assertTrue(link.cheat_tainted)
            self.assertTrue(link.state_loads[0]['cheat_tainted'])
            state.with_name(state.name + '.provenance.json').write_text(json.dumps({
                'rom_sha256': 'wrong', 'state_sha256': biolink.sha(state), 'cheat_tainted': False}))
            with self.assertRaisesRegex(ValueError, 'provenance mismatch'):
                self.make_link(folder).cmd(f'loadstate 0 {state}')

    def test_checked_same_rom_state_remains_clean(self):
        with tempfile.TemporaryDirectory(dir=biolink.ROOT / 'temp') as raw:
            folder = Path(raw)
            state = folder / 'state.ss0'
            state.write_bytes(b'state')
            receipt = folder / 'receipt.json'
            relative_state = str(state.relative_to(biolink.ROOT))
            receipt.write_text(json.dumps({'rom_sha256': biolink.ROM_SHA,
                                           'emulator_exit_code': 0,
                                           'cheat_tainted': False,
                                           'saved_states': [{'path': relative_state}]}))
            state.with_name(state.name + '.provenance.json').write_text(json.dumps({
                'rom_sha256': biolink.ROM_SHA, 'bios_sha256': biolink.BIOS_SHA,
                'state_sha256': biolink.sha(state), 'cheat_tainted': False,
                'producer_receipt': str(receipt.relative_to(biolink.ROOT))}))
            link = self.make_link(folder)
            link.cmd(f'loadstate 0 {state}')
            self.assertFalse(link.cheat_tainted)

    def test_mutating_command_taints(self):
        with tempfile.TemporaryDirectory(dir=biolink.ROOT / 'temp') as raw:
            for command in ('w16 0 02000000 1', 'w32 0 02000000 1',
                            'setreg 0 pc 02000000', 'loadmb payload.bin'):
                link = self.make_link(Path(raw))
                link.cmd(command)
                self.assertTrue(link.cheat_tainted, command)

    def test_nav_rejects_raw_command(self):
        class FakeLink:
            def __init__(self, out):
                self.commands = []

            def cmd(self, line):
                self.commands.append(line)

            def finish(self, extra):
                pass

        with patch.object(bios_nav, 'Link', FakeLink), patch.object(
                bios_nav.sys, 'argv', ['bios_nav.py', 'temp', 'cmd:w16_0_02000000_1']):
            with self.assertRaisesRegex(ValueError, 'raw harness commands'):
                bios_nav.main()


if __name__ == '__main__':
    unittest.main()
