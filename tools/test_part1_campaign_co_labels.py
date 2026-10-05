import unittest
from pathlib import Path
import part1_campaign_co_labels as labels


class CampaignCoLabelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (Path(__file__).resolve().parent.parent / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_native_bank_slot_is_the_only_change(self):
        rom = bytearray(self.original)
        labels.patch_campaign_name(rom, self.original)
        allowed = {a for row in labels.LABELS for a in range(row[1], row[1] + 128)}
        self.assertTrue(all(a in allowed for a, (x, y) in enumerate(zip(rom, self.original)) if x != y))
        for _, address, _, _, white, shadow, outline in labels.LABELS:
            raw = bytes(rom[address:address + 128])
            self.assertNotEqual(raw, self.original[address:address + 128])
            self.assertEqual({x for b in raw for x in (b & 15, b >> 4)}, {0, white, shadow, outline})

    def test_source_pointer_and_accessor_drift_are_rejected(self):
        for address in (*(row[1] for row in labels.LABELS), *labels.POINTERS, labels.ACCESSOR[0]):
            original = bytearray(self.original)
            original[address] ^= 1
            with self.assertRaises(AssertionError):
                labels.patch_campaign_name(bytearray(original), original)

    def test_post_editor_pixels_are_allowed_but_later_overwrites_fail(self):
        rom = bytearray(self.original)
        labels.patch_campaign_name(rom, self.original)
        rom[labels.SOURCE] ^= 1  # Explicit pixel edit, before ownership snapshot.
        evidence = labels.capture_regions(rom, self.original)
        labels.verify_regions(rom, evidence)
        rom[labels.SOURCE + 1] ^= 1
        with self.assertRaisesRegex(AssertionError, 'overwritten'):
            labels.verify_regions(rom, evidence)



    def test_live_accessor_drift_is_rejected(self):
        rom = bytearray(self.original)
        rom[labels.ACCESSOR[0]] ^= 1
        with self.assertRaisesRegex(AssertionError, 'live accessor'):
            labels.patch_campaign_name(rom, self.original)
        with self.assertRaisesRegex(AssertionError, 'final accessor'):
            labels.capture_regions(rom, self.original)


if __name__ == '__main__':
    unittest.main()
