"""Choose a smaller, exactly lossless PNG for a native RGB framebuffer."""
import io

from PIL import Image


def encode_frame_png(image, compress_level):
    if image.mode != 'RGB' or image.size != (240, 160):
        raise ValueError('Expected native 240x160 RGB frame')
    if type(compress_level) is not int or not 0 <= compress_level <= 9:
        raise ValueError('Invalid PNG compression level')

    def encode(candidate):
        buffer = io.BytesIO()
        candidate.save(buffer, format='PNG', compress_level=compress_level)
        return buffer.getvalue()

    rgb_png = encode(image)
    if image.getcolors(256) is None:
        return rgb_png
    pixels = image.tobytes()
    palette = image.quantize(colors=256, method=Image.Quantize.MEDIANCUT,
                             dither=Image.Dither.NONE)
    if palette.convert('RGB').tobytes() != pixels:
        return rgb_png
    palette_png = encode(palette)
    if len(palette_png) >= len(rgb_png):
        return rgb_png
    with Image.open(io.BytesIO(palette_png)) as restored:
        if restored.size != image.size or restored.convert('RGB').tobytes() != pixels:
            raise RuntimeError('Palette PNG roundtrip mismatch')
    return palette_png
