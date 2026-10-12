import unittest

from dialogue_repoint import assert_part1_portrait_page_rows


class PortraitPageRowsTest(unittest.TestCase):
    def test_three_rows_in_one_page_fail(self):
        text = b'\x81\x40'
        page = b'\x0a\x09' + b'\x72\x0a\x09'.join((text,) * 3) + b'\x6b\x0a\x00'
        with self.assertRaisesRegex(AssertionError, 'page 0 rows 3'):
            assert_part1_portrait_page_rows(0xDCFA8C, page)

    def test_two_rows_on_each_page_pass(self):
        page = b'\x0a\x09\x81\x40\x72\x0a\x09\x81\x40'
        assert_part1_portrait_page_rows(0xDCFA8C, page + b'\x6b' + page + b'\x6b\x0a\x00')

    def test_other_part1_consumer_is_not_assumed_portrait(self):
        page = b'\x81\x40' + b'\x72\x0a\x09\x81\x40' * 3
        assert_part1_portrait_page_rows(0xDECAE4, page)


if __name__ == '__main__':
    unittest.main()
