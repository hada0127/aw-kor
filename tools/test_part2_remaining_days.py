import unittest
from pathlib import Path
from unittest.mock import patch

import build_korean_full as builder
import part2_remaining_days as counter


class RemainingDaysTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = Path(builder.P.ROM).read_bytes()

    def test_only_native_label_tiles_change(self):
        rom = bytearray(self.original)
        self.assertEqual(counter.patch(rom, self.original), 2)
        self.assertEqual(len(rom), len(self.original))
        self.assertNotEqual(rom[counter.SOURCE:counter.SOURCE + 96], self.original[counter.SOURCE:counter.SOURCE + 96])
        rom[counter.SOURCE:counter.SOURCE + 96] = self.original[counter.SOURCE:counter.SOURCE + 96]
        self.assertEqual(rom, self.original)

    def test_digit_overlap_column_stays_transparent(self):
        for raw in (self.original[counter.SOURCE:counter.SOURCE + 96], counter.render_labels()):
            self.assertTrue(all((raw[32 + y * 4 + 3] >> 4) == 0 for y in range(8)))
        raw = counter.render_labels()
        self.assertEqual(len(raw), 96)
        self.assertTrue(all((byte & 15) in (0, 1, 7, 15) and (byte >> 4) in (0, 1, 7, 15) for byte in raw))
        self.assertTrue(all(any(raw[start:start + 32]) for start in (0, 32, 64)))

    def test_galmuri_ink_positions_and_outline_boundaries(self):
        raw = counter.render_labels()
        # Decode each physical tile independently, then join the three tiles.
        pixels = [[] for _ in range(8)]
        for start in (0, 32, 64):
            for y in range(8):
                for byte in raw[start + y * 4:start + y * 4 + 4]:
                    pixels[y].extend((byte & 15, byte >> 4))
        # Reviewed Galmuri7 bitmaps at 남 x=1, 은 x=8, 일 x=17.
        expected = (
            '.#....#...###.....##..#.',
            '.#....##.#...#...#..#.#.',
            '.####.#...###.....##..#.',
            '........#######...#####.',
            '..#####.............###.',
            '..#...#..#........##....',
            '..#####..#####....#####.',
            '........................',
        )
        self.assertEqual(tuple(''.join('#' if p == 1 else '.' for p in row)
                               for row in pixels), expected)
        # Keep the reviewed shadow/outline style as well as the ink geometry.
        styled = (
            'O#O..O#OOO###OO.OO##OO#O',
            'O#sOOO##O#Oss#O.O#Os#O#s',
            'O####O#ssO###Os.OO##Os#s',
            'OOssssOs#######..O#####s',
            '.O#####OOssssss..OOs###s',
            '.O#sss#sO#OOOOO..O##Osss',
            '.O#####sO#####O..O#####O',
            '.OOsssssOOsssss..OOsssss',
        )
        symbols = {0: '.', 1: '#', 7: 's', 15: 'O'}
        self.assertEqual(tuple(''.join(symbols[p] for p in row) for row in pixels), styled)
        self.assertEqual([sum(p == 1 for row in pixels for p in row[a:b])
                          for a, b in ((0, 8), (8, 16), (16, 24))], [22, 21, 24])
        self.assertEqual([pixels[y][0] for y in range(3)], [15, 15, 15])
        self.assertEqual(pixels[0][16], 15)
        self.assertEqual(pixels[0][23], 15)
        self.assertEqual(pixels[3][16], 0)  # No outline from prefix into suffix.
        self.assertTrue(all(p == 0 for p in (row[15] for row in pixels)))

    def test_font_geometry_or_missing_glyph_fails_before_write(self):
        font, bounds = counter.load_bdf(str(counter.ROOT / 'reference/fonts/Galmuri7.bdf'))
        variants = []
        missing = dict(font)
        del missing[ord('남')]
        variants.append(missing)
        for char, geometry in (('남', [8, 7, 0, 0]), ('은', [7, 7, 1, 0]),
                               ('일', [7, 7, 0, 0]), ('일', [6, 7, 0, 1])):
            changed = dict(font)
            changed[ord(char)] = dict(font[ord(char)], bbx=geometry)
            variants.append(changed)
        for changed in variants:
            rom = bytearray(self.original)
            with patch.object(counter, 'load_bdf', return_value=(changed, bounds)):
                with self.assertRaises(AssertionError):
                    counter.patch(rom, self.original)
            self.assertEqual(rom, self.original)

    def test_capture_preserves_accepted_editor_pixels(self):
        rom = bytearray(self.original)
        counter.patch(rom, self.original)
        # A palette edit accepted by apply_sprite_overrides takes precedence
        # over the generated default, then becomes immutable for later writes.
        rom[counter.SOURCE] = (rom[counter.SOURCE] & 0xF0) | 7
        regions = counter.capture_regions(rom, self.original)
        self.assertEqual(regions[0][1], rom[counter.SOURCE:counter.SOURCE + counter.SIZE])
        counter.verify_regions(rom, regions)
        rom[counter.SOURCE] ^= 1
        with self.assertRaises(AssertionError):
            counter.verify_regions(rom, regions)

    def test_capture_rejects_loader_or_source_provenance_drift(self):
        for address in (counter.SOURCE, counter.LOADER[0], counter.LITERALS[0]):
            original = bytearray(self.original)
            rom = bytearray(original)
            counter.patch(rom, original)
            original[address] ^= 1
            with self.assertRaises(AssertionError):
                counter.capture_regions(rom, original)

    def test_freeze_rejects_untrusted_evidence(self):
        rom = bytearray(self.original)
        counter.patch(rom, self.original)
        regions = counter.capture_regions(rom, self.original)
        for invalid in ((), ((0, b''),) * 3, regions[::-1],
                        ((counter.SOURCE, b''),) + regions[1:]):
            with self.assertRaises(AssertionError):
                counter.verify_regions(rom, invalid)

    def test_source_and_loader_drift_fail_before_writes(self):
        for address in (counter.SOURCE, counter.LOADER[0], counter.LITERALS[0]):
            for mutate_original in (False, True):
                original = bytearray(self.original)
                rom = bytearray(original)
                rom[address] ^= 1
                if mutate_original:
                    original[address] ^= 1
                before = bytes(rom)
                with self.assertRaises(AssertionError):
                    counter.patch(rom, original)
                self.assertEqual(rom, before)

    def test_final_freeze_detects_late_asset_and_loader_changes(self):
        rom = bytearray(self.original)
        counter.patch(rom, self.original)
        regions = counter.capture_regions(rom, self.original)
        counter.verify_regions(rom, regions)
        for address, _ in regions:
            changed = bytearray(rom)
            changed[address] ^= 1
            with self.assertRaises(AssertionError):
                counter.verify_regions(changed, regions)


if __name__ == '__main__':
    unittest.main()
