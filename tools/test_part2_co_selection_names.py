"""Bind the observed Ryo selection label to its original name object."""
from pathlib import Path
import hashlib
import struct
import unittest
from unittest.mock import patch
import build_korean_full as builder
from lz77_scan import lz77_decompress


class Part2COSelectionNamesTests(unittest.TestCase):
    def test_ryo_native_slot_and_generation_preserve_other_names(self):
        original = Path(builder.P.ROM).read_bytes()
        self.assertEqual(struct.unpack_from('<I', original, 0x81BEAC)[0], 0x0845274C)
        self.assertNotEqual(struct.unpack_from('<I', original, 0x81BE68)[0], 0x0845274C)
        raw, consumed = lz77_decompress(original, 0x45274C)
        # Original bitmap is リョウ, independently viewed with the adjacent
        # Catherine/Max/Hoip/Domino labels in their native table order.
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         'f799555853630edef3000ba1e52bb3611600c3e48cb13e0f23c46041865a659a')
        self.assertEqual(consumed, 193)
        self.assertEqual(builder.CO_NAME_KO[:5], ['캐서린', '료', '맥스', '호이프', '도미노'])
        rom = bytearray(original)
        self.assertEqual(builder.patch_part2_domino_co_name_obj(rom), 19)
        result, used = lz77_decompress(rom, 0x45274C)
        self.assertEqual(result, builder._render_co_name_obj('료'))
        self.assertLessEqual(used, consumed)
        previous = bytearray(original)
        previous_names = list(builder.CO_NAME_KO)
        previous_names[1] = '도미노'
        with patch.object(builder, 'CO_NAME_KO', previous_names):
            builder.patch_part2_domino_co_name_obj(previous)
        self.assertEqual(rom[:0x45274C], previous[:0x45274C])
        self.assertEqual(rom[0x45274C+consumed:], previous[0x45274C+consumed:])
        self.assertEqual(rom[builder.CO_NAME_OBJ_TABLE:builder.CO_NAME_OBJ_TABLE+19*0x44],
                         original[builder.CO_NAME_OBJ_TABLE:builder.CO_NAME_OBJ_TABLE+19*0x44])
        # Verify each other physical slot against its existing name, including
        # Domino at index4, rather than renaming every duplicate display string.
        seen = set();index = 0
        for row in range(24):
            pointer = struct.unpack_from('<I', original, builder.CO_NAME_OBJ_TABLE+row*0x44)[0]
            if not 0x08452000 <= pointer < 0x08460000:
                break
            off = pointer - 0x08000000
            if off in seen:
                continue
            seen.add(off)
            self.assertEqual(lz77_decompress(rom, off)[0], builder._render_co_name_obj(builder.CO_NAME_KO[index]))
            index += 1
        self.assertEqual(index, 19)


if __name__ == '__main__':
    unittest.main()
