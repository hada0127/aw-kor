"""Regression tests for the 2026-10-07 render fixes (CO quotes, seams, labels)."""
import collections
import hashlib
import json
import os
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_korean_full as builder
from dialogue_regions import (PART2_CO_QUOTE_RANGE, PART2_SYSTEM_PROMPT_RANGE,
                              is_part2_story_address)
from dialogue_repoint import (apply_seam_spaces, find_seams, inplace_seam_spaces, seam_is_bound,
                              source_context)

ORIG = Path(builder.P.ROM)


def codes():
    return {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}


def enc(text):
    table = codes()
    return b''.join(table[ch].to_bytes(2, 'big') for ch in text)


class RangeTests(unittest.TestCase):
    def test_co_quote_range_matches_native_table(self):
        original = ORIG.read_bytes()
        lo, hi = PART2_CO_QUOTE_RANGE
        first = struct.unpack_from('<I', original, 0xA384CC)[0] - 0x08000000
        last = struct.unpack_from('<I', original, 0xA386DC)[0] - 0x08000000
        help_first = struct.unpack_from('<I', original, 0xA386E0)[0] - 0x08000000
        self.assertEqual(first, lo)
        self.assertEqual(help_first, hi)
        self.assertTrue(lo < last < hi)
        self.assertEqual(original[hi - 1], 0)
        for address in (0xA30E40, 0xA308B0, 0xA313FC):
            self.assertTrue(is_part2_story_address(address))
        for address in (0xA2FE58, 0xA31444, 0xA31500):
            self.assertFalse(is_part2_story_address(address))

    def test_system_prompt_range_excludes_pair_ui_and_banners(self):
        original = ORIG.read_bytes()
        targets = [struct.unpack_from('<I', original, o)[0] - 0x08000000
                   for o in range(0xA389E0, 0xA38A0C, 4)]
        self.assertEqual(targets[0], 0xA34B6C)
        self.assertEqual(targets[1], PART2_SYSTEM_PROMPT_RANGE[0])
        self.assertEqual(targets[-1], PART2_SYSTEM_PROMPT_RANGE[1])
        self.assertFalse(is_part2_story_address(0xA34B6C))
        self.assertTrue(is_part2_story_address(0xA34BD2))
        self.assertTrue(is_part2_story_address(0xA34CE8))
        self.assertFalse(is_part2_story_address(0xA34D18))

    def test_co_quote_ellipsis_and_prompt_question_are_fullwidth(self):
        table = codes()
        snake, _ = builder.encode_fit('큭큭큭...아픈 건 처음뿐이에요..', 46, table,
                                      collections.Counter(), 0xA30E40)
        self.assertIn(b'\x81\x45' * 3, snake)
        self.assertNotIn(b'.', snake)
        prompt, _ = builder.encode_fit('덮어쓸까요?', 16, table, collections.Counter(), 0xA34BD2)
        self.assertTrue(prompt.endswith(b'\x81\x48'))


class SeamTests(unittest.TestCase):
    def setUp(self):
        self.hangul = {code: syl for syl, code in codes().items()}

    def test_padded_seam_is_found_and_not_bound(self):
        data = enc('몸에') + b'  w' + enc('혹시')
        seams = find_seams(data, self.hangul)
        self.assertEqual(len(seams), 1)
        self.assertEqual(seams[0]['pads'], 2)
        self.assertEqual(seams[0]['next_word'], '혹시')
        self.assertIsNone(seam_is_bound(seams[0], None, None))   # needs source
        self.assertIs(seam_is_bound(seams[0], 'お前の身に', 'もしものこと'), False)

    def test_particle_seam_is_bound(self):
        data = enc('탄약') + b'w' + enc('과')
        seam = find_seams(data, self.hangul)[0]
        self.assertTrue(seam_is_bound(seam, None, None))

    def test_verb_seam_uses_japanese_source(self):
        data = enc('직접공격') + b'w' + enc('하는')
        seam = find_seams(data, self.hangul)[0]
        self.assertIsNone(seam_is_bound(seam, None, None))
        self.assertTrue(seam_is_bound(seam, '直接攻撃', 'するユニット'))
        self.assertFalse(seam_is_bound(seam, 'よし！', 'やってみる'))

    def test_negative_fixtures_never_insert(self):
        cases = [
            (enc('연료') + b'w' + enc('이'), None, None),                 # subject particle
            (enc('연료') + b'w' + enc('가없다'), '燃料', 'がなくなる'),   # unspaced particle run
            (enc('점령') + b'w' + enc('명령이'), '「占領」', 'というコマンド'),
            (enc('탄약') + b'w' + enc('과'), '主砲の弾', 'や'),
            (enc('보병') + b'w' + enc('나'), '歩兵', 'か'),
            (enc('혹시') + b'w' + enc('몰라'), None, None),               # no source: keep
        ]
        for data, jp_prev, jp_next in cases:
            seam = find_seams(data, self.hangul)[0]
            self.assertIsNot(seam_is_bound(seam, jp_prev, jp_next), False, data)
        for word in ('이', '가', '은', '는', '을', '를', '의', '에', '로', '와', '과', '도', '만', '이야', '이다'):
            seam = find_seams(enc('연료') + b'w' + enc(word), self.hangul)[0]
            self.assertTrue(seam_is_bound(seam, None, None), word)

    def test_dot_before_wait_is_not_a_word_char(self):
        seam = find_seams(enc('군은') + b'w' + enc('성가신'), self.hangul)[0]
        self.assertFalse(seam_is_bound(seam, '軍・・・', 'やっかいな'))

    def test_inplace_row_budget_is_shared(self):
        jp = ('一' * 5 + '、').encode('shift_jis')
        source = jp + b'w' + jp + b'w' + jp
        # 3 x 7 glyphs + 2 seams: 42 half-cells before, room for one space only
        part = enc('가' * 7)
        current = part + b'  w' + part + b'  w' + part
        self.assertEqual(len(find_seams(current, self.hangul)), 2)
        new, records = inplace_seam_spaces(current, source, self.hangul)
        self.assertEqual([r['action'] for r in records], ['inserted', 'row_full'])
        self.assertEqual(new.count(b'\x81\x40'), 1)
        self.assertEqual(len(new), len(current))

    def test_after_exclamation_never_bound(self):
        data = enc('좋아') + b'\x81\x49w' + enc('해')
        seam = find_seams(data, self.hangul)[0]
        self.assertFalse(seam_is_bound(seam, '', 'して'))

    def test_source_context_aligns_controls(self):
        original = 'お前の身に'.encode('shift_jis') + b'w' + 'もしもの'.encode('shift_jis')
        current = enc('몸에') + b'  w' + enc('혹시')
        seam = find_seams(current, self.hangul)[0]
        self.assertEqual(source_context(original, current, seam), ('お前の身に', 'もしもの'))

    def test_apply_inserts_fullwidth_space_without_touching_controls(self):
        pieces = [['gap', b'r', b'r'], ['text', enc('마을에서'), b''], ['gap', b'w', b'w'],
                  ['text', enc('조금'), b''], ['gap', b'k\x00', b'k\x00']]
        fixed, wide = apply_seam_spaces(pieces, self.hangul)
        self.assertEqual((fixed, wide), (1, 0))
        self.assertEqual(pieces[1][1], enc('마을에서') + b'\x81\x40')
        self.assertEqual([p[1] for p in pieces if p[0] == 'gap'], [b'r', b'w', b'k\x00'])

    def test_apply_respects_row_capacity(self):
        long = enc('가' * 21)
        pieces = [['text', long, b''], ['gap', b'w', b'w'], ['text', enc('다음'), b'']]
        self.assertEqual(apply_seam_spaces(pieces, self.hangul), (0, 1))


