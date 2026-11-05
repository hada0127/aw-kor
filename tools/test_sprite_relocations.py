#!/usr/bin/env python3
"""Check relocated sprite ownership and saved override build path."""
import json
import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_korean_full as build
import build_title_hangul as title
from export_sprites import tiles_to_indices
from sprite_codec import encode_indices
from lz77_compress import lz77_compress
from lz77_scan import lz77_decompress
from sprite_relocations import RELOCATIONS, resolve_sprite_offset, resolve_sprite_allocation, write_relocated_sprite
import part1_mission_titles as missions
import part1_m19_title as m19
import part1_m20_title as m20

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

    def test_saved_override_writes_destination(self):
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
        self.assertEqual(lz77_decompress(rom, SPEC['destination'])[0], encode_indices(grid, 80, 32))
        self.assertEqual(rom[SOURCE:SOURCE + 448], self.original[SOURCE:SOURCE + 448])


class LiveRelocationOverrideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.environ.get('AW_TEST_ROM')
        if not path:
            raise unittest.SkipTest('AW_TEST_ROM must name the candidate under review')
        cls.rom = Path(path).read_bytes()
        cls.original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        cls.index = {sp['offset_int']: sp for sp in
                     json.loads((ROOT / 'data/sprites_index.json').read_text())['sprites']
                     if sp.get('type') == 'lz77'}

    def test_builder_applies_to_live_allocations_and_preserves_retired_slots(self):
        sources = [next(source for source in missions.relocations() if source in self.index),
                   0xC15A68, 0xC15C5C, 0x5B7CB0]
        for source in sources:
            with self.subTest(source=hex(source)):
                sp = self.index[source]
                live, capacity = resolve_sprite_allocation(self.rom, source, sp['comp_size'])
                self.assertNotEqual(live, source)
                decoded = lz77_decompress(self.rom, live)
                self.assertIsNotNone(decoded)
                self.assertLessEqual(decoded[1], capacity)
                grid, width, height = tiles_to_indices(decoded[0], sp['tile_cols'])
                self.assertEqual((width, height), (sp['width'], sp['height']))
                edited = [row[:] for row in grid]
                edited[0][0] = 1 if edited[0][0] == 0 else 0
                with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as directory:
                    override = Path(directory) / 'overrides.json'
                    report = Path(directory) / 'report.json'
                    override.write_text(json.dumps({sp['id']: {'indices': edited,
                        'width': width, 'height': height, 'type': 'lz77'}}))
                    result_rom = bytearray(self.rom)
                    result = build.apply_sprite_overrides(result_rom, objl_specs=[],
                        ov_path=str(override), report_path=str(report))
                    self.assertEqual((result['applied'], result['skipped']), (1, 0), report.read_text())
                    self.assertEqual(result_rom[source:source + sp['comp_size']],
                                     self.rom[source:source + sp['comp_size']])
                    self.assertNotEqual(result_rom[live:live + capacity], self.rom[live:live + capacity])
                    self.assertEqual(lz77_decompress(result_rom, live)[0], encode_indices(edited, width, height))
                    build.verify_sprite_override_final_bytes(result_rom, result)
                    if source in missions.relocations():
                        missions.capture(result_rom, self.original)
                    if source in (m19.SOURCE, m20.SOURCE):
                        (m19 if source == m19.SOURCE else m20).capture(result_rom, self.original)

    def test_oversize_stream_rejected_without_rom_mutation(self):
        source = next(source for source in missions.relocations() if source in self.index)
        sp = self.index[source]
        live, capacity = resolve_sprite_allocation(self.rom, source, sp['comp_size'])
        decoded = lz77_decompress(self.rom, live)
        self.assertIsNotNone(decoded)
        _, width, height = tiles_to_indices(decoded[0], sp['tile_cols'])
        rng = random.Random(41)
        noisy = [[rng.randrange(16) for _ in range(width)] for _ in range(height)]
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as directory:
            override = Path(directory) / 'overrides.json'
            report = Path(directory) / 'report.json'
            override.write_text(json.dumps({sp['id']: {'indices': noisy, 'type': 'lz77'}}))
            result_rom = bytearray(self.rom)
            result = build.apply_sprite_overrides(result_rom, objl_specs=[],
                ov_path=str(override), report_path=str(report))
            self.assertEqual((result['applied'], result['skipped']), (0, 1))
            self.assertIn('comp_size', json.loads(report.read_text())['records'][0]['reason'])
            self.assertEqual(result_rom, self.rom)

    def test_live_stream_past_allocation_rejected_without_rom_mutation(self):
        source = next(source for source in missions.relocations() if source in self.index)
        sp = self.index[source]
        _, capacity = resolve_sprite_allocation(self.rom, source, sp['comp_size'])
        decoded = lz77_decompress(self.rom, resolve_sprite_offset(self.rom, source))
        grid, _, _ = tiles_to_indices(decoded[0], sp['tile_cols'])
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as directory:
            override = Path(directory) / 'overrides.json'
            report = Path(directory) / 'report.json'
            override.write_text(json.dumps({sp['id']: {'indices': grid, 'type': 'lz77'}}))
            result_rom = bytearray(self.rom)
            with patch('lz77_scan.lz77_decompress', return_value=(bytes(sp['size']), capacity + 1)):
                result = build.apply_sprite_overrides(result_rom, objl_specs=[],
                    ov_path=str(override), report_path=str(report))
            self.assertEqual((result['applied'], result['skipped']), (0, 1))
            self.assertEqual(result_rom, self.rom)


if __name__ == '__main__':
    unittest.main()
