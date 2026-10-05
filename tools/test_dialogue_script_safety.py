"""Regression tests for Part 1 text/control collisions and merged script rows."""
import json
import tempfile
import collections
import ast
import re
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

import build_korean_full as builder
from dialogue_repoint import apply_script_span_ownership, repoint_messages, normalize_text_segment, text_segment_cells


class ScriptSafetyTests(unittest.TestCase):
    def test_observed_mission_boundaries_resolve_to_exact_protected_text(self):
        original = Path(builder.P.ROM).read_bytes()
        dialogue = json.loads((Path(builder.BASE) / 'data/dialogue_overrides.json').read_text())
        intents = builder.load_editor_override_intents(Path(builder.BASE) / 'data/editor_override_intents.json')
        _, members = builder.load_direct_script_metadata()
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        rows = (
            (0xA07B14, 0xA07B1E, 'コング様！', '콩 님!', 8, b'\x77'),
            (0xA07B1F, 0xA07B25, '　今、', ' 지금, ', 10, b'\x77'),
            (0xA07B94, 0xA07B9E, 'コング様、', '콩 님, ', 10, b'\x77'),
            (0xDC3C63, 0xDC3C71, 'さん、リョウ！', ' 사령관님, 료!', 18, b'\x72'),
            (0xDC3935, 0xDC3943, 'それから・・・', '그리고... ', 14, b'\x69'),
            (0xDC3944, 0xDC394C, 'シレイ、', ' 사령,', 8, b'\x72'),
            (0xDC39E8, 0xDC39F4, 'ばかりだな？', '얼마 안 됐지?', 16, b'\x6b'),
            (0xDC3AD2, 0xDC3ADC, 'あばよっ　', '잘 있어 ', 10, b'\x69'),
            (0xDC3ADD, 0xDC3AE5, 'シレイ！', ' 사령!', 8, b'\x6b'),
            (0xA0776C, 0xA07770, '今、', '지금, ', 8, b'\x77'),
            (0xA078F4, 0xA07900, '戦闘ヘリ隊、', '전투헬기대,', 12, b'\x77'),
            (0xA07901, 0xA0790B, 'いけます！', ' 갈 수 있습니다!', 20, b'\x6b'),
        )
        for address, end, japanese, text, size, control in rows:
            with self.subTest(address=hex(address)):
                key = f'0x{address:08X}'
                edited = dialogue.get(key)
                if (edited is not None and builder.ADDRESS_TEXT_OVERRIDES.get(address) == edited
                        and intents.get(key) == builder.editor_text_digest(edited)):
                    text = edited
                    size = len(builder.encode_full_fidelity(text, codes, collections.Counter(), address))
                self.assertEqual(original[address:end].decode('shift_jis'), japanese)
                self.assertEqual(original[end:end+1], control)
                self.assertEqual(builder.SCRIPT_PLAIN_OPERAND_SPANS[address], end)
                self.assertIn(address, builder.PLAYTHROUGH_REPAIR_ROWS)
                self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[address], text)
                self.assertEqual(builder.direct_script_override_text(address, end, members, dialogue), text)
                full = builder.encode_full_fidelity(text, codes, collections.Counter(), address)
                self.assertEqual(len(full), size)
                self.assertEqual(normalize_text_segment(full, True, address), full)
        self.assertEqual(dialogue['0x00A078F4'], builder.ADDRESS_TEXT_OVERRIDES[0xA078F4])

    def test_tank_info_preserves_price_and_connects_mobility_predicate(self):
        address, end = 0xDED20D, 0xDED223
        original = Path(builder.P.ROM).read_bytes()
        self.assertEqual(original[address:end].decode('shift_jis'), '安く、移動力があるため')
        self.assertEqual(original[end:end+3], b'\x72\x0a\x09')
        dialogue = json.loads((Path(builder.BASE) / 'data/dialogue_overrides.json').read_text())
        self.assertEqual(dialogue['0x00DED226'], '좋아서 다루기 쉽다.')
        text = builder.ADDRESS_TEXT_OVERRIDES[address]
        self.assertEqual(text, '가격도 싸고, 이동력이')
        _, members = builder.load_direct_script_metadata()
        self.assertEqual(builder.direct_script_override_text(address, end, members, dialogue), text)
        self.assertEqual(builder.SCRIPT_PLAIN_OPERAND_SPANS[address], end)
        self.assertIn(address, builder.PLAYTHROUGH_REPAIR_ROWS)
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        full = builder.encode_full_fidelity(text, codes, collections.Counter(), address)
        self.assertEqual(len(full), 24)
        self.assertGreater(len(full), end-address)
        self.assertEqual(normalize_text_segment(full, True, address), full)

    def test_air_mission_blurb_keeps_subject_and_native_a3_punctuation(self):
        address, end = 0xA01D41, 0xA01D5D
        original = Path(builder.P.ROM).read_bytes()
        self.assertEqual(original[address:end].decode('shift_jis'), '陸上部隊は撃破できるのか！？')
        self.assertEqual(original[end], 0)
        self.assertFalse(builder.in_region(builder.PAIR_RENDERER_REGIONS, address, end))
        self.assertTrue(builder.is_part2_story_address(address))
        self.assertIn(address, builder.PLAYTHROUGH_REPAIR_ROWS)
        self.assertEqual(builder.SCRIPT_PLAIN_OPERAND_SPANS[address], end)
        text = builder.ADDRESS_TEXT_OVERRIDES[address]
        self.assertEqual(text, '육상부대는 격파 가능할까!?')
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        full = builder.encode_full_fidelity(text, codes, collections.Counter(), address)
        self.assertEqual(len(full), 30)
        self.assertTrue(full.endswith(b'\x81\x49\x81\x48'))
        self.assertGreater(len(full), end-address)

    def test_mission6_kong_name_uses_unchanged_bteam_authority(self):
        address, end = 0xA07228, 0xA07232
        baseline = json.loads((Path(builder.BASE) / 'data/bteam_baseline.json').read_text())
        text = baseline['overrides'][f'0x{address:08X}']
        self.assertEqual(text, '콩 님,')
        self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[address], text)
        original = Path(builder.P.ROM).read_bytes()
        self.assertEqual(original[address:end].decode('shift_jis'), 'コング様、')
        self.assertEqual(original[end:end + 2], b'\x77\x72')
        self.assertEqual(builder.SCRIPT_PLAIN_OPERAND_SPANS[address], end)
        self.assertIn(address, builder.PLAYTHROUGH_REPAIR_ROWS)
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        full = builder.encode_full_fidelity(text, codes, collections.Counter(), address)
        self.assertEqual(len(full), 8)
        self.assertEqual(end-address-len(full), 2)
        self.assertEqual(builder.encode_fit(text, end-address, codes, collections.Counter(), address)[0], full)

    def test_rocket_info_keeps_spaces_around_highlighted_attack(self):
        original = Path(builder.P.ROM).read_bytes()
        self.assertEqual(original[0xDEDAC2:0xDEDAC8], b'\x33' + '攻撃'.encode('shift_jis') + b'\x30')
        self.assertEqual(original[0xDEDACE], 0x72)
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        for address, end, text in ((0xDEDABA, 0xDEDAC2, '육해에 '),
                                   (0xDEDAC8, 0xDEDACE, ' 가능')):
            self.assertEqual(builder.SCRIPT_PLAIN_OPERAND_SPANS[address], end)
            self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[address], text)
            self.assertIn(address, builder.PLAYTHROUGH_REPAIR_ROWS)
            full = builder.encode_full_fidelity(text, codes, collections.Counter(), address)
            self.assertEqual(len(full), end - address)
            self.assertEqual(builder.encode_fit(text, end - address, codes, collections.Counter(), address)[0], full)
            self.assertEqual(normalize_text_segment(full, True, address), full)

    def test_observed_kong_name_matches_authoritative_dialogue(self):
        address = 0xA09E10
        baseline = json.loads((Path(builder.BASE) / 'data/bteam_baseline.json').read_text())
        text = baseline['overrides'][f'0x{address:08X}']
        self.assertEqual(text, '콩의 부대는,')
        self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[address], text)
        self.assertIn(address, builder.PLAYTHROUGH_REPAIR_ROWS)
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        full = builder.encode_full_fidelity(text, codes, collections.Counter(), address)
        self.assertEqual(builder.encode_fit(text, 16, codes, collections.Counter(), address)[0], full)
        original = Path(builder.P.ROM).read_bytes()
        self.assertEqual(original[address:address + 16].decode('shift_jis'), 'コングの部隊は、')
        self.assertEqual(original[address + 16], 0x77)

    def test_victory_request_keeps_direct_addressee_and_message_end(self):
        address, end = 0xA0A109, 0xA0A11F
        original = Path(builder.P.ROM).read_bytes()
        self.assertEqual(original[address:end].decode('shift_jis'), '引きずり出してあげて。')
        self.assertEqual(original[end], 0x6B)
        self.assertEqual(builder.SCRIPT_PLAIN_OPERAND_SPANS[address], end)
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        full = builder.encode_full_fidelity('끌어내 줘.', codes, collections.Counter(), address)
        self.assertEqual(builder.encode_fit(builder.ADDRESS_TEXT_OVERRIDES[address],
                                           end - address, codes, collections.Counter(), address)[0], full)
        self.assertIn(address, builder.PLAYTHROUGH_REPAIR_ROWS)

    def test_victory_kong_fragment_keeps_name_comma_and_separator(self):
        address, end = 0xA0A1AB, 0xA0A1BB
        original = Path(builder.P.ROM).read_bytes()
        self.assertEqual(original[address:end].decode('shift_jis'), 'コングの部隊も、')
        self.assertEqual(original[end], 0x77)
        self.assertEqual(builder.SCRIPT_PLAIN_OPERAND_SPANS[address], end)
        text = builder.ADDRESS_TEXT_OVERRIDES[address]
        self.assertEqual(text, '콩의 부대도, ')
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        full = builder.encode_full_fidelity(text, codes, collections.Counter(), address)
        self.assertEqual(len(full), end - address)
        self.assertTrue(full.endswith(b'\x81\x41\x81\x40'))
        self.assertEqual(builder.encode_fit(text, end - address, codes, collections.Counter(), address)[0], full)
        self.assertIn(address, builder.PLAYTHROUGH_REPAIR_ROWS)

    def test_objective_dialogue_range_preserves_numeric_alignment_and_ui_boundaries(self):
        from dialogue_regions import PART2_OBJECTIVE_DIALOGUE_RANGE, is_part2_story_address
        original = Path(builder.P.ROM).read_bytes()
        lo, hi = PART2_OBJECTIVE_DIALOGUE_RANGE
        targets = struct.unpack_from('<42I', original, 0xA38938)
        self.assertEqual(targets[0] - 0x08000000, lo)
        self.assertTrue(all(lo <= ptr - 0x08000000 < hi for ptr in targets))
        self.assertEqual(struct.unpack_from('<I', original, 0xA389E0)[0] - 0x08000000, hi)
        for address in (lo, 0xA34183, hi - 1):
            self.assertTrue(is_part2_story_address(address))
        for address in (lo - 1, hi, 0xA34B80):
            self.assertFalse(is_part2_story_address(address))
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        text = builder.ADDRESS_TEXT_OVERRIDES[0xA34183]
        payload = builder.encode_full_fidelity(text, codes, collections.Counter(), 0xA34183)
        self.assertTrue(payload.startswith('７'.encode('shift_jis')))
        self.assertEqual(normalize_text_segment(payload, True, 0xA34183), payload)
        self.assertEqual(original[0xA34199], 0x72)

    def test_player_name_boundary_keeps_separator_and_dynamic_name_token(self):
        original = Path(builder.P.ROM).read_bytes()
        self.assertEqual(original[0xDFF8D5], 0x69)
        self.assertEqual(builder.SCRIPT_PLAIN_OPERAND_SPANS[0xDFF8C5], 0xDFF8D5)
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        text = builder.ADDRESS_TEXT_OVERRIDES[0xDFF8C5]
        payload = builder.encode_full_fidelity(text, codes, collections.Counter(), 0xDFF8C5)
        self.assertTrue(payload.endswith(b'\x81\x40'))
        self.assertGreater(len(payload), 0xDFF8D5 - 0xDFF8C5)
        self.assertIn(0xDFF8C5, builder.PLAYTHROUGH_REPAIR_ROWS)
        with self.assertRaisesRegex(AssertionError, 'plain script operand boundary exceeded'):
            builder.direct_script_override_text(0xDFF8C5, 0xDFF8D6, {}, {})
        with self.assertRaisesRegex(AssertionError, 'plain script operand boundary exceeded'):
            builder.direct_script_override_text(0xDFF8C7, 0xDFF8D6, {}, {})

    def test_part2_rejects_quotes_without_native_glyph_instead_of_silent_substitution(self):
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        for text in ('"브레이크"', "'브레이크'", '‘브레이크’'):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, 'no glyph'):
                    builder.encode_full_fidelity(text, codes, collections.Counter(), 0xA0A014)
                with self.assertRaisesRegex(ValueError, 'no glyph'):
                    builder.encode_fit(text, 32, codes, collections.Counter(), 0xA0A014)
        # Fitting must not erase native quotes to satisfy an undersized slot.
        self.assertEqual(builder.encode_fit('「브레이크」', 8, codes,
                                           collections.Counter(), 0xA0A014), (None, 99))

    def test_part2_native_quotes_follow_renderer_not_observed_row_allowlist(self):
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        for address in (0xA040BF, 0xA0A014, 0xA1A9F2, 0xA1C29C, 0xA22402):
            for text in ('「브레이크」', '“브레이크”', '『브레이크』'):
                full = builder.encode_full_fidelity(text, codes, collections.Counter(), address)
                self.assertTrue(full.startswith(b'\x81\x75'))
                self.assertTrue(full.endswith(b'\x81\x76'))
                self.assertEqual(builder.encode_fit(text, 32, codes, collections.Counter(), address)[0], full)
        # Quotes can start and end in different source text operands.
        self.assertTrue(builder.encode_full_fidelity('「구하러 와 줘서,', codes, collections.Counter(), 0xA22402).startswith(b'\x81\x75'))
        self.assertIn(b'\x81\x76', builder.encode_full_fidelity('고마워요」라고.', codes, collections.Counter(), 0xA22417))
        for address in (None, 0xA2D000, 0xA29388, 0xD9C7D5):
            self.assertNotIn(b'\x81\x75', builder.encode_full_fidelity('「브레이크」', codes, collections.Counter(), address))

    def test_part2_quote_gate_checks_native_table_and_byte_boundaries(self):
        from qa_part1_dialogue_punctuation import scan_missing_renderer_symbols
        original = Path(builder.P.ROM).read_bytes()
        root = struct.unpack_from('<I', original, 0x52F960)[0] - 0x08000000
        for code in (0x8165, 0x8166, 0x8167, 0x8168, 0x8177, 0x8178, 0x8175, 0x8176):
            node = struct.unpack_from('<I', original, root + ((code & 255) - 0x40) * 4)[0]
            seen = set()
            found = False
            while node:
                self.assertNotIn(node, seen)
                seen.add(node)
                offset = node - 0x08000000
                if original[offset + 4] == code >> 8:
                    found = True
                    break
                node = struct.unpack_from('<I', original, offset)[0]
            self.assertEqual(found, code in (0x8175, 0x8176))
            payload = code.to_bytes(2, 'big')
            self.assertEqual(bool(scan_missing_renderer_symbols(payload, 0xA0A014)), not found)
            self.assertFalse(scan_missing_renderer_symbols(payload, 0xD9C7D5))
        self.assertFalse(scan_missing_renderer_symbols(b'\x91\x81\x68', 0xA0A014))

    def test_naval_fuel_guidance_keeps_number_and_alternative_boundaries(self):
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        original = Path(builder.P.ROM).read_bytes()
        rows = ((0xA09D26, 0xA09D2C, 0x77, '연료를 '),
                (0xA09D30, 0xA09D3C, 0x6B, '씩 소모해.'),
                (0xA09D3D, 0xA09D59, 0x72, '연료가 0이 되면 침몰해서'),
                (0xA09D8A, 0xA09D98, 0x72, '항구에서 대기하거나'))
        for start, end, control, text in rows:
            with self.subTest(address=hex(start)):
                self.assertEqual(original[end], control)
                self.assertEqual(builder.SCRIPT_PLAIN_OPERAND_SPANS[start], end)
                self.assertIn(start, builder.PLAYTHROUGH_REPAIR_ROWS)
                self.assertEqual(builder.ADDRESS_TEXT_OVERRIDES[start], text)
                payload = builder.encode_full_fidelity(text, codes, collections.Counter(), start)
                self.assertEqual(normalize_text_segment(payload, True, start), payload)
        self.assertEqual(original[0xA09D2C:0xA09D30], b'\x77\x82\x51\x77')
        self.assertTrue(builder.encode_full_fidelity(rows[0][3], codes, collections.Counter(), rows[0][0]).endswith(b'\x81\x40'))

    def test_rocket_range_boundary_requires_lossless_relocation(self):
        address, end = 0xA0907B, 0xA09085
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        original = Path(builder.P.ROM).read_bytes()
        self.assertEqual(original[end], 0x77)  # Numeric emphasis is a separate operand.
        self.assertEqual(builder.SCRIPT_PLAIN_OPERAND_SPANS[address], end)
        self.assertIn(address, builder.PLAYTHROUGH_REPAIR_ROWS)
        text = builder.ADDRESS_TEXT_OVERRIDES[address]
        self.assertEqual(text, '공격 범위 ')
        encoded = builder.encode_full_fidelity(text, codes, collections.Counter(), address)
        self.assertEqual(len(encoded), 12)
        self.assertGreater(len(encoded), end - address)
        self.assertTrue(encoded.endswith(b'\x81\x40'))
        self.assertEqual(normalize_text_segment(encoded, True, address), encoded)

    def test_observed_part2_dive_quotes_use_native_glyphs_and_keep_boundaries(self):
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        original = Path(builder.P.ROM).read_bytes()
        for address, word in ((0xA094B9, '잠항'), (0xA09516, '잠항'), (0xA0962E, '부상')):
            expected = b'\x81\x75' + builder.encode_text(word, codes, collections.Counter()) + b'\x81\x76'
            self.assertEqual(builder.encode_full_fidelity('「' + word + '」', codes, collections.Counter(), address), expected)
            self.assertEqual(builder.encode_fit('「' + word + '」', 10, codes, collections.Counter(), address)[0], expected)
            self.assertEqual(normalize_text_segment(expected, True, address), expected)
            self.assertEqual(original[address:address + 2], b'\x81\x75')
            self.assertEqual(original[address + 8:address + 10], b'\x81\x76')
        for address in (0xD9C7D5, 0xA29388, None):
            self.assertNotIn(b'\x81\x75', builder.encode_full_fidelity('「잠항」', codes, collections.Counter(), address))
            self.assertNotIn(b'\x81\x75', builder.encode_fit('「잠항」', 10, codes, collections.Counter(), address)[0])
        self.assertEqual(builder.encode_full_fidelity('하면 ', codes, collections.Counter(), 0xA09521)[-2:], b'\x81\x40')
        self.assertEqual(original[0xA09520], 0x77)
        self.assertEqual(original[0xA09525], 0x77)
        scoped = builder.PART2_NATIVE_QUOTE_ROWS | {0xA09521, 0xA0961D, 0xA09639}
        for node in ast.walk(ast.parse(Path(builder.__file__).read_text())):
            if not isinstance(node, ast.Dict):
                continue
            keys = [key.value for key in node.keys if isinstance(key, ast.Constant) and key.value in scoped]
            self.assertEqual(len(keys), len(set(keys)), f'duplicate repair key at line {node.lineno}')

    def test_part2_dash_resolves_native_glyph_without_changing_part1_or_ui(self):
        original = Path(builder.P.ROM).read_bytes()
        root = struct.unpack_from('<I', original, 0x52F960)[0] - 0x08000000

        def native_glyph(code):
            node = struct.unpack_from('<I', original, root + ((code & 255) - 0x40) * 4)[0]
            seen = set()
            while node:
                self.assertNotIn(node, seen)
                seen.add(node)
                off = node - 0x08000000
                if original[off + 4] == code >> 8:
                    return off
                node = struct.unpack_from('<I', original, off)[0]
            return None

        self.assertIsNone(native_glyph(0x815C))
        self.assertEqual(native_glyph(0x815B), 0x809CD0)
        for address in (0xA01970, 0xA0A833, 0xA29387):
            for raw in (b'-', b'\x81\x5c'):
                self.assertEqual(builder._part1_dialog_safe_punct(raw, 2, address), b'\x81\x5b')
                self.assertEqual(normalize_text_segment(raw, True, address), b'\x81\x5b')
            # A matching byte pair straddling other SJIS characters is not a symbol.
            raw = b'\x91\x81\x5c'
            self.assertEqual(builder._part1_dialog_safe_punct(raw, 8, address), b'\x91\x81\x81\x5f')
        for address in (0xD91F41, 0xE10D5E, 0xA2D000, 0xA29388, None):
            self.assertEqual(builder._part1_dialog_safe_punct(b'\x81\x5c', 2, address), b'\x81\x5c')

    def test_punctuation_gate_detects_part2_missing_dash_only_at_character_boundaries(self):
        from qa_part1_dialogue_punctuation import scan_missing_renderer_symbols
        self.assertEqual(scan_missing_renderer_symbols(b'\x81\x5c', 0xA0A833), {'P2_missing_0x815C': 1})
        for raw, address in [(b'\x81\x5b', 0xA0A833), (b'\x91\x81\x5c', 0xA0A833),
                             (b'\x81\x5c', 0xE10D5E), (b'\x81\x5c', 0xA29388)]:
            self.assertFalse(scan_missing_renderer_symbols(raw, address))

    def test_part2_full_fidelity_dash_and_repoint_normalization_agree(self):
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        address = 0xA0A833
        full = builder.encode_full_fidelity('준비됐어-.', codes, collections.Counter(), address)
        self.assertTrue(full.endswith(b'\x81\x5b\x81\x42'))
        self.assertEqual(normalize_text_segment(full, True, address), full)

    def test_mission_label_keeps_dynamic_digit_font_and_lookup_key(self):
        from lz77_scan import lz77_decompress
        from lz77_compress import lz77_compress_optimal
        original = Path(builder.P.ROM).read_bytes()
        rom = bytearray(original)
        address = builder.PART2_MISSION_FONT_FILE
        before, capacity = lz77_decompress(original, address)
        builder.patch_part2_mission_number_obj(rom, original)
        builder.verify_part2_mission_number_font(rom, original)
        actual, _ = lz77_decompress(rom, address)
        for tile in range(68):
            if tile not in builder.PART2_MISSION_WORD_TILES:
                self.assertEqual(actual[tile * 32:(tile + 1) * 32],
                                 before[tile * 32:(tile + 1) * 32])
        self.assertEqual(rom[:address], original[:address])
        self.assertEqual(rom[address + capacity:], original[address + capacity:])
        # Corrupt a numeric cell, keeping a valid compressed stream.
        broken = bytearray(actual)
        broken[12 * 32] ^= 1
        compressed = lz77_compress_optimal(bytes(broken), vram_safe=True)
        self.assertLessEqual(len(compressed), capacity)
        rom[address:address + capacity] = compressed + bytes(capacity - len(compressed))
        with self.assertRaisesRegex(AssertionError, 'final mission label/digit'):
            builder.verify_part2_mission_number_font(rom, original)
        builder.patch_part2_mission_number_obj(rom, original)
        rom[builder.PART2_MISSION_WORD_FILE:builder.PART2_MISSION_WORD_FILE + 7] = b' ' * 7
        with self.assertRaisesRegex(AssertionError, 'lookup key'):
            builder.verify_part2_mission_number_font(rom, original)

    def test_mission_title_hangul_is_visible_and_does_not_overlap_next_cell(self):
        glyphs = [builder._mission_title_hangul_glyph(ch) for ch in '전투의서막']
        self.assertEqual(len(set(glyphs)), 5)
        for raw in glyphs:
            self.assertEqual(len(raw), 512)
            self.assertTrue(any(raw))
            self.assertTrue(set(v for byte in raw for v in (byte & 15, byte >> 4)) <= {0, 6, 10})
            for y in range(32):
                for x in range(24, 32):
                    pos = (y // 8 * 4 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
                    self.assertEqual((raw[pos] >> (4 * (x % 2))) & 15, 0)
        with self.assertRaisesRegex(AssertionError, 'missing mission title glyph'):
            builder._mission_title_hangul_glyph('\U0001f600')

    def test_final_mission_title_glyph_validator_rejects_blank_regression(self):
        import struct
        original = Path(builder.P.ROM).read_bytes()
        rom = bytearray(original)
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        address = 0xA2D57C
        text = b''.join(codes[ch].to_bytes(2, 'big') for ch in '전투') + b'\x81\x40\0\0'
        rom[address:address + len(text)] = text
        slots = {address: len(text)}
        evidence = {}
        builder.patch_pair_renderer_title_glyph_table(rom, original, slots, codes, evidence=evidence)
        builder.verify_pair_renderer_title_glyph_table(rom, evidence)
        rom[address:address + 2] = codes['투'].to_bytes(2, 'big')
        with self.assertRaisesRegex(AssertionError, 'final mission title glyph table'):
            builder.verify_pair_renderer_title_glyph_table(rom, evidence)
        rom[address:address + len(text)] = text
        for pos in range(builder.MISSION_TITLE_TABLE_FILE, builder.MISSION_TITLE_GLYPH_FILE, 12):
            code, _, pointer, advance = struct.unpack_from('<HHII', rom, pos)
            if code == codes['전']:
                self.assertEqual(advance, 24)
                start = pointer - 0x08000000
                blank = builder._lz77_literal_block(bytes(512))
                rom[start:start + len(blank)] = blank
                break
        else:
            self.fail('Hangul title glyph not registered')
        with self.assertRaisesRegex(AssertionError, 'final mission title glyph table'):
            builder.verify_pair_renderer_title_glyph_table(rom, evidence)

    def test_world_map_region_label_preserves_all_syllables_and_neighbors(self):
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        original = (Path(builder.BASE) / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        rom = bytearray(original)
        address = builder.PART2_REDSTAR_REGION_ADDRESS
        builder.patch_part2_redstar_region_text(rom, original, codes)
        builder.verify_part2_redstar_region_text(rom, original, codes)
        self.assertEqual(rom[:address], original[:address])
        self.assertEqual(rom[address + 14:], original[address + 14:])
        expected = b''.join(b'\x81\x40' if ch == ' ' else codes[ch].to_bytes(2, 'big')
                            for ch in '레드스타 영토')
        self.assertEqual(rom[address:address + 14], expected)
        self.assertEqual(rom[address + 8:address + 10], b'\x81\x40')
        self.assertEqual(rom[address + 12:address + 14], codes['토'].to_bytes(2, 'big'))
        # This legacy single-byte-space payload contains 토 in ROM but loses it
        # on screen; final verification must reject this exact regression.
        aligned = bytes(rom[address:address + 14])
        rom[address:address + 14] = aligned[:8] + b' ' + aligned[10:] + b'\0'
        with self.assertRaisesRegex(AssertionError, 'text/alignment/terminator'):
            builder.verify_part2_redstar_region_text(rom, original, codes)

    def test_world_map_region_label_rejects_changed_source_and_terminator(self):
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        original = (Path(builder.BASE) / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        address = builder.PART2_REDSTAR_REGION_ADDRESS
        for offset in (0, 14, 15):
            with self.subTest(offset=offset):
                changed = bytearray(original)
                changed[address + offset] ^= 1
                with self.assertRaisesRegex(AssertionError, 'region label boundary'):
                    builder.part2_redstar_region_payload(changed, codes)
        rom = bytearray(original)
        builder.patch_part2_redstar_region_text(rom, original, codes)
        rom[address + 14] = 1
        with self.assertRaisesRegex(AssertionError, 'text/alignment/terminator'):
            builder.verify_part2_redstar_region_text(rom, original, codes)

    def test_campaign_header_obj_lookup_keys_are_not_hangul_text(self):
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        original = (Path(builder.BASE) / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        rom = bytearray(original)
        builder.patch_residual_ascii_labels(rom, codes, collections.Counter())
        builder.verify_part2_campaign_header_keys(rom)
        for address in builder.PART2_CAMPAIGN_HEADER_KEYS:
            old = rom[address]
            rom[address] = 0x81
            with self.assertRaisesRegex(AssertionError, 'OBJ lookup key'):
                builder.verify_part2_campaign_header_keys(rom)
            rom[address] = old

    def test_part2_result_labels_preserve_digits_and_rank_tiles(self):
        from lz77_scan import lz77_decompress
        original = (Path(builder.BASE) / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        rom = bytearray(original)
        before, _ = lz77_decompress(original, 0x59DA5C)
        builder.patch_part2_result_summary_obj(rom)
        after, _ = lz77_decompress(bytes(rom), 0x59DA5C)
        # Full digit row, small digits/NEXT, and all rank artwork are immutable.
        protected = (list(range(8 * 32, 10 * 32))
                     + [y * 32 + x for y in (10, 11) for x in list(range(10)) + list(range(28, 32))]
                     + [y * 32 + x for y in (14, 15) for x in (8, 9)]
                     + list(range(16 * 32, 32 * 32)))
        for tile in protected:
            with self.subTest(tile=tile):
                self.assertEqual(before[tile * 32:(tile + 1) * 32],
                                 after[tile * 32:(tile + 1) * 32])
        self.assertNotEqual(before[12 * 32 * 32:14 * 32 * 32],
                            after[12 * 32 * 32:14 * 32 * 32])

    def test_name_suffix_registers_text_without_swallowing_name_or_newline_control(self):
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        address = 0xDF6030
        original = bytes(address) + b'\x69' + 'さん'.encode('shift_jis') + b'\x72'
        rom = bytearray(original)
        with patch.object(builder, 'WRITE_LOG', []):
            self.assertEqual(builder.patch_name_honorific_fragments(rom, original, codes, collections.Counter()), 1)
            self.assertEqual(rom[address], 0x69)
            self.assertEqual(rom[-1], 0x72)
            self.assertEqual([(r[0], r[1], r[5]) for r in builder.WRITE_LOG], [(address + 1, 4, '님')])

    def test_overflow_script_requires_lossless_relocation(self):
        # Exercise the actual nested writer without running the whole build.
        tree = ast.parse(Path(builder.__file__).read_text())
        writer = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                      and n.name == 'patch_script_row')
        original = (Path(builder.BASE) / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        address, end, text = 0xA0564C, 0xA0565C, '현재 6000이야'
        env = dict(vars(builder))
        env.update(orig=original, rom=bytearray(original), syl_to_code=codes,
                   unmapped=collections.Counter(), direct_script_members={},
                   _dlg_ov={}, required_script_repoints=set(), WRITE_LOG=[],
                   direct_script_override_text=lambda *args: None)
        exec(compile(ast.Module(body=[writer], type_ignores=[]), '<script-writer>', 'exec'), env)
        payload = builder.encode_text(text, codes, collections.Counter(), address)
        self.assertGreater(len(payload), end - address)
        env['patch_script_row'](address, end, payload, 'numeric row', source_text=text)
        self.assertEqual(env['required_script_repoints'], {address})
        self.assertEqual(env['WRITE_LOG'][-1][5], text)
        self.assertEqual(env['rom'][end:], original[end:])
        self.assertEqual(env['rom'][:address], original[:address])
        from dialogue_repoint import apply_script_span_ownership
        _, owners, conflicts = apply_script_span_ownership(
            {address: (end - address, 'original')}, env['WRITE_LOG'], env['rom'])
        self.assertFalse(conflicts)
        self.assertEqual(owners[address], (end - address, text))
        self.assertEqual(env['rom'][address:end], original[address:end])
        full = builder.encode_full_fidelity(text, codes, collections.Counter(), address)
        self.assertIn('６０００'.encode('shift_jis'), full)
        for completed in (set(), {address + 1}):
            with self.assertRaisesRegex(AssertionError, 'required script relocation failed'):
                builder.verify_required_script_repoints(env['required_script_repoints'], completed)
        builder.verify_required_script_repoints({address}, {address})
        with self.assertRaisesRegex(AssertionError, 'overflow'):
            env['patch_script_row'](address, end, payload, 'no source')
        # Missing generated group metadata and editor overrides must not
        # bypass the same mandatory relocation gate.
        for override in (text, '현재 7000이야'):
            env['required_script_repoints'].clear()
            env['direct_script_override_text'] = lambda *args: override
            env['patch_script_row'](address, end, payload, 'override', source_text=text)
            self.assertEqual(env['required_script_repoints'], {address})
            self.assertEqual(env['WRITE_LOG'][-1][5], override)
            with self.assertRaisesRegex(AssertionError, 'required script relocation failed'):
                builder.verify_required_script_repoints(env['required_script_repoints'], set())

    def test_numeric_story_without_fitting_fallback_can_stage_original(self):
        tree = ast.parse(Path(builder.__file__).read_text())
        writer = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                      and n.name == 'patch_script_row')
        original = (Path(builder.BASE) / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        address, end, text = 0xA250EC, 0xA250F6, '2대1이라면'
        self.assertIsNone(builder.encode_fit(text, end - address, codes,
                                           collections.Counter(), address)[0])
        env = dict(vars(builder))
        env.update(orig=original, rom=bytearray(original), syl_to_code=codes,
                   unmapped=collections.Counter(), direct_script_members={}, _dlg_ov={},
                   required_script_repoints=set(), WRITE_LOG=[],
                   direct_script_override_text=lambda *args: None)
        exec(compile(ast.Module(body=[writer], type_ignores=[]), '<script-writer>', 'exec'), env)
        payload = builder.encode_text(text, codes, collections.Counter(), address)
        env['patch_script_row'](address, end, payload, 'numeric ratio', source_text=text)
        self.assertEqual(bytes(env['rom']), original)
        self.assertEqual(env['WRITE_LOG'][-1][5], text)
        self.assertEqual(env['required_script_repoints'], {address})
        env['required_script_repoints'].clear()
        env['direct_script_override_text'] = lambda *args: text
        env['patch_script_row'](address, end, payload, 'numeric override', source_text=text)
        self.assertEqual(bytes(env['rom']), original)
        self.assertEqual(env['required_script_repoints'], {address})

    def test_part2_padding_cannot_be_reintroduced_as_visible_spacing(self):
        original = (Path(builder.BASE) / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        self.assertEqual(builder.verify_part2_padding_dispatch(original, original), 1)
        rom = bytearray(original)
        struct.pack_into('<I', rom, builder.PART2_A3_SPACE_TABLE_ENTRY, builder.PART2_HOOK_A3_SPACE_RT)
        with self.assertRaisesRegex(AssertionError, 'non-advancing dispatcher'):
            builder.verify_part2_padding_dispatch(original, rom)
        rom = bytearray(original)
        rom[0x31431C] ^= 1
        with self.assertRaisesRegex(AssertionError, 'handler body changed'):
            builder.verify_part2_padding_dispatch(original, rom)
        rom = bytearray(original)
        struct.pack_into('<I', rom, len(rom) - 4, builder.PART2_HOOK_A3_SPACE_RT | 1)
        with self.assertRaisesRegex(AssertionError, 'still referenced'):
            builder.verify_part2_padding_dispatch(original, rom)
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        for a in (0xA03915, 0xA0393A, 0xA03B16, 0xA03BB1, 0xA03C0F):
            text = builder.ADDRESS_TEXT_OVERRIDES[a]
            self.assertTrue(builder.encode_full_fidelity(text, codes, collections.Counter(), a).endswith(b'\x81\x40'))

    def test_mission1_intro_spaces_keep_original_pause_boundaries(self):
        original = (Path(builder.BASE) / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        from qa_text_fit import load_direct_patch_texts
        patches = load_direct_patch_texts()
        for address, end in ((0xA046BC, 0xA046C6), (0xA046EC, 0xA046F6),
                             (0xA046F7, 0xA046FD), (0xA04715, 0xA0471B),
                             (0xA0472D, 0xA04739), (0xA04794, 0xA047A2)):
            with self.subTest(address=hex(address)):
                self.assertEqual(patches[address][0], end)
                self.assertEqual(original[end], 0x77)
                payload = builder.encode_full_fidelity(builder.ADDRESS_TEXT_OVERRIDES[address], codes, collections.Counter(), address)
                self.assertTrue(payload.endswith(b'\x81\x40'))
                rom = bytearray(original)
                rom[end] = 0x20
                with self.assertRaisesRegex(AssertionError, 'repaired message control changed'):
                    builder.verify_repaired_message_controls(original, rom)
        self.assertEqual(patches[0xA046C7], (0xA046CD, '강 너머'))

    def test_fog_training_unit_joiners_preserve_highlight_controls(self):
        original = (Path(builder.BASE) / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        from qa_text_fit import load_direct_patch_texts
        patches = load_direct_patch_texts()
        for start, end in ((0xD9DB1C, 0xD9DB1E), (0xD9DBCF, 0xD9DBD1)):
            self.assertEqual(patches[start], (end, '과　'))
            self.assertEqual(builder.SCRIPT_PLAIN_OPERAND_SPANS[start], end)
            self.assertEqual(original[start:end].decode('shift_jis'), 'と')
            self.assertEqual(original[end], 0x32)
            rom = bytearray(original)
            rom[end] = 0x20
            with self.assertRaisesRegex(AssertionError, 'repaired message control changed'):
                builder.verify_repaired_message_controls(original, rom)
        self.assertEqual(patches[0xD9DB2A][1], '은 특별한 힘이 있어。')
        self.assertEqual(patches[0xD9DD26][1], '이 옆에 왔으니')

    def test_observed_playthrough_repairs_never_ship_fit_fallbacks(self):
        tree = ast.parse(Path(builder.__file__).read_text())
        writer = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                      and n.name == 'patch_script_row')
        original = (Path(builder.BASE) / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        from qa_text_fit import load_direct_patch_texts
        patches = load_direct_patch_texts()
        # qa_text_fit intentionally omits punctuation-only direct rows.
        quote_row = next(ast.literal_eval(n) for n in ast.walk(tree)
                         if isinstance(n, ast.Tuple) and len(n.elts) == 4
                         and isinstance(n.elts[0], ast.Constant) and n.elts[0].value == 0xD9DE49)
        patches[quote_row[0]] = (quote_row[1], quote_row[2])
        for address in builder.PLAYTHROUGH_REPAIR_ROWS:
            end, text = patches[address]
            for override in (None, text):
                with self.subTest(address=hex(address), override=override):
                    env = dict(vars(builder))
                    env.update(orig=original, rom=bytearray(original), syl_to_code=codes,
                               unmapped=collections.Counter(), direct_script_members={},
                               _dlg_ov={}, required_script_repoints=set(), WRITE_LOG=[],
                               direct_script_override_text=lambda *args: override)
                    exec(compile(ast.Module(body=[writer], type_ignores=[]), '<writer>', 'exec'), env)
                    env['patch_script_row'](address, end, b'ignored', 'observed repair', source_text=text)
                    exact = builder.encode_full_fidelity(text, codes, collections.Counter(), address)
                    self.assertEqual(env['WRITE_LOG'][-1][5], text)
                    self.assertEqual(env['rom'][:address], original[:address])
                    self.assertEqual(env['rom'][end:], original[end:])
                    if len(exact) > end - address:
                        self.assertEqual(env['rom'][address:end], original[address:end])
                        self.assertEqual(env['required_script_repoints'], {address})
                        with self.assertRaisesRegex(AssertionError, 'required script relocation failed'):
                            builder.verify_required_script_repoints(env['required_script_repoints'], set())
                    else:
                        self.assertEqual(env['rom'][address:address + len(exact)], exact)
                        self.assertFalse(env['required_script_repoints'])
        self.assertEqual(patches[0xD9DE49], (0xD9DE51, '「'))
        self.assertEqual(builder.direct_script_override_text(0xD9DE49, 0xD9DE51,
                         {0xD9DE49: [{'address': 0xD9DE49, 'ko': '된 「'}]},
                         {'0x00D9DE49': '된 「'}), '「')

    def test_transport_type_suffix_excludes_pauses_and_newline(self):
        original = (Path(builder.BASE) / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        from qa_text_fit import load_direct_patch_texts
        patches = load_direct_patch_texts()
        self.assertNotIn(0xA034F6, patches)
        self.assertEqual(patches[0xA034F7], (0xA034FB, '이야。'))
        slots, _ = builder.load_direct_script_metadata()
        self.assertEqual(slots[0xA034F7], 4)
        for a in (0xA034F6, 0xA034FB, 0xA034FC, 0xA034FD):
            rom = bytearray(original)
            rom[a] = 0x20
            with self.assertRaisesRegex(AssertionError, 'repaired message control changed'):
                builder.verify_repaired_message_controls(original, rom)

    def test_attack_instruction_writers_exclude_line_and_pause_controls(self):
        original = (Path(builder.BASE) / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        from qa_text_fit import load_direct_patch_texts
        patches = load_direct_patch_texts()
        slots, _ = builder.load_direct_script_metadata()
        for start, end, control in ((0xA03B02, 0xA03B14, 0x72),
                                    (0xA03B32, 0xA03B58, 0x77),
                                    (0xA03B90, 0xA03BAE, 0x77)):
            self.assertEqual(original[end], control)
            self.assertEqual(patches[start][0], end)
            self.assertEqual(slots[start], end - start)
            rom = bytearray(original)
            rom[end] = 0x20
            with self.assertRaisesRegex(AssertionError, 'repaired message control changed'):
                builder.verify_repaired_message_controls(original, rom)

    def test_capture_instruction_preserves_highlight_command_boundary(self):
        original = (Path(builder.BASE) / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        for address in (0xD9284A, 0xD9284F):
            rom = bytearray(original)
            rom[address] = 0x20
            with self.assertRaisesRegex(AssertionError, 'repaired message control changed'):
                builder.verify_repaired_message_controls(original, rom)
        from qa_text_fit import load_direct_patch_texts
        patches = load_direct_patch_texts()
        self.assertNotIn(0xD92846, patches)
        slots, _ = builder.load_direct_script_metadata()
        self.assertEqual(slots[0xD92846], 4)
        self.assertEqual(slots[0xD9284B], 4)
        self.assertEqual(slots[0xD92850], 32)
        end, text = patches[0xD92850]
        self.assertEqual(end, 0xD92870)
        self.assertIn('Ａ', text)
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        self.assertEqual(len(builder.encode_full_fidelity(text, codes, collections.Counter(), 0xD92850)), 32)
        for addr in (0xD92733, 0xD9280E):
            end, text = patches[addr]
            self.assertTrue(text.endswith('　'))
            self.assertLessEqual(len(builder.encode_text(text, codes, collections.Counter(), addr)), end - addr)

    def test_only_final_unchanged_fixed_fragments_are_frozen_for_repoint(self):
        writes = [[0, 4, 2, '8840', 32, '고정', 0, 'known-story-fragment']]
        rom = bytearray(b'\x88\x40  ')
        self.assertEqual(builder.final_fixed_fragment_addresses(writes, rom), {0})
        self.assertEqual(builder.final_fixed_fragment_addresses(
            writes + [[0, 4, 2, '8840', 32, '새 문장', 0, 'script:row']], rom), set())
        rom[2] = 0x81
        self.assertEqual(builder.final_fixed_fragment_addresses(writes, rom), set())

    def test_duplicate_operand_before_highlight_is_detected_with_particle(self):
        from qa_control_operand_duplicates import find_duplicates
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        word = builder.encode_text('점령', codes, collections.Counter())
        particle = builder.encode_text('을', codes, collections.Counter())
        prefix = word + particle + b'\x81\x40'
        original = b' ' * len(prefix) + b'\x33' + '占領'.encode('shift_jis') + b'\x30'
        patched = prefix + b'\x33' + word + b'\x30'
        issues = find_duplicates(original, patched, codes)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]['direction'], 'before')
        self.assertEqual(issues[0]['word'], '점령')
        self.assertEqual(find_duplicates(original, b' ' * len(prefix) + patched[len(prefix):], codes), [])

    def test_declared_control_replacement_registers_only_text_and_keeps_commands(self):
        address = 0xD8F927
        old = b'\x32' + '歩兵'.encode('shift_jis') + b'\x30'
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        reverse = {v: k for k, v in codes.items()}
        new = b'\x32' + builder.encode_text('보병', codes, collections.Counter()) + b'\x30'
        original = bytes(address) + old
        rom = bytearray(original)
        rom[address:] = new
        with patch.object(builder, 'WRITE_LOG', []):
            builder.record_known_control_replacement(rom, original, address, old, new, reverse)
            self.assertEqual(bytes(rom[address:]), new)
            self.assertEqual([(e[0], e[1], e[5]) for e in builder.WRITE_LOG], [(address + 1, 4, '보병')])
            with self.assertRaisesRegex(AssertionError, 'changed command'):
                builder.record_known_control_replacement(rom, original, address, old, new[:-1] + b'\x31', reverse)
            with self.assertRaisesRegex(AssertionError, 'source mismatch'):
                builder.record_known_control_replacement(rom, original, address, b'\x33' + old[1:], new, reverse)
            with self.assertRaisesRegex(AssertionError, 'introduced command'):
                builder.record_known_control_replacement(rom, original, address, old, b'\x32\x32\x30' + new[3:], reverse)
            rom[address] = 0x33
            with self.assertRaisesRegex(AssertionError, 'current bytes mismatch'):
                builder.record_known_control_replacement(rom, original, address, old, new, reverse)

    def test_repeated_message_opening_is_not_an_independent_inner_reference(self):
        from dialogue_repoint import has_independently_referenced_overlap
        lines = [(0xA11D28, 10), (0xA11D5B, 32)]
        text = ['덕분에、', '당신의재빠른행동덕분에、']
        self.assertFalse(has_independently_referenced_overlap(0xA11D28, lines, text, {0xA11D28}))
        # The short fragment is instead an independently referenced inner line.
        inner_lines = [(0xA11D28, 32), (0xA11D5B, 10)]
        self.assertTrue(has_independently_referenced_overlap(
            0xA11D28, inner_lines, text[::-1], {0xA11D28, 0xA11D5B}))

    def test_known_story_fragment_preserves_punctuation_and_rejects_controls(self):
        original = (Path(builder.BASE) / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        rom = bytearray(original)
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        payload = builder.encode_text('아, ', codes, collections.Counter())
        with patch.object(builder, 'WRITE_LOG', []):
            builder.write_known_story_fragment(rom, original, 0xA078A0, payload, '아, ')
            self.assertEqual(rom[0xA078A0:0xA078A4], codes['아'].to_bytes(2, 'big') + b'\x81\x41')
            self.assertEqual(rom[0xA0789F], original[0xA0789F])
            self.assertEqual(rom[0xA078A4], original[0xA078A4])
            self.assertEqual(builder.WRITE_LOG[-1][7], 'known-story-fragment')
            with self.assertRaisesRegex(AssertionError, 'crosses controls'):
                builder.write_known_story_fragment(rom, original, 0xA034F6, b' ' * 8)
            with self.assertRaisesRegex(AssertionError, 'outside ROM'):
                builder.write_known_story_fragment(rom, original, len(original) - 1, b'  ')
            size_before = len(rom)
            with patch.object(builder, '_part1_dialog_safe_punct', return_value=b'x' * 5):
                with self.assertRaisesRegex(AssertionError, 'punctuation overflow'):
                    builder.write_known_story_fragment(rom, original, 0xA078A0, payload, '아, ')
            self.assertEqual(len(rom), size_before)

    def test_script_writer_cannot_end_inside_source_glyph(self):
        original = 'あ！'.encode('shift_jis') + b'\x6b'
        builder.validate_script_message_span(original, 0, 4)
        with self.assertRaisesRegex(AssertionError, 'splits source glyph'):
            builder.validate_script_message_span(original, 0, 3)

    def test_punctuation_gate_ignores_superseded_sjis_tail_offsets(self):
        from qa_part1_dialogue_punctuation import active_text_payloads, scan_standalone_punct
        a = 0xA0E4AA
        writes = [[a + 1, 2, 2, '917e', 32, 'old', 0, 'old'],
                  [a, 4, 4, '917e8149', 32, 'new', 0, 'new']]
        rom = bytearray(a + 4); rom[a:] = bytes.fromhex('917e8149')
        live = list(active_text_payloads(writes, rom))
        self.assertTrue(live)
        self.assertFalse(any(scan_standalone_punct(payload) for _, _, payload in live))
        writes = [[a, 2, 2, '917e', 32, 'old', 0, 'old'],
                  [a, 1, 1, '20', 32, 'new', 0, 'new']]
        with self.assertRaisesRegex(ValueError, 'Partially overwritten'):
            list(active_text_payloads(writes, rom))

    def test_part2_story_scope_stops_before_special_ui(self):
        from dialogue_regions import is_part2_story_address
        for address in (0xA01970, 0xA01C90, 0xA01CB8, 0xA0249F, 0xA0E398, 0xA29377, 0xA29387):
            self.assertTrue(is_part2_story_address(address))
            self.assertEqual(builder._part1_dialog_safe_punct(b'!', 2, address), b'\x81\x49')
        for address in (0xA0196F, 0xA29388, 0xA2955C, 0xA2CA38, 0xA2CB00, 0xA2D000):
            self.assertFalse(is_part2_story_address(address))
            self.assertEqual(builder._part1_dialog_safe_punct(b'!', 2, address), b'!')
            self.assertFalse(builder.story_requires_lossless_repoint(address, b'!', b'\x81\x49'))

    def test_safe_punctuation_tables_agree_and_loss_is_reported(self):
        from dialogue_repoint import PART1_DIALOG_ASCII_PUNCT
        self.assertEqual(builder.PART1_DIALOG_ASCII_PUNCT, PART1_DIALOG_ASCII_PUNCT)
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        text = '이번엔 거점 건설,'
        encoded, level = builder.encode_fit(text, 18, codes, collections.Counter(), 0xA01BA9)
        self.assertEqual(level, 0)
        self.assertIsNotNone(builder.dialogue_fit_warning(text, encoded, codes, 0xA01BA9))
        full = builder.encode_full_fidelity(text, codes, collections.Counter(), 0xA01BA9)
        self.assertIsNone(builder.dialogue_fit_warning(text, full, codes, 0xA01BA9))

    def test_full_fidelity_restores_dash_after_shared_ui_fallback(self):
        for address in (0xE10D5E, 0xA019F8):
            for text in ('-', '―', '—', '─'):
                self.assertEqual(builder.encode_full_fidelity(
                    text, {}, collections.Counter(), address),
                    b'\x81\x5b' if address == 0xA019F8 else b'\x81\x5c')

    def test_prologue_punctuation_loss_requires_repoint_even_at_level_zero(self):
        from dialogue_regions import needs_safe_dialogue_punctuation
        self.assertEqual(normalize_text_segment(b'\x88\x40!?',
                         needs_safe_dialogue_punctuation(0xA01B98)),
                         b'\x88\x40\x81\x49\x81\x48')
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        address, text = 0xA01BA9, '이번엔 거점 건설,'
        encoded, level = builder.encode_fit(text, 18, codes, collections.Counter(), address)
        full = builder.encode_full_fidelity(text, codes, collections.Counter(), address)
        self.assertEqual(level, 0)  # Existing fit fallback hides the lost comma.
        self.assertTrue(builder.story_requires_lossless_repoint(address, encoded, full))
        self.assertFalse(builder.story_requires_lossless_repoint(address, full, full))
        self.assertFalse(builder.story_requires_lossless_repoint(0xA29388, encoded, full))

    def test_part1_victory_taunt_keeps_ellipsis_and_dash_via_repoint(self):
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        address, text = 0xD91F41, '으으음・・・다음에 두고 보자-!'
        encoded, level = builder.encode_fit(text, 32, codes, collections.Counter(), address)
        full = builder.encode_full_fidelity(text, codes, collections.Counter(), address)
        self.assertEqual(level, 0)
        self.assertNotEqual(encoded, full)
        self.assertTrue(builder.story_requires_lossless_repoint(address, encoded, full))
        self.assertIn(b'\x81\x45' * 3, full)
        self.assertIn(b'\x81\x5c\x81\x49', full)

    def test_part2_prologue_punctuation_preserves_controls_and_words(self):
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        for address, text, slot in ((0xA019F8, '호크는 있나!', 16),
                                    (0xA01A0C, '여기에...', 12),
                                    (0xA01A1A, '헬보우즈 님.', 14)):
            encoded, level = builder.encode_fit(text, slot, codes, collections.Counter(), address)
            expected = builder.encode_full_fidelity(text, codes, collections.Counter(), address)
            self.assertEqual(encoded, expected)
            self.assertLessEqual(len(encoded), slot)
            self.assertEqual(level, 0)
        for address in (0xA0196F, 0xA29388, 0xA2955C, 0xA2CB00, 0xA2D000):
            self.assertEqual(builder._part1_dialog_safe_punct(b'!', 2, address), b'!')
        self.assertEqual(builder._part1_dialog_safe_punct(b'?', 2, 0xA01A9D), b'\x81\x48')

    def test_name_grid_preserves_shared_dialogue_symbol_tiles(self):
        self.assertEqual(builder._part1_dialog_safe_punct(b'-', 2, 0xE10D5E), b'\x81\x5c')
        self.assertEqual(normalize_text_segment(b'-', True), b'\x81\x5c')
        original = (Path(builder.BASE) / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        rom = bytearray(original)
        builder.patch_name_grid(rom)
        builder.restore_symbol_glyphs(rom, original)
        builder.patch_name_grid(rom)  # Same late reapplication as the build.
        for slot in builder.NAME_GRID_SLOTS['z']:
            start = 0xB974D0 + slot * 32
            self.assertEqual(rom[start:start + 32], original[start:start + 32])

    def test_result_dialogue_uses_same_punctuation_guard_as_campaign(self):
        from dialogue_regions import is_part1_dialog_address
        from qa_part1_dialogue_punctuation import in_part1_dialog, scan_standalone_punct
        for address in (0xE10D36, 0xE10FDD, 0xE11304):
            self.assertTrue(is_part1_dialog_address(address))
            self.assertTrue(in_part1_dialog(address))
            safe = builder._part1_dialog_safe_punct(b'A, B?', 16, address)
            self.assertEqual(scan_standalone_punct(safe), {})
        for address in (0xE10000, 0xE10D33, 0xE11314, 0xE12000):
            self.assertFalse(is_part1_dialog_address(address))
            self.assertEqual(builder._part1_dialog_safe_punct(b'?', 2, address), b'?')

    def test_duplicate_operand_gate_requires_source_control_and_accepts_suffix(self):
        from qa_control_operand_duplicates import find_duplicates
        codes = {'공': 0x8840, '격': 0x8841}
        # Limit the fixture to one known operand, keeping unrelated graphics
        # with the same bytes outside the original text token untouched.
        from unittest.mock import patch
        with patch('qa_control_operand_duplicates.WORDS', {'攻撃': '공격'}):
            original = b'\x33' + '攻撃'.encode('shift_jis') + b'\x30' + b' ' * 20
            live = b'\x33\x88\x40\x88\x41\x30'
            self.assertEqual(len(find_duplicates(original, live + b'\x81\x40\x88\x40\x88\x41', codes)), 1)
            self.assertEqual(find_duplicates(original, live + b'\x88\x42', codes), [])
            self.assertEqual(find_duplicates(b' ' * len(original), live + b'\x88\x40\x88\x41', codes), [])

    def test_duplicate_operand_gate_follows_repointed_message(self):
        from qa_control_operand_duplicates import check_rom
        codes = {'공': 0x8840, '격': 0x8841}
        original = bytearray(100)
        original[:6] = b'\x33' + '攻撃'.encode('shift_jis') + b'\x30'
        live = b'\x33\x88\x40\x88\x41\x30'
        manifest = [{'msg': '0x0', 'new_addr': '0x20', 'ptr_off': '0x10',
                     'old_len': 12, 'new_len': 16, 'status': 'relocated'}]
        patched = bytearray(100)
        struct.pack_into('<I', patched, 16, 0x08000020)
        with patch('qa_control_operand_duplicates.WORDS', {'攻撃': '공격'}):
            patched[32:43] = b' ' + live + b'\x88\x40\x88\x41'
            issues = check_rom(original, patched, codes, manifest)
            self.assertEqual(issues[0]['operand_address'], '0x00000021')
            patched[32:48] = b' ' * 16
            patched[:10] = live + b'\x88\x40\x88\x41'
            self.assertEqual(check_rom(original, patched, codes, manifest), [])
            patched[16] ^= 1
            with self.assertRaises(ValueError):
                check_rom(original, patched, codes, manifest)

    def test_terrain_messages_reject_erased_boundary_and_stale_editor_spans(self):
        rom = bytearray((Path(builder.BASE) / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes())
        self.assertEqual(builder.verify_terrain_comparison_boundaries(rom), 7)
        rom[0xD915B2:0xD915BA] = b' ' * 8
        with self.assertRaises(AssertionError):
            builder.verify_terrain_comparison_boundaries(rom)
        slots, _ = builder.load_direct_script_metadata()
        self.assertEqual(slots[0xD9159E], 12)
        self.assertEqual(slots[0xD915BA], 8)
        self.assertEqual(slots[0xD9B54F], 8)
        with self.assertRaises(AssertionError):
            builder.validate_script_message_span(rom, 0xD9B54F, 0xD9B55B)
        builder.validate_script_message_span(rom, 0xD9B54F, 0xD9B557)

    def test_nonempty_tsv_override_does_not_need_duplicate_json_record(self):
        addr = 0xD9159E
        with patch.dict(builder.ADDRESS_TEXT_OVERRIDES, {addr: '하지만 이　'}):
            members = {addr: [{'address': addr, 'ko': '옛 문구'}]}
            self.assertEqual(builder.direct_script_override_text(addr, addr + 12, members, {}), '하지만 이　')

    def test_legacy_fragments_cannot_remove_default_command_operands(self):
        _, members = builder.load_direct_script_metadata()
        for start, end in ((0xD8FD5A, 0xD8FD80), (0xD8FDAE, 0xD8FDDA)):
            with patch.dict(builder.ADDRESS_TEXT_OVERRIDES, {start: '문장 조각'}):
                self.assertIsNone(builder.direct_script_override_text(start, end, members, {}))
            with patch.dict(builder.ADDRESS_TEXT_OVERRIDES, {start: ''}):
                self.assertIsNone(builder.direct_script_override_text(start, end, members, {}))
            with self.assertRaises(ValueError):
                builder.direct_script_override_text(start, end, members, {f'0x{start:08X}': '문장 조각'})

    def test_secondary_protected_clear_is_authoritative_and_merged_end_is_checked(self):
        addr = 0xD9159E
        members = {addr: [{'address': addr, 'ko': ''}, {'address': addr + 2, 'ko': '삭제할 문구'}]}
        with patch.dict(builder.ADDRESS_TEXT_OVERRIDES, {addr + 2: ''}):
            self.assertEqual(builder.direct_script_override_text(addr, addr + 12, members, {f'0x{addr + 2:08X}': ''}), '')
        start, end = next(iter(builder.WHOLE_SCRIPT_ROWS.items()))
        with self.assertRaises(AssertionError):
            builder.direct_script_override_text(start, end - 1, {}, {})
        address = 0xD902DC
        members = {address: [{'address': address, 'ko': '기존'},
                             {'address': address + 50, 'ko': '부터,을 해 줘.'}]}
        text = builder.direct_script_override_text(address, 0xD90321, members, {})
        self.assertEqual(text, '이미 모든 유닛이 움직였으니 종료해 줘。')

    def test_repaired_messages_preserve_controls_and_operand_spans_are_pure_text(self):
        original = (Path(builder.BASE) / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        self.assertGreater(builder.verify_repaired_message_controls(original, original), 40)
        for start, end in builder.SCRIPT_OPERAND_SPANS.items():
            builder.validate_script_message_span(original, start, end)
            text = original[start:end].decode('shift_jis')
            if start != 0xD902DC:  # This existing merged row includes a newline token.
                self.assertFalse(any(ord(char) < 0x20 for char in text))
        with self.assertRaises(AssertionError):
            builder.validate_script_message_span(original, 0xD98E74, 0xD98E82)
        for address in (0xA02EEF, 0xA02F54, 0xA030B5, 0xA031C7, 0xA03B73, 0xD9B557):
            rom = bytearray(original)
            rom[address] = 0x20
            with self.assertRaises(AssertionError):
                builder.verify_repaired_message_controls(original, rom)

    def test_protected_empty_script_clears_without_receipt_and_preserves_children(self):
        addr = 0xD90D26
        overrides = {'0x00D90D26': ''}
        with patch.dict(builder.ADDRESS_TEXT_OVERRIDES, {addr: ''}):
            self.assertEqual(builder.direct_script_override_text(addr, addr + 8, {}, overrides), '')
            intents = {'0x00D90D26': builder.editor_text_digest('')}
            self.assertEqual(builder.direct_script_override_text(addr, addr + 8, {}, overrides), '')
            members = {addr: [{'address': addr, 'ko': '기존'}, {'address': addr + 4, 'ko': '뒷말'}]}
            self.assertEqual(builder.direct_script_override_text(addr, addr + 8, members, overrides), '뒷말')
            self.assertEqual(builder.direct_script_override_text(addr, addr + 2,
                {addr: [{'address': addr + 4, 'ko': '범위 밖'}]}, overrides), '')
            source = Path(builder.__file__).read_text()
            node = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == 'patch_script_row')
            rom = bytearray(b'x' * (addr + 8))
            namespace = {**vars(builder), 'required_script_repoints': set(),
                         'direct_script_override_text': builder.direct_script_override_text,
                         'validate_script_message_span': builder.validate_script_message_span,
                         'orig': bytes(b'x' * (addr + 8)),
                         'direct_script_members': {}, '_dlg_ov': overrides, '_editor_intents': intents,
                         'encode_fit': builder.encode_fit, 'syl_to_code': {}, 'unmapped': {},
                         'rom': rom, 'FILL_BYTE': 0x20, 'WRITE_LOG': []}
            exec(compile(ast.Module(body=[node], type_ignores=[]), '<actual script writer>', 'exec'), namespace)
            namespace['patch_script_row'](addr, addr + 8, b'default', 'test')
            self.assertEqual(rom[addr:addr + 8], b' ' * 8)
            self.assertEqual(namespace['WRITE_LOG'][0][5], '')

    def test_day_hud_final_gate_rejects_changed_label_or_pointer(self):
        rom = bytearray(0xB829C8)
        rom[0xB829C4:0xB829C8] = b'DAY\0'
        struct.pack_into('<I', rom, 0xB27444, 0x08B829C4)
        self.assertEqual(builder.verify_part1_battle_day_hud_label(rom), 1)
        for address in (0xB829C4, 0xB27444):
            rom[address] ^= 1
            with self.assertRaises(AssertionError):
                builder.verify_part1_battle_day_hud_label(rom)
            rom[address] ^= 1

    def test_repoint_honors_explicit_spacing_but_preserves_legacy_policy(self):
        source = Path(builder.__file__).read_text()
        node = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == '_rp_dlg')
        address = 0xA07528
        edited = '이름대로 공중유닛에 강하지만,'
        spaced = '이름대로 공중 유닛에 강하지만,'
        namespace = {'_rp_script_owners': {}, '_display_ov': {}, 'ADDRESS_TEXT_OVERRIDES': {},
                     '_rp_bteam': set(), '_rp_ov': lambda a: edited, '_rp_intended': {address: spaced},
                     '_rp_strip_sp': lambda text: text.replace(' ', '').replace('　', ''),
                     '_dlg_ov': {'0x00A07528': edited}, '_editor_intents': {},
                     'editor_text_digest': builder.editor_text_digest,
                     'BTEAM_SCRIPT_SPACING_REPAIRS': builder.BTEAM_SCRIPT_SPACING_REPAIRS,
                     'BTEAM_SCRIPT_LAYOUT_REPAIRS': builder.BTEAM_SCRIPT_LAYOUT_REPAIRS,
                     'is_verified_bteam_script_repair': builder.is_verified_bteam_script_repair}
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<actual repoint selector>', 'exec'), namespace)
        choose = namespace['_rp_dlg']
        self.assertEqual(choose(address), spaced)
        namespace['_editor_intents']['0x00A07528'] = builder.editor_text_digest(edited)
        self.assertEqual(choose(address), edited)
        namespace['_editor_intents']['0x00A07528'] = builder.editor_text_digest('이전 편집')
        self.assertEqual(choose(address), spaced)
        namespace['ADDRESS_TEXT_OVERRIDES'][address] = ''
        self.assertEqual(choose(address), '')
        namespace['ADDRESS_TEXT_OVERRIDES'][address] = '이　'
        namespace['_editor_intents']['0x00A07528'] = builder.editor_text_digest('이　')
        self.assertEqual(choose(address), '이　')

    def test_bteam_name_boundary_exception_cannot_change_words_or_other_rows(self):
        source = Path(builder.__file__).read_text()
        node = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == '_rp_dlg')
        address = 0xDC3C63
        baseline = json.loads((Path(builder.BASE) / 'data/bteam_baseline.json').read_text())['overrides']
        authoritative = baseline['0x00DC3C63']
        namespace = {'_rp_script_owners': {address: (14, ' 사령관님, 료!')},
                     '_rp_bteam': {address}, '_rp_ov': lambda a: authoritative,
                     '_dlg_ov': {}, '_editor_intents': {}, 'editor_text_digest': builder.editor_text_digest,
                     'is_verified_bteam_spacing_repair': builder.is_verified_bteam_spacing_repair,
                     'BTEAM_SCRIPT_SPACING_REPAIRS': builder.BTEAM_SCRIPT_SPACING_REPAIRS,
                     'BTEAM_SCRIPT_LAYOUT_REPAIRS': builder.BTEAM_SCRIPT_LAYOUT_REPAIRS,
                     'is_verified_bteam_script_repair': builder.is_verified_bteam_script_repair}
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<actual repoint selector>', 'exec'), namespace)
        choose = namespace['_rp_dlg']
        self.assertEqual(authoritative, '사령관님,료!')
        self.assertEqual(choose(address), ' 사령관님, 료!')
        for text in [' 사령관님, 맥스!', ' 님, 료!', ' 사령관님, 료?', ' 사령관님, 료! ', '사령관님, 료!', ' 사령관님,료!']:
            namespace['_rp_script_owners'][address] = (14, text)
            with self.assertRaisesRegex(AssertionError, 'owner missing or changed'):
                choose(address)
        for edited in [' 다른 이름!', '', '  양쪽 공백　']:
            namespace['_dlg_ov'][f'0x{address:08X}'] = edited
            namespace['_editor_intents'][f'0x{address:08X}'] = builder.editor_text_digest(edited)
            namespace['_rp_script_owners'][address] = (14, edited)
            self.assertEqual(choose(address), edited)
            namespace['_editor_intents'][f'0x{address:08X}'] = builder.editor_text_digest('stale')
            with self.assertRaisesRegex(AssertionError, 'owner missing or changed'):
                choose(address)
        namespace['_rp_script_owners'].clear()
        namespace['ADDRESS_TEXT_OVERRIDES'] = {address: ' 사령관님, 료!'}
        with self.assertRaisesRegex(AssertionError, 'owner missing or changed'):
            choose(address)
        self.assertFalse(builder.is_verified_bteam_spacing_repair(address+1, authoritative, ' 사령관님, 료!'))
        self.assertFalse(builder.is_verified_bteam_spacing_repair(address, '사령님,료!', ' 사령관님, 료!'))

    def test_recorded_bteam_edit_flows_through_writer_owner_and_repoint_selector(self):
        tree = ast.parse(Path(builder.__file__).read_text())
        nodes = [next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
                 for name in ['patch_script_row', '_rp_dlg']]
        original = Path(builder.P.ROM).read_bytes()
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        address, end = 0xDC3C63, 0xDC3C71
        key = f'0x{address:08X}'
        edited = ' 다른 이름! '
        for tsv_matches, receipt_matches in [(True, True), (False, True), (True, False)]:
            with self.subTest(tsv_matches=tsv_matches, receipt_matches=receipt_matches):
                text = edited if tsv_matches else builder.BTEAM_SCRIPT_SPACING_REPAIRS[address][1]
                namespace = {**vars(builder), 'orig': original, 'rom': bytearray(original),
                             'syl_to_code': codes, 'unmapped': collections.Counter(), 'WRITE_LOG': [],
                             'required_script_repoints': set(), 'direct_script_members': {},
                             '_dlg_ov': {key: edited}, '_rp_ov': lambda a: edited.strip(),
                             '_editor_intents': {key: builder.editor_text_digest(edited if receipt_matches else 'stale')},
                             '_rp_bteam': {address}}
                with patch.dict(builder.ADDRESS_TEXT_OVERRIDES, {address: text}):
                    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<actual writer and selector>', 'exec'), namespace)
                    namespace['patch_script_row'](address, end, b'', 'receipt pipeline', source_text=text)
                    _, owners, conflicts = apply_script_span_ownership(
                        {address: (end-address, original[address:end].decode('shift_jis'))},
                        namespace['WRITE_LOG'], namespace['rom'])
                    self.assertFalse(conflicts)
                    namespace['_rp_script_owners'] = owners
                    if tsv_matches and receipt_matches:
                        self.assertEqual(namespace['_rp_dlg'](address), edited)
                        self.assertIn(address, namespace['required_script_repoints'])
                    else:
                        with self.assertRaisesRegex(AssertionError, 'owner missing or changed'):
                            namespace['_rp_dlg'](address)

    def test_editor_intent_receipts_reject_invalid_data(self):
        root = Path(builder.__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root / 'temp') as directory:
            path = Path(directory) / 'intents.json'
            self.assertEqual(builder.load_editor_override_intents(path), {})
            for raw in ['[]', '{"0xA07528":"short"}', '{"0xA07528":null}', '{"0xA07528":"' + 'G' * 64 + '"}']:
                path.write_text(raw)
                with self.subTest(raw=raw), self.assertRaises(ValueError):
                    builder.load_editor_override_intents(path)
            digest = builder.editor_text_digest('이름대로 공중유닛에 강하지만.')
            path.write_text(json.dumps({'0xA07528': digest}))
            self.assertEqual(builder.load_editor_override_intents(path), {'0x00A07528': digest})

    def test_script_override_preserves_intentional_boundary_space(self):
        members = {4: [{'address': 4, 'ko': '옛문구'}]}
        for text in ['이　', ' 조사', '양쪽 ']:
            self.assertEqual(builder.direct_script_override_text(4, 20, members, {'0x00000004': text}), text)
        self.assertIsNone(builder.nonempty_script_text('　 '))

    def test_malformed_dialogue_authority_never_silently_disappears(self):
        root = Path(builder.__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root / 'temp') as directory:
            path = Path(directory) / 'overrides.json'
            for raw in ['{broken', '[]', '{"bad-address":"문구"}', '{"0x4":null}', '{"0x4":"가","0x4":"나"}', '{"0x4":"가","0x00000004":"나"}']:
                path.write_text(raw)
                with self.subTest(raw=raw), self.assertRaises(ValueError):
                    builder.load_dialogue_overrides(path)
            path.write_text(json.dumps({'0x4': '이　'}, ensure_ascii=False))
            self.assertEqual(builder.load_dialogue_overrides(path), {'0x00000004': '이　'})

    def test_literal_alnum_in_main_requires_explicit_renderer_context(self):
        tree = ast.parse(Path(builder.__file__).read_text())
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
        unsafe = []
        for node in ast.walk(main):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == 'encode_text' and node.args
                    and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
                    and re.search('[A-Za-z0-9]', node.args[0].value)):
                address = node.args[3] if len(node.args) >= 4 else next(
                    (kw.value for kw in node.keywords if kw.arg == 'addr'), None)
                if address is None or (isinstance(address, ast.Constant) and address.value is None):
                    unsafe.append(node.lineno)
        self.assertEqual(unsafe, [])

    def dictionary_rom(self):
        rom = bytearray(0x1000000)
        struct.pack_into('<I', rom, builder.PART1_BATTLE_DICTIONARY_POINTER, 0x08D82A1C)
        rom[0xD82A1C:0xD82A22] = b'\x82\x40\x82\x41\x82\x40'
        for address, source, _ in builder.PART1_BATTLE_MENU_LABELS:
            size = len(source.encode('shift_jis'))
            rom[address:address + size] = b'\x88\xaa' * (size // 2)
        return rom

    def test_system_dictionary_keeps_codes_after_ascii_space_and_stops_at_nul(self):
        rom = self.dictionary_rom()
        address, size = builder.PART1_SYSTEM_LABEL_SPANS[0]
        label = b'\x88\xab \x88\xac\x88\xab'
        rom[address:address + size] = label.ljust(size, b'\0')
        before = bytes(rom[address:address + size])
        self.assertEqual(builder.patch_part1_battle_dictionary(rom), 5)
        target = builder.PART1_BATTLE_DICTIONARY_FILE
        self.assertEqual(rom[target:target + 14],
                         b'\x82\x40\x82\x41\x82\x40\x88\xaa\x88\xab\x88\xac\0\0')
        self.assertEqual(rom[address:address + size], before)

    def test_system_dictionary_rejects_split_code_and_nonzero_padding_before_write(self):
        for value in (b'\x88\xab' + b' ' * 11 + b'\x88',
                      b'\x88\xab\0\x88\xac' + b'\0' * 9):
            with self.subTest(value=value):
                rom = self.dictionary_rom()
                address, size = builder.PART1_SYSTEM_LABEL_SPANS[0]
                self.assertEqual(len(value), size)
                rom[address:address + size] = value
                before = bytes(rom)
                with self.assertRaisesRegex(AssertionError, 'System label'):
                    builder.patch_part1_battle_dictionary(rom)
                self.assertEqual(rom, before)

    def test_dictionary_preserves_order_and_appends_each_code_once(self):
        rom = self.dictionary_rom()
        self.assertEqual(builder.patch_part1_battle_dictionary(rom), 3)
        target = builder.PART1_BATTLE_DICTIONARY_FILE
        self.assertEqual(rom[target:target + 10], b'\x82\x40\x82\x41\x82\x40\x88\xaa\0\0')
        self.assertEqual(struct.unpack_from('<I', rom, builder.PART1_BATTLE_DICTIONARY_POINTER)[0],
                         target + 0x08000000)

    def test_dictionary_rejects_tile_capacity_before_writing(self):
        rom = self.dictionary_rom()
        before = bytes(rom)
        with patch.object(builder, 'PART1_BATTLE_MAX_CODES', 2):
            with self.assertRaisesRegex(AssertionError, 'tile allocation'):
                builder.patch_part1_battle_dictionary(rom)
        self.assertEqual(rom, before)

    def test_dictionary_rejects_overlap_with_dialogue_tiles(self):
        rom = self.dictionary_rom()
        codes = [bytes((0x83, i)) for i in range(0x40, 0xFD) if i != 0x7F][:114]
        raw = b''.join(codes) + b'\0\0'
        rom[0xD82A1C:0xD82A1C + len(raw)] = raw
        before = bytes(rom)
        # The menu's extra code would occupy tile 0x100, which dialogue uses.
        with self.assertRaisesRegex(AssertionError, 'tile allocation'):
            builder.patch_part1_battle_dictionary(rom)
        self.assertEqual(rom, before)

    def menu_font_rom(self):
        original = (Path(builder.BASE) / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        rom = bytearray(original)
        builder.patch_part2_ui_kanji_glyphs(rom, original)
        builder.patch_part2_ui_context_tokens(rom)
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        return original, rom, codes

    def test_menu_font_preserves_words_metadata_and_legacy_dictionary_order(self):
        original, rom, codes = self.menu_font_rom()
        before = bytes(rom)
        builder.patch_part1_battle_menu_labels(rom, original, codes)
        reverse = {v.to_bytes(2, 'big'): k for k, v in codes.items()}
        reverse.update({jp.encode('shift_jis'): ko for jp, ko in builder.PART2_UI_KANJI_GLYPH_SUBS.items()})
        reverse[b'\x81\x40'] = ' '
        previous = 0
        for address, source, text in sorted(builder.PART1_BATTLE_MENU_LABELS):
            self.assertEqual(rom[previous:address], before[previous:address])
            size = len(source.encode('shift_jis'))
            actual = bytes(rom[address:address + size])
            pairs = [actual[i:i + 2] for i in range(0, size, 2)]
            self.assertEqual(''.join(reverse[c] for c in pairs if c != b'\0\0'), text)
            previous = address + size
        self.assertEqual(rom[previous:], before[previous:])
        count = builder.patch_part1_battle_dictionary(rom)
        builder.verify_part1_battle_menu_labels(rom, original, codes)
        self.assertLessEqual(0x1C + 2 * count, 0x100)
        start = builder.PART1_BATTLE_DICTIONARY_FILE
        end = before.index(b'\0\0', 0xD82A1C)
        self.assertEqual(rom[start:start + end - 0xD82A1C], before[0xD82A1C:end])
        rom[0xB82DC6] ^= 1
        with self.assertRaisesRegex(AssertionError, 'final menu label'):
            builder.verify_part1_battle_menu_labels(rom, original, codes)

    def test_menu_font_rejects_changed_source_or_alias_glyph_before_writing(self):
        original, rom, codes = self.menu_font_rom()
        changed_source = bytearray(original)
        changed_source[0xB82D6A] ^= 1
        before = bytes(rom)
        with self.assertRaisesRegex(AssertionError, 'source boundary'):
            builder.patch_part1_battle_menu_labels(rom, changed_source, codes)
        self.assertEqual(rom, before)
        top, _ = builder._kanji_table_slots(original)[int.from_bytes('員'.encode('shift_jis'), 'big')]
        rom[builder.P.FONT_FILE + top * 32] ^= 1
        before = bytes(rom)
        with self.assertRaisesRegex(AssertionError, 'alias glyph'):
            builder.patch_part1_battle_menu_labels(rom, original, codes)
        self.assertEqual(rom, before)

    def test_dictionary_rejects_text_opcode(self):
        rom = self.dictionary_rom()
        rom[0xB82DEE] = ord('A')
        before = bytes(rom)
        with self.assertRaisesRegex(AssertionError, 'unsafe System label'):
            builder.patch_part1_battle_dictionary(rom)
        self.assertEqual(rom, before)

    def test_part1_text_alnum_never_becomes_commands(self):
        encoded, _ = builder.encode_fit('A B 10 HP', 40, {}, collections.Counter(), 0xD90885)
        self.assertEqual(encoded, 'Ａ　Ｂ　１０　ＨＰ'.encode('shift_jis'))
        self.assertEqual(builder.encode_full_fidelity('A B 10 HP', {}, collections.Counter(),
                                                    0xD90885), encoded)

    def test_non_dialogue_context_keeps_ascii(self):
        encoded, _ = builder.encode_fit('AB10', 4, {}, collections.Counter(), 0x83FAF6)
        self.assertEqual(encoded, b'AB10')

    def test_part2_story_digits_and_buttons_are_text_not_opcodes(self):
        for address in (0xA01972, 0xA02AF5, 0xA0306D, 0xA03087, 0xA29377):
            with self.subTest(address=hex(address)):
                text = 'A B 3 6 HP'
                expected = 'Ａ　Ｂ　３　６　ＨＰ'.encode('shift_jis')
                encoded, _ = builder.encode_fit(text, 40, {}, collections.Counter(), address)
                self.assertEqual(encoded, expected)
                self.assertEqual(builder.encode_full_fidelity(text, {}, collections.Counter(), address), expected)
                stream = b'\x33' + builder.encode_text('6', {}, collections.Counter(), address) + b'\x30\x6b\0'
                self.assertEqual(stream, b'\x33' + '６'.encode('shift_jis') + b'\x30\x6b\0')
        for address in (0xA29388, 0x83FAF6):
            with self.subTest(ui_address=hex(address)):
                self.assertEqual(builder.encode_text('AB36', {}, collections.Counter(), address), b'AB36')
        # Mission titles have a separate renderer that consumes two-byte pairs.
        self.assertEqual(builder.encode_text('AB36', {}, collections.Counter(), 0xA2D000),
                         'ＡＢ３６'.encode('shift_jis'))
        # Mode-help already required fullwidth text before this story fix.
        self.assertEqual(builder.encode_text('AB36', {}, collections.Counter(), 0xA2C098),
                         'ＡＢ３６'.encode('shift_jis'))

    def test_script_text_without_override_preserves_control_bytes(self):
        text = builder.encode_text('A10', {}, collections.Counter(), 0xD903CD)
        stream = b'\x33' + text + b'\x30\x6b\x00'
        self.assertEqual(stream, b'\x33' + 'Ａ１０'.encode('shift_jis') + b'\x30\x6b\x00')

    def test_whole_row_does_not_append_stale_fragments(self):
        _, members = builder.load_direct_script_metadata()
        overrides = {'0x00D8FFE3': '전투에선 먼저 공격하면 유리해',
                     '0x00D8FFF9': '걸어오는 쪽이', '0x00D9000C': '유리하니까'}
        self.assertEqual(builder.direct_script_override_text(
            0xD8FFE3, 0xD9001C, members, overrides), '전투에선 먼저 공격하면 유리해')

    def test_merged_writer_owns_original_children(self):
        rom = bytearray(b'\0' * 32)
        rom[4:14] = b'\x88\x40\x88\x41' + b' ' * 6
        writes = [[4, 10, 4, '88408841', 32, '완성', 0, 'script:merged']]
        rows, owners, conflicts = apply_script_span_ownership(
            {4: (2, '부모'), 8: (4, '조각'), 16: (2, '다음')}, writes, rom)
        self.assertEqual(rows, {4: (10, '완성'), 16: (2, '다음')})
        self.assertEqual(owners, {4: (10, '완성')})
        self.assertFalse(conflicts)

    def test_partial_overlap_with_command_is_rejected(self):
        rom = bytearray(b' ' * 32)
        rom[4:8] = b'\x88\x40\x88\x41'
        rom[12:14] = b'k\0'
        writes = [[4, 8, 4, '88408841', 32, '완성', 0, 'script:merged']]
        _, _, conflicts = apply_script_span_ownership({8: (6, '조각')}, writes, rom)
        self.assertTrue(conflicts)

    def test_later_overwrite_invalidates_claimed_writer(self):
        rom = bytearray(b' ' * 32)
        writes = [[4, 8, 4, '88408841', 32, '완성', 0, 'script:merged']]
        _, owners, conflicts = apply_script_span_ownership({4: (8, '원문')}, writes, rom)
        self.assertFalse(owners)
        self.assertEqual(conflicts, {4})

    def test_later_write_inside_padding_invalidates_owner(self):
        rom = bytearray(b' ' * 32)
        rom[4:8] = b'\x88\x40\x88\x41'
        rom[10] = 0x6b
        writes = [[4, 8, 4, '88408841', 32, '완성', 0, 'script:merged']]
        _, owners, conflicts = apply_script_span_ownership({4: (8, '원문')}, writes, rom)
        self.assertFalse(owners)
        self.assertEqual(conflicts, {4})

    def test_identical_bytes_do_not_hide_a_later_writer(self):
        rom = bytearray(b' ' * 32)
        rom[4:8] = b'\x88\x40\x88\x41'
        writes = [[4, 8, 4, '88408841', 32, '완성', 0, 'script:merged'],
                  [6, 2, 2, '8841', 32, '다른 의도', 0, 'late-text']]
        _, owners, conflicts = apply_script_span_ownership({4: (8, '원문')}, writes, rom)
        self.assertFalse(owners)
        self.assertEqual(conflicts, {4})

    def control_gap_fixture(self, mutate=False, max_cells=50, payload=b'\x88\x40! '):
        original = bytearray(b'\xff' * 0xE10000)
        msg, pointer = 0xD90000, 0xDA0000
        original[msg:msg + 13] = b'\x33\x2c\x88\x40\x20\x30\x21\x88\x41\x20\x6b\x00\x00'
        struct.pack_into('<I', original, pointer, msg + 0x08000000)
        rom = bytearray(original)
        if mutate:
            rom[msg + 1] = 0x2e
        before = bytes(rom)
        manifest, stats = repoint_messages(
            rom, original, fixable=lambda a: True, fixed_bytes=lambda a: payload,
            fit_level_dlg=lambda a: 6, decode_text=lambda raw: '문장',
            cell_width=lambda a: 4, max_cells=max_cells, slots={},
            line_index={msg + 2: (3, '첫 줄'), msg + 7: (3, '둘째 줄')},
            table_offsets=[], extra_messages={msg: [pointer]},
            free_start=0xA3D000, free_end=0xA40000)
        return rom, before, manifest, stats

    def test_repoint_preserves_punctuation_operands_and_trailing_spaces(self):
        rom, _, manifest, stats = self.control_gap_fixture()
        expected = b'\x33\x2c\x88\x40\x81\x49 \x30\x21\x88\x40\x81\x49 \x6b\x00\x00'
        self.assertEqual(rom[0xA3D000:0xA3D000 + len(expected)], expected)
        self.assertEqual(struct.unpack_from('<I', rom, 0xDA0000)[0], 0x08A3D000)

    def test_repoint_skips_changed_control_gap(self):
        rom, before, _, stats = self.control_gap_fixture(mutate=True)
        self.assertEqual(stats['skip_control_changed'], 1)
        self.assertEqual(rom, before)

    def test_normalization_preserves_high_sjis_trails(self):
        self.assertEqual(normalize_text_segment(b'\xe3\x5c!', True), b'\xe3\x5c\x81\x49')
        self.assertEqual(normalize_text_segment(b'\xb1!', True), b'\xb1\x81\x49')
        self.assertEqual(text_segment_cells(b'\x88\x40\x81\x40\x88\x41 '), 6)

    def test_normalized_width_gate_covers_actual_bytes(self):
        rom, before, _, stats = self.control_gap_fixture(max_cells=4, payload=b'\x88\x40 \x88\x41')
        self.assertEqual(stats['skip_normalized_wide'], 1)
        self.assertEqual(rom, before)

    def test_impure_text_span_is_not_normalized(self):
        rom, before, _, stats = self.control_gap_fixture(payload=b'\x88\x40\x0a!')
        self.assertEqual(stats['skip_impure_span'], 1)
        self.assertEqual(rom, before)

    def test_renderjam_detection_width_and_unique_skip(self):
        original = bytearray(b'\xff' * 0xE10000)
        msg, pointer = 0xD90000, 0xDA0000
        original[msg:msg + 8] = b'\x0a\x09\xb1 \x88\x40k\x00'
        struct.pack_into('<II', original, pointer, msg + 0x08000000, msg + 0x08000000)
        for limit in (50, 4):
            with self.subTest(max_cells=limit):
                rom = bytearray(original)
                manifest, stats = repoint_messages(
                    rom, original, fixable=lambda a: False, fixed_bytes=lambda a: b'',
                    fit_level_dlg=lambda a: 0, decode_text=lambda raw: '대사',
                    cell_width=lambda a: 0, slots={}, line_index={msg + 2: (4, '대사')},
                    table_offsets=[], extra_messages={msg: [pointer, pointer + 4]}, max_cells=limit,
                    free_start=0xA3D000, free_end=0xA40000)
                if limit == 50:
                    self.assertEqual(stats['relocated'], 1)
                    self.assertEqual(rom[0xA3D000:0xA3D009], b'\x0a\x09\xb1\x81\x40\x88\x40k\x00')
                else:
                    self.assertEqual(stats['skip_normalized_wide'], 1)
                    self.assertEqual(len(manifest), 1)
                    self.assertEqual(rom, original)

    def test_removed_child_pointer_still_blocks_relocation(self):
        original = bytearray(b'\xff' * 0xE10000)
        msg, pointer = 0xD90000, 0xDA0000
        original[msg:msg + 10] = b'\x0a\x09\x88\x40\x88\x41\x88\x42k\0'
        struct.pack_into('<I', original, pointer, msg + 0x08000000)
        struct.pack_into('<I', original, 0x200, msg + 4 + 0x08000000)
        rom = bytearray(original)
        manifest, stats = repoint_messages(
            rom, original, fixable=lambda a: True, fixed_bytes=lambda a: b'\x88\x40',
            fit_level_dlg=lambda a: 6, decode_text=lambda raw: '문장',
            cell_width=lambda a: 4, slots={msg + 2: 6},
            line_index={msg + 2: (6, '합친 문장')}, table_offsets=[],
            extra_messages={msg: [pointer]}, original_line_starts={msg + 2, msg + 4},
            free_start=0xA3D000, free_end=0xA40000)
        self.assertEqual(stats['skip_mid_ref'], 1)
        self.assertEqual(rom, original)


if __name__ == '__main__':
    unittest.main()
