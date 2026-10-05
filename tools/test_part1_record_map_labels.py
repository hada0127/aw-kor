from pathlib import Path
import struct
import unittest

import part1_record_map_labels as patcher


class RecordMapGateTests(unittest.TestCase):
    def setUp(self):
        self.original = bytes(patcher.ROW_GATE + len(patcher.ROW_CODE))
        self.rom = bytearray(self.original)
        fixture = Path(__file__).with_name('fixtures') / 'part1_compact_map_hook_a290f200.hex'
        self.rom[patcher.HOOK:patcher.HOOK + patcher.HOOK_SIZE] = bytes.fromhex(fixture.read_text())

    def test_patch_is_confined_and_verifies(self):
        before = bytes(self.rom)
        result = patcher.patch(self.rom, self.original)
        patcher.verify(self.rom)
        self.assertEqual(result['hidden_state_rejected'], '0x03000F80')
        for address, raw in patcher.WRITES:
            self.assertEqual(bytes(self.rom[address:address + len(raw)]), raw)
        allowed = {i for address, raw in patcher.WRITES for i in range(address, address + len(raw))}
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(before, self.rom))))

    def test_old_hook_change_is_rejected_atomically(self):
        self.rom[patcher.HOOK + 2] ^= 1
        before = bytes(self.rom)
        with self.assertRaisesRegex(AssertionError, 'layout changed'):
            patcher.patch(self.rom, self.original)
        self.assertEqual(self.rom, before)

    def test_dynamic_table_extent_is_checked_without_pin_to_one_translation(self):
        for value in (0x08F30800, 0x08F32008, 0x08F31E81):
            with self.subTest(value=hex(value)):
                struct.pack_into('<I', self.rom, patcher.HOOK + patcher.TABLE_END_OFFSET, value)
                before = bytes(self.rom)
                with self.assertRaisesRegex(AssertionError, 'table extent'):
                    patcher.patch(self.rom, self.original)
                self.assertEqual(self.rom, before)
        struct.pack_into('<I', self.rom, patcher.HOOK + patcher.TABLE_END_OFFSET, 0x08F31E88)
        patcher.patch(self.rom, self.original)
        patcher.verify(self.rom)

    def test_occupied_rom_gap_and_changed_original_are_rejected(self):
        for address in (patcher.GATE, patcher.ROW_GATE):
            self.rom[address + 5] = 1
            before = bytes(self.rom)
            with self.assertRaisesRegex(AssertionError, 'pristine'):
                patcher.patch(self.rom, self.original)
            self.assertEqual(self.rom, before)
            self.rom[address + 5] = 0
        original = bytearray(self.original)
        original[patcher.GATE] = 1
        with self.assertRaisesRegex(AssertionError, 'pristine'):
            patcher.patch(self.rom, original)

    def test_later_overwrite_is_rejected(self):
        patcher.patch(self.rom, self.original)
        self.rom[patcher.GATE + 3] ^= 1
        with self.assertRaisesRegex(AssertionError, 'overwritten'):
            patcher.verify(self.rom)


if __name__ == '__main__':
    unittest.main()
