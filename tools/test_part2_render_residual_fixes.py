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
from dialogue_repoint import (SeamDecisionError, apply_seam_spaces, find_seams, inplace_seam_spaces,
                              jp_context, load_seam_decisions, seam_after, seam_decision,
                              unseen_seam_decisions)

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


def table_for(msg, seams, decision='space', source=b''):
    table = {}
    for seam in seams:
        jp_prev, jp_next = jp_context(source, seam['wait_ordinal'])
        table[(msg, seam['wait_ordinal'])] = {
            'prev_word': seam['prev_word'], 'next_word': seam['next_word'], 'before': seam['context'],
            'after': seam_after(seam['context'], decision), 'jp_prev': jp_prev or '', 'jp_next': jp_next or '',
            'decision': decision, 'reason': 'test'}
    return table


class SeamTests(unittest.TestCase):
    def setUp(self):
        self.hangul = {code: syl for syl, code in codes().items()}

    def test_padded_seam_is_found(self):
        seams = find_seams(enc('몸에') + b'  w' + enc('혹시'), self.hangul)
        self.assertEqual(len(seams), 1)
        self.assertEqual((seams[0]['pads'], seams[0]['prev_word'], seams[0]['next_word'],
                          seams[0]['wait_ordinal']), (2, '몸에', '혹시', 0))

    def test_reviewed_table_covers_cited_regressions(self):
        table = load_seam_decisions()
        self.assertEqual(len(table), 321)
        by_words = {}
        for row in table.values():
            by_words.setdefault((row['prev_word'], row['next_word']), set()).add(row['decision'])
        self.assertEqual(by_words[('이제', '이')], {'space'})        # 이제 이 땅은
        self.assertEqual(by_words[('잠깐', '이')], {'space'})        # 잠깐 이 자식
        self.assertEqual(by_words[('대기를', '골라')], {'space'})    # 대기를 골라
        self.assertEqual(by_words[('탄약', '과')], {'join'})         # 탄약과
        self.assertEqual(by_words[('연료', '가')], {'join'})
        self.assertTrue(all(row['reason'].strip() for row in table.values()))
        self.assertEqual({row['decision'] for row in table.values()}, {'space', 'join', 'defer'})

    def test_missing_or_drifted_row_fails(self):
        seam = find_seams(enc('몸에') + b'  w' + enc('혹시'), self.hangul)[0]
        with self.assertRaises(SeamDecisionError):
            seam_decision({}, 0xA00000, seam, b'')
        table = table_for(0xA00000, [seam])
        table[(0xA00000, 0)]['next_word'] = '만약'
        with self.assertRaises(SeamDecisionError):
            seam_decision(table, 0xA00000, seam, b'')

    def test_context_drift_invalidates_row(self):
        source = 'これで'.encode('shift_jis') + b'w' + 'この土地は'.encode('shift_jis')
        reviewed = enc('이제') + b'  w' + enc('이') + b'\x81\x40' + enc('땅은')
        table = table_for(0xA00000, find_seams(reviewed, self.hangul), source=source)
        self.assertEqual(seam_decision(table, 0xA00000, find_seams(reviewed, self.hangul)[0], source), 'space')
        # Same adjacent words, different role of 이 (이 -> particle): the row is stale.
        drifted = enc('이제') + b'  w' + enc('이') + b'\x81\x40' + enc('끝이다')
        with self.assertRaisesRegex(SeamDecisionError, 'context changed'):
            seam_decision(table, 0xA00000, find_seams(drifted, self.hangul)[0], source)
        # Japanese source drift also invalidates it.
        other = 'これで'.encode('shift_jis') + b'w' + 'あの町は'.encode('shift_jis')
        with self.assertRaisesRegex(SeamDecisionError, 'context changed'):
            seam_decision(table, 0xA00000, find_seams(reviewed, self.hangul)[0], other)
        # A tampered after-text is rejected too.
        table[(0xA00000, 0)]['after'] = table[(0xA00000, 0)]['before']
        with self.assertRaisesRegex(SeamDecisionError, 'after-text'):
            seam_decision(table, 0xA00000, find_seams(reviewed, self.hangul)[0], source)

    def test_unvisited_rows_are_reported(self):
        seam = find_seams(enc('몸에') + b'  w' + enc('혹시'), self.hangul)[0]
        table = table_for(0xA00000, [seam])
        self.assertEqual(unseen_seam_decisions(table), [(0xA00000, 0)])
        seam_decision(table, 0xA00000, seam, b'')
        self.assertEqual(unseen_seam_decisions(table), [])

    def test_inplace_applies_only_table_and_shares_row_budget(self):
        part = enc('가' * 7)
        current = part + b'  w' + part + b'  w' + part
        seams = find_seams(current, self.hangul)
        table = table_for(0xA00000, seams)
        new, records = inplace_seam_spaces(current, 0xA00000, table, self.hangul, b'')
        self.assertEqual([r['action'] for r in records], ['inserted', 'row_full'])
        self.assertEqual(new.count(b'\x81\x40'), 1)
        self.assertEqual(len(new), len(current))
        join = table_for(0xA00000, seams, 'join')
        same, records = inplace_seam_spaces(current, 0xA00000, join, self.hangul, b'')
        self.assertEqual(same, current)
        self.assertEqual([r['action'] for r in records], ['join', 'join'])

    def test_apply_inserts_fullwidth_space_without_touching_controls(self):
        pieces = [['gap', b'r', b'r'], ['text', enc('마을에서'), b''], ['gap', b'w', b'w'],
                  ['text', enc('조금'), b''], ['gap', b'k\x00', b'k\x00']]
        seams = find_seams(b''.join(p[1] for p in pieces), self.hangul)
        fixed, _ = apply_seam_spaces(pieces, 0xA00000, table_for(0xA00000, seams), self.hangul, b'')
        self.assertEqual(fixed, 1)
        self.assertEqual(pieces[1][1], enc('마을에서') + b'\x81\x40')
        self.assertEqual([p[1] for p in pieces if p[0] == 'gap'], [b'r', b'w', b'k\x00'])

    def test_apply_message_leading_exclamation(self):
        pieces = [['gap', b'\x81\x49w', b'\x81\x49w'], ['text', enc('기다려'), b''], ['gap', b'\x00', b'\x00']]
        seams = find_seams(b''.join(p[1] for p in pieces), self.hangul)
        self.assertEqual(seams[0]['prev_word'], '！')
        fixed, _ = apply_seam_spaces(pieces, 0xA00000, table_for(0xA00000, seams), self.hangul, b'')
        self.assertEqual(fixed, 1)
        self.assertEqual(pieces[1][1], b'\x81\x40' + enc('기다려'))
        self.assertEqual(pieces[0][1], b'\x81\x49w')

    def test_apply_space_that_overflows_the_row_fails(self):
        pieces = [['text', enc('가' * 21), b''], ['gap', b'w', b'w'], ['text', enc('다음'), b'']]
        seams = find_seams(b''.join(p[1] for p in pieces), self.hangul)
        with self.assertRaises(SeamDecisionError):
            apply_seam_spaces(pieces, 0xA00000, table_for(0xA00000, seams), self.hangul, b'')
        pieces = [['text', enc('가' * 21), b''], ['gap', b'w', b'w'], ['text', enc('다음'), b'']]
        self.assertEqual(apply_seam_spaces(pieces, 0xA00000, table_for(0xA00000, seams, 'defer'),
                                           self.hangul, b'')[0], 0)


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
        # Per variant only the old lettering and the new glyph/outline change.
        glyph, outline = labels.move_label_pixels(font)
        allowed = set(labels.OLD_LABEL) | glyph | outline
        for k in range(labels.MOVE_COUNT):
            first = labels.MOVE_FIRST + 8 * k
            for y in range(16):
                for x in range(32):
                    t, px, py = labels._sprite_px(buf, first, 4, x, y)
                    new, old = labels._get(buf, t, px, py), labels._get(data, t, px, py)
                    if (x, y) not in allowed:
                        self.assertEqual(new, old, (k, x, y))
                    elif (x, y) in glyph:
                        self.assertEqual(new, 1)
                    elif (x, y) in outline:
                        self.assertEqual(new, 0xF)
                    else:
                        self.assertEqual(new, 0)   # old lettering cleared, no plate
        self.assertEqual(len(layout[2]['variants']), 8)
        # Tiles outside the three label ranges are untouched.
        touched = {8, 9, 14, 15, 16, 17} | set(range(labels.MOVE_FIRST, labels.MOVE_FIRST + 64))
        for t in range(82):
            if t not in touched:
                self.assertEqual(buf[t * 32:(t + 1) * 32], data[t * 32:(t + 1) * 32], t)
        self.assertLessEqual(len(lz77_compress_optimal(bytes(buf), vram_safe=True)), consumed)
        with self.assertRaises(AssertionError):
            labels.patch(buf, font)   # already patched: source hash guard

    def test_movement_label_approval_rejects_extra_icon_overwrite(self):
        from bdf import load_bdf
        from lz77_scan import lz77_decompress
        import part1_production_info_labels as labels
        data, _ = lz77_decompress(ORIG.read_bytes(), 0xBC7C00)
        font, _ = load_bdf(os.path.join(builder.BASE, 'reference/fonts/Galmuri7.bdf'))
        approval = labels.load_approval()
        self.assertIn('approved by coordinator 2026-10-07', approval['note'])
        clean = bytearray(data)
        labels.check_move_approval(labels.render_move_labels(clean, font), approval)
        # An icon pixel under the new glyph that the approval does not list.
        glyph, outline = labels.move_label_pixels(font)
        first = labels.MOVE_FIRST
        spot = next((x, y) for x, y in sorted(glyph | outline) if (x, y) not in labels.OLD_LABEL
                    and labels._get(data, *labels._sprite_px(data, first, 4, x, y)) == 0)
        tampered = bytearray(data)
        labels._put(tampered, *labels._sprite_px(tampered, first, 4, *spot), 5)
        with self.assertRaisesRegex(AssertionError, 'approved exception'):
            labels.check_move_approval(labels.render_move_labels(tampered, font), approval)
        # Changed output bytes with the same covered set also fail.
        report = labels.render_move_labels(bytearray(data), font)
        report[3]['result_sha256'] = '0' * 64
        with self.assertRaisesRegex(AssertionError, 'approved exception'):
            labels.check_move_approval(report, approval)

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
