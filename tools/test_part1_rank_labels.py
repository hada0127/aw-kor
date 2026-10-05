import unittest
from unittest.mock import patch
from pathlib import Path

import part1_rank_labels as ranks
from lz77_scan import lz77_decompress


class RankLabelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (Path(__file__).resolve().parent.parent / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_only_declared_compressed_bytes_change_and_native_glyphs_fit(self):
        rom = bytearray(self.original)
        ranks.patch_rank_labels(rom, self.original)
        outside = bytearray(rom)
        for spec in ranks.LABELS:
            source, _, _, _, text, x = spec
            _, cap = ranks.original_label(self.original, spec)
            raw, consumed = lz77_decompress(rom, source)
            self.assertEqual(raw, ranks.render_label(text, x))
            self.assertLessEqual(consumed, cap)
            self.assertTrue(any(raw[:128]))
            self.assertTrue(any(raw[128:]))
            self.assertEqual({n for b in raw for n in (b & 15, b >> 4)}, {0, 10})
            outside[source:source + cap] = self.original[source:source + cap]
        self.assertEqual(outside, self.original)

    def test_silver_preserves_alignment_padding_and_neighbor(self):
        spec = next(s for s in ranks.LABELS if s[4] == '실버')
        source, pointer, following = spec[:3]
        self.assertEqual((source, pointer, following), (0xBF152C, 0xDFA36C, 0xBF1598))
        _, capacity = ranks.original_label(self.original, spec)
        self.assertEqual(capacity, 105)
        rom = bytearray(self.original)
        with patch.object(ranks, 'LABELS', (spec,)):
            ranks.patch_rank_labels(rom, self.original)
        self.assertEqual(lz77_decompress(rom, source)[0], ranks.render_label('실버', 0))
        self.assertEqual(rom[source + capacity:following + 96], self.original[source + capacity:following + 96])
        self.assertEqual(rom[pointer:pointer + 8], self.original[pointer:pointer + 8])

    def test_gold_allocation_neighbor_and_specific_overflow(self):
        spec = next(s for s in ranks.LABELS if s[4] == '골드')
        source, pointer, following = spec[:3]
        self.assertEqual((source, pointer, following), (0xBF1598, 0xDFA370, 0xBF15F8))
        _, capacity = ranks.original_label(self.original, spec)
        self.assertEqual(capacity, 96)
        with patch.object(ranks, 'LABELS', (spec,)):
            rom = bytearray(self.original)
            ranks.patch_rank_labels(rom, self.original)
            self.assertEqual(lz77_decompress(rom, source)[0], ranks.render_label('골드', 0))
            self.assertEqual(rom[following:following + 102], self.original[following:following + 102])
            self.assertEqual(rom[pointer:pointer + 8], self.original[pointer:pointer + 8])
            pristine = bytearray(self.original)
            with patch.object(ranks, 'lz77_compress_optimal', return_value=bytes(97)):
                with self.assertRaisesRegex(AssertionError, 'overflow'):
                    ranks.patch_rank_labels(pristine, self.original)
            self.assertEqual(pristine, self.original)

    def test_platinum_exact_glyphs_capacity_padding_and_neighbor(self):
        spec = next(s for s in ranks.LABELS if s[4] == '플래티넘')
        source, pointer, following = spec[:3]
        self.assertEqual((source, pointer, following), (0xBF15F8, 0xDFA374, 0xBF1660))
        _, capacity = ranks.original_label(self.original, spec)
        self.assertEqual(capacity, 102)
        with patch.object(ranks, 'LABELS', (spec,)):
            rom = bytearray(self.original)
            ranks.patch_rank_labels(rom, self.original)
            raw, consumed = lz77_decompress(rom, source)
            self.assertEqual(raw, ranks.render_label('플래티넘', 0))
            self.assertEqual(consumed, 94)
            self.assertEqual(rom[source + capacity:following + 68], self.original[source + capacity:following + 68])
            self.assertEqual(rom[pointer:pointer + 8], self.original[pointer:pointer + 8])
            for column in range(4):
                self.assertTrue(any(raw[column * 32:(column + 1) * 32]))
                self.assertTrue(any(raw[128 + column * 32:160 + column * 32]))
            pristine = bytearray(self.original)
            with patch.object(ranks, 'lz77_compress_optimal', return_value=bytes(103)):
                with self.assertRaisesRegex(AssertionError, 'overflow'):
                    ranks.patch_rank_labels(pristine, self.original)
            self.assertEqual(pristine, self.original)

    def test_rejects_source_or_reference_drift(self):
        for where in (address for spec in ranks.LABELS for address in (spec[0], spec[1], spec[1] + 4)):
            original = bytearray(self.original)
            original[where] ^= 1
            with self.assertRaises(AssertionError):
                ranks.patch_rank_labels(bytearray(original), original)
        with self.assertRaisesRegex(AssertionError, '32x16'):
            ranks.render_label('브론즈래트', 0)

    def test_rejects_overflow_instead_of_touching_next_asset(self):
        rom = bytearray(self.original)
        with patch.object(ranks, 'lz77_compress_optimal', return_value=bytes(109)):
            with self.assertRaisesRegex(AssertionError, 'overflow'):
                ranks.patch_rank_labels(rom, self.original)
        self.assertEqual(rom, self.original)

    def test_animal_ranks_cover_whole_table_and_last_entry_sentinel(self):
        import struct
        self.assertEqual(len(ranks.LABELS), 22)
        for i, spec in enumerate(ranks.LABELS):
            self.assertEqual(spec[1], 0xDFA360 + 4 * i)
            if i + 1 < len(ranks.LABELS):
                self.assertEqual(spec[2], ranks.LABELS[i + 1][0])
        self.assertEqual([s[4] for s in ranks.LABELS[7:]],
                         ['치킨', '래빗', '캣', '도그', '몽키', '시프', '가젤', '호스', '울프',
                          '불', '팬서', '베어', '타이거', '라이온', '드래곤'])
        self.assertTrue(all(s[5] == 3 for s in ranks.LABELS[6:]))
        last = ranks.LABELS[-1]
        self.assertEqual(struct.unpack_from('<I', self.original, ranks.TABLE_END)[0], ranks.TABLE_END_WORD)
        _, capacity = ranks.original_label(self.original, last)
        rom = bytearray(self.original)
        with patch.object(ranks, 'LABELS', (last,)):
            ranks.patch_rank_labels(rom, self.original)
        self.assertEqual(rom[last[0] + capacity:last[2] + 64], self.original[last[0] + capacity:last[2] + 64])
        original = bytearray(self.original)
        original[ranks.TABLE_END] ^= 1
        with self.assertRaises(AssertionError):
            ranks.original_label(original, last)

    def test_post_editor_snapshot_detects_late_writer_and_pointer_mutation(self):
        rom = bytearray(self.original)
        ranks.patch_rank_labels(rom, self.original)
        evidence = ranks.capture_rank_regions(rom, self.original)
        ranks.verify_rank_regions(rom, evidence)
        for address in (ranks.LABELS[1][0], ranks.LABELS[1][1]):
            broken = bytearray(rom)
            broken[address] ^= 1
            with self.assertRaisesRegex(AssertionError, 'overwritten'):
                ranks.verify_rank_regions(broken, evidence)


if __name__ == '__main__':
    unittest.main()
