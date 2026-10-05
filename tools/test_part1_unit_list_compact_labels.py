import unittest
from pathlib import Path

import build_korean_full as builder
import part1_unit_list_compact_labels as U
from render_galmuri_8x16 import render_char


class UnitListCompactLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (Path(builder.BASE) / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def compact_rom(self):
        rom = bytearray(self.original)
        builder.patch_part2_ui_kanji_glyphs(rom, self.original)
        builder.patch_part2_ui_context_tokens(rom)
        return rom

    def test_names_render_korean_through_every_native_dictionary(self):
        rom = self.compact_rom()
        before = bytes(rom)
        rows = U.patch(rom, self.original)
        self.assertEqual(len(rows), len(U.COMPACT_NAMES))
        U.verify_semantics(rom, self.original, builder.PART2_UI_KANJI_GLYPH_SUBS, render_char)
        allowed = {a for a, slot, _, _ in U.payloads() for a in range(a, a + slot)}
        allowed |= {a + i for a, _, after in U.DICTIONARY_EDITS for i in range(len(after.encode('shift_jis')))}
        self.assertTrue(all(a in allowed for a, (x, y) in enumerate(zip(rom, before)) if x != y))
        # Infantry ammo uses the native two-cell infinite mark again.
        for ch in U.INFINITE_AMMO:
            code = ch.encode('shift_jis')
            for start in U.INFINITE_AMMO_DICTIONARIES:
                self.assertIn(code, U.dictionary_codes(rom, start))
        for _, address, _, placeholder, korean in U.COMPACT_NAMES:
            text = ''.join(builder.PART2_UI_KANJI_GLYPH_SUBS[c] for c in placeholder)
            self.assertEqual(text, korean)
            self.assertEqual(rom[address:address + len(placeholder) * 2], placeholder.encode('shift_jis'))

    def test_placeholder_glyph_slots_are_not_owned_by_name_grid(self):
        # The Part 1 name grid re-patches its FONT_BASE slots last (e.g. 航 top = slot 352),
        # so no glyph-sub key and no unit/ammo placeholder may share them.
        owned = {slot for slots in builder.NAME_GRID_SLOTS.values() for slot in slots}
        table = builder._kanji_table_slots(self.original)
        chars = (set(builder.PART2_UI_KANJI_GLYPH_SUBS) | set(''.join(row[3] for row in U.COMPACT_NAMES))
                 | set(U.INFINITE_AMMO))
        clashes = sorted(ch for ch in chars if set(table[builder._sjis_code(ch)]) & owned)
        self.assertEqual(clashes, [])
        self.assertEqual(builder.part2_ui_kanji_glyph_slot_clashes(self.original), [])

    def test_compact_dictionaries_carry_no_name_grid_owned_kanji_placeholders(self):
        rom = self.compact_rom()
        U.patch(rom, self.original)
        owned = {slot for slots in builder.NAME_GRID_SLOTS.values() for slot in slots}
        table = builder._kanji_table_slots(self.original)
        # 航/費 were placeholders; native 防御 (terrain dictionary) is rewritten to
        # reserved codes by the full build, so only build-written codes are checked there.
        retired = {ch.encode('shift_jis') for ch in '航費'}
        for start, end in ((0x805100, 0x805A24), (0xD82740, 0xD83100)):
            pos = start
            while pos < end:
                if rom[pos] == 0:
                    pos += 1
                    continue
                code = bytes(rom[pos:pos + 2])
                self.assertNotIn(code, retired, hex(pos))
                if code in table:
                    original_code = bytes(self.original[pos:pos + 2])
                    if code != original_code:  # placeholders written by the build
                        self.assertFalse(set(table[code]) & owned, hex(pos))
                pos += 2 if rom[pos] >= 0x81 else 1

    def test_final_glyph_guard_rejects_overwritten_sub(self):
        rom = self.compact_rom()
        self.assertEqual(builder.verify_part2_ui_kanji_glyphs(rom, self.original),
                         len(builder.PART2_UI_KANJI_GLYPH_SUBS))
        top, _ = builder._kanji_table_slots(self.original)[builder._sjis_code('佐')]
        rom[builder.P.FONT_FILE + top * 32] ^= 1
        with self.assertRaisesRegex(AssertionError, 'overwritten'):
            builder.verify_part2_ui_kanji_glyphs(rom, self.original)

    def test_shared_full_name_and_weapon_fields_are_covered(self):
        rom = self.compact_rom()
        U.patch(rom, self.original)
        U.verify_semantics(rom, self.original, builder.PART2_UI_KANJI_GLYPH_SUBS, render_char)
        for field, _, _ in U.SHARED_FIELDS:
            broken = bytearray(rom)
            broken[field] ^= 4
            with self.assertRaises(AssertionError):
                U.verify_semantics(broken, self.original, builder.PART2_UI_KANJI_GLYPH_SUBS, render_char)
        broken = bytearray(rom)
        broken[0xB819C8] = 0x81  # 路編砲 -> 路編 + junk
        with self.assertRaises(AssertionError):
            U.verify_semantics(broken, self.original, builder.PART2_UI_KANJI_GLYPH_SUBS, render_char)

    def test_asuka_and_cost_labels_use_safe_aliases(self):
        rom = self.compact_rom()
        subs = builder.PART2_UI_KANJI_GLYPH_SUBS
        for address in (0xD82C22, 0xD82CF2, 0xD830B6, 0x8054AE, 0x80557E, 0x805942):
            self.assertEqual(''.join(subs[c] for c in rom[address - 4:address + 2].decode('shift_jis')), '아스카')
        for address in (0xD82B8C, 0xD82C5A, 0xD82F08, 0xD82F94, 0xD83084,
                        0x805418, 0x8054E6, 0x805794, 0x805820, 0x805910):
            self.assertEqual(''.join(subs[c] for c in rom[address:address + 4].decode('shift_jis')), '비용')

    def test_reserved_korean_compact_name_is_rejected(self):
        rom = self.compact_rom()
        U.patch(rom, self.original)
        rom[0xB81A6C:0xB81A72] = bytes.fromhex('88648fc890b4')  # reserved-code 경전차
        with self.assertRaises(AssertionError):
            U.verify_semantics(rom, self.original, builder.PART2_UI_KANJI_GLYPH_SUBS, render_char)

    def test_infinite_ammo_glyph_alias_is_rejected(self):
        rom = self.compact_rom()
        U.patch(rom, self.original)
        top, _ = builder._kanji_table_slots(self.original)[0x96B2]
        rom[builder.P.FONT_FILE + top * 32:builder.P.FONT_FILE + top * 32 + 32] = render_char('유')[0]
        with self.assertRaisesRegex(AssertionError, 'infinite-ammo glyph'):
            U.verify_semantics(rom, self.original, builder.PART2_UI_KANJI_GLYPH_SUBS, render_char)

    def test_source_drift_and_late_writer_fail_closed(self):
        original = bytearray(self.original)
        original[0xB81A6C] ^= 1
        with self.assertRaises(AssertionError):
            U.patch(self.compact_rom(), original)
        rom = self.compact_rom()
        rom[0xD82E16] ^= 1
        with self.assertRaisesRegex(AssertionError, 'pre-patch'):
            U.patch(rom, self.original)
        rom = self.compact_rom()
        U.patch(rom, self.original)
        evidence = U.capture_regions(rom, self.original)
        U.verify_regions(rom, evidence)
        rom[0xB81840] ^= 1
        with self.assertRaisesRegex(AssertionError, 'overwritten'):
            U.verify_regions(rom, evidence)


if __name__ == '__main__':
    unittest.main()
