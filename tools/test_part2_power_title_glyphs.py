from hashlib import sha256
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

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
# gfx R3 (2026-11-05): Hada Sans ExtraBold gothic face, R2 JP-height sizing,
# preserving each column's binary stroke topology and the existing AA ramp.
GOLDEN_SHA256 = '97f1b9bb9cc4088ac7b58f81f3000c515efca9ba1df95f5e286539a14dc281a3'
PACKED_BYTES = 6984


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
        # fixB H: the live dictionary is relocated (64-glyph capacity) and both
        # consumer literals point at it.
        titles.relocate_dictionary(cls.base, cls.original, cls.names, cls.codes)
        cls.raw = titles.source(cls.original)
        cls.rendered = titles.render(cls.raw, cls.dictionary)
        cls.patched = bytearray(cls.base)
        cls.result = titles.patch(cls.patched, cls.original, cls.names, cls.codes)

    def test_57_correct_cells_match_approved_style_and_unused_cells_are_preserved(self):
        self.assertEqual(sha256(titles._font_bytes()).hexdigest(), titles.FONT_SHA256)
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
            # gfx T5: JP's own white/light/mid-blue/outline ramp, no new color.
            values = {value for row in new for value in row}
            self.assertTrue({0, 1, 14} <= values <= {0, 1, 8, 10, 14}, (i, values))
            occupied = [(x, y) for y in range(32) for x in range(32) if new[y][x]]
            self.assertTrue(all(6 <= x <= 25 and 3 <= y <= 28 for x, y in occupied))
        self.assertEqual(len(distinct), 57)
        # This observed regression is a glyph-index mismatch, not a sound effect.
        old_dictionary = self.original[titles.NATIVE_DICTIONARY:titles.NATIVE_DICTIONARY + 122].decode('shift_jis')
        self.assertEqual(''.join(old_dictionary[self.dictionary.index(ch)] for ch in '강타'), 'ドン')
        self.assertEqual(''.join(old_dictionary[self.dictionary.index(ch)] for ch in '직격'), 'グサ')

    def test_patch_relocates_atlas_retires_native_slot_and_roundtrips(self):
        packed = self.result['packed_bytes']
        self.assertEqual(packed, PACKED_BYTES)
        self.assertGreater(packed, titles.SLOT_SIZE)  # why the stream moved
        self.assertEqual(self.result['headroom'], titles.ATLAS_CAPACITY - packed)
        self.assertEqual(len(self.patched), len(self.base))
        changed = [i for i in range(len(self.base)) if self.patched[i] != self.base[i]]
        allowed = set(range(titles.ATLAS, titles.ATLAS + titles.ATLAS_CAPACITY))
        for address in titles.ATLAS_POINTERS:
            allowed |= set(range(address, address + 4))
            self.assertEqual(self.patched[address:address + 4], struct.pack('<I', 0x08000000 + titles.ATLAS))
        self.assertTrue(changed and set(changed) <= allowed)
        # The native slot is retired: original bytes, no remaining reference.
        native = struct.pack('<I', 0x08000000 + titles.OFFSET)
        self.assertEqual(self.patched[titles.OFFSET:titles.OFFSET + titles.SLOT_SIZE],
                         self.original[titles.OFFSET:titles.OFFSET + titles.SLOT_SIZE])
        self.assertNotIn(native, bytes(self.patched))
        end = titles.ATLAS + titles.ATLAS_CAPACITY
        self.assertEqual(titles._decode_bounded(self.patched[titles.ATLAS:end]), (self.rendered, packed))
        titles.verify_generated(self.patched, self.original, self.names, self.codes)
        # A second writer, occupied destination or moved literal fails closed.
        with self.assertRaisesRegex(AssertionError, 'ownership|occupied'):
            titles.patch(bytearray(self.patched), self.original, self.names, self.codes)
        rom = bytearray(self.base)
        rom[titles.ATLAS + 100] = 1
        with self.assertRaisesRegex(AssertionError, 'occupied'):
            titles.patch(rom, self.original, self.names, self.codes)
        rom = bytearray(self.patched)
        rom[titles.OFFSET + 5] ^= 1
        with self.assertRaisesRegex(AssertionError, 'retired native slot'):
            titles.verify_generated(rom, self.original, self.names, self.codes)

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
        for address in [a for a, *_ in titles.GUARDS] + [a for a, *_ in titles.ATLAS_POINTER_GUARDS]:
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
        with self.assertRaisesRegex(AssertionError, '1..64 unique Hangul'):
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
        # At the 64-entry capacity the renderer terminates on the relocated
        # dictionary's own NUL halfword (fixB H), checked with the dictionary.
        rom[titles.DICTIONARY + titles.DICTIONARY_SIZE] = 1
        with self.assertRaisesRegex(AssertionError, 'dictionary differs'):
            titles.bind_dictionary(rom, names, self.codes)

    def test_compression_overflow_malformed_and_unsafe_streams_are_rejected(self):
        with patch('lz77_compress.lz77_compress_optimal', return_value=bytes(titles.ATLAS_CAPACITY + 1)):
            with self.assertRaisesRegex(AssertionError, 'exceeds relocated atlas'):
                titles._compress(self.rendered)
        # One literal followed by distance=1, which is unsafe for BIOS VRAM LZ.
        with self.assertRaisesRegex(AssertionError, 'unsafe LZ backref'):
            titles._decode_bounded(bytes.fromhex('1000800040010000'))
        for bad in (b'', bytes.fromhex('1000800000'), bytes.fromhex('10000100')):
            with self.assertRaises(AssertionError):
                titles._decode_bounded(bad)
        padding = bytearray(self.patched[titles.ATLAS:titles.ATLAS + titles.ATLAS_CAPACITY])
        padding[-1] = 1
        with self.assertRaisesRegex(AssertionError, 'nonzero slot padding'):
            titles._decode_bounded(padding)

    def test_final_snapshot_protects_glyphs_dictionary_and_consumers(self):
        regions = titles.capture_regions(self.patched, self.original, self.names, self.codes, editor_result={})
        titles.verify_regions(self.patched, regions)
        for a in (titles.ATLAS + 20, titles.OFFSET + 20, titles.DICTIONARY, titles.NAMES_START,
                  0x380644, 0x38121C, 0x5B5720):
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
        self.assertEqual(lz77_decompress(rom, titles.ATLAS)[0], bytes(user_raw))
        with self.assertRaisesRegex(AssertionError, 'before editor'):
            titles.verify_generated(rom, self.original, self.names, self.codes)
        with self.assertRaisesRegex(AssertionError, 'without an explicit'):
            titles.capture_regions(rom, self.original, self.names, self.codes, editor_result={})
        regions = titles.capture_regions(rom, self.original, self.names, self.codes, editor_result=result)
        titles.verify_regions(rom, regions)
        self.assertEqual(rom[titles.ATLAS:titles.ATLAS + titles.ATLAS_CAPACITY], regions[titles.ATLAS])
        with self.assertRaisesRegex(AssertionError, 'skipped'):
            titles.capture_regions(rom, self.original, self.names, self.codes, editor_result={'skipped': 1})


    def test_common_horizontal_scale_and_23px_baseline_including_former_tall_glyphs(self):
        # Every syllable shares the width scale of 다 and a fixed 23 px face.
        # Fixed witnesses and run counts guard both scaling stages.
        from hangul_pixel_fit import runs
        dictionary = ''.join(dict.fromkeys(''.join(APPROVED_NAMES[:20] + ('야마토다마시이',) + APPROVED_NAMES[20:])))
        self.assertLessEqual(len(dictionary), titles.MAX_GLYPHS)
        rendered = titles.render(self.raw, dictionary)
        scale = titles.uniform_scale()
        self.assertAlmostEqual(scale, 18 / titles._outline('다')[0].width)
        heights = {}
        for i, ch in enumerate(dictionary):
            fill = titles._fill(ch)
            natural = titles._natural_core(ch)
            self.assertEqual(sha256(natural.tobytes()).hexdigest(),
                             titles.CORE_WITNESSES[ch], ch)
            box = fill.getbbox()
            self.assertLessEqual(box[2] - box[0], titles.FACE_W, ch)
            self.assertEqual(box[3] - box[1], titles.TARGET_FACE_HEIGHT, ch)
            cropped = fill.crop(box)
            for x in range(natural.width):
                count = lambda im: sum(n for n, _, _ in runs(
                    [im.getpixel((x, y)) for y in range(im.height)]))
                self.assertEqual(count(natural), count(cropped), (ch, x))
            cell = titles.decode_cell(rendered, i)
            face_bytes = bytes(255 if v == 1 else 0 for row in cell for v in row)
            witness = json.loads((titles.ROOT / 'data/graphic_hangul_shape_witnesses.json').read_text())
            self.assertEqual(sha256(face_bytes).hexdigest(), witness['cutin_face'][ch])
            face = [y for y in range(32) for x in range(32) if cell[y][x] == 1]
            heights[ch] = max(face) - min(face) + 1
        self.assertTrue(all(height == titles.TARGET_FACE_HEIGHT for height in heights.values()), heights)
        # Same line: 대 and 승 occupy the same vertical extent in 대승.
        da, seung = titles._fill('대').getbbox(), titles._fill('승').getbbox()
        self.assertEqual((da[1], da[3]), (seung[1], seung[3]))

    def test_fixed_witness_rejects_damaged_hada_core(self):
        natural = titles._natural_core('별').copy()
        natural.putpixel((natural.width // 2, natural.height // 2),
                         0 if natural.getpixel((natural.width // 2, natural.height // 2)) else 255)
        with patch.object(titles, '_natural_core', return_value=natural):
            with self.assertRaisesRegex(AssertionError, 'Hada core changed'):
                titles._glyph('별', None)


if __name__ == '__main__':
    unittest.main()
