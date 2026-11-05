import unittest
import hashlib
import json
import struct
from pathlib import Path
from unittest.mock import patch

import part1_m20_title as m
from lz77_scan import lz77_decompress


class TitleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (Path(__file__).resolve().parent.parent /
                        'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_bounded_patch_and_native_tile_geometry(self):
        rom = bytearray(self.original)
        m.patch(rom, self.original)
        self.assertEqual(rom[m.SOURCE:m.FOLLOWING], self.original[m.SOURCE:m.FOLLOWING])
        self.assertEqual(struct.unpack_from('<I', rom, m.POINTER)[0], m.RELOCATION + 0x08000000)
        raw, size = lz77_decompress(rom, m.RELOCATION)
        self.assertLessEqual(size, m.RELOCATION_LIMIT - m.RELOCATION)
        self.assertEqual(raw, m.render())
        colors, ink = set(), []
        for y in range(32):
            for x in range(128):
                # Each source 1024B forms a separate native 64x32 sprite.
                off = (x // 64) * 1024 + (y // 8) * 256 + ((x % 64) // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
                color = (raw[off] >> (4 * (x % 2))) & 15
                colors.add(color)
                if color in (10, 11):
                    ink.append((x, y))
        self.assertEqual(colors, {0, 10, 11, 13, 15})
        self.assertEqual((min(x for x, _ in ink), max(x for x, _ in ink)), (43, 84))
        self.assertTrue(any(x < 64 for x, _ in ink) and any(x >= 64 for x, _ in ink))

    def test_source_and_live_pointer_corruption_rejected(self):
        for address in (m.SOURCE + 1, m.SOURCE + 5, m.POINTER, m.POINTER + 4):
            original = bytearray(self.original)
            original[address] ^= 1
            with self.assertRaises((AssertionError, ValueError)):
                m.source_guard(original)
        for address in (m.POINTER, m.SOURCE + 10, m.SOURCE + m.CAPACITY):
            rom = bytearray(self.original)
            rom[address] ^= 1
            with self.assertRaises(AssertionError):
                m.patch(rom, self.original)

    def test_overflow_does_not_modify_rom(self):
        rom = bytearray(self.original)
        with patch.object(m, 'lz77_compress_optimal', return_value=bytes(m.RELOCATION_LIMIT - m.RELOCATION + 1)):
            with self.assertRaises(AssertionError):
                m.patch(rom, self.original)
        self.assertEqual(rom, self.original)

    def test_render_keeps_large_hada_geometry(self):
        m.render.cache_clear()
        witness = json.loads((Path(__file__).resolve().parents[1] /
                              'data/graphic_hangul_shape_witnesses.json').read_text())[
                                  'm19_m20'][f'0x{m.SOURCE:06X}']
        ink = bytes(value for point in sorted(m._ink(m.MAX_SIZE)) for value in point)
        self.assertEqual(hashlib.sha256(ink).hexdigest(), witness['ink'])
        raw = m.render()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), witness['sheet'])
        damaged = bytearray(raw)
        damaged[next(i for i, value in enumerate(damaged) if value)] ^= 1
        self.assertNotEqual(hashlib.sha256(damaged).hexdigest(), witness['sheet'])
        m.render.cache_clear()

    def test_final_snapshot_and_padding_guard(self):
        rom = bytearray(self.original)
        m.patch(rom, self.original)
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)
        for address in (m.RELOCATION + 10, m.SOURCE + m.CAPACITY, m.POINTER):
            changed = bytearray(rom)
            changed[address] ^= 1
            with self.assertRaises(AssertionError):
                m.verify(changed, regions)
        rom[m.SOURCE + m.CAPACITY] ^= 1
        with self.assertRaises(AssertionError):
            m.capture(rom, self.original)

    def test_independent_vram_safe_stream_and_duplicate_reference(self):
        raw = m.render()
        compressed = m.lz77_compress_optimal(raw, vram_safe=True)
        self.assertEqual(int.from_bytes(compressed[1:4], 'little'), len(raw))
        decoded, cursor = bytearray(), 4
        while len(decoded) < len(raw):
            flags = compressed[cursor]
            cursor += 1
            for bit in range(7, -1, -1):
                if len(decoded) >= len(raw):
                    break
                if flags & (1 << bit):
                    a, b = compressed[cursor:cursor + 2]
                    cursor += 2
                    distance, count = ((a & 15) << 8 | b) + 1, (a >> 4) + 3
                    self.assertGreaterEqual(distance, 2)
                    self.assertLessEqual(distance, len(decoded))
                    for _ in range(count):
                        decoded.append(decoded[-distance])
                else:
                    decoded.append(compressed[cursor])
                    cursor += 1
        self.assertEqual(decoded, raw)
        original = bytearray(self.original)
        original[0:4] = (m.SOURCE + 0x08000000).to_bytes(4, 'little')
        with self.assertRaises(AssertionError):
            m.source_guard(original)

    def test_editor_geometry_and_unsafe_editor_stream(self):
        from sprite_editor import server
        layout = server.part1_tiled_layer_layout({'id': 'lz77_00C15C5C', 'tile_cols': 32}, m.SOURCE)
        self.assertEqual((layout['w'], layout['h'], layout['obj1d']), (128, 32, 1))
        self.assertEqual([(c['x'], c['y'], c['tw'], c['th'], c['tile_off']) for c in layout['cells']],
                         [(0, 0, 8, 4, 0), (64, 0, 8, 4, 32)])
        self.assertTrue(all(c['bank'] == 6 and c['palbase'] == 256 for c in layout['cells']))
        with patch.object(server, 'load_layouts', return_value={'layouts': {
                'lz77_00C15C5C': {'pal_file': 'wrong.pal', 'cells': [
                    {'tw': 8, 'th': 4, 'bank': 2, 'palbase': 0}]}}}):
            hinted = server.part1_tiled_layer_layout({'id': 'lz77_00C15C5C'}, m.SOURCE)
        self.assertTrue(all(c['bank'] == 6 and c['palbase'] == 256 for c in hinted['cells']))
        self.assertNotEqual(hinted['pal_file'], 'wrong.pal')
        rom = bytearray(self.original)
        m.patch(rom, self.original)
        self.assertTrue(m.generated_matches(rom))
        unsafe = m.lz77_compress_optimal(m.render(), vram_safe=False)
        self.assertLessEqual(len(unsafe), m.RELOCATION_LIMIT - m.RELOCATION)
        self.assertEqual(lz77_decompress(unsafe, 0)[0], m.render())
        rom[m.RELOCATION:m.RELOCATION + len(unsafe)] = unsafe
        with self.assertRaisesRegex(AssertionError, 'unsafe VRAM'):
            m.capture(rom, self.original)


if __name__ == '__main__':
    unittest.main()
