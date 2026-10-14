#!/usr/bin/env python3
"""Unit + mutation tests for the link-play client font stage and its QA gate."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import link_client_font as L  # noqa: E402
import qa_link_client_font as Q  # noqa: E402

ORIG = Q.DEFAULT_ORIG


@unittest.skipUnless(os.path.exists(ORIG), 'original ROM not available')
class LinkClientFontTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(ORIG, 'rb') as stream:
            cls.orig = stream.read()
        cls.codes = L.load_codes()
        cls.rom = bytearray(cls.orig)
        cls.report = L.apply(cls.rom, cls.orig, None, cls.codes)

    def fresh(self):
        return bytearray(self.rom)

    def test_clean_build_passes_gate(self):
        problems, summary = Q.check(self.rom, self.orig, self.codes)
        self.assertEqual(problems, [])
        for row in summary:
            self.assertLessEqual(row['codes'], L.MAX_CODES)

    def test_capacity_and_sentinel(self):
        for spec in L.SPECS:
            table = L.decode_table(self.rom, spec)
            self.assertLessEqual(len(table), 59)
            self.assertIn(L.PUNCT['▼'], table)
            self.assertIn(L.PUNCT['　'], table)
            end = spec.table + 2 * L.TABLE_HALFWORDS
            self.assertEqual(self.rom[spec.table + 2 * len(table):end],
                             L.SENTINEL * (L.TABLE_HALFWORDS - len(table)))

    def test_yesno_keeps_option_columns(self):
        for spec in L.SPECS:
            item = next(x for x in spec.live if x[0] == 'yesno')
            self.assertEqual(item[4], '　예　　　아뇨')
            self.assertEqual(item[4].index('예'), item[3].index('はい'))
            self.assertEqual(item[4].index('아뇨'), item[3].index('いいえ'))
            self.assertLessEqual(len(item[4]), len(item[3]))

    def test_mutation_drop_table_entry(self):
        rom = self.fresh()
        spec = L.SPECS[0]
        table = L.decode_table(rom, spec)
        code = self.codes['패']
        index = table.index(code)
        rest = table[:index] + table[index + 1:]
        rom[spec.table:spec.table + 120] = b''.join(rest) + L.SENTINEL * (60 - len(rest))
        problems, _ = Q.check(rom, self.orig, self.codes)
        self.assertTrue(any('not in table' in p for p in problems), problems)

    def test_mutation_halfwidth_bang(self):
        rom = self.fresh()
        spec = L.SPECS[1]
        item = next(x for x in spec.live if x[0] == 'defeat_red')
        enc = L.encode(item[4], self.codes)
        pos = enc.index(L.PUNCT['！'])
        rom[item[1] + pos:item[1] + pos + 2] = b'!\x00'
        problems, _ = Q.check(rom, self.orig, self.codes)
        self.assertTrue(any('halfwidth byte 0x21' in p for p in problems), problems)
        with self.assertRaises(L.LinkClientFontError):
            L.encode('패배!', self.codes)

    def test_mutation_grow_past_59(self):
        spec = L.SPECS[0]
        extra = '각간갇갈감갑값갓강갖같갚개객갠갤갬갭갯'
        grown = L.Spec(spec.name, spec.rom, spec.size, spec.layout, spec.table_ew, spec.sheet_ew,
                       spec.live + (('unit_none', 0x9295B0, 8, 'なし', '없음', 'test'),))
        order = L.glyph_order(grown, extra)
        self.assertGreater(len(order), 59)
        orig_glyph_order = L.glyph_order
        try:
            L.glyph_order = lambda s, e='': orig_glyph_order(s, extra)
            with self.assertRaises(L.LinkClientFontError):
                L.build_program(self.orig, grown, self.codes)
        finally:
            L.glyph_order = orig_glyph_order

    def _cells(self, rom, spec, index):
        cell = spec.cell(index)
        return ((spec.sheet + cell * 32, spec.sheet + cell * 32 + 32),
                (spec.sheet + (cell + spec.row) * 32, spec.sheet + (cell + spec.row) * 32 + 32))

    def test_mutation_swap_glyph_cells(self):
        rom = self.fresh()
        spec = L.SPECS[0]
        table = L.decode_table(rom, spec)
        a, b = table.index(self.codes['패']), table.index(self.codes['배'])
        for (sa, ea), (sb, eb) in zip(self._cells(rom, spec, a), self._cells(rom, spec, b)):
            rom[sa:ea], rom[sb:eb] = bytes(rom[sb:eb]), bytes(rom[sa:ea])
        problems, _ = Q.check(rom, self.orig, self.codes)
        self.assertTrue(any('glyph pixels mismatch' in p for p in problems), problems)

    def test_mutation_ink_reverted_to_9(self):
        rom = self.fresh()
        spec = L.SPECS[1]
        table = L.decode_table(rom, spec)
        index = table.index(self.codes['패'])
        for s, e in self._cells(rom, spec, index):
            rom[s:e] = bytes((0x9 if b & 15 == 0xA else b & 15) | ((0x9 if b >> 4 == 0xA else b >> 4) << 4)
                             for b in rom[s:e])
        problems, _ = Q.check(rom, self.orig, self.codes)
        self.assertTrue(any('glyph pixels mismatch' in p for p in problems), problems)

    def test_line_width_guard(self):
        spec = L.SPECS[0]
        item = ('label_end', 0x929660, 8, '終了', '종료종료', 'test')
        with self.assertRaises(L.LinkClientFontError):
            L.check_live_item(self.orig, spec, item)

    def test_control_sequence_guard(self):
        spec = L.SPECS[0]
        item = next(x for x in spec.live if x[0] == 'surrender_confirm')
        bad = item[:4] + (item[4].replace('wQn', 'Qn'),) + item[5:]
        with self.assertRaises(L.LinkClientFontError):
            L.check_live_item(self.orig, spec, bad)

    def test_outside_byte_and_dead_copy_detected(self):
        rom = self.fresh()
        rom[0x90DC7C + 0x100] ^= 1           # P2 program code, outside owned/asset
        rom[0x97AE40] ^= 1                    # dead charset table
        problems, _ = Q.check(rom, self.orig, self.codes)
        self.assertTrue(any('outside table/sheet/live/asset' in p for p in problems), problems)
        self.assertTrue(any('0x97AE40' in p for p in problems), problems)

    def test_restores_text_writes_in_client_images(self):
        rom = bytearray(self.orig)
        rom[0x929244:0x929248] = b'\x88\x40\x88\x40'     # stray Korean in P2 program
        rom[0x961ECC:0x961ED0] = b'\x88\x40\x88\x40'     # stray Korean in dead copy
        log = [[0x929244, 4, 4, '88408840', 0, '가가', 0, 'import-csv'],
               [0xA00000, 4, 4, '88408840', 0, '가가', 0, 'import-csv']]
        report = L.apply(rom, self.orig, log, self.codes)
        self.assertEqual(rom[0x929244:0x929248], self.orig[0x929244:0x929248])
        self.assertEqual(rom[0x961ECC:0x961ED0], self.orig[0x961ECC:0x961ED0])
        self.assertEqual(len(log), 1)
        self.assertEqual(report['write_log_dropped'], 1)

    def test_final_rom_if_configured(self):
        path = os.environ.get('AW_TEST_ROM')
        if not path:
            self.skipTest('AW_TEST_ROM not set')
        self.assertTrue(os.path.exists(path), f'AW_TEST_ROM does not exist: {path}')
        with open(path, 'rb') as stream:
            rom = stream.read()
        if L.decode_table(rom, L.SPECS[0]) == L.original_table(self.orig, L.SPECS[0]):
            self.skipTest('AW_TEST_ROM predates the link client font stage')
        problems, _ = Q.check(rom, self.orig, self.codes)
        self.assertEqual(problems, [])


if __name__ == '__main__':
    unittest.main()
