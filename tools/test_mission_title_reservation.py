"""Reservation and native VRAM stream regressions; no title expectations changed."""
import hashlib
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

import part2_mission_title_fit as fit
import test_part2_mission_title_fit as existing
from lz77_scan import lz77_decompress


def halfword_decode(stream):
    """Independent BIOS-style output: the odd pending byte is not readable yet."""
    assert stream[0] == 0x10
    size = int.from_bytes(stream[1:4], 'little')
    assert size > 0 and size % 2 == 0
    out = bytearray(size)
    count, cursor, pending = 0, 4, 0
    while count < size:
        flags = stream[cursor]
        cursor += 1
        for bit in range(7, -1, -1):
            if count == size:
                break
            if flags & (1 << bit):
                a, b = stream[cursor:cursor+2]
                cursor += 2
                length, distance = (a >> 4) + 3, ((a & 15) << 8 | b) + 1
                assert 2 <= distance <= count and count + length <= size
                values = None
            else:
                length, distance = 1, 0
                values = stream[cursor]
                cursor += 1
            for _ in range(length):
                value = out[count-distance] if distance else values
                if count % 2:
                    out[count-1], out[count] = pending, value
                else:
                    pending = value
                count += 1
    return bytes(out), cursor


class ReservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (Path(__file__).resolve().parents[1] /
                        'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def fixture(self):
        return existing.MissionTitleFitTests.fixture(self)

    def test_native_dispatch_contract(self):
        # Loader selects (type high nibble >> 3) + destination class; VRAM=0.
        self.assertEqual(self.original[0x311CC0:0x311CEC].hex(),
                         '30b5031c0c1cfa20000621180e480122814200d800221d78f0202840c00810180a49800040180268002a13d1')
        self.assertEqual(struct.unpack_from('<I', self.original, 0x804D54+2*4)[0], 0x0838B44D)
        self.assertEqual(self.original[0x38B44C:0x38B450], bytes.fromhex('12df7047'))

    def test_codec_halfword_roundtrip_and_rejection(self):
        for raw in (bytes(512), bytes(range(256))*2, bytes(range(256))*16):
            stream = fit.compress_asset(raw)
            self.assertEqual(halfword_decode(stream), (raw, len(stream)))
        wrong = existing.builder._lz77_literal_block(bytes(512))
        with patch.object(fit, 'lz77_compress', return_value=wrong):
            with self.assertRaisesRegex(AssertionError, 'changed pixels'):
                fit.compress_asset(bytes([1])*512)
        # One literal followed by distance=1: regular LZ decoder accepts it,
        # but the native halfword destination cannot read that pending byte.
        unsafe = bytes.fromhex('1004000040410000')
        self.assertEqual(lz77_decompress(unsafe, 0)[0], b'AAAA')
        with patch.object(fit, 'lz77_compress', return_value=unsafe):
            with self.assertRaisesRegex(AssertionError, 'unsafe VRAM'):
                fit.compress_asset(b'AAAA')
        with patch.object(fit, 'lz77_compress', return_value=b'\x10\x00\x02\x00'):
            with self.assertRaisesRegex(AssertionError, 'truncated'):
                fit.compress_asset(bytes(512))

    def test_patch_preserves_titles_pixels_and_adjacent_allocations(self):
        before = self.fixture()
        literal, compressed = bytearray(before), bytearray(before)
        _, old_report = fit.patch(literal, self.original, existing.builder._lz77_literal_block)
        _, report = fit.patch(compressed, self.original, fit.compress_asset)
        self.assertLess(report['glyph_bytes'], old_report['glyph_bytes'])
        self.assertEqual(report['map_layouts'], old_report['map_layouts'])
        self.assertEqual(fit.active_titles(self.original, compressed), fit.active_titles(self.original, before))
        for offset in range(fit.TABLE, fit.TABLE+24, 12):
            a, b = (struct.unpack_from('<I', rom, offset+4)[0]-0x08000000 for rom in (literal, compressed))
            if a < 0:
                continue
            self.assertEqual(b % 4, 0)
            raw, used = halfword_decode(compressed[b:fit.END])
            self.assertEqual(raw, lz77_decompress(literal, a)[0])
            self.assertLessEqual(b+used, fit.END)
        for offset in range(fit.MAP_DESCRIPTORS, fit.MAP_DESCRIPTORS+64, 32):
            a, b = (struct.unpack_from('<I', rom, offset+4)[0]-0x08000000 for rom in (literal, compressed))
            self.assertEqual(b % 4, 0)
            raw, used = halfword_decode(compressed[b:fit.END])
            self.assertEqual(raw, lz77_decompress(literal, a)[0])
            self.assertLessEqual(b+used, fit.END)
        restored = bytearray(compressed)
        restored[fit.BASE:fit.END] = before[fit.BASE:fit.END]
        for address, expected, _ in (*fit.SITES, fit.MAP_SITE):
            restored[address:address+len(expected)] = before[address:address+len(expected)]
        self.assertEqual(restored, before)
        self.assertEqual(compressed[0xF70000:0xF77800], before[0xF70000:0xF77800])

    def test_each_reservation_overflow_rejects_before_any_write(self):
        for changes in ({'CODE': bytes(1025)}, {'TABLE': fit.MAP_DESCRIPTORS+32},
                        {'GLYPHS': fit.TABLE+12}, {'END': fit.GLYPHS+4}):
            rom = self.fixture()
            before = bytes(rom)
            if 'END' in changes:
                changes['FREE_SHA'] = hashlib.sha256(self.original[fit.BASE:changes['END']]).hexdigest()
            with self.subTest(changes=list(changes)), patch.multiple(fit, **changes):
                with self.assertRaisesRegex(AssertionError, 'overlap reservation: code: .*descriptors: .*table: .*glyphs:'):
                    fit.patch(rom, self.original, fit.compress_asset)
            self.assertEqual(rom, before)


if __name__ == '__main__':
    unittest.main()
