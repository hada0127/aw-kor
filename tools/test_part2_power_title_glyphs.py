from hashlib import sha256
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import part2_power_title_glyphs as titles
from lz77_scan import lz77_decompress

# Approved Korean labels are our own fixture. No original ROM bytes or glyph
# assets are stored here. Later user edits to live display names do not silently
# redefine the style golden or cause this fixture to overwrite their changes.
APPROVED_NAMES = ('기적', '별꿈', '하이퍼수리', '강화', '승리', '대승', '강타', '직격',
                  '상혼', '축제', '골드', '재력', '저격', '원저격', '설백', '눈보라',
                  '일도', '배수', '탐색', '반격', '혼', '돌격', '번개돌진', '번개강습',
                  '큰파도', '큰폭풍', '충전', '대폭발', '화염', '대분쇄', '전술', '지휘',
                  '측돌파', '측기습', '흑파도', '흑폭풍')
GOLDEN_SHA256 = '41eb6a7fb7cdbb6ea6cae6819f34a6efcfaac35beeb0848a12ce44cf70b12b91'


class PowerTitleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Full canonical source ROM and pinned local font are mandatory asset
        # gate inputs, not optional test skips; do not commit extracted assets.
        cls.original = (titles.ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        cls.codes = {ch: int(code, 16) for ch, code in json.loads(
            (titles.ROOT / 'data/syllable_to_code_2350.json').read_text()).items()}
        addresses = tuple(x - 0x8000000 for x in struct.unpack_from('<36I', cls.original, titles.NAME_POINTERS))
        cls.names = dict(zip(addresses, APPROVED_NAMES))
        cls.dictionary = ''.join(dict.fromkeys(''.join(APPROVED_NAMES)))
        cls.base = bytearray(cls.original)
        encode = lambda s: b''.join(cls.codes[ch].to_bytes(2, 'big') for ch in s)
        for a, end in zip(addresses, (*addresses[1:], titles.NAMES_END)):
            cls.base[a:end] = encode(cls.names[a]).ljust(end - a, b'\0')
        cls.base[titles.DICTIONARY:titles.DICTIONARY + titles.DICTIONARY_SIZE] = encode(cls.dictionary).ljust(titles.DICTIONARY_SIZE, b'\0')
        cls.raw = titles.source(cls.original)
        cls.rendered = titles.render(cls.raw, cls.dictionary)
        cls.patched = bytearray(cls.base)
        cls.result = titles.patch(cls.patched, cls.original, cls.names, cls.codes)

    def test_57_correct_cells_match_approved_style_and_unused_cells_are_preserved(self):
        self.assertEqual(sha256(self.rendered).hexdigest(), GOLDEN_SHA256)
        self.assertEqual(titles.bind_dictionary(self.base, self.names, self.codes), self.dictionary)
        distinct = set()
        for i in range(64):
            old, new = titles.decode_cell(self.raw, i), titles.decode_cell(self.rendered, i)
            if i >= 57:
                self.assertEqual(old, new, i)
                continue
            self.assertNotEqual(old, new, (i, self.dictionary[i]))
            distinct.add(bytes(value for row in new for value in row))
            self.assertEqual({value for row in new for value in row}, {0, 1, 14})
            occupied = [(x, y) for y in range(32) for x in range(32) if new[y][x]]
            self.assertTrue(all(7 <= x <= 24 and 3 <= y <= 28 for x, y in occupied))
        self.assertEqual(len(distinct), 57)
        # This observed regression is a glyph-index mismatch, not a sound effect.
        old_dictionary = self.original[titles.DICTIONARY:titles.DICTIONARY + 122].decode('shift_jis')
        self.assertEqual(''.join(old_dictionary[self.dictionary.index(ch)] for ch in '강타'), 'ドン')
        self.assertEqual(''.join(old_dictionary[self.dictionary.index(ch)] for ch in '직격'), 'グサ')

    def test_patch_changes_only_original_lz_slot_and_roundtrips(self):
        self.assertEqual(self.result['packed_bytes'], 5966)
        self.assertEqual(self.result['headroom'], 195)
        self.assertEqual(len(self.patched), len(self.base))
        self.assertEqual(self.patched[:titles.OFFSET], self.base[:titles.OFFSET])
        end = titles.OFFSET + titles.SLOT_SIZE
        self.assertEqual(self.patched[end:], self.base[end:])
        self.assertEqual(titles._decode_bounded(self.patched[titles.OFFSET:end]), (self.rendered, 5966))
        titles.verify_generated(self.patched, self.original, self.names, self.codes)

    def test_source_font_scope_and_existing_writer_are_rejected_without_mutation(self):
        rom = bytearray(self.base)
        wrong_source = bytearray(self.original)
        wrong_source[0] ^= 1
        with self.assertRaisesRegex(AssertionError, 'original ROM'):
            titles.patch(rom, wrong_source, self.names, self.codes)
        with patch.object(titles, '_font_bytes', return_value=b'not the font'):
            with self.assertRaisesRegex(AssertionError, 'font changed'):
                titles.patch(rom, self.original, self.names, self.codes)
        self.assertEqual(rom, self.base)
        rom[titles.OFFSET + 20] ^= 1
        before = bytes(rom)
        with self.assertRaisesRegex(AssertionError, 'another writer'):
            titles.patch(rom, self.original, self.names, self.codes)
        self.assertEqual(rom, before)
        with self.assertRaisesRegex(AssertionError, 'source asset'):
            titles.render(bytes(titles.RAW_SIZE), self.dictionary)
        with self.assertRaisesRegex(AssertionError, 'scope'):
            titles.render(self.raw, self.dictionary + self.dictionary[0])

    def test_consumer_pointer_palette_neighbors_and_name_table_guards(self):
        for address, _, _ in titles.GUARDS:
            with self.subTest(address=hex(address)):
                rom = bytearray(self.base)
                rom[address] ^= 1
                before = bytes(rom)
                with self.assertRaisesRegex(AssertionError, 'consumer/pointer/palette/neighbor'):
                    titles.patch(rom, self.original, self.names, self.codes)
                self.assertEqual(rom, before)
        with self.assertRaisesRegex(AssertionError, 'complete'):
            titles.patch(bytearray(100), self.original, self.names, self.codes)

    def test_dictionary_names_codes_and_padding_must_match(self):
        for address in (titles.DICTIONARY, titles.DICTIONARY + 121, titles.NAMES_START, titles.NAMES_END - 1):
            with self.subTest(address=hex(address)):
                rom = bytearray(self.base)
                rom[address] ^= 1
                with self.assertRaisesRegex(AssertionError, 'dictionary differs|name/padding differs'):
                    titles.bind_dictionary(rom, self.names, self.codes)
        names = dict(self.names)
        names.pop(titles.NAMES_START)
        with self.assertRaisesRegex(AssertionError, 'exact 36'):
            titles.bind_dictionary(self.base, names, self.codes)
        names = dict(self.names)
        names[titles.NAMES_START] = '기 적'
        with self.assertRaisesRegex(AssertionError, '1..61 unique Hangul'):
            titles.bind_dictionary(self.base, names, self.codes)
        for code in (self.codes['적'], 0x2040, 0x8840 + 0x3F):
            codes = dict(self.codes)
            codes['기'] = code
            with self.assertRaisesRegex(AssertionError, 'two-byte dictionary codes'):
                titles.bind_dictionary(self.base, self.names, codes)

    def test_explicit_display_name_edit_can_change_dictionary_count(self):
        # The existing title editor permits changed Hangul names. Do not pin its
        # live dictionary to the current default's 57 entries.
        for suffix in ('가', '가갸걀걔'):
            names = dict(self.names)
            names[titles.NAMES_START] += suffix
            dictionary = ''.join(dict.fromkeys(''.join(names.values())))
            self.assertEqual(len(dictionary), 57 + len(suffix))
            encode = lambda s: b''.join(self.codes[ch].to_bytes(2, 'big') for ch in s)
            rom = bytearray(self.base)
            addresses = tuple(names)
            for a, end in zip(addresses, (*addresses[1:], titles.NAMES_END)):
                rom[a:end] = encode(names[a]).ljust(end - a, b'\0')
            rom[titles.DICTIONARY:titles.DICTIONARY + titles.DICTIONARY_SIZE] = encode(dictionary).ljust(titles.DICTIONARY_SIZE, b'\0')
            self.assertEqual(titles.bind_dictionary(rom, names, self.codes), dictionary)
            rendered = titles.render(self.raw, dictionary)
            for i in range(len(dictionary), 64):
                self.assertEqual(titles.decode_cell(rendered, i), titles.decode_cell(self.raw, i))
            if len(suffix) == 1:
                result = titles.patch(rom, self.original, names, self.codes)
                self.assertEqual(result['glyphs'], 58)
                titles.verify_generated(rom, self.original, names, self.codes)
        # At 61 entries the renderer terminates on the adjacent native NUL.
        rom[titles.DICTIONARY + titles.DICTIONARY_SIZE] = 1
        with self.assertRaisesRegex(AssertionError, 'consumer/pointer/palette/neighbor'):
            titles.bind_dictionary(rom, names, self.codes)

    def test_compression_overflow_malformed_and_unsafe_streams_are_rejected(self):
        with patch('lz77_compress.lz77_compress_optimal', return_value=bytes(titles.SLOT_SIZE + 1)):
            with self.assertRaisesRegex(AssertionError, 'exceeds original slot'):
                titles._compress(self.rendered)
        # One literal followed by distance=1, which is unsafe for BIOS VRAM LZ.
        with self.assertRaisesRegex(AssertionError, 'unsafe LZ backref'):
            titles._decode_bounded(bytes.fromhex('1000800040010000'))
        for bad in (b'', bytes.fromhex('1000800000'), bytes.fromhex('10000100')):
            with self.assertRaises(AssertionError):
                titles._decode_bounded(bad)
        padding = bytearray(self.patched[titles.OFFSET:titles.OFFSET + titles.SLOT_SIZE])
        padding[-1] = 1
        with self.assertRaisesRegex(AssertionError, 'nonzero slot padding'):
            titles._decode_bounded(padding)

    def test_final_snapshot_protects_glyphs_dictionary_and_consumers(self):
        regions = titles.capture_regions(self.patched, self.original, self.names, self.codes, editor_result={})
        titles.verify_regions(self.patched, regions)
        for a in (titles.OFFSET + 20, titles.DICTIONARY, titles.NAMES_START, 0x380644, 0x5B5720):
            rom = bytearray(self.patched)
            rom[a] ^= 1
            with self.assertRaises(AssertionError):
                titles.verify_regions(rom, regions)
        with self.assertRaisesRegex(AssertionError, 'wrong extents'):
            titles.verify_regions(self.patched, {titles.OFFSET: regions[titles.OFFSET]})

    def test_explicit_real_editor_overlay_is_retained_without_accepting_unknown_write(self):
        from build_korean_full import apply_sprite_overrides
        from export_sprites import tiles_to_indices
        rom = bytearray(self.patched)
        user_raw = bytearray(self.rendered)
        # An intentional user edit even to a previously unused cell is respected.
        pos = titles.cell_rows(63)[0][0]
        user_raw[pos] = 0x11
        grid, width, height = tiles_to_indices(user_raw, 32)
        self.assertEqual((width, height), (256, 256))
        with tempfile.TemporaryDirectory(dir=titles.ROOT / 'temp', prefix='part2_power_editor_') as directory:
            directory = Path(directory)
            override = directory / 'override.json'
            override.write_text(json.dumps({titles.ASSET_ID: {'indices': grid,
                titles.BINDING_KEY: titles.dictionary_binding(rom, self.names, self.codes)}}))
            result = apply_sprite_overrides(rom, ov_path=str(override),
                idx_path=str(titles.ROOT / 'data/sprites_index.json'), report_path=str(directory / 'report.json'),
                power_title_context=(self.names, self.codes))
        self.assertEqual(result['applied'], 1)
        self.assertEqual(result['skipped'], 0)
        self.assertEqual(lz77_decompress(rom, titles.OFFSET)[0], bytes(user_raw))
        with self.assertRaisesRegex(AssertionError, 'before editor'):
            titles.verify_generated(rom, self.original, self.names, self.codes)
        with self.assertRaisesRegex(AssertionError, 'without an explicit'):
            titles.capture_regions(rom, self.original, self.names, self.codes, editor_result={})
        regions = titles.capture_regions(rom, self.original, self.names, self.codes, editor_result=result)
        titles.verify_regions(rom, regions)
        self.assertEqual(rom[titles.OFFSET:titles.OFFSET + titles.SLOT_SIZE], regions[titles.OFFSET])
        with self.assertRaisesRegex(AssertionError, 'skipped'):
            titles.capture_regions(rom, self.original, self.names, self.codes, editor_result={'skipped': 1})


if __name__ == '__main__':
    unittest.main()
