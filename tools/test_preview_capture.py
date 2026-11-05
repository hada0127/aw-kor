"""Preview navigation, cache identity, encoding and failed-write cleanup."""
from collections import Counter
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
import build_korean_full as build
import preview_capture as preview
import qa_visual_regions

ROOT = Path(__file__).resolve().parents[1]


class PreviewCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.environ.get('AW_TEST_ROM')
        if not path:
            raise unittest.SkipTest('AW_TEST_ROM must name the candidate under review')
        cls.candidate = Path(path)

    def test_rejects_unknown_navigation(self):
        with self.assertRaisesRegex(ValueError, 'unknown preview navigation'):
            preview._nav(Mock(), [['pres', 'A', 1]])

    def test_named_cache_tracks_text_and_preserves_sweep_frames(self):
        class Driver:
            def __init__(self, rom, directory, harness):
                self.directory = directory
            def shot(self, stem):
                image = Image.new('RGB', (240, 160), 'white')
                image.putpixel((0, 0), (0, 0, 0))
                image.save(self.directory / (stem + '.png'))
                return image
            def frames(self, count):
                pass
            def close(self):
                pass
        cv = {**preview.CANVASES['part2_menu'], 'nav': [],
              'sweep': {'frames': [1, 2], 'score_box': [0, 0, 8, 8], 'keep_all': True}}
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as directory, \
             patch.object(preview, 'CACHE', Path(directory)), \
             patch.dict(preview.CANVASES, {'test': cv}), \
             patch.object(qa_visual_regions, 'MGBADriver', Driver):
            base = self.candidate
            first = preview.capture('가', canvas='test', out_name='named.png', base_rom=base)
            second = preview.capture('나', canvas='test', out_name='named.png', base_rom=base)
            self.assertNotEqual(first['png'], second['png'])
            self.assertFalse(second['cached'])
            self.assertTrue(preview.capture('나', canvas='test', out_name='named.png', base_rom=base)['cached'])
            for item in first['sweep']['candidates']:
                self.assertTrue(Path(item['png']).is_file())
            self.assertEqual(list(Path(directory).glob('run_*')), [])

    def test_partial_rom_write_failure_cleans_run_directory(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'temp') as directory:
            cache = Path(directory)
            write = Path.write_bytes
            def fail_rom(path, data):
                if path.name == 'preview.gba':
                    write(path, data[:128])
                    raise OSError('injected disk write failure')
                return write(path, data)
            with patch.object(preview, 'CACHE', cache), patch.object(Path, 'write_bytes', fail_rom):
                with self.assertRaisesRegex(OSError, 'injected disk write'):
                    preview.capture('검증', canvas='part2_menu', use_cache=False,
                                    base_rom=self.candidate)
            self.assertEqual(list(cache.iterdir()), [])

    def test_encoder_preserves_complete_sjis_characters(self):
        payload, truncated = preview.encode_payload('あい', 'ja', 4)
        self.assertTrue(truncated)
        self.assertEqual(payload, 'あ'.encode('shift_jis') + bytes(2))
        payload, truncated = preview.encode_payload('가나', 'ko', 4)
        self.assertTrue(truncated)
        self.assertEqual(payload[2:], bytes(2))
        payload, truncated = preview.encode_payload('A1!', 'ko', 8, address=0xDF8E16)
        expected = build.encode_text('A1!', preview._syl_to_code(), Counter(), 0xDF8E16)
        self.assertFalse(truncated)
        self.assertEqual(payload[:len(expected)], expected)


if __name__ == '__main__':
    unittest.main()
