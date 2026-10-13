"""CLI mutation checks on AW_TEST_ROM, never on a locally rendered stand-in.

Set AW_SPRITE_BASELINE and AW_SPRITE_BASELINE_SHA256 explicitly as well.
Each mutation gets its own create-exclusive copy below temp/.
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from lz77_compress import lz77_compress_optimal
from lz77_scan import lz77_decompress

ROOT = Path(__file__).resolve().parents[1]


class FinalSpriteMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = Path(os.environ['AW_TEST_ROM']).read_bytes()
        cls.baseline = Path(os.environ['AW_SPRITE_BASELINE'])
        cls.baseline_sha = os.environ['AW_SPRITE_BASELINE_SHA256']
        if hashlib.sha256(cls.baseline.read_bytes()).hexdigest() != cls.baseline_sha:
            raise AssertionError('explicit test baseline SHA-256 mismatch')
        (ROOT / 'temp').mkdir(exist_ok=True)

    def reject(self, name, mutate, expected_asset):
        rom = bytearray(self.rom)
        mutate(rom)
        self.assertNotEqual(rom, self.rom)
        with tempfile.TemporaryDirectory(prefix='sprite-mutation-', dir=ROOT / 'temp') as tmp:
            path = Path(tmp) / (name + '.gba')
            with path.open('xb') as stream:
                stream.write(rom)
            for shape in (False, True):
                with self.subTest(name=name, shape=shape):
                    report = Path(tmp) / ('shape.json' if shape else 'gap.json')
                    cmd = [sys.executable, str(ROOT / 'tools/qa_sprite_art_shapes.py'), str(path),
                           '--baseline', str(self.baseline), '--baseline-sha256', self.baseline_sha,
                           '--report', str(report)] + (['--shape'] if shape else [])
                    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    # A traceback or missing prerequisite is not a successful detection.
                    self.assertTrue(report.is_file(), result.stdout + result.stderr)
                    findings = json.loads(report.read_text())['failures']
                    self.assertTrue(any(expected_asset in row['asset'] for row in findings), findings)
                    print(f'{name} {"shape" if shape else "gap"}: exit {result.returncode}; '
                          f'detected {expected_asset}', flush=True)

    @staticmethod
    def change_lz_pixel(rom, off):
        raw, capacity = lz77_decompress(rom, off)
        raw = bytearray(raw)
        # Border pixel (0,0), deliberately remains a non-ink index.
        value = raw[0] & 15
        raw[0] = (raw[0] & 240) | (2 if value != 2 else 3)
        encoded = lz77_compress_optimal(bytes(raw), vram_safe=True)
        original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        capacity = lz77_decompress(original, off)[1]
        if len(encoded) > capacity:
            raise AssertionError('mutation exceeds original compressed allocation')
        rom[off:off + capacity] = encoded.ljust(capacity, b'\0')

    def test_stray_unit_label_ink(self):
        def mutate(rom):
            self.assertEqual(rom[0x466568] & 15, 0)
            rom[0x466568] |= 1
        self.reject('unit_ink', mutate, '0x466568')

    def test_large_plate_border(self):
        self.reject('large_border', lambda r: self.change_lz_pixel(r, 0x5B7930), '0x5b7930')

    def test_small_plate_border(self):
        self.reject('small_border', lambda r: self.change_lz_pixel(r, 0x5B8E44), '0x5b8e44')

    def test_link_plate_reverted_to_japanese(self):
        def mutate(rom):
            original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
            _, size = lz77_decompress(original, 0x54E538)
            rom[0x54E538:0x54E538 + size] = original[0x54E538:0x54E538 + size]
        self.reject('link_japanese', mutate, '0x54e538')

    def test_empty_co1_dictionary(self):
        def mutate(rom):
            pos = struct.unpack_from('<I', rom, 0xB3C1F8)[0] - 0x08000000
            rom[pos:pos + 2] = bytes(2)
        self.reject('empty_co1', mutate, 'CO1 dictionary population')

    def test_truncated_compact_table(self):
        # Preserve a real prefix so this also catches mid-table truncation.
        self.reject('truncated_compact',
                    lambda r: struct.pack_into('<I', r, 0xF66800 + 12 * 5 + 4, 0),
                    'compact table')

    def test_low_private_glyph_pointer(self):
        def mutate(rom):
            for pos in range(0xF40000, 0xF42000 - 11, 12):
                if struct.unpack_from('<I', rom, pos + 4)[0] >= 0x08F42000:
                    struct.pack_into('<I', rom, pos + 4, 0x08000000)
                    return
            raise AssertionError('candidate has no private glyph pointer')
        self.reject('low_private_pointer', mutate, 'private table')


class CleanOverridePrerequisiteTests(unittest.TestCase):
    def test_missing_editor_export_uses_complete_adopted_metadata(self):
        import build_korean_full as builder
        from unittest.mock import patch
        with patch.object(builder, 'DGROUPS', str(ROOT / 'temp/absent-dialogue-groups.json')):
            slots, members = builder.load_direct_script_metadata()
        self.assertEqual((len(slots), len(members)), (6889, 6889))
        for address, end in builder.SCRIPT_OPERAND_SPANS.items():
            self.assertEqual(slots[address], end - address)
            self.assertTrue(all(address <= row['address'] < end for row in members[address]))

    def test_adopted_overrides_build_without_generated_index(self):
        import build_korean_full as builder
        from unittest.mock import patch
        original = Path(builder.P.ROM).read_bytes()
        rom = bytearray(original)
        with tempfile.TemporaryDirectory(prefix='sprite-index-', dir=ROOT / 'temp') as tmp:
            with patch.object(builder, 'BASE', tmp):
                result = builder.apply_sprite_overrides(
                    rom, ov_path=str(ROOT / 'data/sprites_overrides.json'),
                    report_path=str(Path(tmp) / 'report.json'))
        self.assertEqual((result['applied'], result['skipped']), (2, 0))
        candidate = Path(os.environ['AW_TEST_ROM']).read_bytes()
        for off, size in ((0xC03880, 622), (0xC03AF0, 1144)):
            self.assertEqual(rom[off:off + size], candidate[off:off + size])



if __name__ == '__main__':
    unittest.main()
