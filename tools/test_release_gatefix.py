import struct
import unittest
from pathlib import Path
from unittest.mock import patch

import qa_transient_overlays as overlays
import run_release_qa as release


class NameControlPointerTests(unittest.TestCase):
    POINTERS = (0x20, 0x24, 0x28)
    ORPHANS = (0x402, 0x502, 0x602)

    def rom(self):
        rom = bytearray(0x3000)
        for pointer, target in zip(self.POINTERS, (0x100, 0x200, 0x300)):
            struct.pack_into('<I', rom, pointer, 0x08000000 + target)
            rom[target:target + 8] = b'\x0a\x09\x69\x81\x40\x00\x00\x00'
        for hit in self.ORPHANS:
            rom[hit-2:hit+8] = b'\x0a\x09' + overlays.PART1_RAW_NAME_CONTROL_SAN + b'\x20\x00\x00'
        return rom

    def status(self, rom):
        with patch.object(overlays, 'PART1_NAME_CONTROL_POINTERS', self.POINTERS), \
             patch.object(overlays, 'PART1_ORPHAN_SAN_HITS', self.ORPHANS):
            return overlays.name_control_san_status(rom)

    def test_proven_orphans_pass(self):
        rows, live, invalid, unexplained, proof = self.status(self.rom())
        self.assertTrue(all(row['valid'] for row in rows))
        self.assertEqual((live, invalid, unexplained), ([], [], []))
        self.assertEqual(len(proof), 3)

    def test_another_reference_to_orphan_fails(self):
        rom = self.rom()
        struct.pack_into('<I', rom, 0x30, 0x08000403)  # interior of first message
        self.assertEqual(self.status(rom)[3], [0x402])

    def test_pattern_beyond_512_fails(self):
        rom = self.rom()
        rom[0x100:0x100+700] = b'A' * 700
        rom[0x100+600:0x100+605] = overlays.PART1_RAW_NAME_CONTROL_SAN
        rom[0x100+700] = 0
        self.assertEqual(set(self.status(rom)[1]), {0x100+600})

    def test_missing_or_truncated_terminator_fails(self):
        rom = self.rom()
        rom[0x100:0x100+overlays.PART1_NAME_CONTROL_MAX_LEN] = b'A' * overlays.PART1_NAME_CONTROL_MAX_LEN
        self.assertTrue(self.status(rom)[2])
        rom = self.rom()
        struct.pack_into('<I', rom, self.POINTERS[0], 0x08000000 + len(rom) - 3)
        rom[-3:] = b'AAA'
        self.assertTrue(self.status(rom)[2])

    def test_another_live_consumer_target_fails(self):
        rom = self.rom()
        rom[0x800:0x800+6] = overlays.PART1_RAW_NAME_CONTROL_SAN + b'\x00'
        self.assertEqual(self.status(rom)[3], [0x800])


class HarnessSelectionTests(unittest.TestCase):
    def test_linux_darwin_and_override(self):
        with patch.object(release.platform, 'system', return_value='Linux'), \
             patch.object(Path, 'exists', return_value=True), \
             patch.dict(release.os.environ, {}, clear=True):
            self.assertIn('mgbah_linux', ' '.join(release.visual_region_cmd()))
        with patch.object(release.platform, 'system', return_value='Darwin'), \
             patch.object(Path, 'exists', return_value=True), \
             patch.dict(release.os.environ, {}, clear=True):
            command = ' '.join(release.visual_region_cmd())
            self.assertIn('mgbah', command)
            self.assertNotIn('mgbah_linux', command)
        with patch.dict(release.os.environ, {'MGBA_HARNESS': '/custom/harness'}):
            self.assertIn('/custom/harness', release.visual_region_cmd())


if __name__ == '__main__':
    unittest.main()
