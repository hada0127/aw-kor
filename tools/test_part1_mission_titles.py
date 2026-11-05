import struct
import json
import hashlib
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

    def test_fixed_mission_shape_witness_rejects_damaged_sheet(self):
        witnesses = json.loads((Path(__file__).resolve().parents[1] /
                                'data/graphic_hangul_shape_witnesses.json').read_text())['mission_sheet']
        for source, *_ in m.TITLES:
            raw = lz77_decompress(self.rom, m.stream_address(self.rom, source))[0]
            self.assertEqual(hashlib.sha256(raw).hexdigest(), witnesses[f'0x{source:06X}'])
        source = m.TITLES[0][0]
        damaged = bytearray(lz77_decompress(self.rom, m.stream_address(self.rom, source))[0])
        damaged[next(i for i, value in enumerate(damaged) if value)] ^= 1
        self.assertNotEqual(hashlib.sha256(damaged).hexdigest(), witnesses[f'0x{source:06X}'])

    def test_only_owned_allocations_change(self):
        outside = bytearray(self.rom)
        moved = m.relocations()
        # R4 Hada Sans sheets that exceed a native LZ77 slot are repointed.
        self.assertEqual(len(moved), 22)
        for source, following, capacity, size, _, indices in m._all_blocks():
            address = m.stream_address(self.rom, source)
            raw, used = lz77_decompress(self.rom, address)
            self.assertEqual(raw, m.render(source))
            if source in moved:
                destination, length = moved[source]
                self.assertEqual((address, used), (destination, length))
                self.assertGreater(length, capacity)
                self.assertTrue(m.RELOCATION_START <= destination and destination + length <= m.RELOCATION_END)
                # Retired native slot: original bytes, no remaining reference.
                self.assertEqual(self.rom[source:following], self.original[source:following])
                self.assertNotIn(struct.pack('<I', source + 0x08000000), bytes(self.rom))
                outside[destination:destination + length] = self.original[destination:destination + length]
                for i in indices:
                    outside[m.TABLE + 4 * i:m.TABLE + 4 * i + 4] = self.original[m.TABLE + 4 * i:m.TABLE + 4 * i + 4]
            else:
                self.assertEqual(address, source)
                self.assertLessEqual(used, capacity)
                self.assertEqual(self.rom[source + capacity:following],
                                 self.original[source + capacity:following])
                outside[source:source + capacity] = self.original[source:source + capacity]
        self.assertEqual(outside, self.original)
        # An occupied or referenced relocation area fails closed, atomically.
        rom = bytearray(self.original)
        rom[m.RELOCATION_START + 9] = 1
        before = bytes(rom)
        with self.assertRaisesRegex(AssertionError, 'relocation area occupied'):
            m.patch(rom, self.original)
        self.assertEqual(bytes(rom), before)

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
            # OBJ6 corner AA index 11 remains legal on Hada Sans sheets.
            self.assertLessEqual(colors, {0, m.INK, 11, m.SHADOW, m.OUTLINE})
            self.assertIn(m.INK, colors)
        # The mission-2 text continues into the 32x32 extension cell; tiles 16..31 stay blank.
        ext = m.render(m.EXTENSION[0])
        self.assertTrue(any(ext[:512]))
        self.assertFalse(any(ext[512:]))
        sizes = {row[0]: m.chosen_size(row[0]) for row in m.TITLES}
        for row in m.TITLES:
            size = sizes[row[0]]
            if size is not None:
                ink = m._ink_hada(m._text(row[0]), 160 if row[0] == m.EXTENSION_OWNER else 128, size)
                self.assertTrue(ink)
        self.assertTrue(all(size is not None for size in sizes.values()))
        self.assertEqual(sizes[0xC1689C], 20)
        self.assertEqual(sizes[0xC13EE0], 15)  # width-limited

    def test_wrong_font_hash_is_not_a_fit_fallback(self):
        m.chosen_size.cache_clear()
        with patch.object(m.aw_fonts, 'hadasans_extrabold_path', side_effect=AssertionError('wrong font hash')):
            with self.assertRaisesRegex(AssertionError, 'wrong font hash'):
                m.chosen_size(0xC1689C)
        m.chosen_size.cache_clear()

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
                return bytes(0x2000)   # cannot fit even the relocation area
            return real(raw, vram_safe=vram_safe)
        m.relocations.cache_clear()
        try:
            with patch.object(m, 'lz77_compress_optimal', side_effect=fake):
                with self.assertRaisesRegex(AssertionError, 'overflow'):
                    m.patch(rom, self.original)
        finally:
            m.relocations.cache_clear()
        self.assertEqual(rom, self.original)

    def test_snapshot_detects_late_writer_and_unsafe_stream(self):
        rom = bytearray(self.rom)
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)
        self.assertTrue(m.generated_matches(rom))
        for address in (0xC15E00 + 10, m.TABLE + 4 * 47, 0xC12E40 + 3,
                        0xC14C9C + 5, m.relocations()[0xC14C9C][0] + 7):
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
