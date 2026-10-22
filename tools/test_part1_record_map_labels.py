from pathlib import Path
import json
import struct
import unittest

import part1_record_map_labels as patcher
import build_korean_full as builder


class RecordMapGateTests(unittest.TestCase):
    def setUp(self):
        self.original = bytes(patcher.ROW_STATE_GATE + len(patcher.ROW_STATE_GATE_CODE))
        self.rom = bytearray(self.original)
        fixture = Path(__file__).with_name('fixtures') / 'part1_compact_map_hook_a290f200.hex'
        self.rom[patcher.HOOK:patcher.HOOK + patcher.HOOK_SIZE] = bytes.fromhex(fixture.read_text())

    def test_patch_is_confined_and_verifies(self):
        before = bytes(self.rom)
        result = patcher.patch(self.rom, self.original)
        patcher.verify(self.rom)
        self.assertEqual(result['hidden_state_rejected'], '0x03000F80')
        self.assertIn('0x030010A0', result['states'])
        for address, raw in patcher.WRITES:
            self.assertEqual(bytes(self.rom[address:address + len(raw)]), raw)
        allowed = {i for address, raw in patcher.WRITES for i in range(address, address + len(raw))}
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(before, self.rom))))

    def test_old_hook_change_is_rejected_atomically(self):
        self.rom[patcher.HOOK + 2] ^= 1
        before = bytes(self.rom)
        with self.assertRaisesRegex(AssertionError, 'layout changed'):
            patcher.patch(self.rom, self.original)
        self.assertEqual(self.rom, before)

    def test_dynamic_table_extent_is_checked_without_pin_to_one_translation(self):
        for value in (0x08F30800, 0x08F31F88, 0x08F32008, 0x08F31E81):
            with self.subTest(value=hex(value)):
                struct.pack_into('<I', self.rom, patcher.HOOK + patcher.TABLE_END_OFFSET, value)
                before = bytes(self.rom)
                with self.assertRaisesRegex(AssertionError, 'table extent'):
                    patcher.patch(self.rom, self.original)
                self.assertEqual(self.rom, before)
        struct.pack_into('<I', self.rom, patcher.HOOK + patcher.TABLE_END_OFFSET, 0x08F31E88)
        patcher.patch(self.rom, self.original)
        patcher.verify(self.rom)

    def test_occupied_rom_gap_and_changed_original_are_rejected(self):
        for address in (patcher.GATE, patcher.ROW_GATE, patcher.SOURCE_PTR,
                        patcher.SOURCE_GATE, patcher.ROW_STATE_GATE):
            probe = address + (1 if address == patcher.SOURCE_PTR else 5)
            self.rom[probe] = 1
            before = bytes(self.rom)
            with self.assertRaisesRegex(AssertionError, 'pristine'):
                patcher.patch(self.rom, self.original)
            self.assertEqual(self.rom, before)
            self.rom[probe] = 0
        original = bytearray(self.original)
        original[patcher.GATE] = 1
        with self.assertRaisesRegex(AssertionError, 'pristine'):
            patcher.patch(self.rom, original)

    def test_later_overwrite_is_rejected(self):
        patcher.patch(self.rom, self.original)
        self.rom[patcher.GATE + 3] ^= 1
        with self.assertRaisesRegex(AssertionError, 'overwritten'):
            patcher.verify(self.rom)

    def test_all_a5_link_source_cells_fit_the_table(self):
        start, end = builder.PART1_MAP_LABEL_A5_SOURCE_RANGE
        rom = bytearray(max(builder.PART1_MAP_LABEL_SOURCE_RANGE[1],
                            builder.PART1_EDITOR_CAPTION_SOURCE_RANGE[1]))
        for address in range(start, end, 2):
            rom[address:address + 2] = b'\x88\x40'
        glyphs = {ch: {'top': 1, 'bot': 2} for ch in '미공개반'}
        entries = builder._part1_map_label_entries(rom, glyphs, {'반': 0x8840})
        sources = {source for source, _, _ in entries}
        self.assertEqual({0x08000000 + address for address in range(start, end, 2)}
                         - sources, set())
        self.assertLessEqual(builder.PART1_MAP_LABEL_TABLE_FILE + len(entries) * 8,
                             patcher.SOURCE_GATE)

    def test_unlocked_link_page_tile_budget(self):
        glyph_tiles = (builder.PART1_MAP_LABEL_LIST_ROWS * builder.PART1_MAP_LABEL_LIST_COLUMNS
                       + builder.PART1_MAP_LABEL_CATEGORY_COLUMNS) * 2
        self.assertEqual(glyph_tiles, 112)
        self.assertEqual(builder.PART1_MAP_LABEL_PRIVATE_TILE_BASE + glyph_tiles,
                         builder.PART1_MAP_LABEL_PRIVATE_TILE_END)
        self.assertLessEqual(builder.PART1_MAP_LABEL_PRIVATE_TILE_END, 0x180)
        hook = builder.PART1_MAP_LABEL_HOOK_TEMPLATE
        self.assertEqual(hook[0x7c:0x80], bytes.fromhex('c046c046'))  # row * 8
        self.assertEqual(hook[0x8c:0x8e], bytes.fromhex('3030'))  # page1 + 48 cells
        self.assertEqual(hook[0x104:0x108], struct.pack('<I', builder.PART1_MAP_LABEL_PRIVATE_TILE_BASE))
        self.assertIn(bytes.fromhex('0829'), patcher.ROW_CODE)  # eight visible columns

    def test_all_link_map_names_and_category_titles_fit_private_page(self):
        overrides = json.loads((Path(__file__).parents[1] / 'data' /
                                'dialogue_overrides.json').read_text(encoding='utf-8'))
        # The B8 link-map block covers the four category lists. One page draws
        # six rows plus its title; each text cell consumes two private tiles.
        names = {int(address, 16): value for address, value in overrides.items()
                 if 0xB82024 <= int(address, 16) < 0xB827C0}
        self.assertGreaterEqual(len(names), 115)
        titles = [overrides[address] for address in
                  ('0x00B81D00', '0x00B81CE0', '0x00B81CF0', '0x00B81CD0')
                  if address in overrides]
        self.assertEqual(len(titles), 4)
        for address, value in names.items():
            with self.subTest(address=hex(address)):
                self.assertLessEqual(len(value), builder.PART1_MAP_LABEL_LIST_COLUMNS)
        for title in titles:
            with self.subTest(title=title):
                self.assertLessEqual(len(title), builder.PART1_MAP_LABEL_CATEGORY_COLUMNS)
        worst_case_tiles = (builder.PART1_MAP_LABEL_LIST_ROWS *
                            max(map(len, names.values())) + max(map(len, titles))) * 2
        self.assertLessEqual(worst_case_tiles,
                             builder.PART1_MAP_LABEL_PRIVATE_TILE_END -
                             builder.PART1_MAP_LABEL_PRIVATE_TILE_BASE)


if __name__ == '__main__':
    unittest.main()
