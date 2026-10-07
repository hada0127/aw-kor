#!/usr/bin/env python3
"""Focused final-ROM B-team drift gate tests."""
import json
import tempfile
import unittest
from pathlib import Path

from qa_bteam_drift import check_rom


ROOT = Path(__file__).resolve().parents[1]
CODE = json.loads((ROOT / 'data/syllable_to_code_2350.json').read_text())['가']
CODE = int(CODE, 0) if isinstance(CODE, str) else CODE
GLYPH = CODE.to_bytes(2, 'big')


class RomDriftTest(unittest.TestCase):
    def test_wrapped_and_adjacent_rows(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            folder = Path(tmp)
            rom = bytearray(256)
            rom[0x20:0x22] = b'AB'
            rom[0x23:0x25] = b'CD'
            rom[0x80:0x87] = b'AB\x72\x0a\x09CD'
            rom[0x10:0x14] = (0x08000080).to_bytes(4, 'little')
            writes = [[0x20, 2, 2, b'AB'.hex(), None, 'AB', 0, 'test'],
                      [0x23, 2, 2, b'CD'.hex(), None, 'CD', 0, 'test']]
            paths = [folder / name for name in ('rom.gba', 'map.json', 'manifest.json')]
            paths[0].write_bytes(rom)
            paths[1].write_text(json.dumps(writes))
            paths[2].write_text('[]')
            self.assertEqual(check_rom({'overrides': {'0x00000020': 'ABCD'}},
                                       *map(str, paths)), [])
            self.assertEqual(len(check_rom({'overrides': {'0x00000020': 'A BCD'}},
                                           *map(str, paths))), 1)
            manifest = [{'msg': '0x40', 'old_len': 8, 'status': 'relocated',
                         'ptr_off': '0x10', 'ptr_sites': ['0x10'],
                         'new_addr': '0x80', 'new_len': 7,
                         'line_spans': {'0x000040': [0, 7]}}]
            paths[2].write_text(json.dumps(manifest))
            self.assertEqual(check_rom({'overrides': {'0x00000040': 'AB CD'}},
                                       *map(str, paths)), [])
            self.assertEqual(check_rom({'overrides': {'0x00000040': 'ABCD'}},
                                       *map(str, paths)), [])
            self.assertEqual(len(check_rom({'overrides': {'0x00000040': 'A BCD'}},
                                           *map(str, paths))), 1)

    def test_middle_dot_ellipsis_is_not_empty(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            folder = Path(tmp)
            rom = bytearray(64)
            paths = [folder / name for name in ('rom.gba', 'map.json', 'manifest.json')]
            paths[2].write_text('[]')
            base = {'overrides': {'0x00000020': '・・・・・・'}}
            rom[0x20:0x26] = b'      '
            paths[0].write_bytes(rom)
            paths[1].write_text(json.dumps([[0x20, 6, 6, b'      '.hex(), None,
                                             '      ', 0, 'test']]))
            self.assertEqual(len(check_rom(base, *map(str, paths))), 1)
            rom[0x20:0x26] = b'......'
            paths[0].write_bytes(rom)
            paths[1].write_text(json.dumps([[0x20, 6, 6, b'......'.hex(), None,
                                             '......', 0, 'test']]))
            self.assertEqual(check_rom(base, *map(str, paths)), [])

    def test_direct_and_repointed_bytes(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as tmp:
            folder = Path(tmp)
            rom = bytearray(256)
            rom[0x20:0x22] = GLYPH
            rom[0x80:0x82] = GLYPH
            rom[0x82] = 0
            rom[0x10:0x14] = (0x08000080).to_bytes(4, 'little')
            writes = [[0x20, 2, 2, GLYPH.hex(), None, '가', 0, 'test']]
            manifest = [{'msg': '0x40', 'old_len': 8, 'status': 'relocated',
                         'ptr_off': '0x10', 'ptr_sites': ['0x10'],
                         'new_addr': '0x80', 'new_len': 3,
                         'line_spans': {'0x000040': [0, 2]}}]
            base = {'overrides': {'0x00000020': '가', '0x00000040': '가'}}
            paths = [folder / name for name in ('rom.gba', 'map.json', 'manifest.json')]
            paths[0].write_bytes(rom)
            paths[1].write_text(json.dumps(writes))
            paths[2].write_text(json.dumps(manifest))
            self.assertEqual(check_rom(base, *map(str, paths)), [])

            rom[0x20:0x22] = b'AB'
            rom[0x80:0x82] = b'CD'
            writes[0][3] = b'AB'.hex()
            paths[0].write_bytes(rom)
            paths[1].write_text(json.dumps(writes))
            issues = check_rom(base, *map(str, paths))
            self.assertEqual({x['address'] for x in issues}, set(base['overrides']))
            self.assertEqual(issues[0]['rom_text'], 'AB')
            self.assertEqual(issues[1]['rom_text'], 'CD')

            # Finding the protected word elsewhere in the message is not a pass.
            rom[0x83:0x85] = GLYPH
            manifest[0]['new_len'] = 5
            paths[0].write_bytes(rom)
            paths[2].write_text(json.dumps(manifest))
            issues = check_rom(base, *map(str, paths))
            self.assertEqual(issues[1]['rom_text'], 'CD')

            rom[0x10:0x14] = (0x08000040).to_bytes(4, 'little')
            paths[0].write_bytes(rom)
            issues = check_rom(base, *map(str, paths))
            self.assertEqual(issues[1]['cause'], 'repoint pointer mismatch')

            rom[0x10:0x14] = (0x08000080).to_bytes(4, 'little')
            rom[0x20:0x22] = GLYPH
            paths[0].write_bytes(rom)
            with self.assertRaisesRegex(ValueError, 'integrity map does not match ROM'):
                check_rom(base, *map(str, paths))

            writes[0][3] = GLYPH.hex()
            paths[1].write_text(json.dumps(writes))
            manifest[0]['ptr_sites'] = ['0x10', '0x14']
            paths[2].write_text(json.dumps(manifest))
            issues = check_rom(base, *map(str, paths))
            self.assertEqual(issues[0]['cause'], 'repoint pointer mismatch')

            manifest[0]['ptr_sites'] = ['0x10']
            paths[2].write_text(json.dumps(manifest))
            map_rom = folder / 'map_rom.gba'
            map_rom.write_bytes(rom)
            rom[0x20:0x22] = b'AB'
            paths[0].write_bytes(rom)
            with self.assertRaisesRegex(ValueError, 'overlay changed protected in-place slot'):
                check_rom(base, *map(str, paths), str(map_rom))


if __name__ == '__main__':
    unittest.main()
