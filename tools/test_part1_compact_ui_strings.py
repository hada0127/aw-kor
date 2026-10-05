"""Static checks for the Part 1 compact glyph-bank labels (sweep C1-C8, F5, F8).

Optional full-ROM check: COMPACT_UI_ROM=<built rom> python3 -m unittest test_part1_compact_ui_strings
"""
import collections
import json
import os
import struct
import unittest
from pathlib import Path

import build_korean_full as builder
import part1_compact_ui_strings as M
from render_galmuri_8x16 import render_char

ROOT = Path(builder.BASE)


def load_syllables():
    return {k: int(v, 16) for k, v in json.loads((ROOT / 'data/syllable_to_code_2350.json').read_text()).items()}


class CompactUiStringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.chdir(ROOT)   # render_char loads its BDF relative to the repository
        cls.original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        cls.syl = load_syllables()

    def compact_rom(self):
        rom = bytearray(self.original)
        builder.patch_part2_ui_kanji_glyphs(rom, self.original)
        builder.patch_part2_ui_context_tokens(rom)
        # The full build writes the rule bank with reserved codes (ADDRESS_TEXT_OVERRIDES).
        text = builder.ADDRESS_TEXT_OVERRIDES[0xD83138]
        self.assertTrue(text.startswith('0123456789'))
        # (encode_text expands 장군 to 사령관+space; the shipped bank uses 0x8140 there)
        payload = self.original[0xD83138:0xD83138 + 20] + M.encode_spec(
            text[10:].replace('장군', '사령관　'), self.syl)
        rom[0xD83138:0xD83138 + len(payload)] = payload
        return rom

    def test_specs_fit_their_slots_without_single_bytes(self):
        for address, slot, spec, expected, _, _, _ in M.STRINGS:
            if spec is None:
                continue
            raw = M.encode_spec(spec, self.syl)
            self.assertLessEqual(len(raw), slot, hex(address))
            self.assertEqual(len(raw) % 2, 0, hex(address))
        for address, size, spec in M.APPENDS:
            raw = bytes(self.original[address:address + size]) if spec is None else M.encode_spec(spec, self.syl)
            self.assertLessEqual(len(raw), size, hex(address))
            self.assertTrue(all(b >= 0x81 for b in raw[0::2]), hex(address))

    def test_preload_lists_cover_their_consumers(self):
        # 0xB8322C is the only bank of the transfer screen; 0xB8319C feeds the link status rows.
        transfer = set(M._codes(M.encode_spec(dict((a, s) for a, _, s in M.APPENDS)[0xB8322C], self.syl)))
        for address in (0xB83254, 0xB83268):
            spec = next(row[2] for row in M.STRINGS if row[0] == address)
            for code in M._codes(M.encode_spec(spec, self.syl)):
                self.assertIn(code, transfer, hex(address))
        status = set(M._codes(M.encode_spec(dict((a, s) for a, _, s in M.APPENDS)[0xB8319C], self.syl)))
        for word in ('미접속', '준비중', '접속중', '에러'):
            for code in M._codes(M.encode_spec(word, self.syl)):
                self.assertIn(code, status, word)

    def test_connector_placeholders_are_unused_and_exclusive(self):
        owned = {slot for slots in builder.NAME_GRID_SLOTS.values() for slot in slots}
        table = builder._kanji_table_slots(self.original)
        used = collections.Counter(s for pos in range(*M.KANJI_TABLE, 6)
                                   for s in struct.unpack_from('<HH', self.original, pos + 2))
        reserved = set(self.syl.values())
        texts = (ROOT / 'data/translation_for_import.csv').read_text(encoding='utf-8')
        for ch in M.CONNECTORS:
            top, bottom = table[builder._sjis_code(ch)]
            self.assertFalse({top, bottom} & owned, ch)
            self.assertEqual((used[top], used[bottom]), (1, 1), ch)
            self.assertNotIn(ch, builder.PART2_UI_KANJI_GLYPH_SUBS)
            self.assertNotIn(builder._sjis_code(ch), reserved)
            self.assertNotIn(ch, texts)
        # The native connectors really lost their top tile to the name grid.
        self.assertIn(M._symbol_slot(self.original, 0x81A8, 0), owned)

    def test_patch_writes_only_declared_bytes_and_decodes(self):
        rom = self.compact_rom()
        before = bytes(rom)
        rows = M.patch(rom, self.original, self.syl, builder.NAME_GRID_SLOTS.values())
        report = M.verify(rom, self.original, self.syl, builder.PART2_UI_KANJI_GLYPH_SUBS, render_char,
                          written_only=True)
        self.assertTrue(report)
        for address, expected, shown, groups, advisory in report:
            self.assertEqual(shown, expected, hex(address))
        allowed = set()
        for address, size, *_ in rows:
            allowed.update(range(address, address + size))
        table = builder._kanji_table_slots(self.original)
        for ch in M.CONNECTORS:
            for slot in table[builder._sjis_code(ch)]:
                allowed.update(range(M.FONT_FILE + slot * 32, M.FONT_FILE + slot * 32 + 32))
        changed = [a for a, (x, y) in enumerate(zip(rom, before)) if x != y]
        self.assertTrue(changed)
        self.assertEqual([hex(a) for a in changed if a not in allowed], [])
        # Connector glyphs equal the original (pre name-grid) tree tiles.
        tiles = M.connector_tiles(self.original)
        for ch, (top_tile, bottom_tile) in tiles.items():
            top, bottom = table[builder._sjis_code(ch)]
            self.assertEqual((M._tile(rom, top), M._tile(rom, bottom)), (top_tile, bottom_tile))
        # Unit-list banks preload ｜奇材 instead of pads (context tokens).
        for start in (0xD82D48, 0xD82E1C):
            codes = M.dictionary_codes(rom, start)
            for ch in '｜奇材':
                self.assertIn(ch.encode('shift_jis'), codes)

    def test_status_page_switch_keeps_tab_and_army_cells(self):
        # Native screen (candidate3): 戦闘状況/部隊 drawn on the battle-info page read
        # '존전군상'/'산부' after RIGHT because 존 sat inside the shared prefix of D82F30.
        rom = self.compact_rom()
        M.patch(rom, self.original, self.syl, builder.NAME_GRID_SLOTS.values())
        checked = M.verify_page_persistence(rom, self.original, self.syl,
                                            builder.PART2_UI_KANJI_GLYPH_SUBS, render_char)
        self.assertEqual(checked, len(M.PAGE_PERSISTENT) * len(M.PAGE_GROUPS) ** 2)
        for address, _, after in M.DICTIONARY_EDITS:
            if address in range(0xD82F30, 0xD82F30 + 2 * M.SHARED_PREFIX_CODES):
                self.assertEqual(address, 0xD82F30 + 2 * (M.SHARED_PREFIX_CODES - 1), after)
        broken = bytearray(rom)
        broken[0xD82F70:0xD82F72] = M.encode_spec('존', self.syl)   # candidate3 placement
        with self.assertRaises(AssertionError):
            M.verify_page_persistence(broken, self.original, self.syl,
                                      builder.PART2_UI_KANJI_GLYPH_SUBS, render_char)
        M_prefix = M.SHARED_PREFIX_CODES
        try:
            M.SHARED_PREFIX_CODES = 0   # bypass the byte-prefix guard: the switch decode alone must catch it
            with self.assertRaisesRegex(AssertionError, '존전군상'):
                M.verify_page_persistence(broken, self.original, self.syl,
                                          builder.PART2_UI_KANJI_GLYPH_SUBS, render_char)
        finally:
            M.SHARED_PREFIX_CODES = M_prefix

    def test_existence_aliases_do_not_show_jang(self):
        # S4: 存 shows 장 (保存); 生存 must use the reserved 존 cell instead.
        self.assertEqual(builder.PART2_UI_KANJI_GLYPH_SUBS['存'], '장')
        spec = next(row[2] for row in M.STRINGS if row[0] == 0xDF8B8A)
        self.assertNotIn('存', spec)
        self.assertIn('존', spec)

    @unittest.skipUnless(os.environ.get('COMPACT_UI_ROM'), 'set COMPACT_UI_ROM to a built ROM')
    def test_built_rom(self):
        rom = Path(os.environ['COMPACT_UI_ROM']).read_bytes()
        report = M.verify(rom, self.original, self.syl, builder.PART2_UI_KANJI_GLYPH_SUBS, render_char)
        self.assertEqual(len(report), len(M.STRINGS))


