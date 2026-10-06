import struct
import unittest

import part2_attack_range_legend as m


class AttackRangeLegendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (m.ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()

    def test_consumer_facts(self):
        m.source_guard(self.original)
        rom = self.original
        # movs r0,#0x92 ; bl 0x0831F708 (VRAM load in screen init)
        self.assertEqual(rom[0x385736:0x385738], bytes([0x92, 0x20]))
        # the three sprite-placing task callbacks are referenced by script 0x08A3BD94
        for slot, func in ((0xA3BDA0, 0x08386571), (0xA3BDA8, 0x08386615), (0xA3BDB0, 0x083865C1)):
            self.assertEqual(struct.unpack_from('<I', rom, slot)[0], func)
        # the script slot read by the input handler (R on page 4)
        self.assertEqual(struct.unpack_from('<I', rom, 0x54EF14)[0], 0x08A3BD8C)
        self.assertEqual(struct.unpack_from('<I', rom, 0x385874)[0], 0x0854EF14)

    def test_patch_capture_verify_idempotent(self):
        rom = bytearray(self.original)
        self.assertEqual(m.patch(rom, self.original), 1)
        new = m.decode(bytes(rom[m.OFFSET:m.OFFSET + m.TILES * 32]))
        old = m.decode(bytes(self.original[m.OFFSET:m.OFFSET + m.TILES * 32]))
        for y in range(m.HEIGHT):
            for x in list(range(0, 33)) + [125, 126, 127]:
                self.assertEqual(new[y][x], old[y][x], (x, y))   # frame, bars, icon 1, dash 1
        self.assertTrue({v for row in new for v in row} <= {v for row in old for v in row})
        outside = bytearray(rom)
        outside[m.OFFSET:m.OFFSET + m.TILES * 32] = self.original[m.OFFSET:m.OFFSET + m.TILES * 32]
        self.assertEqual(outside, self.original)
        regions = m.capture(rom, self.original)
        m.verify(rom, regions)
        self.assertTrue(m.generated_matches(rom, self.original))
        again = bytearray(rom)
        m.patch(again, self.original)
        self.assertEqual(again, rom)
        rom[m.OFFSET + 5] ^= 1
        with self.assertRaises(AssertionError):
            m.verify(rom, regions)

    def test_conflicts_rejected(self):
        rom = bytearray(self.original)
        rom[m.OFFSET + 200] ^= 1
        with self.assertRaises(AssertionError):
            m.patch(rom, self.original)
        original = bytearray(self.original)
        original[m.SIZE_TABLE + 146 * 4] = 15
        with self.assertRaises(AssertionError):
            m.source_guard(original)


if __name__ == '__main__':
    unittest.main()
