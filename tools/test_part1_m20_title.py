import unittest
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
        self.assertEqual(rom[:m.SOURCE], self.original[:m.SOURCE])
        self.assertEqual(rom[m.SOURCE + m.CAPACITY:], self.original[m.SOURCE + m.CAPACITY:])
        raw, size = lz77_decompress(rom, m.SOURCE)
        self.assertLessEqual(size, m.CAPACITY)
        self.assertEqual(raw, m.render())
        colors, ink = set(), []
        for y in range(32):
            for x in range(128):
                # Each source 1024B forms a separate native 64x32 sprite.
                off = (x // 64) * 1024 + (y // 8) * 256 + ((x % 64) // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
                color = (raw[off] >> (4 * (x % 2))) & 15
                colors.add(color)
                if color == 10:
                    ink.append((x, y))
        self.assertEqual(colors, {0, 10, 13, 15})
        # OkDanDan ink box (2026-10-08 font rule; Galmuri7 2x was (48, 77)).
        self.assertEqual((min(x for x, _ in ink), max(x for x, _ in ink)), (50, 76))
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
        with patch.object(m, 'lz77_compress_optimal', return_value=bytes(m.CAPACITY + 1)):
            with self.assertRaises(AssertionError):
                m.patch(rom, self.original)
        self.assertEqual(rom, self.original)

    def test_forced_capacity_cannot_select_small_okdandan(self):
        m.render.cache_clear()
        with patch.object(m, 'lz77_compress_optimal', return_value=bytes(m.CAPACITY + 1)):
            with self.assertRaisesRegex(AssertionError, 'overflow'):
                m.render()
        m.render.cache_clear()

    def test_final_snapshot_and_padding_guard(self):
        rom = bytearray(self.original)
        m.patch(rom, self.original)
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)
        for address in (m.SOURCE + 10, m.SOURCE + m.CAPACITY, m.POINTER):
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
        self.assertLessEqual(len(unsafe), m.CAPACITY)
        self.assertEqual(lz77_decompress(unsafe, 0)[0], m.render())
        rom[m.SOURCE:m.SOURCE + m.CAPACITY] = unsafe + bytes(m.CAPACITY - len(unsafe))
        with self.assertRaisesRegex(AssertionError, 'unsafe VRAM'):
            m.capture(rom, self.original)


if __name__ == '__main__':
    unittest.main()
