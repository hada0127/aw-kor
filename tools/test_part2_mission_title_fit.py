import struct
import json
import ast
import collections
import unittest
from pathlib import Path

import build_korean_full as builder
import part2_mission_title_fit as fit


class MissionTitleFitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = Path(builder.P.ROM).read_bytes()

    def test_compact_ink_preserves_height_and_fits_20px_cell(self):
        for char in '해상도시를노려라전투의서막':
            original = builder._mission_title_hangul_glyph(char)
            compact = fit.compact_glyph(original)
            rows = []
            for raw in (original, compact):
                active = set()
                for y in range(32):
                    for x in range(32):
                        a = (y // 8 * 4 + x // 8) * 32 + y % 8 * 4 + x % 8 // 2
                        value = raw[a] >> (4 * (x % 2)) & 15
                        if value:
                            active.add(y)
                            if raw is compact:
                                self.assertLess(x, 19)
                rows.append(active)
            self.assertTrue(rows[1])
            self.assertEqual(min(rows[0]), min(rows[1]))
            self.assertEqual(max(rows[0]), max(rows[1]))
        self.assertEqual(fit.compact_glyph(bytes(512)), bytes(512))

    def test_active_relocated_title_is_checked_not_stale_source(self):
        rom = bytearray(self.original)
        pointer = 0xA382B8
        destination = 0xF71000
        rom[destination:destination + 25] = b'\x81\x40' * 12 + b'\0'
        struct.pack_into('<I', rom, pointer, 0x08000000 + destination)
        with self.assertRaisesRegex(AssertionError, '11-code'):
            fit.active_titles(self.original, rom)

    def test_hook_or_reserved_area_drift_fails_before_writes(self):
        for address in (fit.BASE, *(a for a, _, _ in fit.SITES)):
            rom = bytearray(self.original)
            rom[address] ^= 1
            before = bytes(rom)
            with self.assertRaises(AssertionError):
                fit.patch(rom, self.original, builder._lz77_literal_block)
            self.assertEqual(bytes(rom), before)

    def fixture(self):
        rom = bytearray(self.original)
        for pointer, _, _, _ in fit.active_titles(self.original, self.original):
            struct.pack_into('<I', rom, pointer, 0x08F71000)
        rom[0xF71000:0xF71005] = b'\x88\x40' * 2 + b'\0'
        for pointer, destination, count in ((0xA382B8, 0xF71100, 11), (0xA382F4, 0xF71200, 10)):
            struct.pack_into('<I', rom, pointer, destination + 0x08000000)
            rom[destination:destination + count * 2 + 1] = b'\x88\x40' * count + b'\0'
        rom[0xF40000:0xF40018] = struct.pack('<HHII', 0x8840, 0, 0x08F42000, 24) + bytes(12)
        glyph = builder._lz77_literal_block(builder._mission_title_hangul_glyph('해'))
        rom[0xF42000:0xF42000 + len(glyph)] = glyph
        return rom

    def test_successful_patch_freezes_active_titles_and_preserves_other_bytes(self):
        rom = self.fixture()
        before = bytes(rom)
        regions, report = fit.patch(rom, self.original, builder._lz77_literal_block)
        self.assertEqual((report['titles'], report['long_titles'], report['compact_codes']), (179, 2, 1))
        for start, expected in regions:
            self.assertEqual(rom[start:start + len(expected)], expected)
        restored = bytearray(rom)
        restored[fit.BASE:fit.END] = before[fit.BASE:fit.END]
        for address, expected, _ in fit.SITES:
            restored[address:address + len(expected)] = before[address:address + len(expected)]
        self.assertEqual(restored, before)

    def test_missing_long_title_glyph_fails_without_mutation(self):
        rom = self.fixture()
        rom[0xF71100:0xF71102] = b'\x88\x41'
        before = bytes(rom)
        with self.assertRaisesRegex(AssertionError, 'unregistered'):
            fit.patch(rom, self.original, builder._lz77_literal_block)
        self.assertEqual(rom, before)

    def test_short_and_relocated_titles_reject_ascii_and_partial_pairs(self):
        for destination in (0xA2D5C8, 0xF71300):
            for payload in (b'\x88\x40' * 4 + b'7\x88\x40\0', b'\x88\x40!\0\0', b'\x88\x40  \0'):
                rom = self.fixture()
                struct.pack_into('<I', rom, 0xA382C0, 0x08000000 + destination)
                rom[destination:destination + len(payload)] = payload
                with self.assertRaisesRegex(AssertionError, 'invalid mission title pair'):
                    fit.active_titles(self.original, rom)

    def test_short_title_missing_blank_or_invalid_glyph_fails_before_writes(self):
        for problem in ('missing', 'blank', 'pointer', 'duplicate'):
            rom = self.fixture()
            rom[0xF71000:0xF71002] = b'\x88\x41'
            entry = struct.pack('<HHII', 0x8841, 0, 0x08F43000, 24)
            if problem != 'missing':
                rom[0xF4000C:0xF40024] = entry + bytes(12)
                if problem == 'pointer':
                    struct.pack_into('<I', rom, 0xF40010, 0x07000000)
                elif problem == 'duplicate':
                    rom[0xF40018:0xF40030] = entry + bytes(12)
                glyph = builder._lz77_literal_block(bytes(512) if problem == 'blank' else builder._mission_title_hangul_glyph('해'))
                rom[0xF43000:0xF43000 + len(glyph)] = glyph
            before = bytes(rom)
            with self.assertRaisesRegex(AssertionError, 'unregistered|blank visible|outside ROM|duplicate'):
                fit.patch(rom, self.original, builder._lz77_literal_block)
            self.assertEqual(rom, before)

    def test_title_encoder_preserves_digits_letters_signs_and_full_spacing(self):
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        payload = fit.encode_pair_title('내일로 7일간', codes)
        expected = b''.join(codes[c].to_bytes(2, 'big') if c in codes else c.encode('shift_jis')
                            for c in '내일로　７일간')
        self.assertEqual(payload, expected)
        self.assertEqual(len(payload), 14)
        self.assertEqual(fit.encode_pair_title('VS 2!', codes), 'ＶＳ　２！'.encode('shift_jis'))
        self.assertEqual(fit.encode_pair_title('ＶＳ　２！', codes), 'ＶＳ　２！'.encode('shift_jis'))
        for text in ('\0', '\n', '🙂', 'ﾊ'):
            with self.assertRaises(AssertionError):
                fit.encode_pair_title(text, codes)
        self.assertFalse(fit.is_pair_title(0xA01D41))
        self.assertFalse(fit.is_pair_title(0xA2CFFF))
        self.assertFalse(fit.is_pair_title(0xA2D8B0))

    def test_builder_encoding_and_actual_direct_writer_keep_title_pairs(self):
        codes = {s: int(c, 16) for s, c in json.loads(Path(builder.SYLCODE).read_text()).items()}
        text = builder.ADDRESS_TEXT_OVERRIDES[0xA2D5C8]
        expected = fit.encode_pair_title(text, codes)
        self.assertEqual(len(expected), 14)
        for encode in (builder.encode_text, builder.encode_full_fidelity):
            self.assertEqual(encode(text, codes, collections.Counter(), 0xA2D5C8), expected)
        self.assertEqual(builder.encode_fit(text, 14, codes, collections.Counter(), 0xA2D5C8)[0], expected)
        tree = ast.parse(Path(builder.__file__).read_text())
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'patch_script_row')
        rom = bytearray(self.original)
        namespace = dict(vars(builder), orig=self.original, rom=rom, syl_to_code=codes,
                         unmapped=collections.Counter(), direct_script_members={}, _dlg_ov={},
                         required_script_repoints=set(), WRITE_LOG=[])
        exec(compile(ast.Module(body=[node], type_ignores=[]), builder.__file__, 'exec'), namespace)
        namespace['patch_script_row'](0xA2D5C8, 0xA2D5D6, b'wrong', 'test', source_text=text)
        self.assertEqual(rom[0xA2D5C8:0xA2D5D8], expected + b'\0\0')
        namespace['patch_script_row'](0xA2D028, 0xA2D038, fit.encode_pair_title('승리 라인', codes), 'test', source_text='승리 라인')
        payload = bytes.fromhex(namespace['WRITE_LOG'][-1][3])
        self.assertEqual(rom[0xA2D028 + len(payload):0xA2D038], bytes(16 - len(payload)))
        # A native ten-byte title expands to fourteen bytes; keep the source
        # intact until guarded relocation, with exact text as its writer owner.
        text = '해 VS 공!'
        start, end = 0xA2D7D4, 0xA2D7DE
        before = bytes(rom[start:end + 2])
        namespace['patch_script_row'](start, end, fit.encode_pair_title(text, codes), 'test', source_text=text)
        self.assertEqual(rom[start:end + 2], before)
        self.assertIn(start, namespace['required_script_repoints'])
        self.assertEqual(namespace['WRITE_LOG'][-1][5], text)
        with self.assertRaisesRegex(AssertionError, 'required script relocation failed'):
            builder.verify_required_script_repoints(namespace['required_script_repoints'], set())
        # Context selection leaves the non-title command and ordinary UI paths.
        self.assertEqual(builder.encode_text('VS 2!', codes, collections.Counter()), b'VS 2!')
        self.assertEqual(builder.encode_text('2!', codes, collections.Counter(), 0xA01D41), '２'.encode('shift_jis') + b'!')

    def test_active_relocated_short_glyph_is_registered_after_repoint(self):
        rom = self.fixture()
        # This syllable occurs only in a relocated title, never its stale slot.
        rom[0xF71000:0xF71002] = b'\x88\x41'
        evidence = {}
        builder.patch_pair_renderer_title_glyph_table(rom, self.original, {}, { '해': 0x8840, '상': 0x8841 }, evidence=evidence)
        regions, _ = fit.patch(rom, self.original, builder._lz77_literal_block)
        self.assertTrue(regions)
        builder.verify_pair_renderer_title_glyph_table(rom, evidence)

    def test_missing_fullwidth_digit_and_latin_title_art_is_visible(self):
        rom = self.fixture()
        payload = '２ＶＳ'.encode('shift_jis') + b'\0'
        rom[0xF71000:0xF71000 + len(payload)] = payload
        builder.patch_pair_renderer_title_glyph_table(rom, self.original, {}, {'해': 0x8840}, evidence={})
        entries = {}
        for off in range(0xF40000, 0xF42000, 12):
            code, _, pointer, _ = struct.unpack_from('<HHII', rom, off)
            if not pointer:
                break
            entries[code] = pointer - 0x08000000
        from lz77_scan import lz77_decompress
        for pair in (0x8251, 0x8275, 0x8272):
            self.assertTrue(any(lz77_decompress(rom, entries[pair])[0]))
        self.assertTrue(fit.patch(rom, self.original, builder._lz77_literal_block)[0])

    def test_inplace_title_cannot_read_into_next_entry(self):
        rom = bytearray(self.original)
        end = self.original.index(b'\0', 0xA2D5C8)
        rom[end:end + 2] = b'\x88\x40'
        with self.assertRaisesRegex(AssertionError, 'partial code|terminator'):
            fit.active_titles(self.original, rom)
        # Unsupported odd-byte ordinary names are rejected at their own NUL;
        # no evidence range may silently swallow the next field.
        rom = bytearray(self.original)
        rom[0xA2CC4C:0xA2CC4E] = b'A\0'
        with self.assertRaisesRegex(AssertionError, 'partial code'):
            fit.active_titles(self.original, rom)

    def test_non_strict_long_title_cannot_use_blank_compact_art(self):
        self.assertFalse(fit.is_pair_title(struct.unpack_from('<I', self.original, 0xA38084)[0] - 0x08000000))
        rom = self.fixture()
        struct.pack_into('<I', rom, 0xA38084, 0x08F71300)
        rom[0xF71300:0xF71315] = b'\x88\x41'*10+b'\0'
        rom[0xF4000C:0xF40024] = struct.pack('<HHII', 0x8841, 0, 0x08F43000, 24)+bytes(12)
        raw = builder._lz77_literal_block(bytes(512))
        rom[0xF43000:0xF43000+len(raw)] = raw
        with self.assertRaisesRegex(AssertionError, 'blank visible glyph'):
            fit.patch(rom, self.original, builder._lz77_literal_block)

    def test_title_outside_old_filter_is_validated(self):
        rom = self.fixture()
        struct.pack_into('<I', rom, 0xA38084, 0x08F71300)
        rom[0xF71300:0xF71319] = b'\x88\x40' * 12 + b'\0'
        with self.assertRaisesRegex(AssertionError, '11-code'):
            fit.active_titles(self.original, rom)

    def test_unterminated_title_and_source_drift_fail(self):
        rom = self.fixture()
        struct.pack_into('<I', rom, 0xA382B8, 0x08000000 + len(rom) - 2)
        rom[-2:] = b'\x88\x40'
        with self.assertRaisesRegex(AssertionError, 'terminator'):
            fit.active_titles(self.original, rom)
        for address in (fit.BASE, fit.SITES[0][0], 0x324E04):
            original = bytearray(self.original)
            original[address] ^= 1
            with self.assertRaises(AssertionError):
                fit.patch(bytearray(original), original, builder._lz77_literal_block)


if __name__ == '__main__':
    unittest.main()
