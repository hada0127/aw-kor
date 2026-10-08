"""Round-2 residual restorations (2026-10-07): consumer-safe encodings per consumer."""
import csv
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qa_bteam_drift as drift

ROOT = Path(__file__).resolve().parents[1]
ORIG = (ROOT / 'original' / 'Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
BASE = json.loads((ROOT / 'data' / 'bteam_baseline.json').read_text(encoding='utf-8'))['overrides']
RESIDUALS = {int(r['address'], 16): r for r in csv.DictReader(
    (ROOT / 'data' / 'bteam_round2_residuals.tsv').open(encoding='utf-8'), delimiter='\t')}
PINS = {int(k, 16) for k in json.loads((ROOT / 'data' / 'bteam_round2_active_pins.json').read_text())}
SLOTS = {int(r['address'], 16): int(r['length']) for r in csv.DictReader(
    (ROOT / 'data' / 'game_wars_found_texts.csv').open(encoding='utf-8'))
    if r['address'].startswith('0x') and r['length'].isdigit()}
BATTLE_MENU_RESTORED = {0xB82D2A: '룰', 0xB82D36: '사령관', 0xB82D6A: '항복한다',
                        0xB82D82: '애니메 무', 0xB82DB6: '배경음 무', 0xB82DC6: '배경음 유'}


def strip_marks(text):
    return ''.join(ch for ch in text if '가' <= ch <= '힣')


class OriginalGlyphConsumerTests(unittest.TestCase):
    def test_restored_rows_left_the_residual_list_and_pins(self):
        restored = drift.ROUND2_ORIGINAL_GLYPH_ROWS | set(BATTLE_MENU_RESTORED) | {0xB81B14}
        self.assertFalse(restored & set(RESIDUALS))
        self.assertFalse(restored & PINS)
        self.assertEqual(len(RESIDUALS), 118)

    def test_original_rows_used_fullwidth_glyphs(self):
        # The consumer drew these exact SJIS punctuation codes in the original game.
        for address in drift.ROUND2_ORIGINAL_GLYPH_ROWS:
            source = ORIG[address:address + SLOTS[address]]
            text = source.split(b'\0')[0].decode('shift_jis', 'replace')
            self.assertFalse(any(0x21 <= b <= 0x2F for b in source.split(b'\0')[0]
                                 if b < 0x80), hex(address))
            self.assertTrue(any(ch in text for ch in '！？、。'), hex(address))

    def test_expected_form_keeps_every_word_and_uses_no_ascii_punctuation(self):
        for address in drift.ROUND2_ORIGINAL_GLYPH_ROWS:
            baseline = BASE[f'0x{address:08X}']
            expected = drift.display_equivalent(baseline, address)
            self.assertEqual(strip_marks(expected), strip_marks(baseline), hex(address))
            self.assertFalse(any(ch in expected for ch in '!?,.- '), (hex(address), expected))
            self.assertEqual(expected.count('！') + expected.count('？'),
                             baseline.count('!') + baseline.count('?'), hex(address))
            # Every expected character is a fullwidth cell (2 half-cells).
            self.assertLessEqual(len(expected) * 2, 44, hex(address))

    def test_examples_per_consumer(self):
        self.assertEqual(drift.display_equivalent('맥스의 약점!?', 0xB81EE0), '맥스의　약점！？')
        self.assertEqual(drift.display_equivalent('본부가 2개 이상이고,각 군에', 0xA2C720),
                         '본부가　２개　이상이고、각　군에')
        self.assertEqual(drift.display_equivalent('이 정도려나-?', 0xB83EB8), '이　정도려나ー？')
        # Rows outside the table keep the previous expectation.
        self.assertEqual(drift.display_equivalent('그럼,어디.', 0xB83C70), '그럼,어디.')


class CompactConsumerTests(unittest.TestCase):
    def test_battle_menu_labels_carry_the_baseline_words(self):
        import build_korean_full as builder
        labels = {a: ko for a, _, ko in builder.PART1_BATTLE_MENU_LABELS}
        for address, text in BATTLE_MENU_RESTORED.items():
            self.assertEqual(labels[address], text)
            self.assertEqual(BASE[f'0x{address:08X}'], text)

    def test_unit_info_no_equipment_uses_preloaded_aliases(self):
        import part1_compact_ui_strings as compact
        row = next(r for r in compact.STRINGS if r[0] == 0xB81B14)
        self.assertEqual((row[2], row[3]), ('箕装備', '미장비'))
        self.assertEqual(BASE['0x00B81B14'], '미장비')

    def test_status_and_rules_compact_rows(self):
        import build_korean_full as builder
        import part1_compact_ui_strings as compact
        strings = {r[0]: r for r in compact.STRINGS}
        appends = {a: spec for a, _, spec in compact.APPENDS}
        # 불참가: 가 comes from the 0xBE701C append whose か cell it replaces.
        self.assertEqual(strings[0xDF8BC6][2:4], ('不残가', '불참가'))
        self.assertEqual(appends[0xBE701C], '拠点全滅ふさん가？')
        self.assertEqual(len(compact.encode_spec(appends[0xBE701C], {'가': 0x8840})), 18)
        # 룰: the rules dictionary 0xD83138 preloads 룰 where it preloaded 규.
        self.assertEqual(strings[0xB839F0][2:4], ('룰　　', '룰'))
        self.assertTrue(builder.ADDRESS_TEXT_OVERRIDES[0xD83138].startswith('0123456789룰칙'))
        self.assertNotIn(0xDF8BC6, RESIDUALS)
        self.assertNotIn(0xB839F0, RESIDUALS)


if __name__ == '__main__':
    unittest.main()
