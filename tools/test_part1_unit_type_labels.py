from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

import part1_unit_type_labels as labels
from lz77_scan import lz77_decompress


class UnitTypeLabelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Local source ROM is required for this asset gate; never commit its data.
        source = Path(__file__).resolve().parents[1] / 'original/Game Boy Wars Advance 1+2 (Japan).gba'
        packed = source.read_bytes()[labels.OFFSET:labels.OFFSET + labels.SLOT_SIZE]
        cls.original = bytes(labels.OFFSET) + packed
        cls.raw = lz77_decompress(packed, 0)[0]
        cls.rendered = labels.render(cls.raw)

    def test_only_caption_pixels_change_and_native_art_and_badges_survive(self):
        self.assertEqual(self.raw[:6 * 512], self.rendered[:6 * 512])
        for index in range(6, 15):
            before = labels.decode_image(self.raw, index)
            after = labels.decode_image(self.rendered, index)
            self.assertNotEqual(before, after)
            if index < 12:
                self.assertEqual(before[:14], after[:14])
                # Original captions use grayscale antialiasing 1..4 and outline 5;
                # the unit illustrations use the distinct brown colors 7..9.
                self.assertLessEqual(set(v for row in before[14:] for v in row), set(range(6)))
                self.assertTrue(all(v == 0 for row in before[24:] for v in row))
                self.assertTrue(any(1 in row for row in after[14:]))
                self.assertTrue(any(5 in row for row in after[14:]))
                self.assertTrue(all(v == 0 for row in after[24:] for v in row))
            else:
                self.assertEqual(before[7], after[7])
                for y, row in enumerate(before):
                    for x, value in enumerate(row):
                        if value in (0, 1):
                            self.assertEqual(value, after[y][x], (index, x, y))
                self.assertEqual(set(v for row in after for v in row), {0, 1, (9, 12, 15)[index-12], (6, 10, 13)[index-12]})
                untouched = [(x, 7) for x in range(32)] + [(x, 0) for x in (6, 7, 24, 25)]
                untouched += [(x, y) for y in range(7) for x in (*range(6), *range(26, 32))]
                self.assertTrue(all(before[y][x] in (0, 1, (9, 12, 15)[index-12]) for x, y in untouched))
            before_caption = before[14:] if index < 12 else before
            after_caption = after[14:] if index < 12 else after
            self.assertLessEqual({v for row in after_caption for v in row},
                                 {v for row in before_caption for v in row})

    def test_short_glyph_uses_its_bdf_baseline(self):
        # Galmuri7 '보' is BBX 7x6 at yoffset=1; it starts beside 병 at
        # y=16, and ends one row above the seven-pixel 병 glyph.
        pixels = labels.decode_image(self.rendered, 6)
        first_glyph_rows = {y for y in range(14, 24) for x in range(9, 16) if pixels[y][x] == 1}
        second_glyph_rows = {y for y in range(14, 24) for x in range(17, 23) if pixels[y][x] == 1}
        self.assertEqual((min(first_glyph_rows), max(first_glyph_rows)), (16, 21))
        self.assertEqual((min(second_glyph_rows), max(second_glyph_rows)), (16, 22))

    def test_patch_roundtrips_within_original_slot_and_has_final_guard(self):
        rom = bytearray(self.original)
        result = labels.patch(rom, self.original)
        self.assertLessEqual(result['packed_bytes'], labels.SLOT_SIZE)
        self.assertEqual(rom[:labels.OFFSET], self.original[:labels.OFFSET])
        self.assertEqual(len(rom), len(self.original))
        self.assertEqual(lz77_decompress(rom, labels.OFFSET)[0], self.rendered)
        self.assertEqual(result['raw_sha256'], hashlib.sha256(self.rendered).hexdigest())
        labels.verify(rom, self.original)
        rom[-1] ^= 1
        with self.assertRaisesRegex(AssertionError, 'overwritten'):
            labels.verify(rom, self.original)

    def test_changed_source_and_occupied_target_fail_without_mutation(self):
        rom = bytearray(self.original)
        rom[-4] ^= 1
        before = bytes(rom)
        with self.assertRaisesRegex(AssertionError, 'another writer'):
            labels.patch(rom, self.original)
        self.assertEqual(rom, before)
        with self.assertRaisesRegex(AssertionError, 'source asset'):
            labels.render(bytes(len(self.raw)))
        with self.assertRaisesRegex(AssertionError, 'matching complete'):
            labels.patch(bytearray(12), self.original)

    def test_slot_overflow_is_rejected_before_write(self):
        labels._payload.cache_clear()
        rom = bytearray(self.original)
        with patch('lz77_compress.lz77_compress_optimal', return_value=bytes(labels.SLOT_SIZE + 1)):
            with self.assertRaisesRegex(AssertionError, 'exceeds original slot'):
                labels.patch(rom, self.original)
        self.assertEqual(rom, self.original)
        labels._payload.cache_clear()

    def test_real_sprite_editor_overlay_is_preserved_and_late_overwrite_rejected(self):
        from build_korean_full import apply_sprite_overrides
        rom = bytearray(self.original)
        labels.patch(rom, self.original)
        # Deliberate user artwork change in the first background image.
        user_raw = bytearray(self.rendered)
        user_raw[0] ^= 1
        grid = []
        for y in range(408):
            grid.append([(user_raw[((y // 8) * 4 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2]
                          >> (4 * (x % 2))) & 15 for x in range(32)])
        base = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=base / 'temp', prefix='unit_type_editor_') as directory:
            directory = Path(directory)
            override = directory / 'override.json'
            override.write_text(json.dumps({'lz77_00BD1AF0': {'indices': grid}}))
            result = apply_sprite_overrides(
                rom, ov_path=str(override), idx_path=str(base / 'data/sprites_index.json'),
                report_path=str(directory / 'report.json'))
        self.assertEqual(result['applied'], 1)
        self.assertEqual(result['skipped'], 0)
        self.assertEqual(lz77_decompress(rom, labels.OFFSET)[0], bytes(user_raw))
        regions = labels.capture_regions(rom, self.original)
        labels.verify_regions(rom, regions)
        rom[labels.OFFSET + 30] ^= 1
        with self.assertRaisesRegex(AssertionError, 'after editor'):
            labels.verify_regions(rom, regions)


if __name__ == '__main__':
    unittest.main()
