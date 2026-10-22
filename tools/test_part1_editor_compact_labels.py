import struct
import unittest

import part1_editor_compact_labels as editor
import part1_record_map_labels as record


class EditorCompactGateTests(unittest.TestCase):
    def setUp(self):
        self.original = bytes(max(editor.CODE_OFFSET + len(editor.CODE),
                                  max(editor.REPLACES) + 4,
                                  max(address + len(payload)
                                      for address, payload in record.WRITES)))
        self.rom = bytearray(self.original)
        for address, (old, _) in editor.REPLACES.items():
            struct.pack_into('<I', self.rom, address, old)

    def test_patch_is_guarded_and_confined(self):
        before = bytes(self.rom)
        editor.patch(self.rom, self.original)
        editor.verify(self.rom)
        allowed = set(range(editor.CODE_OFFSET, editor.CODE_OFFSET + len(editor.CODE)))
        for address in editor.REPLACES:
            allowed.update(range(address, address + 4))
        self.assertTrue(all(a == b or index in allowed
                            for index, (a, b) in enumerate(zip(before, self.rom))))

    def test_occupied_allocation_and_changed_predecessor_fail_atomically(self):
        self.rom[editor.CODE_OFFSET + 1] = 1
        before = bytes(self.rom)
        with self.assertRaisesRegex(AssertionError, 'allocation occupied'):
            editor.patch(self.rom, self.original)
        self.assertEqual(bytes(self.rom), before)
        self.rom[editor.CODE_OFFSET + 1] = 0
        address = next(iter(editor.REPLACES))
        self.rom[address] ^= 1
        before = bytes(self.rom)
        with self.assertRaisesRegex(AssertionError, 'predecessor changed'):
            editor.patch(self.rom, self.original)
        self.assertEqual(bytes(self.rom), before)

    def test_existing_gate_verifier_accepts_only_declared_literal_changes(self):
        overlays = {address: struct.pack('<I', target)
                    for address, (_, target) in editor.REPLACES.items()}
        # Construct the exact Round 2 gate bytes, then overlay the editor
        # targets. This checks the shared gate verifier's integration contract.
        for address, payload in record.WRITES:
            if address + len(payload) <= len(self.rom):
                self.rom[address:address + len(payload)] = payload
        editor.patch(self.rom, self.original)
        record.verify(self.rom, overlays)
        with self.assertRaisesRegex(AssertionError, 'overwritten'):
            record.verify(self.rom)


if __name__ == '__main__':
    unittest.main()
