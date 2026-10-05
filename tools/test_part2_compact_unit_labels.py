"""Requires the canonical local ROM and fonts, never extracted ROM fixtures."""
from hashlib import sha256
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

import build_korean_full as builder
import part2_compact_unit_labels as labels

ROOT = Path(__file__).resolve().parents[1]


class Part2CompactUnitLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (ROOT / 'original/Game Boy Wars Advance 1+2 (Japan).gba').read_bytes()
        rom = bytearray(cls.original)
        cls.metadata = {}
        def record(group, source, title, entries):
            cls.metadata[group] = entries
        labels.validate_source(cls.original, rom)
        with patch.object(builder, 'rec_objlabel', side_effect=record):
            builder.patch_part2_battle_obj_labels(rom)
        cls.generated = bytes(rom)

    def test_all37_original_slots_generated_bytes_and_metadata(self):
        self.assertEqual(len(labels.COMPACT_LABELS), 19)
        self.assertEqual(len(labels.STATUS_LABELS), 18)
        labels.validate_source(self.original, self.generated)
        labels.verify_generated(self.generated)
        labels.verify_metadata(self.metadata)
        for address, *_ in labels.COMPACT_LABELS + labels.STATUS_LABELS:
            raw = self.generated[address:address + labels.SLOT_SIZE]
            self.assertEqual(len(raw), 256)
            self.assertNotEqual(raw, bytes(256))
            self.assertLessEqual({n for byte in raw for n in (byte & 15, byte >> 4)}, {0, 1})

    def test_native_type_lookup_binds_the_four_corrected_labels(self):
        text_by_address = {address: text for address, text, *_ in labels.COMPACT_LABELS}
        for unit_type, address, text in ((8, 0x466868, '신형전차'), (14, 0x466E68, '대공전차'),
                                         (19, 0x467268, '전투헬기'), (20, 0x467368, '수송헬기')):
            index = struct.unpack_from('<H', self.original, 0x815D88 + unit_type * 4)[0]
            native_address = 0x466568 + (((index << 3) & 0x3FF) << 5)
            self.assertEqual(native_address, address)
            self.assertEqual(text_by_address[address], text)
        # These are separate sources with deliberately different row order.
        status = {text: address for address, text, *_ in labels.STATUS_LABELS}
        self.assertEqual(status['대공전차'], 0xB94B10)
        self.assertEqual(status['수송헬기'], 0xB95210)
        self.assertEqual(status['전투헬기'], 0xB95310)

    def test_wrong_mapping_or_blank_output_is_rejected(self):
        rom = bytearray(self.generated)
        for left, right in ((0x466868, 0x466E68), (0x467268, 0x467368)):
            rom[left:left + 256], rom[right:right + 256] = self.generated[right:right + 256], self.generated[left:left + 256]
            with self.assertRaisesRegex(AssertionError, 'mapping/render'):
                labels.verify_generated(rom)
            rom[left:left + 256], rom[right:right + 256] = self.generated[left:left + 256], self.generated[right:right + 256]
        for address, *_ in labels.COMPACT_LABELS + labels.STATUS_LABELS:
            with self.subTest(address=hex(address)):
                rom[address + 255] ^= 1
                with self.assertRaisesRegex(AssertionError, 'mapping/render'):
                    labels.verify_generated(rom)
                rom[address + 255] ^= 1

    def test_mutated_original_slot_or_live_consumer_is_rejected(self):
        original = bytearray(self.original)
        for address, *_ in labels.COMPACT_LABELS + labels.STATUS_LABELS:
            original[address] ^= 1
            with self.assertRaisesRegex(AssertionError, 'source changed'):
                labels.validate_source(original, self.generated)
            original[address] ^= 1
        current = bytearray(self.generated)
        for address, size, _ in (labels.ACCESSOR, labels.TYPE_LOOKUP):
            for changed in (address, address + size - 1):
                current[changed] ^= 1
                with self.assertRaisesRegex(AssertionError, 'consumer changed'):
                    labels.validate_source(original, current)
                current[changed] ^= 1

    def test_editor_metadata_cannot_keep_the_old_names(self):
        groups = {key: [dict(entry) for entry in entries] for key, entries in self.metadata.items()}
        for entry in groups['objlabel_p2_unit_compact']:
            if entry['off'] == 0x466E68:
                entry['text'] = '신형전차'
        with self.assertRaisesRegex(AssertionError, 'metadata changed'):
            labels.verify_metadata(groups)


if __name__ == '__main__':
    unittest.main()
