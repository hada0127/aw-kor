import os
import unittest
from pathlib import Path
from part2_link_plates import repair_captions, canvas
from lz77_scan import lz77_decompress

ROOT = Path(__file__).resolve().parents[1]


class LinkPlatesTests(unittest.TestCase):
    def test_all_caption_variants_and_protected_upper_art(self):
        native = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        raw = lz77_decompress(native, 0x54E538)[0]
        fixed = repair_captions(raw)
        self.assertEqual(len(raw), len(fixed))
        for offset in (0, 0x1000):
            old, new = [canvas(d, offset, 64, 32) for d in (raw, fixed)]
            self.assertEqual(old.crop((0, 0, 128, 22)).tobytes(), new.crop((0, 0, 128, 22)).tobytes())
            self.assertEqual(old.tobytes(), new.tobytes())
        for offset in (0x1800, 0x1c00, 0x2000):
            self.assertNotEqual(raw[offset:offset+0x400], fixed[offset:offset+0x400])
        self.assertEqual(raw[0x800:0x1000], fixed[0x800:0x1000])

    def test_final_candidate_matches_all_six_variants(self):
        candidate = os.environ.get('AW_TEST_ROM')
        if not candidate:
            self.skipTest('AW_TEST_ROM required')
        from build_korean_full import patch_part2_link_mode_residual_labels
        native = bytearray((ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes())
        patch_part2_link_mode_residual_labels(native)
        self.assertEqual(lz77_decompress(Path(candidate).read_bytes(), 0x54E538)[0],
                         lz77_decompress(native, 0x54E538)[0])
