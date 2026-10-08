import struct
import unittest
from pathlib import Path
from unittest.mock import patch

import part1_mission_titles as m
import part1_m19_title as m19
import part1_m20_title as m20
from lz77_scan import lz77_decompress


class MissionTitleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (Path(__file__).resolve().parent.parent /
                        'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        cls.rom = bytearray(cls.original)
        cls.count = m.patch(cls.rom, cls.original)

    def test_table_coverage_and_skip_set(self):
        owned = {row[0] for row in m.TITLES} | {m.EXTENSION[0]}
        self.assertEqual(self.count, len(owned))
        self.assertEqual(len(owned), 35)
        table = {struct.unpack_from('<I', self.original, m.TABLE + 4 * i)[0] - 0x08000000
                 for i in range(m.TABLE_ENTRIES)}
        # Every unique sheet in the 63-entry table is either owned here or skipped.
        self.assertEqual(table, owned | m.SKIP)
        self.assertFalse(owned & m.SKIP)
        self.assertIn(m19.SOURCE, m.SKIP)
        self.assertIn(m20.SOURCE, m.SKIP)
        # Shared sheets are patched exactly once.
        sources = [row[0] for row in m.TITLES]
        self.assertEqual(len(sources), len(set(sources)))

    def test_only_owned_allocations_change(self):
        outside = bytearray(self.rom)
        for source, following, capacity, *_ in m._all_blocks():
            raw, used = lz77_decompress(self.rom, source)
            self.assertEqual(raw, m.render(source))
            self.assertLessEqual(used, capacity)
            self.assertEqual(self.rom[source + capacity:following],
                             self.original[source + capacity:following])
            outside[source:source + capacity] = self.original[source:source + capacity]
        self.assertEqual(outside, self.original)

    def test_m19_m20_modules_still_apply_after_this_module(self):
        rom = bytearray(self.rom)
        m19.patch(rom, self.original)
        m20.patch(rom, self.original)
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)

    def test_palette_and_native_cells(self):
        for source, *_ in m._all_blocks():
            raw = m.render(source)
            colors = {n for b in raw for n in (b & 15, b >> 4)}
            self.assertLessEqual(colors, {0, m.INK, m.SHADOW, m.OUTLINE})
            self.assertIn(m.INK, colors)
        # The mission-2 text continues into the 32x32 extension cell; tiles 16..31 stay blank.
        ext = m.render(m.EXTENSION[0])
        self.assertTrue(any(ext[:512]))
        self.assertFalse(any(ext[512:]))
        tiers = {row[0]: m.layout(row[5], 160 if row[0] == m.EXTENSION_OWNER else 128)[0]
                 for row in m.TITLES}
        # 2026-10-08 font rule: every title is OkDanDan (was g7x2/g11 Galmuri tiers).
        self.assertTrue(all(t.startswith('okdandan') for t in tiers.values()))
        self.assertEqual(tiers[0xC1689C], 'okdandan20')
        self.assertEqual(tiers[0xC13EE0], 'okdandan20')
        # Capacity may step a size down; at <= 16 px a title is small text and
        # falls back to the Galmuri layout (2026-10-08 decision).
        sizes = {row[0]: m.chosen_size(row[0]) for row in m.TITLES}
        self.assertTrue(all(v is None or v > 16 for v in sizes.values()))
        self.assertIsNone(sizes[0xC133DC])   # 하늘의 용사! (506-byte allocation)

    def test_texts_match_bteam_baseline(self):
        import json
        root = Path(__file__).resolve().parent.parent
        bteam = json.loads((root / 'data/bteam_baseline.json').read_text())['overrides']
        for row in m.TITLES:
            note = row[6]
            if note.startswith('bteam '):
                self.assertEqual(bteam[note.split()[1]], row[5], note)

    def test_source_and_pointer_drift_rejected(self):
        for address in (0xC10DC0 + 7, 0xC1100C + 3, m.TABLE + 4 * 2, m.TABLE + 4 * 16, 0xC12E40 + 9):
            original = bytearray(self.original)
            original[address] ^= 1
            with self.assertRaises(AssertionError):
                m.source_guard(original)
        # A foreign reference to an owned sheet is rejected.
        original = bytearray(self.original)
        original[0:4] = struct.pack('<I', 0xC13844 + 0x08000000)
        with self.assertRaises(AssertionError):
            m.source_guard(original)
        for address in (m.TABLE + 4, 0xC10DC0 + 20, 0xC1100C + 717):
            rom = bytearray(self.original)
            rom[address] ^= 1
            with self.assertRaises(AssertionError):
                m.patch(rom, self.original)

    def test_overflow_is_atomic(self):
        rom = bytearray(self.original)
        real = m.lz77_compress_optimal

        def fake(raw, vram_safe=True):
            if raw == m.render(0xC1689C):
                return bytes(669)
            return real(raw, vram_safe=vram_safe)
        with patch.object(m, 'lz77_compress_optimal', side_effect=fake):
            with self.assertRaisesRegex(AssertionError, 'overflow'):
                m.patch(rom, self.original)
        self.assertEqual(rom, self.original)

    def test_snapshot_detects_late_writer_and_unsafe_stream(self):
        rom = bytearray(self.rom)
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)
        self.assertTrue(m.generated_matches(rom))
        for address in (0xC15E00 + 10, m.TABLE + 4 * 47, 0xC12E40 + 3):
            broken = bytearray(rom)
            broken[address] ^= 1
            with self.assertRaises(AssertionError):
                m.verify(broken, regions)
        source, capacity = 0xC13844, 493
        unsafe = m.lz77_compress_optimal(m.render(source), vram_safe=False)
        if len(unsafe) <= capacity and unsafe != m.lz77_compress_optimal(m.render(source)):
            rom[source:source + capacity] = unsafe + bytes(capacity - len(unsafe))
            with self.assertRaisesRegex(AssertionError, 'unsafe VRAM'):
                m.capture(rom, self.original)


if __name__ == '__main__':
    unittest.main()
