import struct
import json
import ast
import collections
import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import build_korean_full as builder
import part2_mission_title_fit as fit
import aw_fonts
import qa_sprite_shape as sprite_shape


def compact_shape_oracle():
    """Load the gate's pure oracle without running its command-line audit."""
    path = Path(__file__).with_name('qa_sprite_art_shapes.py')
    tree = ast.parse(path.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == 'compact_hada_shape')
    namespace = dict(Image=Image, ImageDraw=ImageDraw, ImageFont=ImageFont,
                     ImageFilter=ImageFilter)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace['compact_hada_shape']


class CompactShapeOracleTests(unittest.TestCase):
    @staticmethod
    def mutate(raw, changes):
        result = bytearray(raw)
        for x, y, value in changes:
            index = (y // 8 * 4 + x // 8) * 32 + (y % 8) * 4 + x % 8 // 2
            shift = 4 * (x % 2)
            result[index] = (result[index] & ~(15 << shift)) | (value << shift)
        return bytes(result)

    @staticmethod
    def face(raw):
        from aw_fonts import obj_canvas
        return {(x, y) for y, row in enumerate(obj_canvas(raw, 1, 4, 4))
                for x, value in enumerate(row) if value == 6}

    def test_approved_compact_population_and_corruptions(self):
        check = compact_shape_oracle()
        raw = fit.compact_glyph(builder._mission_title_hangul_glyph('막'))
        self.assertEqual(check('막', raw)['failures'], [])
        face = self.face(raw)
        mask = Image.new('L', (32, 32))
        for point in face:
            mask.putpixel(point, 255)
        parts = sprite_shape.components(mask)
        self.assertGreaterEqual(len(parts), 2)

        runs = []
        for y in range(32):
            xs = {x for x, yy in face if yy == y}
            for x in xs:
                if x - 1 not in xs:
                    run = []
                    while x in xs:
                        run.append((x, y, 0))
                        x += 1
                    runs.append(run)
        dropped = self.mutate(raw, max(runs, key=len))
        self.assertIn('Hada component stroke missing', check('막', dropped)['failures'])

        # Join two formerly separate jamo with a face-index bridge.
        a, b = min(((a, b) for a in parts[0] for b in parts[1]),
                   key=lambda pair: abs(pair[0][0]-pair[1][0])+abs(pair[0][1]-pair[1][1]))
        bridge = []
        x, y = a
        while x != b[0]:
            x += 1 if b[0] > x else -1
            bridge.append((x, y, 6))
        while y != b[1]:
            y += 1 if b[1] > y else -1
            bridge.append((x, y, 6))
        self.assertIn('split/merged/stray components',
                      check('막', self.mutate(raw, bridge))['failures'])

        # Fill an internal vertical gap between two face strokes.
        gaps = []
        for x in range(19):
            ys = sorted(y for xx, y in face if xx == x)
            for lo, hi in zip(ys, ys[1:]):
                if hi - lo > 1:
                    gaps.append((x, lo, hi))
        self.assertTrue(gaps)
        x, lo, hi = max(gaps, key=lambda gap: gap[2]-gap[1])
        filled = self.mutate(raw, [(x, y, 6) for y in range(lo+1, hi)])
        self.assertIn('Hada jamo stroke gap removed', check('막', filled)['failures'])


class MissionTitleFitTests(unittest.TestCase):
    def test_comma_pixels_and_advance_fit_native_obj(self):
        raw = builder._mission_title_hangul_glyph(',')
        self.assertEqual(len(raw), 512)
        # Independent OBJ decoder, also used by the sprite shape oracle.
        pixels = aw_fonts.obj_canvas(raw, 1, 4, 4)
        ink = [(x, y) for y, row in enumerate(pixels) for x, v in enumerate(row) if v]
        self.assertTrue(ink)
        self.assertEqual({v for row in pixels for v in row}, {0, 6, 10})
        self.assertLess(max(x for x, y in ink), builder.MISSION_TITLE_COMMA_ADVANCE)
        self.assertGreater(min(y for x, y in ink), 16)  # baseline comma, not a raised dot
        self.assertLess(max(y for x, y in ink), 32)
        self.assertEqual(fit.compact_glyph(raw), raw)
        for unsupported in ('', '.', '，', ',,', '😀'):
            with self.subTest(unsupported=unsupported), self.assertRaises(AssertionError):
                builder._mission_title_hangul_glyph(unsupported)

    def test_restored_comma_title_registers_and_survives_layout(self):
        from lz77_scan import lz77_decompress
        codes = {k: int(v, 16) for k, v in json.loads(Path(builder.SYLCODE).read_text()).items()}
        text = '푸른 달이여,영원히'
        payload = fit.encode_pair_title(text, codes) + b'\0'
        self.assertEqual(payload[12:14], bytes.fromhex('8143'))
        for sample in (payload, bytes.fromhex('814300'), bytes.fromhex('81438143814000')):
            with self.subTest(payload=sample.hex()):
                rom = self.fixture()
                pointer, destination = 0xA38304, 0xF71300
                struct.pack_into('<I', rom, pointer, destination + 0x08000000)
                rom[destination:destination + len(sample)] = sample
                evidence = {}
                builder.patch_pair_renderer_title_glyph_table(rom, self.original, {}, codes, evidence=evidence)
                entries = {}
                for a in range(0xF40000, 0xF42000, 12):
                    c, _, p, advance = struct.unpack_from('<HHII', rom, a)
                    if not p:
                        break
                    entries[c] = (p, advance)
                p, advance = entries[0x8143]
                self.assertEqual(advance, 12)
                self.assertEqual(p % 4, 0)
                decoded = lz77_decompress(bytes(rom), p - 0x08000000)[0]
                self.assertEqual(decoded, builder._mission_title_hangul_glyph(','))
                self.assertTrue(any(decoded))
                self.assertNotIn('8143', evidence['legacy_blank_sources'])
                # Original native entries, including other punctuation, stay byte-identical.
                self.assertEqual(rom[0xF40000:0xF40000 + 144 * 12],
                                 self.original[0xA3AF04:0xA3AF04 + 144 * 12])
                fit.patch(rom, self.original, builder._lz77_literal_block)
                builder.verify_pair_renderer_title_glyph_table(rom, evidence)
                self.assertEqual(rom[destination:destination + len(sample)], sample)
                self.assertIn((pointer, destination, tuple(int.from_bytes(sample[i:i+2], 'big')
                                  for i in range(0, len(sample)-1, 2)), sample),
                              fit.active_titles(self.original, rom))

    def test_hangul_glyph_uses_pinned_hada_fonts(self):
        bold, guide = builder._mission_title_hangul_fonts()
        self.assertEqual(hashlib.sha256(Path(bold.path).read_bytes()).hexdigest(), aw_fonts.HADASANS_SHA256)
        self.assertEqual(hashlib.sha256(Path(guide.path).read_bytes()).hexdigest(), aw_fonts.HADASANS_BLACK_SHA256)
        self.assertNotEqual(Path(bold.path), Path(builder._mission_title_font().path))
        with patch.object(builder, '_mission_title_hangul_fonts', side_effect=FileNotFoundError('Hada missing')):
            with self.assertRaisesRegex(FileNotFoundError, 'Hada missing'):
                builder._mission_title_hangul_glyph('한')

    def test_hangul_glyph_ink_bounds_and_glyph_payload_hashes(self):
        titles = {
            '레드스타 진군!': 'c6376f19ef96d391b4a4954c58d95ac97d6ad836f06c1d856a4a7015a2d1bd49',
            '최종결전!': 'bfc602aa1d15d000a1f2f159475479a3be74d906e66f6b1f22ea47a9123a512e',
            '검은 악마를 막아라!': '8ee82faa835a01afb192396fc873734387cd4a7c1da21347ace84b32e5616834',
        }
        for title, expected in titles.items():
            raw = bytearray()
            for char in title:
                if not '가' <= char <= '힣':
                    continue  # space and punctuation retain their native table entries
                glyph = builder._mission_title_hangul_glyph(char)
                face, all_ink = [], []
                for y in range(32):
                    for x in range(32):
                        a = (y // 8 * 4 + x // 8) * 32 + y % 8 * 4 + x % 8 // 2
                        value = glyph[a] >> (4 * (x % 2)) & 15
                        if value == 6:
                            face.append((x, y))
                        if value:
                            all_ink.append((x, y))
                self.assertTrue(face, char)
                width = max(x for x, _ in face) - min(x for x, _ in face) + 1
                height = max(y for _, y in face) - min(y for _, y in face) + 1
                self.assertTrue(19 <= width <= 21, (char, width))
                self.assertEqual(height, 22, char)
                self.assertLess(max(x for x, _ in all_ink), 24)
                self.assertLess(max(y for _, y in all_ink), 32)
                if len(title) > 9:
                    glyph = fit.compact_glyph(glyph)
                    compact_x = [x for y in range(32) for x in range(32)
                                 if glyph[(y // 8 * 4 + x // 8) * 32 + y % 8 * 4 + x % 8 // 2]
                                 >> (4 * (x % 2)) & 15]
                    self.assertLess(max(compact_x), 19)
                raw.extend(glyph)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), expected, title)

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
        for address in (fit.BASE, *(a for a, _, _ in (*fit.SITES, fit.MAP_SITE))):
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
        for address, expected, _ in (*fit.SITES, fit.MAP_SITE):
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
        self.assertEqual(text, '내일로의 7일간')
        self.assertEqual(len(expected), 16)
        for encode in (builder.encode_text, builder.encode_full_fidelity):
            self.assertEqual(encode(text, codes, collections.Counter(), 0xA2D5C8), expected)
        self.assertIsNone(builder.encode_fit(text, 14, codes, collections.Counter(), 0xA2D5C8)[0])
        tree = ast.parse(Path(builder.__file__).read_text())
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'patch_script_row')
        rom = bytearray(self.original)
        namespace = dict(vars(builder), orig=self.original, rom=rom, syl_to_code=codes,
                         unmapped=collections.Counter(), direct_script_members={},
                         _dlg_ov={'0x00A2D5C8': text, '0x00A2D028': '승리 라인',
                                  '0x00A2D7D4': '해 VS 공!'},
                         required_script_repoints=set(), WRITE_LOG=[])
        exec(compile(ast.Module(body=[node], type_ignores=[]), builder.__file__, 'exec'), namespace)
        before_title = bytes(rom[0xA2D5C8:0xA2D5D8])
        namespace['patch_script_row'](0xA2D5C8, 0xA2D5D6, b'wrong', 'test', source_text=text)
        # Approved wording is now 16 bytes, so the 14-byte native slot must
        # remain intact until the existing lossless title relocation step.
        self.assertEqual(rom[0xA2D5C8:0xA2D5D8], before_title)
        self.assertIn(0xA2D5C8, namespace['required_script_repoints'])
        self.assertEqual(namespace['WRITE_LOG'][-1][5], text)
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
        # Shared full-fidelity writer preserves mixed/repeated spaces and signs.
        for text in ('해  VS 공!', '해　 VS 공!', '해[]{};▼・공!'):
            namespace['_dlg_ov']['0x00A2D7D4'] = text
            namespace['patch_script_row'](start, end, b'wrong', 'test', source_text='ignored')
            self.assertEqual(rom[start:end + 2], before)
            self.assertEqual(namespace['WRITE_LOG'][-1][5], text)
            self.assertIn(start, namespace['required_script_repoints'])
            self.assertEqual(builder.encode_full_fidelity(text, codes, collections.Counter(), start),
                             fit.encode_pair_title(text, codes))
        with self.assertRaisesRegex(AssertionError, 'required script relocation failed'):
            builder.verify_required_script_repoints(namespace['required_script_repoints'], set())
        # Context selection leaves the non-title command and ordinary UI paths.
        self.assertEqual(builder.encode_text('VS 2!', codes, collections.Counter()), b'VS 2!')
        # b24: the 31424C renderer profile also widens authored punctuation.
        self.assertEqual(builder.encode_text('2!', codes, collections.Counter(), 0xA01D41), '２！'.encode('shift_jis'))

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

    def test_newly_catalogued_long_title_cannot_use_blank_compact_art(self):
        self.assertTrue(fit.is_pair_title(struct.unpack_from('<I', self.original, 0xA38084)[0] - 0x08000000))
        rom = self.fixture()
        struct.pack_into('<I', rom, 0xA38084, 0x08F71300)
        rom[0xF71300:0xF71315] = b'\x88\x41'*10+b'\0'
        rom[0xF4000C:0xF40024] = struct.pack('<HHII', 0x8841, 0, 0x08F43000, 24)+bytes(12)
        raw = builder._lz77_literal_block(bytes(512))
        rom[0xF43000:0xF43000+len(raw)] = raw
        with self.assertRaisesRegex(AssertionError, 'blank visible glyph'):
            fit.patch(rom, self.original, builder._lz77_literal_block)

    def test_catalogued_names_use_all_writer_padding_and_lossless_guards(self):
        codes = {'도':0x8840,'넛':0x8841,'섬':0x8842}
        start = 0xA2CC4C
        payload = fit.encode_pair_title('도넛 섬', codes)
        rom = bytearray(self.original)
        builder.write_slot_text(rom,start,12,payload,'도넛 섬',0,'test')
        self.assertEqual(rom[start:start+12],payload+bytes(4))
        self.assertTrue(builder.in_region(builder.PAIR_RENDERER_REGIONS,start,start+12))
        for row in fit.NATIVE_TITLES:
            a,z = int(row['source'],16),int(row['source_end'],16)
            self.assertTrue(fit.is_pair_title(a))
            self.assertTrue(builder.in_region(builder.PAIR_RENDERER_REGIONS,a,z))
        from qa_bteam_drift import display_equivalent
        self.assertEqual(display_equivalent('VS 2!',start),'ＶＳ　２！')
        self.assertNotEqual(display_equivalent('VS 2!',start),'ＶＳ２！')

    def test_chunked_raster_preserves_native_geometry_and_decoration_banks(self):
        glyph = builder._mission_title_hangul_glyph('해')
        spacing = struct.unpack_from('<12H',self.original,0x8FD6C4)
        # 10-code: native 24px glyphs, two 12px spaces, final 26px sign.
        # 11-code: same font/spacing exceeds screen, using existing compact art.
        for codes,expected in (([1]*7+[2]*2+[3],(227,8,False,6)),
                               ([1]*8+[2]*2+[3],(220,7,True,10))):
            raw, report = fit.map_title_raster(codes,{1:glyph,2:bytes(512),3:glyph},
                                               {1:24,2:12,3:26},spacing)
            self.assertEqual((report['span'],report['chunks'],report['compact'],report['x']),expected)
            self.assertEqual(len(raw),report['chunks']*512)
            self.assertEqual(report['sum_width']+(report['chunks']-1)*spacing[report['chunks']],report['span'])
            for bank in (0,0xD0):
                self.assertLessEqual(bank+report['bank_tiles'],bank+0x90)
            # Transparent tail must not create glyph fragments in unused pixels.
            last = fit.glyph_pixels(raw[-512:]);tail = report['span']%32
            self.assertTrue(all(not any(row[tail:]) for row in last))

    def test_final_rom_gate_detects_corrupt_composite_and_trampoline(self):
        from qa_native_title_layout import audit
        rom = self.fixture()
        fit.patch(rom,self.original,builder._lz77_literal_block)
        struct.pack_into('<I',rom,0x37C548,0x08F40000)
        self.assertEqual(audit(self.original,rom)['map_composites'],2)
        for address in (fit.MAP_DESCRIPTORS+12,fit.MAP_SITE[0]):
            damaged=bytearray(rom);damaged[address]^=1
            with self.assertRaises(ValueError):audit(self.original,damaged)

    def test_catalogue_drift_and_map_consumer_drift_fail_before_writes(self):
        with patch.object(fit,'NATIVE_TITLE_POINTERS_BY_MAP',{**fit.NATIVE_TITLE_POINTERS_BY_MAP,0:0xA38088}):
            with self.assertRaisesRegex(AssertionError,'descriptor differs'):
                fit.active_titles(self.original,self.fixture_for_catalogue())
        rom = self.fixture()
        rom[0x36B7A0] ^= 1
        before = bytes(rom)
        with self.assertRaisesRegex(AssertionError,'consumer geometry'):
            fit.patch(rom,self.original,builder._lz77_literal_block)
        self.assertEqual(rom,before)

    def fixture_for_catalogue(self):
        return bytearray(self.original)

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
