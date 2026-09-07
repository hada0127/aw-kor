#!/usr/bin/env python3
"""Check relocated sprite ownership and the editor/build round trip."""
import json
import tempfile
import unittest
from pathlib import Path

import build_korean_full as build
import build_title_hangul as title
from export_sprites import tiles_to_indices
from lz77_compress import lz77_compress
from lz77_scan import lz77_decompress
from sprite_editor import server as editor
from sprite_relocations import RELOCATIONS, resolve_sprite_offset, write_relocated_sprite

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 0xC1A81C
SPEC = RELOCATIONS[SOURCE]


class RelocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        cls.tiles = title.part1_logo_layer_to_tiles(title.make_part1_submenu_label_block('기록', 18))
        cls.compressed = lz77_compress(cls.tiles, vram_safe=True)

    def test_build_and_editor_follow_the_same_pointer(self):
        rom = bytearray(self.original)
        self.assertEqual(resolve_sprite_offset(rom, SOURCE), SOURCE)
        write_relocated_sprite(rom, SOURCE, self.compressed)
        self.assertEqual(resolve_sprite_offset(rom, SOURCE), SPEC['destination'])
        self.assertEqual(lz77_decompress(rom, SPEC['destination'])[0], self.tiles)
        self.assertEqual(rom[SOURCE:SOURCE + 448], self.original[SOURCE:SOURCE + 448])
        for begin, end in ((0, SPEC['destination']),
                           (SPEC['destination'] + SPEC['capacity'], SPEC['pointer']),
                           (SPEC['pointer'] + 4, len(rom))):
            self.assertEqual(rom[begin:end], self.original[begin:end])
        sprite = {'offset_int': SOURCE, 'type': 'lz77', 'tile_cols': 10}
        grid, width, height, _ = editor.decode_from_rom(rom, sprite)
        self.assertEqual(editor.encode_indices(grid, width, height), self.tiles)

    def test_reject_occupied_storage_without_writing(self):
        rom = bytearray(self.original)
        rom[SPEC['destination']] = 0
        expected = bytes(rom)
        with self.assertRaisesRegex(ValueError, 'unused FF'):
            write_relocated_sprite(rom, SOURCE, self.compressed)
        self.assertEqual(bytes(rom), expected)

    def test_reject_unexpected_reference_or_size(self):
        rom = bytearray(self.original)
        rom[0xAFF000 - 4:0xAFF000] = (SOURCE + 0x08000000).to_bytes(4, 'little')
        expected = bytes(rom)
        with self.assertRaisesRegex(ValueError, 'reference set'):
            write_relocated_sprite(rom, SOURCE, self.compressed)
        self.assertEqual(bytes(rom), expected)
        with self.assertRaisesRegex(ValueError, 'payload'):
            write_relocated_sprite(bytearray(self.original), SOURCE, lz77_compress(bytes(32), vram_safe=True))

    def test_editor_override_writes_destination(self):
        rom = bytearray(self.original)
        write_relocated_sprite(rom, SOURCE, self.compressed)
        grid, _, _ = tiles_to_indices(self.tiles, 10)
        grid[0][0] = 1
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp', prefix='sprite-test-') as directory:
            root = Path(directory)
            override = root / 'overrides.json'
            override.write_text(json.dumps({'lz77_00C1A81C': {'indices': grid}}))
            result = build.apply_sprite_overrides(rom, ov_path=str(override), report_path=str(root / 'report.json'))
        self.assertEqual(result['applied'], 1)
        self.assertEqual(result['skipped'], 0)
        self.assertEqual(lz77_decompress(rom, SPEC['destination'])[0], editor.encode_indices(grid, 80, 32))
        self.assertEqual(rom[SOURCE:SOURCE + 448], self.original[SOURCE:SOURCE + 448])


if __name__ == '__main__':
    unittest.main()
