import unittest
from pathlib import Path

import part1_capture_word_obj as word


class CaptureWordTests(unittest.TestCase):
    def test_source_guard_and_confined_patch(self):
        root = Path(__file__).resolve().parents[1]
        original = (root / 'original' / 'Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        before = original[word.OFFSET - 1:word.OFFSET + word.SIZE + 1]
        rom = bytearray(original)
        result = word.patch(rom, original)
        word.verify(rom, original)
        self.assertEqual(result['font'], 'OkDanDan-Bold')
        self.assertEqual(rom[word.OFFSET - 1], before[0])
        self.assertEqual(rom[word.OFFSET + word.SIZE], before[-1])
        self.assertNotEqual(rom[word.OFFSET:word.OFFSET + word.SIZE],
                            original[word.OFFSET:word.OFFSET + word.SIZE])
        modified = bytearray(original)
        modified[word.OFFSET] ^= 1
        with self.assertRaisesRegex(AssertionError, 'source changed'):
            word.generated(modified)


if __name__ == '__main__':
    unittest.main()
