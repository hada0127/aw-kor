"""Static checks for the Part 2 battle-start day OBJ replacement."""

import unittest
import hashlib
from pathlib import Path

from build_korean_full import patch_part2_battle_start_day_overlay_obj
from lz77_scan import lz77_decompress


ROOT = Path(__file__).resolve().parents[1]
BLOCKS = {
    0x45EC74: (9216, range(10, 18)),
    0x92DF84: (7168, range(10, 14)),
    0x966C0C: (7168, range(10, 14)),
    0x99F4B0: (7168, range(10, 14)),
    0x9D7D54: (7168, range(10, 14)),
    0x92EB5C: (1024, range(0, 2)),
    0x9677E4: (1024, range(0, 2)),
    0x9A0088: (1024, range(0, 2)),
    0x9D892C: (1024, range(0, 2)),
}
CELL_HASHES = {
    '일': '65cdd213167e210564713b4004263651ea9b837361c443e985d1fd10d6757b8c',
    '째': 'd208048ec610085e7ac5e84f0ad59f757140cd02e136dda8a7f295ba0103a08a',
    '작': '0cfa2baaa3f38e9a862aee96415718f5d732d6a4e8ea30064e15b3fdab70c1c7',
    '전': '675a716eeb8f8ba29e43a28f288f73bf07b78d2461d4756176074cc5d5a5e631',
    '개': '3d2165d7a85d17c315512a39bb2a693027bce78efe1e83fd2fc6d0b61cf6bb39',
    '시': '982b7087d1e63f7f836039bab4b43d4cf7ba77a50c07740c29886ca853b877a7',
    '실': 'cd6f57141133dac98c582b4aaf3a4c71bbe2d8077aaf9dc50e5f8c05b880b6e7',
    '패': '6e97a2896574d2e672136d24db081001bc423c9c9d9227209c6c018cd0c7d6b1',
}
LABELS = {0x45EC74: '일째작전개시실패',
          **{off: '일째개시' for off in (0x92DF84, 0x966C0C, 0x99F4B0, 0x9D7D54)},
          **{off: '작전' for off in (0x92EB5C, 0x9677E4, 0x9A0088, 0x9D892C)}}


def validate_cell(cell, ch):
    """Pin the committed Hada Bold layout, face size, and palette per cell."""
    if hashlib.sha256(cell).hexdigest() != CELL_HASHES[ch]:
        raise AssertionError(f'wrong rendered cell: {ch}')
    pixels = []
    for y in range(32):
        for x in range(32):
            pos = ((y // 8) * 4 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
            pixels.append((x, y, cell[pos] >> (4 * (x % 2)) & 15))
    if {v for _, _, v in pixels} != {0, 6, 9, 11, 13, 15}:
        raise AssertionError(f'wrong palette: {ch}')
    face = [(x, y) for x, y, v in pixels if v == 15]
    box = (min(x for x, _ in face), min(y for _, y in face),
           max(x for x, _ in face) + 1, max(y for _, y in face) + 1)
    if not (2 <= box[0] <= 3 and box[1] == 3 and 27 <= box[2] <= 28 and box[3] == 28):
        raise AssertionError(f'face outside JP cell ink range: {ch}: {box}')


class BattleDayBannerTest(unittest.TestCase):
    def test_replacement_tiles_and_native_digits(self):
        original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        patched = bytearray(original)
        self.assertEqual(patch_part2_battle_start_day_overlay_obj(patched), 512)
        for off, (expected_size, chunks) in BLOCKS.items():
            before, consumed = lz77_decompress(original, off)
            after, used = lz77_decompress(patched, off)
            self.assertEqual(len(after), expected_size, hex(off))
            self.assertLessEqual(used, consumed, hex(off))
            if expected_size > 1024:
                self.assertEqual(after[:10 * 512], before[:10 * 512], hex(off))
            for chunk in chunks:
                cell = after[chunk * 512:(chunk + 1) * 512]
                self.assertTrue(any(cell), (hex(off), chunk))
                self.assertNotEqual(cell, before[chunk * 512:(chunk + 1) * 512])
                validate_cell(cell, LABELS[off][chunk - chunks.start])

    def test_corrupted_cell_rejected(self):
        original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        patched = bytearray(original)
        patch_part2_battle_start_day_overlay_obj(patched)
        data, _ = lz77_decompress(patched, 0x45EC74)
        first, second = data[10 * 512:11 * 512], data[11 * 512:12 * 512]
        for corrupted in (bytes(512), second, bytes(v ^ 0x01 for v in first)):
            with self.subTest(corrupted=hashlib.sha256(corrupted).hexdigest()[:8]):
                with self.assertRaises(AssertionError):
                    validate_cell(corrupted, '일')


if __name__ == '__main__':
    unittest.main()