class EncodeFitVisibleGuardTests(unittest.TestCase):
    """F5: a visible source must not encode to an empty (space-only) payload."""

    @classmethod
    def setUpClass(cls):
        cls.syl = load_syllables()

    def test_punctuation_only_lines_keep_their_source_punctuation(self):
        # Review N1: the B-team rows must ship exactly their native fullwidth dots.
        for address, text, slot, native in ((0xDCFCCA, '・・・・・', 10, '・・・・・'),
                                            (0xDCA57A, '・・・・・.', 12, '・・・・・。'),
                                            (0xE08562, '・・・・・.', 12, '・・・・・。'),
                                            (0xE0EEDE, '・・・・・', 10, '・・・・・')):
            enc, _ = builder.encode_fit(text, slot, self.syl, collections.Counter(), address)
            self.assertEqual(enc, native.encode('shift_jis'), hex(address))
        enc, _ = builder.encode_fit('・・・・・', 4, self.syl, collections.Counter(), 0xDCFCCA)
        self.assertEqual(enc, '・・'.encode('shift_jis'))   # longest dot run that fits

    def test_intentional_blank_rows_stay_blank(self):
        for address, slot in ((0xD92833, 14), (0xD9609A, 14), (0xDF6D3A, 10)):
            enc, _ = builder.encode_fit('', slot, self.syl, collections.Counter(), address)
            self.assertEqual(enc, b'', hex(address))

    def test_noise_rows_with_unmapped_kanji_are_not_rewritten(self):
        # Extraction-noise rows (graphics data) must not gain '...' bytes.
        enc, _ = builder.encode_fit('劔勦劔劔劔劔劔劔畿', 27, self.syl, collections.Counter(), 0x8AE1C8)
        self.assertNotIn(b'.', enc)
        self.assertNotIn(b'\x81\x45', enc)

    def test_no_room_for_ellipsis_fails_the_fit(self):
        enc, level = builder.encode_fit('・・・・・', 1, self.syl, collections.Counter(), 0xDCFCCA)
        self.assertIsNone(enc)
        self.assertEqual(level, 99)


