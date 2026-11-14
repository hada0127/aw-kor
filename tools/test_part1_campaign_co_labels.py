import hashlib
import unittest
from pathlib import Path
import part1_campaign_co_labels as labels

# Current-generator goldens (R18, 2026-11-09; R20 캐서린/키쿠치요/이글 redrawn).  Campaign names use six-row
# Galmuri cuts with a black outline; battle HUD names keep the older renderer.
GOLDEN = {
    'campaign_hoip': '50e8b8e31ab333dcda6418a521e8d334c2cfcaf8f3a3859fdfdb46b506df4d52',
    'campaign_ryo': '283ddd15e9056db4dad18f41a07344b63b369aa95daf3b6b889ae2ba1ceb58c3',
    'campaign_max': 'b8f69a73f1009f3ffa155ba165711e7af3c4ce264c97f68bbcc8661657d13788',
    'campaign_domino': 'ed8d90af739ee364126933b386e8ce038bef58d0829eb9903cf202f7b781667d',
    'campaign_billy': '01907699d43967ee4836c59b4058ed762b4225d9816c79fad84c92a2b1f817d7',
    'battle_ryo': '9aab8206bec0dc901efa64e4889582a370709beeca212c133889d8f1cfc60c76',
    'battle_max': '64c55b9410bef333d84d7b848e5694c5adb37247f987c6eefa8e7032bd07af20',
    'campaign_catherine': '52f8897ee7001d4790e30004a015b5497da8ff9d346984dbd940c71e8b682c92',
    'campaign_kikuchiyo': '8850ca30605c3a80567a6351f1329f8430ba011a2f85457ba5d680488919f268',
    'campaign_asuka': '10faa4b272298ea0341c2a26aea61aa6893f6a5dc7998c66025ecb0e586a3311',
    'campaign_eagle': '257c6935ac0c8f83c951ff37d145e231c0f38e55b53a7f8fb62041eab9cabd4a',
    'campaign_mop': '128c7537cc65be21bc55f1b122c815c975ccaeb11816823180c8d2f8ac2ef3e6',
    'campaign_sturm': '59efcc3ef63cce335ea0d02206ff9c61f9e1f6c8039d8ff7803f58e695a5d427',
    'campaign_sturm_alt': '59efcc3ef63cce335ea0d02206ff9c61f9e1f6c8039d8ff7803f58e695a5d427',
    'battle_domino': '137fe7004c73405c8b4e702d8a082a73470f8d3f7d8e72dffefbf0dfa54a97f4',
    'battle_billy': '29c223de92d3cb9764d3b44d1d59dff8ebffcdeab4042eacfb8be0c12fc65b6e',
    'battle_kikuchiyo': '21be03041897fcd6b5940343b291947afe4ae967336023a21ac856c6cb3a78a3',
    'battle_asuka': 'e578702453ccdfc353b38b080efbe521e23bd71561730e80f33bc4826e6895aa',
    'battle_eagle': 'ed513508cb0fe48888cc5fa52fa3e12a472f1db837d7bd5796f9755d5aa93bfb',
    'battle_mop': '237c2b1f4fb68f2ab4095edd6359e3893b30323846872db01dc4f25471b735f0',
    'battle_sturm': '574289180a63b9bea17f96bdf900093c85ef8f72fc0639bfca1f1d3c8214e2c9',
}


def pixels(raw):
    return [[(raw[x // 8 * 32 + y * 4 + x % 8 // 2] >> (4 * (x % 2))) & 15 for x in range(32)]
            for y in range(8)]


class CampaignCoLabelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (Path(__file__).resolve().parent.parent / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_native_bank_slot_is_the_only_change(self):
        rom = bytearray(self.original)
        labels.patch_campaign_name(rom, self.original)
        allowed = {a for row in labels.LABELS for a in range(row[1], row[1] + 128)}
        self.assertTrue(all(a in allowed for a, (x, y) in enumerate(zip(rom, self.original)) if x != y))
        for label_id, address, _, _, white, shadow, outline in labels.LABELS:
            raw = bytes(rom[address:address + 128])
            self.assertNotEqual(raw, self.original[address:address + 128])
            used = {0, white, outline} if label_id.startswith('campaign_') else {0, white, shadow, outline}
            self.assertEqual({x for b in raw for x in (b & 15, b >> 4)}, used)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), GOLDEN[label_id], label_id)

    def test_campaign_names_keep_japanese_margins(self):
        rom = bytearray(self.original)
        labels.patch_campaign_name(rom, self.original)
        for label_id, address, _, text, white, _, _ in labels.LABELS:
            if not label_id.startswith('campaign_'):
                continue
            px = pixels(rom[address:address + 128])
            ink = [(x, y) for y in range(8) for x in range(32) if px[y][x] == white]
            self.assertEqual({y for _, y in ink}, set(range(1, 7)), text)
            self.assertGreaterEqual(min(x for x, _ in ink), 2, text)
            self.assertLessEqual(max(x for x, _ in ink), 29, text)
            self.assertTrue(all(px[y][0] == px[y][31] == 0 for y in range(8)), text)

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
