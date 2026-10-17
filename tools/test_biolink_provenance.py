"""Clean link receipts must not silently accept state or command injection."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scene_routes.verify4_link import biolink, bios_nav
from scene_routes.verify5_link import battle_probe, error_probe, step


class FakeProcess:
    def __init__(self):
        self.stdin = io.StringIO()
        self.stdout = io.StringIO('OK command\n' * 8)


class LinkProvenanceTest(unittest.TestCase):
    def test_verify5_battle_routes_load_clean_b39_transfer_states(self):
        class RecordingLink:
            commands = []

            def __init__(self, out):
                self.commands = []
                RecordingLink.commands.append(self.commands)

            def cmd(self, line):
                self.commands.append(line)

            def capture(self, *args, **kwargs):
                pass

            def press(self, *args, **kwargs):
                pass

        with tempfile.TemporaryDirectory(dir=biolink.ROOT / 'temp') as raw:
            fixture_root = Path(raw)
            for part in (1, 2):
                source = fixture_root / f'temp/release_C/canon8/link/part{part}/transfer'
                source.mkdir(parents=True)
                states = [source / name for name in ('host_end.ss0', 'client_end.ss0')]
                for state in states:
                    state.write_bytes(f'b39 part {part} {state.name}'.encode())
                receipt = source / 'receipt.json'
                receipt.write_text(json.dumps({
                    'rom_sha256': battle_probe.b.ROM_SHA, 'emulator_exit_code': 0,
                    'cheat_tainted': False,
                    'saved_states': [{'path': str(state.relative_to(fixture_root))}
                                     for state in states]}))
                for state in states:
                    state.with_name(state.name + '.provenance.json').write_text(json.dumps({
                        'rom_sha256': battle_probe.b.ROM_SHA,
                        'bios_sha256': biolink.BIOS_SHA,
                        'state_sha256': biolink.sha(state), 'cheat_tainted': False,
                        'producer_receipt': str(receipt.relative_to(fixture_root))}))
            with patch.object(battle_probe, 'ROOT', fixture_root), patch.object(
                    battle_probe.b, 'Link', RecordingLink), patch.object(
                    battle_probe.b, 'finish_checked'):
                for part in (1, 2):
                    battle_probe.run(part, Path('temp/unused'))
            for part in (1, 2):
                with self.subTest(part=part):
                    source = fixture_root / f'temp/release_C/canon8/link/part{part}/transfer'
                    expected = [f'loadstate 0 {source / "host_end.ss0"}',
                                f'loadstate 1 {source / "client_end.ss0"}']
                    actual = [line for line in RecordingLink.commands[part - 1]
                              if line.startswith('loadstate ')]
                    self.assertEqual(actual, expected)
                    link = self.make_link(fixture_root, battle_probe.b)
                    with patch.object(battle_probe.b, 'ROOT', fixture_root):
                        for line in actual:
                            link.cmd(line)
                    self.assertFalse(link.cheat_tainted)
                    self.assertEqual(len(link.state_loads), 2)
                    self.assertTrue(all(not load['cheat_tainted']
                                        for load in link.state_loads))

    def test_host_save_cannot_bypass_provenance(self):
        with self.assertRaises(TypeError):
            biolink.Link(Path('temp/unused'), host_save='untracked.sav')

    def make_link(self, folder, driver=biolink):
        link = driver.Link.__new__(driver.Link)
        link.proc = FakeProcess()
        link.out = folder
        link.transcript = []
        link.cheat_tainted = False
        link.state_loads = []
        link.saved_states = []
        return link

    def test_missing_and_foreign_rom_state_are_rejected_before_load(self):
        with tempfile.TemporaryDirectory(dir=biolink.ROOT / 'temp') as raw:
            folder = Path(raw)
            state = folder / 'state.ss0'
            state.write_bytes(b'state')
            link = self.make_link(folder)
            with self.assertRaisesRegex(ValueError, 'provenance missing'):
                link.cmd(f'loadstate 0 {state}')
            self.assertEqual(link.proc.stdin.getvalue(), '')
            self.assertEqual(link.state_loads, [])
            state.with_name(state.name + '.provenance.json').write_text(json.dumps({
                'rom_sha256': 'wrong', 'state_sha256': biolink.sha(state), 'cheat_tainted': False}))
            link = self.make_link(folder)
            with self.assertRaisesRegex(ValueError, 'provenance mismatch'):
                link.cmd(f'loadstate 0 {state}')
            self.assertEqual(link.proc.stdin.getvalue(), '')
            self.assertEqual(link.state_loads, [])

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
            self.assertEqual(link.state_loads[0]['cheat_tainted'], False)
            self.assertIn('loadstate 0', link.proc.stdin.getvalue())

    def test_matching_rom_inherits_taint(self):
        with tempfile.TemporaryDirectory(dir=biolink.ROOT / 'temp') as raw:
            folder = Path(raw)
            state = folder / 'state.ss0'
            state.write_bytes(b'tainted state')
            state.with_name(state.name + '.provenance.json').write_text(json.dumps({
                'rom_sha256': biolink.ROM_SHA, 'state_sha256': biolink.sha(state),
                'cheat_tainted': True}))
            link = self.make_link(folder)
            link.cmd(f'loadstate 0 {state}')
            self.assertTrue(link.cheat_tainted)
            self.assertTrue(link.state_loads[0]['cheat_tainted'])

    def test_verify5_drivers_propagate_finish_status_and_preserve_route_error(self):
        class FakeLink:
            fail_status = False

            def __init__(self, out):
                pass

            def cmd(self, line):
                if self.fail_status and line == 'status':
                    raise ValueError('route failed')

            def capture(self, *args, **kwargs):
                pass

            def press(self, *args, **kwargs):
                pass

            def finish(self, extra):
                return 7

        for module, args in ((step, (Path('temp/unused'), [])),
                             (battle_probe, (1, Path('temp/unused'))),
                             (error_probe, (1, Path('temp/unused')))):
            with self.subTest(module=module.__name__), patch.object(module.b, 'Link', FakeLink):
                with self.assertRaisesRegex(RuntimeError, 'emulator exited with status 7'):
                    module.run(*args)
        FakeLink.fail_status = True
        with patch.object(step.b, 'Link', FakeLink):
            with self.assertRaisesRegex(ValueError, 'route failed'):
                step.run(Path('temp/unused'), [])

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
