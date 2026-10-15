import struct
import unittest
from pathlib import Path

import link_stage1_graphics as m
from build_korean_full import patch_part2_battle_start_day_overlay_obj
from lz77_scan import lz77_decompress


class LinkStage1GraphicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (Path(__file__).resolve().parent.parent / 'original' /
                        'Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        cls.prepared = bytearray(cls.original)
        patch_part2_battle_start_day_overlay_obj(cls.prepared)

    def test_both_fixed_images_round_trip_and_only_owned_ranges_change(self):
        rom = bytearray(self.prepared)
        report = m.patch(rom, self.original)
        self.assertEqual(set(report), {'p1', 'p2', 'payload_failure'})
        outside = bytearray(rom)
        for spec in m.IMAGES:
            name, start, end, base, warn_off, first, count, error_off, map_off, refs = spec
            old, old_stage, _ = m._source(self.original, spec)
            new = bytes(rom[start:end])
            self.assertEqual(len(new), len(old))
            self.assertEqual(new[:0x2B0], old[:0x2B0])
            stage, used = lz77_decompress(new, 0x2B0)
            self.assertLessEqual(used, len(new) - 0x2B0)
            self.assertEqual(len(stage), len(old_stage))
            for off, ref in zip((warn_off, 0x308C if name == 'p2' else 0x10E0,
                                 error_off, map_off), refs if name == 'p2' else
                                (refs[1], refs[0], refs[2], refs[3])):
                self.assertEqual(struct.unpack_from('<I', stage, ref)[0], base + off)
            warning, _ = lz77_decompress(stage, warn_off)
            self.assertEqual(warning[first*32:(first+count)*32],
                             m.warning_tiles(count//2, name == 'p1'))
            sheet, _ = lz77_decompress(stage, error_off)
            tmap, _ = lz77_decompress(stage, map_off)
            expected_sheet, expected_map = m.error_graphics(
                m._source(self.original, spec)[2][error_off][0],
                m._source(self.original, spec)[2][map_off][0], name)
            self.assertEqual((sheet, tmap), (expected_sheet, expected_map))
            outside[start:end] = self.original[start:end]
        main, _ = lz77_decompress(rom, 0x45EC74)
        for off in m.PAYLOAD_FAILURE_COPIES:
            sheet, _ = lz77_decompress(rom, off)
            self.assertEqual(sheet, main[16*512:18*512])
            outside[off:off+675] = self.prepared[off:off+675]
        self.assertEqual(outside, self.prepared)
        m.verify(rom, self.original)

    def test_source_and_final_writer_guards(self):
        drift = bytearray(self.original)
        drift[m.IMAGES[0][1] + 0x300] ^= 1
        patch_part2_battle_start_day_overlay_obj(drift)
        with self.assertRaises(AssertionError):
            m.patch(bytearray(drift), drift)
        rom = bytearray(self.prepared)
        rom[m.IMAGES[0][1] + 0x300] ^= 1
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        rom = bytearray(self.prepared)
        m.patch(rom, self.original)
        rom[m.IMAGES[1][1] + 0x300] ^= 1
        with self.assertRaises(AssertionError):
            m.verify(rom, self.original)
        rom = bytearray(self.prepared)
        m.patch(rom, self.original)
        rom[m.PAYLOAD_FAILURE_COPIES[0] + 20] ^= 1
        with self.assertRaises(AssertionError):
            m.verify(rom, self.original)

    def test_part1_bubble_replaces_only_lettering_in_native_obj_blocks(self):
        spec = m.IMAGES[1]
        native = m._source(self.original, spec)[2][spec[4]][0]
        source = native[0x58*32:0x78*32]
        result = m.bubble_tiles(source)
        self.assertNotEqual(result, source)
        self.assertEqual(len(result), 1024)
        def color(raw, x, y):
            tile = (x//32)*16 + (y//8)*4 + (x%32)//8
            pos = tile*32 + (y%8)*4 + (x%8)//2
            return (raw[pos] >> (4*(x%2))) & 15

        korean = {}
        for line, x0, dy in zip(m.BUBBLE_LINES, (16, 18), (-1, 13)):
            ink, _ = m._pixels(line)
            korean.update({(x0+x+1, y+dy+1): 5 for x, y in ink})
            korean.update({(x0+x, y+dy): 13 for x, y in ink})
        # The first Japanese stroke starts left of the former clear rectangle.
        self.assertNotEqual(color(source, 9, 3), 1)
        self.assertEqual(color(result, 9, 3), 1)
        self.assertEqual(color(source, 43, 7), 13)
        self.assertEqual(color(result, 43, 7), 13)
        for y in range(32):
            white = [x for x in range(64) if color(source, x, y) == 1]
            for x in range(64):
                interior = 2 <= y < 28 and white[0] <= x <= white[-1]
                expected = korean.get((x, y), 1) if interior else color(source, x, y)
                self.assertEqual(color(result, x, y), expected, (x, y))

    def test_part1_obj_warning_tile_order(self):
        linear = m.warning_tiles(26)
        obj = m.warning_tiles(26, obj_blocks=True)
        self.assertEqual(len(obj), 52*32)
        for block in range(6):
            for row in range(2):
                for col in range(4):
                    src = (row*26 + block*4 + col)*32
                    dst = (block*8 + row*4 + col)*32
                    self.assertEqual(obj[dst:dst+32], linear[src:src+32])
        for row in range(2):
            for col in range(2):
                src = (row*26 + 24 + col)*32
                dst = (48 + row*2 + col)*32
                self.assertEqual(obj[dst:dst+32], linear[src:src+32])


if __name__ == '__main__':
    unittest.main()
