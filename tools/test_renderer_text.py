import collections
import json
import os
from pathlib import Path
import unittest
from renderer_text import (P1_SCRIPT, P2_SCRIPT, P1_PAIRS, normalize_text,
                           halfwidth_violations, renderer_for_address)
from build_korean_full import _abs_tramp, encode_text


class RendererTextTests(unittest.TestCase):
    def test_authored_digits_letters_punctuation_are_pairs(self):
        raw = encode_text('40 WARS2!', {}, collections.Counter(), 0xA35680)
        self.assertEqual(raw, '４０　ＷＡＲＳ２！'.encode('shift_jis'))
        self.assertFalse(halfwidth_violations(raw, P2_SCRIPT))
        for b in b'034AW!':
            self.assertTrue(halfwidth_violations(bytes([b]) + raw, P2_SCRIPT))

    def test_native_style_codes_and_hangul_trails(self):
        native = b'2\x95\xe0\x95\xba0r\x0a\x09'
        korean = b'2\x88\x40\x8d\x690r\x0a\x09'
        self.assertFalse(halfwidth_violations(korean, P1_SCRIPT, native))
        self.assertTrue(halfwidth_violations(korean + b'3', P1_SCRIPT, native))
        self.assertTrue(halfwidth_violations(korean, P1_PAIRS, native))

    def test_added_control_requires_recorded_reflow(self):
        native = b'\x81\x40'
        payload = native + b'k'
        self.assertEqual(halfwidth_violations(payload, P1_SCRIPT, native), [(2, ord('k'))])
        self.assertFalse(halfwidth_violations(payload, P1_SCRIPT, native,
                                              added_controls=b'k'))
        self.assertEqual(halfwidth_violations(payload + b'k', P1_SCRIPT, native,
                                              added_controls=b'k'), [(3, ord('k'))])

    def test_null_text_final_script_owner_is_audited(self):
        from qa_renderer_text import check
        addr = 0xDC67B6
        rom = bytearray(addr + 16)
        rom[addr:addr + 2] = b'k '
        writes = [[addr, 2, 2, '6b20', 0x20, None, None, 'script:snow you are row']]
        count, errors = check(rom, bytearray(len(rom)), writes, [])
        self.assertEqual(count, 1)
        self.assertTrue(any(int(e[0], 16) == addr for e in errors))

    def test_numeric_decimal_and_ellipsis_preserve_their_roles(self):
        self.assertEqual(normalize_text('1.5 ... 끝.', P2_SCRIPT), '１・５ ・・・ 끝。')

    def test_latin_only_owner_is_guarded(self):
        from qa_renderer_text import check
        rom = bytearray(0xA35300)
        rom[0xA352B4:0xA352B8] = b'WAR2'
        writes = [[0xA352B4, 4, 4, '57415232', None, 'WAR2', 0, 'test']]
        count, errors = check(rom, bytearray(len(rom)), writes, [])
        self.assertEqual(count, 1)
        self.assertTrue(errors)

    def test_partial_owner_cannot_hide_ascii(self):
        from qa_renderer_text import check
        rom = bytearray(0xA35300)
        rom[0xA352B4:0xA352B8] = 'Ｗ'.encode('shift_jis') + b'AR'
        writes = [[0xA352B4, 4, 4, '', None, 'WAR', 0, 'old'],
                  [0xA352B4, 2, 2, '', None, 'Ｗ', 0, 'new']]
        count, errors = check(rom, bytearray(len(rom)), writes, [])
        self.assertEqual(count, 2)
        self.assertTrue(any(int(e[0], 16) == 0xA352B6 for e in errors))

    def test_width_depends_on_native_renderer_and_installed_hook(self):
        from text_metrics import encoded_len, visual_cells, encoded_visual_cells
        self.assertEqual(encoded_len('40 WARS2', P2_SCRIPT), 15)
        self.assertEqual(visual_cells('40 WARS2', P2_SCRIPT), 14)
        raw = '４０ ＷＡＲＳ２'.encode('shift_jis')
        self.assertEqual(encoded_visual_cells(raw, P2_SCRIPT), 14)
        self.assertEqual(encoded_visual_cells(raw, P1_SCRIPT, p1_space_hook=True), 16)
        self.assertEqual(encoded_visual_cells(raw, P1_PAIRS), 14)
        with self.assertRaises(ValueError):
            encoded_visual_cells(b'4', P2_SCRIPT)

    def test_client_images_are_excluded(self):
        for a in (0x929398, 0x962020, 0x99a8c4, 0x9d3168, 0xee22c4):
            self.assertIsNone(renderer_for_address(a))

    def test_unaligned_thumb_literal_resolves_hook(self):
        for site, hook in ((0x08313FD6, 0x08F30360), (0x08B11DFE, 0x08F303A0)):
            raw = _abs_tramp(0, hook, site)
            insn = int.from_bytes(raw[:2], 'little')
            literal = ((site + 4) & ~3) + (insn & 255) * 4
            self.assertEqual(literal & 3, 0)
            self.assertEqual(int.from_bytes(raw[literal-site:literal-site+4], 'little'), hook | 1)
            self.assertEqual(len(raw), 10)
            # Native newline (+12) and non-control (+10) branches survive.
            self.assertLessEqual(len(raw), 10)

    def test_mutated_final_rom_ascii_digit_fails_guard(self):
        candidate = os.environ.get('AW_TEST_ROM')
        if not candidate:
            self.skipTest('AW_TEST_ROM required')
        from qa_renderer_text import check
        root = Path(__file__).resolve().parents[1]
        rom = bytearray(Path(candidate).read_bytes())
        original = (root / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        writes = json.loads((root / 'temp/integrity_map.json').read_text())
        manifest = json.loads((root / 'temp/repoint_manifest.json').read_text())
        self.assertFalse(check(rom, original, writes, manifest)[1])
        self.assertEqual(rom[0xB81CF0:0xB81CF2], '３'.encode('shift_jis'))
        rom[0xB81CF0:0xB81CF2] = b'3 '
        self.assertTrue(any(int(e[0], 16) == 0xB81CF0 for e in check(rom, original, writes, manifest)[1]))

    def test_approved_punctuation_compromise_is_exact_address_and_payload(self):
        root = Path(__file__).resolve().parents[1]
        decisions = json.loads((root / 'data/part1_punctuation_decisions.json').read_text())
        self.assertEqual(set(decisions), {'0x00DC67B6'})
        decision = decisions['0x00DC67B6']
        self.assertEqual(decision['source'], '너란 녀석은...')
        self.assertEqual(decision['shipped'], '너란 녀석은・・')
        self.assertEqual(len(bytes.fromhex(decision['payload_hex'])), 16)
