"""Korean-style 、/。 glyph images (P1 FONT_BASE slots and P2 A3 nodes)."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_korean_full as builder  # noqa: E402
from dialogue_pixel_layout import Glyphs  # noqa: E402

SOURCE = Path(__file__).resolve().parents[1] / 'original' / 'Game Boy Wars Advance 1+2 (Japan).gba'
FONT = 0xB974D0


def ink(rom, code, game):
    bitmap = Glyphs(bytes(rom)).bitmap(code.to_bytes(2, 'big'), game)
    return {(x, y): v for y, row in enumerate(bitmap) for x, v in enumerate(row) if v}


class KoreanPunctGlyphTest(unittest.TestCase):
    def setUp(self):
        if not SOURCE.exists():
            self.skipTest('source ROM absent')
        self.original = SOURCE.read_bytes()
        # Same order as the build: the name grid moves t/u off the shared
        # bottoms, then the native punctuation tiles are restored.
        self.rom = bytearray(self.original)
        builder.patch_name_grid(self.rom)
        builder.restore_symbol_glyphs(self.rom, self.original)

    def test_native_sharers_are_only_the_late_digit_entries(self):
        # The native table also points 0xB806D4/0xB806D6 at slots 285/286.
        # Only those (rewritten by the late digit pass) are tolerated.
        owners = builder._korean_punct_symbol_slot_owners(self.original)
        self.assertEqual(owners[286], [0xB8028E, 0xB806D6])
        self.assertEqual(owners[285], [0xB80290, 0xB806D4])
        tolerated = builder._korean_punct_digit_table_entries()
        self.assertEqual({0xB806D4, 0xB806D6} & tolerated, {0xB806D4, 0xB806D6})
        self.assertEqual(len(tolerated), 20)

    def test_writes_exact_bytes_only_at_owned_locations(self):
        before = bytes(self.rom)
        self.assertEqual(builder.patch_korean_punct_glyphs(self.rom, self.original), 2)
        comma = bytes(16) + bytes.fromhex('000a0000a0000000') + bytes(8)
        period = bytes(16) + bytes.fromhex('a00a0000a00a0000') + bytes(8)
        self.assertEqual(self.rom[FONT + 286 * 32:FONT + 287 * 32], comma)
        self.assertEqual(self.rom[FONT + 285 * 32:FONT + 286 * 32], period)
        self.assertEqual(self.rom[0x807BE8 + 6:0x807BE8 + 70], bytes(32) + comma)
        self.assertEqual(self.rom[0x807D50 + 6:0x807D50 + 70], bytes(32) + period)
        changed = [i for i in range(len(before)) if before[i] != self.rom[i]]
        allowed = set(range(FONT + 285 * 32, FONT + 287 * 32))
        allowed |= set(range(0x807BE8 + 6, 0x807BE8 + 70))
        allowed |= set(range(0x807D50 + 6, 0x807D50 + 70))
        self.assertTrue(changed)
        self.assertLessEqual(set(changed), allowed)
        # Shared blank top, A3 headers/pads, 0x8145 ・ and its A3 node untouched.
        self.assertEqual(self.rom[FONT + 95 * 32:FONT + 96 * 32], bytes(32))
        for node in (0x807BE8, 0x807D50, 0x808188):
            self.assertEqual(self.rom[node:node + 6], self.original[node:node + 6])
            self.assertEqual(self.rom[node + 70:node + 72], self.original[node + 70:node + 72])
        for slot in (677, 693):
            self.assertEqual(self.rom[FONT + slot * 32:FONT + slot * 32 + 32],
                             self.original[FONT + slot * 32:FONT + slot * 32 + 32])
        self.assertEqual(self.rom[0x808188:0x808188 + 72], self.original[0x808188:0x808188 + 72])

    def test_rendered_pixels_match_in_both_renderers(self):
        builder.patch_korean_punct_glyphs(self.rom, self.original)
        # Final verification is strict: it fails until the digit pass has
        # moved the native sharers off 285/286, then passes.
        with self.assertRaises(AssertionError):
            builder.verify_korean_punct_glyphs(self.rom, self.original)
        builder.patch_fullwidth_digit_glyphs(self.rom)
        for game in ('p1', 'p2'):
            self.assertEqual(ink(self.rom, 0x8141, game), {(2, 12): 10, (1, 13): 10})
            self.assertEqual(ink(self.rom, 0x8142, game),
                             {(x, y): 10 for x in (1, 2) for y in (12, 13)})
            self.assertEqual(ink(self.rom, 0x8145, game), ink(self.original, 0x8145, game))
        builder.verify_korean_punct_glyphs(self.rom, self.original)

    def test_slots_and_nodes_are_not_shared(self):
        builder.patch_fullwidth_digit_glyphs(self.rom)
        owners = builder._korean_punct_symbol_slot_owners(self.rom)
        self.assertEqual(owners[286], [0xB8028E])
        self.assertEqual(owners[285], [0xB80290])
        self.assertIn(0xB8027E, owners[95])
        self.assertIn(0xB80280, owners[95])
        a3 = builder._korean_punct_a3_owners(self.rom)
        self.assertEqual(a3[0x807BE8], [(0x41, 0x81)])
        self.assertEqual(a3[0x807D50], [(0x42, 0x81)])

    def test_rejects_shared_slot_or_changed_source(self):
        # Another code pointing at slot 285 must stop the patch (0x8143's
        # bottom is outside the tolerated late digit entries).
        shared = bytearray(self.rom)
        index = builder._symbol_table_index(0x8143)
        struct.pack_into('<H', shared, 0xB8027C + (index + 8) * 2, 285)
        with self.assertRaises(AssertionError):
            builder.patch_korean_punct_glyphs(shared, self.original)
        # A modified source tile or A3 node must stop it too.
        for offset in (FONT + 286 * 32 + 16, 0x807D50 + 56):
            with self.subTest(offset=hex(offset)):
                rom = bytearray(self.rom)
                rom[offset] ^= 1
                with self.assertRaises(AssertionError):
                    builder.patch_korean_punct_glyphs(rom, self.original)

    def test_qa_consumers_accept_redrawn_tiles_only(self):
        from part1_compact_ui_strings import decode_cell
        from qa_part1_dialogue_punctuation import glyph_state
        builder.patch_korean_punct_glyphs(self.rom, self.original)
        builder.patch_fullwidth_digit_glyphs(self.rom)
        for code, ch in ((0x8141, '、'), (0x8142, '。')):
            pair = code.to_bytes(2, 'big')
            self.assertTrue(glyph_state(self.rom, self.original, code)['restored'])
            self.assertEqual(decode_cell(self.rom, self.original, pair, {}, None, {}, {}), ch)
            # Native tile still decodes; any other drawing does not.
            self.assertEqual(decode_cell(bytearray(self.original), self.original, pair, {}, None, {}, {}), ch)
            broken = bytearray(self.rom)
            broken[FONT + builder.KOREAN_PUNCT_P1_BOTTOM[code] * 32 + 18] ^= 0x10
            self.assertEqual(decode_cell(broken, self.original, pair, {}, None, {}, {}), '?')
            self.assertFalse(glyph_state(broken, self.original, code)['restored'])
        self.assertTrue(glyph_state(self.rom, self.original, 0x8145)['restored'])

    def test_final_verification_catches_later_writes(self):
        builder.patch_korean_punct_glyphs(self.rom, self.original)
        builder.patch_fullwidth_digit_glyphs(self.rom)
        for offset in (FONT + 285 * 32 + 16, 0x807BE8 + 54, 0x807BE8 + 5, FONT + 95 * 32):
            with self.subTest(offset=hex(offset)):
                self.rom[offset] ^= 1
                with self.assertRaises((AssertionError, ValueError)):
                    builder.verify_korean_punct_glyphs(self.rom, self.original)
                self.rom[offset] ^= 1
        builder.verify_korean_punct_glyphs(self.rom, self.original)


class EllipsisGlyphTest(unittest.TestCase):
    """fixB J (plan_C E3): one-cell 「…」 0x8163 glyph and the run rule."""

    def setUp(self):
        if not SOURCE.exists():
            self.skipTest('source ROM absent')
        self.original = SOURCE.read_bytes()
        self.rom = bytearray(self.original)
        builder.patch_name_grid(self.rom)
        builder.restore_symbol_glyphs(self.rom, self.original)

    def test_glyph_written_only_at_owned_locations(self):
        before = bytes(self.rom)
        self.assertEqual(builder.patch_ellipsis_glyph(self.rom, self.original), 1)
        tile = bytes.fromhex('000a0a0a') + bytes(28)
        slot = builder.ELLIPSIS_P1_BOTTOM_SLOT
        self.assertEqual(self.rom[FONT + slot * 32:FONT + slot * 32 + 32], tile)
        for table in (0xB8027C, 0x38F9E4):
            self.assertEqual(struct.unpack_from('<H', self.rom, table + 67 * 2)[0], 95)
            self.assertEqual(struct.unpack_from('<H', self.rom, table + 75 * 2)[0], slot)
        node = 0xFD00A0
        self.assertEqual(self.rom[node:node + 4], self.original[0x807680 + 0x63 * 4:0x807680 + 0x63 * 4 + 4])
        self.assertEqual(self.rom[node + 4:node + 6], b'\x81\x08')
        self.assertEqual(self.rom[node + 6:node + 70], bytes(32) + tile)
        self.assertEqual(struct.unpack_from('<I', self.rom, 0x807680 + 0x63 * 4)[0], 0x08FD00A0)
        allowed = set(range(FONT + slot * 32, FONT + slot * 32 + 32))
        allowed |= {0xB8027C + 150, 0xB8027C + 151, 0x38F9E4 + 150, 0x38F9E4 + 151}
        allowed |= set(range(node, node + 72)) | set(range(0x807680 + 0x63 * 4, 0x807680 + 0x63 * 4 + 4))
        changed = {i for i in range(len(before)) if before[i] != self.rom[i]}
        self.assertTrue(changed)
        self.assertLessEqual(changed, allowed)
        # Shared blank, middle dot 0x8145 (P1 slots + A3 node) untouched.
        self.assertEqual(self.rom[FONT + 95 * 32:FONT + 96 * 32], bytes(32))
        self.assertEqual(self.rom[0x808188:0x808188 + 72], self.original[0x808188:0x808188 + 72])
        for game in ('p1', 'p2'):
            self.assertEqual(ink(self.rom, 0x8163, game), {(2, 8): 10, (4, 8): 10, (6, 8): 10})
            self.assertEqual(ink(self.rom, 0x8145, game), ink(self.original, 0x8145, game))
        builder.verify_ellipsis_glyph(self.rom, self.original)

    def test_rejects_occupied_slot_node_or_table(self):
        for mutate in (lambda r: r.__setitem__(FONT + 255 * 32 + 3, 1),
                       lambda r: struct.pack_into('<H', r, 0xB8027C + 75 * 2, 96),
                       lambda r: struct.pack_into('<H', r, 0x38F9E4 + 75 * 2, 96),
                       lambda r: r.__setitem__(0xFD00A0 + 10, 1)):
            rom = bytearray(self.rom)
            mutate(rom)
            with self.assertRaises(AssertionError):
                builder.patch_ellipsis_glyph(rom, self.original)

    def test_precompaction_restore_checks_the_exact_transform(self):
        # plan_C J decision (a): byte-pinning verifiers see the logged
        # pre-compaction bytes; the logged transform must be exact.
        import korean_punct_glyphs as K
        dot, gly = b'\x81\x45', b'\x88\x9f'
        before = gly + dot * 3 + gly
        after, segments = K.compact_ellipsis_bytes(before)
        self.assertEqual(segments, [(0, len(before))])
        rom = bytearray(64)
        rom[8:8 + len(before)] = after
        entry = [8, len(before), len(before), after.hex(), None, '…', None, K.COMPACT_WRITER,
                 {'before_hex': before.hex()}]
        other = [0, 2, 2, '0000', None, None, None, 'other']
        restored, kept = K.restore_precompaction(bytes(rom), [other, entry])
        self.assertEqual(restored[8:8 + len(before)], before)
        self.assertEqual(kept, [other])
        for broken in (entry[:8],
                       entry[:8] + [{'before_hex': (gly + dot * 2 + gly + b'  ').hex()}],
                       entry[:8] + [{'before_hex': before[:-2].hex()}]):
            with self.assertRaises(ValueError):
                K.restore_precompaction(bytes(rom), [broken])
        changed = bytearray(rom); changed[10] ^= 1
        with self.assertRaises(ValueError):
            K.restore_precompaction(bytes(changed), [entry])
        with self.assertRaises(ValueError):
            K.restore_precompaction(bytes(rom), [entry, entry])

    def test_run_rule_bytes(self):
        import korean_punct_glyphs as k
        dot, ell = b'\x81\x45', b'\x81\x63'
        han = b'\x88\x87'
        for n, cells in ((1, 0), (2, 0), (3, 1), (4, 1), (5, 1), (6, 2), (7, 2)):
            raw = b'\x0a\x09' + han + dot * n + han + b'\x72\x0a\x00'
            new, segs = k.compact_ellipsis_bytes(raw)
            self.assertEqual(len(new), len(raw))
            if cells:
                body = han + ell * cells + han
                self.assertEqual(new, b'\x0a\x09' + body + b'\x20' * (len(raw) - 5 - len(body)) + b'\x72\x0a\x00')
                self.assertEqual(segs, [(2, len(raw) - 5)])
            else:
                self.assertEqual((new, segs), (raw, []))
        # Controls and other segments never move; a 0x45 trail of another code is not a dot.
        raw = b'\x88\x81\x45\x81\x45\x81\x45\x6b' + dot * 3 + b'\x00'
        new, segs = k.compact_ellipsis_bytes(raw)
        # 88 81 | 45 | 81 45 | 81 45 | 6b: only two real dots before the control.
        self.assertEqual(new, raw[:8] + ell + b'\x20' * 4 + b'\x00')
        self.assertEqual(k.compact_ellipsis_text('가・나 ・・ 다・・・라 ・・・・・ ・・・・・・'),
                         '가・나 ・・ 다…라 … ……')


if __name__ == '__main__':
    unittest.main()
