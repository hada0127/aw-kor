"""Negative fixtures for the final protected-row byte and wording gate."""
import unittest

from build_korean_full import (LINK_WELCOME_SENTENCES, validate_bteam_payload,
                               bteam_retained_equal, verify_link_welcome_sentences)
from qa_integrity_map import load_syl
from qa_text_fit import is_korean_display_row


class RestorationBytesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codes = load_syl()
        cls.ga = next(code.to_bytes(2, 'big') for code, ch in cls.codes.items() if ch == '가')

    def test_rejects_halfwidth_kana(self):
        with self.assertRaisesRegex(AssertionError, 'invalid text byte'):
            validate_bteam_payload(self.ga + b'\xa6', self.codes, 0xA34F98)

    def test_rejects_invalid_and_incomplete_bytes(self):
        for suffix in (b'\xff', b'\x81', b'\x81\x7f', b'\x00A', b'A'):
            with self.subTest(suffix=suffix), self.assertRaises(AssertionError):
                validate_bteam_payload(self.ga + suffix, self.codes, 0xA34F98)

    def test_rejects_ordinary_sjis_kana_and_kanji(self):
        for suffix in ('ア'.encode('shift_jis'), '漢'.encode('shift_jis')):
            with self.subTest(suffix=suffix), self.assertRaisesRegex(AssertionError, 'ordinary SJIS'):
                validate_bteam_payload(self.ga + suffix, self.codes, 0xA34F98)
        with self.assertRaisesRegex(AssertionError, 'unsupported SJIS glyph'):
            validate_bteam_payload(self.ga + 'Ω'.encode('shift_jis'), self.codes, 0xA34F98)
        validate_bteam_payload(self.ga + '・ー！'.encode('shift_jis'), self.codes, 0xA34F98)

    def test_compact_exception_is_address_pinned(self):
        pad = self.ga + '倶'.encode('shift_jis') * 2
        validate_bteam_payload(pad, self.codes, 0xDF8BBA, compact=True,
                               compact_expected=pad)
        with self.assertRaisesRegex(AssertionError, 'differ from verified writer'):
            validate_bteam_payload(pad + b'X', self.codes, 0xDF8BBA, compact=True,
                                   compact_expected=pad)
        with self.assertRaisesRegex(AssertionError, 'Unreviewed compact'):
            validate_bteam_payload(pad, self.codes, 0xA34F98, compact=True,
                                   compact_expected=pad)
        self.assertFalse(bteam_retained_equal('부대', '부대倶倶', 0xA34F98, compact=True))

    def test_residual_width_and_text_equality(self):
        with self.assertRaisesRegex(AssertionError, '44 half-cells'):
            validate_bteam_payload(self.ga * 23, self.codes, 0xA34F98)
        self.assertFalse(bteam_retained_equal('친구들이 모이면 시작 버튼 눌러줘!',
                                               '친구들이 모이면 시작 시작을 눌러▯▯▯', 0xA34F98))
        self.assertFalse(bteam_retained_equal('가 나', '가 나', 0xA34F98))
        self.assertTrue(bteam_retained_equal('가 나', '가　나', 0xA34F98))
        with self.assertRaisesRegex(AssertionError, 'interior halfwidth space'):
            validate_bteam_payload(self.ga + b' ' + self.ga, self.codes, 0xA34F98)
        self.assertTrue(bteam_retained_equal('골라!', '골라！', 0xA34F98))

    def test_listed_wide_residual_is_exact(self):
        for cells, accepted in ((66, True), (65, False), (67, False)):
            payload = self.ga * (cells // 2) + (b'1' if cells % 2 else b'')
            with self.subTest(cells=cells):
                if accepted:
                    validate_bteam_payload(payload, self.codes, 0xD9009E)
                else:
                    with self.assertRaisesRegex(AssertionError, '44 half-cells'):
                        validate_bteam_payload(payload, self.codes, 0xD9009E)

    def test_mixed_display_is_non_korean(self):
        for value in ('가ア', '가漢', '가▯', '가ﾊ'):
            with self.subTest(value=value):
                self.assertFalse(is_korean_display_row(value))
        self.assertTrue(is_korean_display_row('가！'))
        self.assertTrue(is_korean_display_row('가・・・'))

    def test_sibling_sentence_overlap_is_rejected(self):
        rom = bytearray(max(LINK_WELCOME_SENTENCES) + 48)
        rows = {}
        for address in LINK_WELCOME_SENTENCES:
            rom[address:address + 46] = self.ga * 2 + b' ' * 42
            rows[address] = [address, 46, 4, (self.ga * 2).hex(), 0x20,
                             '가가', 0, 'import-csv']
        verify_link_welcome_sentences(rom, rows)
        for address in LINK_WELCOME_SENTENCES:
            for offset in (2, 4, 46, 47):
                with self.subTest(address=hex(address), offset=offset):
                    old = rom[address + offset]
                    rom[address + offset] = old ^ 1
                    with self.assertRaisesRegex(AssertionError, 'overwritten'):
                        verify_link_welcome_sentences(rom, rows)
                    rom[address + offset] = old


if __name__ == '__main__':
    unittest.main()
