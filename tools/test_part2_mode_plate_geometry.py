"""Part 2 LARGE mode plates against the pinned, user-approved b20 geometry.

data/part2_mode_plate_geometry.json is an independent record (scale, tracking,
ink bbox, syllable boxes/indices, pixel hashes, font SHAs). The generator must
reproduce it exactly; changing a generator constant must fail here until a new
approval re-pins the profile. AW_TEST_ROM additionally binds the final ROM.
"""
import hashlib
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import aw_fonts
import hangul_pixel_fit as fit
from lz77_scan import lz77_decompress

ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads((ROOT / 'data/part2_mode_plate_geometry.json').read_text(encoding='utf-8'))


def clear_caches():
    for fn in (fit.plate_width_scale, fit._plate_raster):
        fn.cache_clear()


def profile_mismatches():
    out = []
    ox, oy = PROFILE['band']['origin']
    if (fit.PLATE_ORIGIN, fit.PLATE_WIDTH, fit.PLATE_HEIGHT) != ((ox, oy), PROFILE['band']['width'],
                                                                PROFILE['band']['height']):
        out.append('band')
    for text, want in PROFILE['labels'].items():
        scale = fit.plate_width_scale(text)
        mask, records = fit.plate_line(text)
        box = mask.getbbox()
        got = {
            'width_scale': scale,
            'tracking_px': [records[i + 1][1][0] - records[i][1][2] for i in range(len(records) - 1)],
            'ink_bbox_plate': [box[0] + ox, box[1] + oy, box[2] + ox - 1, box[3] + oy - 1],
            'syllable_boxes_plate': [[a + ox, b + oy, c + ox, d + oy] for _, (a, b, c, d) in records],
            'syllable_indices': fit.plate_syllable_indices(text),
            'body_mask_sha256': hashlib.sha256(mask.tobytes()).hexdigest(),
        }
        for key, value in got.items():
            if want[key] != value:
                out.append((text, key, want[key], value))
        if scale > PROFILE['max_width_scale'] or max(got['tracking_px'] or [0]) > PROFILE['max_tracking_px']:
            out.append((text, 'limit'))
    return out


class PinnedPlateGeometryTest(unittest.TestCase):
    def setUp(self):
        clear_caches()

    def tearDown(self):
        clear_caches()

    def test_fonts_match_pinned_profile(self):
        self.assertEqual(PROFILE['fonts']['HadaSans-Bold.otf'], aw_fonts.HADASANS_SHA256)
        self.assertEqual(PROFILE['fonts']['HadaSans-Black.otf'], aw_fonts.HADASANS_BLACK_SHA256)
        aw_fonts.hadasans_path(); aw_fonts.hadasans_black_path()   # files present, SHA checked

    def test_generator_reproduces_approved_profile(self):
        self.assertEqual(profile_mismatches(), [])
        self.assertEqual(set(PROFILE['labels']), set(fit.PLATE_LABELS))

    def test_final_rom_plates_match_profile(self):
        if not os.environ.get('AW_TEST_ROM'):
            self.skipTest('AW_TEST_ROM not set')
        rom = Path(os.environ['AW_TEST_ROM']).read_bytes()
        for text, want in PROFILE['labels'].items():
            raw = lz77_decompress(rom, int(want['asset'], 16))[0]
            self.assertEqual(hashlib.sha256(raw).hexdigest(), want['decompressed_plate_sha256'], text)

    def test_raised_scale_limit_fails(self):
        with patch.object(fit, 'PLATE_MAX_WIDTH_SCALE', 2.2):
            clear_caches()
            self.assertTrue(any(m[1] == 'width_scale' for m in profile_mismatches() if len(m) > 2))

    def test_lowered_scale_limit_fails(self):
        with patch.object(fit, 'PLATE_MAX_WIDTH_SCALE', 1.6):
            clear_caches()
            self.assertTrue(profile_mismatches())

    def test_changed_tracking_fails(self):
        for value in (6, 12):
            with self.subTest(max_gap=value), patch.object(fit, 'PLATE_MAX_GAP', value):
                clear_caches()
                self.assertTrue(any(m[1] == 'tracking_px' for m in profile_mismatches() if len(m) > 2))

    def test_changed_min_gap_fails(self):
        with patch.object(fit, 'PLATE_MIN_GAP', 4):
            clear_caches()
            self.assertTrue(profile_mismatches())


if __name__ == '__main__':
    unittest.main()
