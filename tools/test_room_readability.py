import unittest
from unittest.mock import patch

from PIL import ImageChops
import build_title_hangul as title


class RoomReadabilityTest(unittest.TestCase):
    def test_room_counters_have_two_dark_rows(self):
        image = title.make_part1_option_block('작전룸', 28)
        for point in ((87, 9), (87, 10), (88, 21), (88, 22)):
            self.assertEqual(image.getpixel(point), 14, point)

    def test_room_hint_preserves_prefix_position_and_english(self):
        for make, boundary, has_footer in (
                (lambda: title.make_part1_option_block('작전룸', 28), 75, False),
                (title.make_part1_operation_block, 41, True)):
            with patch.object(title, 'part1_menu_text_mask', title.text_mask_layer):
                before = make()
            after = make()
            self.assertEqual(before.getbbox(), after.getbbox())
            self.assertEqual(before.crop((0, 0, boundary, 32)).tobytes(),
                             after.crop((0, 0, boundary, 32)).tobytes())
            self.assertIsNotNone(ImageChops.difference(before, after).getbbox())
            if has_footer:
                self.assertEqual(before.crop((0, 24, 80, 32)).tobytes(),
                                 after.crop((0, 24, 80, 32)).tobytes())

    def test_other_options_are_unchanged(self):
        for name, _, text, size in title.PART1_MODE_OPTION_BLOCKS:
            if text == '작전룸':
                continue
            with patch.object(title, 'part1_menu_text_mask', title.text_mask_layer):
                before = title.make_part1_option_block(text, size)
            after = title.make_part1_option_block(text, size)
            self.assertEqual(before.tobytes(), after.tobytes(), name)


if __name__ == '__main__':
    unittest.main()
