import unittest
from pathlib import Path

import part1_supply_popup as S


class SupplyPopupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (S.ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_frame_icon_and_transparency_preserved(self):
        old = self.original[S.SOURCE:S.SOURCE + S.SIZE]
        new = S.replacement(self.original)
        x0, y0, x1, y1 = S.TEXT_BOX
        self.assertEqual(len(new), S.SIZE)
        self.assertNotEqual(old, new)
        for y in range(32):
            for x in range(64):
                if not (x0 <= x < x1 and y0 <= y < y1):
                    self.assertEqual(S.pixel(old, x, y), S.pixel(new, x, y))
        colors = {S.pixel(new, x, y) for y in range(y0, y1) for x in range(x0, x1)}
        self.assertEqual(colors, {S.INTERIOR, S.INK})

    def test_jp_outlined_strokes_and_gap_before_bang(self):
        # R20: white strokes, black 8-way outline; one white column between
        # the last syllable's outline and the outline of '!'.
        for source, text, box, _ in S.BUBBLES:
            raw = S.bubble(self.original, source)
            ink, _ = S._ink(text)
            left, top = S.text_origin(text, box)
            body = {(left + x, top + y) for x, y in ink}
            ring = {(x + dx, y + dy) for x, y in body for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - body
            self.assertTrue(all(S.pixel(raw, x, y) == S.INTERIOR for x, y in body), text)
            self.assertTrue(all(S.pixel(raw, x, y) == S.INK for x, y in ring), text)
            bang = max(x for x, _ in body)   # '!' is one column wide
            columns = {x for x, _ in ring | body}
            self.assertEqual((bang - 1 in columns, bang - 2 in columns, bang - 3 in columns),
                             (True, False, True), text)   # outline, white column, outline
            self.assertEqual({y for _, y in ring | body}, set(range(box[1], box[3])), text)

    def test_source_drift_fails_closed(self):
        original = bytearray(self.original)
        original[S.SOURCE] ^= 1
        with self.assertRaises(ValueError):
            S.replacement(original)

    def test_late_writer_rejected(self):
        rom = bytearray(self.original)
        S.patch(rom, self.original)
        S.verify(rom, self.original)
        rom[S.SOURCE + 33] ^= 1
        with self.assertRaises(ValueError):
            S.verify(rom, self.original)

    def test_previous_writer_conflict_rejected(self):
        rom = bytearray(self.original)
        rom[S.SOURCE + 100] ^= 1
        with self.assertRaises(ValueError):
            S.patch(rom, self.original)

    def test_all_bubbles_and_lz_copies(self):
        from lz77_scan import lz77_decompress
        rom = bytearray(self.original)
        self.assertEqual(S.patch(rom, self.original), len(S.BUBBLES) + len(S.LZ_COPIES))
        S.verify(rom, self.original)
        for source, text, (x0, y0, x1, y1), _ in S.BUBBLES:
            old = self.original[source:source + S.SIZE]
            new = bytes(rom[source:source + S.SIZE])
            self.assertNotEqual(old, new)
            for y in range(32):
                for x in range(64):
                    if not (x0 <= x < x1 and y0 <= y < y1):
                        self.assertEqual(S.pixel(old, x, y), S.pixel(new, x, y))
        sheet = b''.join(bytes(rom[s:s + S.SIZE]) for s, *_ in S.BUBBLES)
        for offset, capacity, _ in S.LZ_COPIES:
            decoded = lz77_decompress(rom, offset)
            self.assertEqual(decoded[0], sheet)
            self.assertLessEqual(decoded[1], capacity)
            self.assertEqual(rom[offset + capacity:offset + capacity + 8],
                             self.original[offset + capacity:offset + capacity + 8])
        again = bytearray(rom)
        S.patch(again, self.original)  # idempotent
        self.assertEqual(again, rom)

    def test_enemy_turn_bubble_is_right_supply_copy(self):
        # VRAM tile429 of 0019_A_0002371.ss0 == original 0xBD1390 (sha below).
        self.assertEqual(S.BUBBLES[3][0], 0xBD1390)
        self.assertEqual(self.original.count(self.original[0xBD1390:0xBD1390 + 1024]), 1)

    def test_lz_copy_conflict_rejected(self):
        rom = bytearray(self.original)
        rom[0x92BF3C + 20] ^= 1
        with self.assertRaises(ValueError):
            S.patch(rom, self.original)


if __name__ == '__main__':
    unittest.main()
