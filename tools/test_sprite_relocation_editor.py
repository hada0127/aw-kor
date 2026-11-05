"""Editor and builder round trips for live relocated graphic streams."""
import json
import os
import random
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build_korean_full as build
import part1_mission_titles as missions
import part1_m19_title as m19
import part1_m20_title as m20
from sprite_relocations import resolve_sprite_allocation
from sprite_editor import server as editor

ROOT = Path(__file__).resolve().parents[1]


class RelocatedSpriteEditorTests(unittest.TestCase):
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

    def test_live_decode_validate_override_and_retired_slot(self):
        sources = [next(source for source in missions.relocations()
                        if source in self.index), 0xC15A68, 0xC15C5C,
                   0x5B7CB0, 0x5B3ECC]
        for source in sources:
            with self.subTest(source=hex(source)):
                sp = self.index[source]
                live, capacity = resolve_sprite_allocation(self.rom, source, sp['comp_size'])
                self.assertNotEqual(live, source)
                self.assertGreater(capacity, 0)
                self.assertIsNotNone(editor.decode_from_rom(self.original, sp))
                decoded = editor.decode_from_rom(self.rom, sp)
                self.assertIsNotNone(decoded)
                grid, width, height, cols = decoded
                self.assertEqual((width, height), (sp['width'], sp['height']))
                edited = [row[:] for row in grid]
                if source != 0x5B3ECC:
                    edited[0][0] = 1 if edited[0][0] == 0 else 0
                self.assertEqual(editor.validate_sprite_edit(sp, edited, None,
                                 rom_snapshot=self.rom)[0], editor.encode_indices(edited, width, height))
                if source == 0x5B3ECC:
                    continue  # Power atlas uses its dictionary-binding override contract.
                with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as work:
                    override = Path(work) / 'overrides.json'
                    report = Path(work) / 'report.json'
                    override.write_text(json.dumps({sp['id']: {'indices': edited,
                        'width': width, 'height': height, 'type': 'lz77'}}))
                    result_rom = bytearray(self.rom)
                    result = build.apply_sprite_overrides(result_rom, objl_specs=[],
                        ov_path=str(override), report_path=str(report))
                    self.assertEqual((result['applied'], result['skipped']), (1, 0), report.read_text())
                    self.assertEqual(result_rom[source:source + sp['comp_size']],
                                     self.rom[source:source + sp['comp_size']])
                    self.assertNotEqual(result_rom[live:live + capacity],
                                        self.rom[live:live + capacity])
                    self.assertEqual(editor.decode_from_rom(result_rom, sp)[0], edited)
                    build.verify_sprite_override_final_bytes(result_rom, result)
                    if source in missions.relocations():
                        original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
                        missions.capture(result_rom, original)
                    if source in (m19.SOURCE, m20.SOURCE):
                        original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
                        (m19 if source == m19.SOURCE else m20).capture(result_rom, original)

    def test_mission_allocation_rejects_oversize_edit(self):
        source = next(source for source in missions.relocations() if source in self.index)
        sp = self.index[source]
        _, width, height, _ = editor.decode_from_rom(self.rom, sp)
        rng = random.Random(41)
        noisy = [[rng.randrange(16) for _ in range(width)] for _ in range(height)]
        with self.assertRaisesRegex(ValueError, '할당'):
            editor.validate_sprite_edit(sp, noisy, None, rom_snapshot=self.rom)

    def test_decode_and_builder_reject_stream_past_live_boundary(self):
        source = next(source for source in missions.relocations() if source in self.index)
        sp = self.index[source]
        _, capacity = resolve_sprite_allocation(self.rom, source, sp['comp_size'])
        decoded = editor.decode_from_rom(self.rom, sp)
        with patch.object(editor.ES, 'lz77_decompress', return_value=(bytes(sp['size']), capacity + 1)):
            self.assertIsNone(editor.decode_from_rom(self.rom, sp))
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as work:
            override = Path(work) / 'overrides.json'
            report = Path(work) / 'report.json'
            override.write_text(json.dumps({sp['id']: {'indices': decoded[0],
                'width': decoded[1], 'height': decoded[2], 'type': 'lz77'}}))
            result_rom = bytearray(self.rom)
            with patch('lz77_scan.lz77_decompress', return_value=(bytes(sp['size']), capacity + 1)):
                result = build.apply_sprite_overrides(result_rom, objl_specs=[],
                    ov_path=str(override), report_path=str(report))
            self.assertEqual((result['applied'], result['skipped']), (0, 1))
            self.assertEqual(result_rom, self.rom)


if __name__ == '__main__':
    unittest.main()
