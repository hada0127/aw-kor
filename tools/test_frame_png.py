import io
import contextlib
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from frame_png import encode_frame_png
import test_playthrough_png_compression as capture_tests


class FramePngTests(unittest.TestCase):
    def frame(self):
        image = Image.new('RGB', (240, 160))
        image.putdata([((x * 19) % 256, (x * 31) % 256, (x * 47) % 256)
                       for x in range(240 * 160)])
        return image

    def test_exact_pixels_and_smaller_palette(self):
        image = self.frame()
        for level in (0, 3, 6, 9):
            raw = encode_frame_png(image, level)
            with Image.open(io.BytesIO(raw)) as restored:
                self.assertEqual(restored.convert('RGB').tobytes(), image.tobytes())
            baseline = io.BytesIO()
            image.save(baseline, format='PNG', compress_level=level)
            self.assertLessEqual(len(raw), len(baseline.getvalue()))
        with Image.open(io.BytesIO(encode_frame_png(image, 0))) as restored:
            self.assertEqual(restored.mode, 'P')

    def test_more_than_256_colors_keeps_rgb(self):
        image = Image.new('RGB', (240, 160))
        image.putdata([(x % 256, x // 256, 17) for x in range(240 * 160)])
        with patch.object(Image.Image, 'quantize', side_effect=AssertionError('must not quantize')):
            raw = encode_frame_png(image, 3)
        with Image.open(io.BytesIO(raw)) as restored:
            self.assertEqual(restored.mode, 'RGB')
            self.assertEqual(restored.tobytes(), image.tobytes())

    def test_inexact_quantization_falls_back(self):
        image = self.frame()
        with patch.object(Image.Image, 'quantize', return_value=Image.new('P', image.size)):
            raw = encode_frame_png(image, 3)
        with Image.open(io.BytesIO(raw)) as restored:
            self.assertEqual(restored.mode, 'RGB')
            self.assertEqual(restored.tobytes(), image.tobytes())

    def test_larger_palette_keeps_rgb(self):
        image = Image.new('RGB', (240, 160), 'white')
        original_save = Image.Image.save
        def larger_palette(candidate, buffer, **kwargs):
            original_save(candidate, buffer, **kwargs)
            if candidate.mode == 'P':
                buffer.write(b'padding' * 1000)
        with patch.object(Image.Image, 'save', larger_palette):
            raw = encode_frame_png(image, 9)
        with Image.open(io.BytesIO(raw)) as restored:
            self.assertEqual(restored.mode, 'RGB')

    def test_invalid_contract(self):
        for image, level in ((Image.new('P', (240, 160)), 3),
                             (Image.new('RGB', (1, 1)), 3), (self.frame(), True)):
            with self.assertRaises(ValueError):
                encode_frame_png(image, level)

    def test_corrupt_palette_png_is_rejected(self):
        image = self.frame()
        original_save = Image.Image.save
        def corrupt_palette(candidate, buffer, **kwargs):
            if candidate.mode == 'P':
                candidate = Image.new('P', candidate.size)
            original_save(candidate, buffer, **kwargs)
        with patch.object(Image.Image, 'save', corrupt_palette):
            with self.assertRaisesRegex(RuntimeError, 'Palette PNG roundtrip mismatch'):
                encode_frame_png(image, 0)


class PaletteCaptureTests(capture_tests.PngCaptureTests):
    def recorder(self, level):
        recorder = super().recorder(level)
        recorder.lossless_palette_frames = True
        return recorder

    def test_palette_and_rgb_capture_have_identical_ledgers(self):
        palette = self.recorder(0)
        rgb = capture_tests.PngCaptureTests.recorder(self, 3)
        for recorder in (palette, rgb):
            for keys in (1, 0, 16):
                recorder.capture(keys)
        self.assertEqual(palette.ledger.getvalue(), rgb.ledger.getvalue())
        with Image.open(palette.pending_png[0]) as image:
            self.assertEqual(image.mode, 'P')
        with Image.open(rgb.pending_png[0]) as image:
            self.assertEqual(image.mode, 'RGB')

    def test_action_applies_selected_level_to_frames_endpoint_and_sheet(self):
        # Palette encoding uses in-memory alternatives; endpoints/sheets stay RGB.
        recorder = self.recorder(3)
        recorder.segment = 0
        recorder.last_checkpoint = None
        recorder.actions = io.StringIO()
        recorder.checkpoint = Mock(return_value=recorder.out / 'checkpoint.json')
        with contextlib.redirect_stdout(io.StringIO()):
            recorder.action('A', 2, 1)
        self.assertEqual(recorder.committed, 3)
        self.assertEqual(len(recorder.pending_png), 2)
        endpoints = list(recorder.out.glob('*.png'))
        self.assertEqual(len(endpoints), 2)
        for path in endpoints:
            with Image.open(path) as image:
                self.assertEqual(image.mode, 'RGB')
        recorder.checkpoint.assert_called_once()


if __name__ == '__main__':
    unittest.main()
