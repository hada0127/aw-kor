import struct
import unittest
from unittest.mock import patch

from capture_sprite_style import observed_sprites


class SpriteCaptureTest(unittest.TestCase):
    def test_disabled_output_does_not_observe_resident_tiles(self):
        for dispcnt in (0x0040, 0x10C0):
            self.assertEqual(observed_sprites(b'', b'', b'', dispcnt), [])

    def test_object_window_is_not_visible_sprite(self):
        oam = bytearray(struct.pack('<4H', 0x200, 0, 0, 0) * 128)
        with patch('capture_sprite_style.th.lz77_decompress', return_value=(b'\x11' * 32, 32)), \
             patch('capture_sprite_style.resolve_sprite_offset', return_value=0):
            for mode in (0, 1, 2, 3):
                struct.pack_into('<4H', oam, 0, mode << 10, 0, 0, 0)
                observed = observed_sprites(b'', oam, b'\x11' * 32, 0x1040)
                self.assertEqual(bool(observed), mode < 2)


if __name__ == '__main__':
    unittest.main()