class LabelAndTextTests(unittest.TestCase):
    def test_production_info_labels(self):
        from bdf import load_bdf
        from lz77_compress import lz77_compress_optimal
        from lz77_scan import lz77_decompress
        import part1_production_info_labels as labels
        original = ORIG.read_bytes()
        data, consumed = lz77_decompress(original, 0xBC7C00)
        buf = bytearray(data)
        font, _ = load_bdf(os.path.join(builder.BASE, 'reference/fonts/Galmuri7.bdf'))
        before = labels.region_hashes(buf)
        layout = labels.patch(buf, font)
        self.assertEqual([e['text'] for e in layout], ['연료', '색적', '이동'])
        after = labels.region_hashes(buf)
        self.assertTrue(all(before[k] != after[k] for k in before))
        # Every pixel of all 8 movement sprites outside the approved box is unchanged.
        for k in range(labels.MOVE_COUNT):
            first = labels.MOVE_FIRST + 8 * k
            for y in range(16):
                for x in range(32):
                    if labels._in_box(x, y):
                        continue
                    t, px, py = labels._sprite_px(buf, first, 4, x, y)
                    self.assertEqual(labels._get(buf, t, px, py), labels._get(data, t, px, py), (k, x, y))
        # Tiles outside the three label ranges are untouched.
        touched = {8, 9, 14, 15, 16, 17} | set(range(labels.MOVE_FIRST, labels.MOVE_FIRST + 64))
        for t in range(82):
            if t not in touched:
                self.assertEqual(buf[t * 32:(t + 1) * 32], data[t * 32:(t + 1) * 32], t)
        self.assertLessEqual(len(lz77_compress_optimal(bytes(buf), vram_safe=True)), consumed)
        with self.assertRaises(AssertionError):
            labels.patch(buf, font)   # already patched: source hash guard

    def test_part1_can_i_use_keeps_question_mark(self):
        self.assertTrue(builder.ADDRESS_TEXT_OVERRIDES[0xDD07E1].endswith('?'))

    def test_part2_meaning_repairs(self):
        o = builder.ADDRESS_TEXT_OVERRIDES
        self.assertEqual(o[0xA20949], '함락될 곳이 아니에요.')
        self.assertEqual(o[0xA21B7A], '어떻게 쓰지?')
        self.assertEqual(o[0xA21E2E], '내버려 둘 수는 없다.')
        self.assertEqual(o[0xA21E4B], '저 마을은')
        bteam = json.loads(Path(builder.BASE, 'data', 'bteam_addresses.json').read_text())
        bteam = {int(a, 16) for a in (bteam.get('addresses', bteam) if isinstance(bteam, dict) else bteam)}
        for address in (0xA20949, 0xA21B7A, 0xA21E2E, 0xA21E4B, 0xA227EA, 0xA2ACE4, 0xA2ACFF, 0xDD07E1):
            self.assertNotIn(address, bteam)


if __name__ == '__main__':
    unittest.main()
