import unittest

from dialogue_repoint import assert_part1_portrait_page_rows


class PortraitPageRowsTest(unittest.TestCase):
    def test_existing_four_field_page_reflow_preserves_authored_space(self):
        from dialogue_repoint import repoint_messages
        original = bytearray(b'\xff' * 0xE10000)
        msg, first, second, site = 0xDCFA8C, 0xDCFA8E, 0xDCFA93, 0xDE7000
        native = b'\x0a\x09\x88\x40\x72\x0a\x09\x88\x41\x6b\x0a\0'
        original[msg:msg + len(native)] = native
        original[site:site + 4] = (0x08000000 + msg).to_bytes(4, 'little')
        left, tail, following = b'\x88\x40', b'\x88\x41', b'\x88\x42'
        fixed = {first: left + b'\x81\x40' + tail, second: following}
        rom = bytearray(original)
        manifest, stats = repoint_messages(
            rom, original, fixable=lambda a: True, fixed_bytes=fixed.__getitem__,
            fit_level_dlg=lambda a: 6, decode_text=lambda raw: '문장',
            cell_width=lambda a: len(fixed[a]), slots={},
            line_index={first: (2, '첫째'), second: (2, '둘째')}, table_offsets=[],
            extra_messages={msg: [site]}, free_start=0xA3D000, free_end=0xA40000,
            line_layouts={first: (left, tail)},
            page_reflows={msg: (first, second, left, tail + b'\x81\x40' + following)})
        self.assertEqual(stats['relocated'], 1)
        expected = b'\x0a\x09' + left + b'\x72\x0a\x09' + tail + b'\x81\x40' + following + b'\x6b\x0a\0'
        self.assertEqual(rom[0xA3D000:0xA3D000 + len(expected)], expected)

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