class Part2DamageLabelTests(unittest.TestCase):
    def test_part2_bubble_draws_pihae_and_keeps_frame(self):
        from lz77_scan import lz77_decompress
        original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        rom = bytearray(original)
        self.assertEqual(builder.patch_part2_damage_label_obj(rom), 1)
        self.assertEqual(rom[0x3376B0:0x3376B4], original[0x3376B0:0x3376B4])
        old, consumed = lz77_decompress(original, 0x4827C0)
        new, _ = lz77_decompress(rom, 0x4827C0)
        self.assertEqual(len(new), len(old))
        # Only the 16 label tiles change, and inside them only rows 3..10.
        self.assertEqual(new[:0x280], old[:0x280])
        self.assertEqual(new[0x280 + 16 * 32:], old[0x280 + 16 * 32:])

        def pixels(data):
            px = [[0] * 32 for _ in range(32)]
            for t in range(16):
                tile = data[0x280 + t * 32:0x280 + t * 32 + 32]
                for r in range(8):
                    for c in range(8):
                        b = tile[r * 4 + c // 2]
                        px[(t // 4) * 8 + r][(t % 4) * 8 + c] = (b >> 4) if c & 1 else b & 15
            return px
        a, b = pixels(old), pixels(new)
        for y in range(32):
            if not 3 <= y <= 10:
                self.assertEqual(a[y], b[y], y)
        ink = sum(row.count(7) for row in b[3:11])
        self.assertGreater(ink, 20)
        self.assertEqual({v for row in b[3:11] for v in row[1:31]}, {1, 7})

    def test_part1_bubble_keeps_its_behaviour_under_the_new_name(self):
        self.assertFalse(hasattr(builder, 'patch_part2_damage_forecast_label_obj'))
        original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        rom = bytearray(original)
        self.assertEqual(builder.patch_part1_damage_forecast_label_obj(rom), 1)
        self.assertNotEqual(rom[0xBD4FBC:0xBD4FBC + 447], original[0xBD4FBC:0xBD4FBC + 447])


if __name__ == '__main__':
    unittest.main()
