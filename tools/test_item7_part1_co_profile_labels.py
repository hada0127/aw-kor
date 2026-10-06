import unittest
from pathlib import Path

import item7_part1_co_profile_labels as m


class Item7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parent.parent
        cls.original = (root / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def regions(self):
        rom = bytearray(self.original)
        count = m.patch(rom, self.original)
        return rom, count

    def test_patch_changes_only_owned_bytes_and_is_idempotent(self):
        rom, count = self.regions()
        self.assertGreater(count, 0)
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)
        self.assertTrue(m.generated_matches(rom, self.original))
        outside = bytearray(rom)
        for address, raw in regions:
            outside[address:address + len(raw)] = self.original[address:address + len(raw)]
        self.assertEqual(outside, self.original)
        self.assertNotEqual(bytes(rom), self.original)
        again = bytearray(rom)
        m.patch(again, self.original)
        self.assertEqual(again, rom)

    def test_late_writer_detected(self):
        rom, _ = self.regions()
        regions = m.capture(rom, self.original)
        address, raw = regions[0]
        rom[address + len(raw) // 2] ^= 0x11
        with self.assertRaises(AssertionError):
            m.verify(rom, regions)

    def test_earlier_writer_conflict_rejected(self):
        rom, _ = self.regions()
        address = m.capture(rom, self.original)[0][0]
        conflicted = bytearray(self.original)
        conflicted[address + 8] ^= 0x22
        with self.assertRaises(AssertionError):
            m.patch(conflicted, self.original)

    def test_source_drift_fails_closed(self):
        rom, _ = self.regions()
        address = m.capture(rom, self.original)[-1][0]
        original = bytearray(self.original)
        original[address + 1] ^= 0x01
        with self.assertRaises(Exception):
            m.patch(bytearray(original), bytes(original))


class ProfileGeometryTests(unittest.TestCase):
    def test_pictures_and_metadata_kept(self):
        original = (Path(__file__).resolve().parent.parent / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        for entry, w, h, *_ in m.LABELS:
            offset = m.entry_span(original, entry)[0]
            new = m.render(original, entry)
            old = original[offset:offset + w * h * 32]
            keep_rows = range(8) if w == 2 or entry in (96, 97) else ()
            for y in keep_rows:
                for x in range(w * 8):
                    i = ((y // 8) * w + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
                    self.assertEqual((old[i] >> (4 * (x % 2))) & 15, (new[i] >> (4 * (x % 2))) & 15)
        rom = bytearray(original)
        rom[0xD8D7CC] ^= 1
        with self.assertRaises(AssertionError):
            m.patch(rom, original)
