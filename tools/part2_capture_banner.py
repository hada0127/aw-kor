"""Replace the Part 2 capture-complete OBJ picture text (占領!) with 점령!.

The native 64x32 OBJ is decoded bytes 0x800..0xBFF of the LZ77 sheet at
0x47F79C. Runtime OAM uses OBJ tile 519, palette 3, affine mode; the first
0x800 decoded bytes are the capture-point window and must stay intact.
"""
import hashlib
import struct

from PIL import Image, ImageDraw

import aw_fonts
from lz77_compress import lz77_compress_optimal
from lz77_scan import lz77_decompress

SOURCE = 0x47F79C
POINTER = 0x341334
SOURCE_LENGTH = 1068
DECODED_LENGTH = 3072
SOURCE_SHA256 = '9951ef60fa99785f991e3eca89910fc2ab2d379ad2fb25ac9fb415b07413e488'
TEXT_OFFSET = 2048
TEXT = '점령!'


def _source(original):
    if struct.unpack_from('<I', original, POINTER)[0] != 0x08000000 + SOURCE:
        raise AssertionError('Part 2 capture banner pointer changed')
    if original.count(struct.pack('<I', 0x08000000 + SOURCE)) != 1:
        raise AssertionError('Part 2 capture banner has another ROM pointer')
    decoded = lz77_decompress(original, SOURCE)
    if decoded is None or decoded[1] != SOURCE_LENGTH or len(decoded[0]) != DECODED_LENGTH:
        raise AssertionError('Part 2 capture banner source size changed')
    if hashlib.sha256(decoded[0]).hexdigest() != SOURCE_SHA256:
        raise AssertionError('Part 2 capture banner source changed')
    return decoded[0]


def _picture():
    font, box = aw_fonts.fit_okdandan(TEXT, 53, 23, 34, min_size=20)
    mask = Image.new('L', (64, 32))
    x = (64 - (box[2] - box[0])) // 2 - box[0]
    y = (32 - (box[3] - box[1])) // 2 - box[1]
    ImageDraw.Draw(mask).text((x, y), TEXT, font=font, fill=255)
    ink_box = mask.getbbox()
    if ink_box is None:
        raise AssertionError('empty capture title')
    # Match the native 占領! banner's nearly full 64-pixel horizontal span.
    wide = mask.crop(ink_box).resize((55, ink_box[3] - ink_box[1]), Image.Resampling.NEAREST)
    mask = Image.new('L', (64, 32))
    mask.paste(wide, ((64 - 55) // 2, ink_box[1]))
    body = {(x, y) for y in range(32) for x in range(64) if mask.getpixel((x, y)) >= 96}
    aw_fonts.require_large_line(body, margin_top=3, margin_bottom=3)
    if not body:
        raise AssertionError('empty capture title')
    def ring(points):
        return {(x + dx, y + dy) for x, y in points
                for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                if dx or dy} - points
    # The native cut-in uses a dark outside edge, a second dark shade,
    # and a light face with pink shading. Keep those palette roles.
    near1 = ring(body)
    near2 = ring(body | near1)
    near3 = ring(body | near1 | near2)
    pixels = [[0] * 64 for _ in range(32)]
    for px, py in body | near1 | near2 | near3:
        if px + 1 < 64 and py + 2 < 32:
            pixels[py + 2][px + 1] = 1
    for points, color in ((near3, 1), (near2, 2), (near1, 3), (body, 6)):
        for px, py in points:
            if 0 <= px < 64 and 0 <= py < 32:
                pixels[py][px] = color
    # Lower-right face shading is present in the native kanji picture.
    for px, py in body:
        if (px, py + 1) not in body:
            pixels[py][px] = 4
        elif (px, py + 2) not in body:
            pixels[py][px] = 5
    if any(pixels[y][x] for y in (0, 31) for x in range(64)):
        raise AssertionError('capture title touches vertical OBJ edge')
    out = bytearray(1024)
    for tile_y in range(4):
        for tile_x in range(8):
            off = (tile_y * 8 + tile_x) * 32
            for row in range(8):
                for col in range(4):
                    left = pixels[tile_y * 8 + row][tile_x * 8 + col * 2]
                    right = pixels[tile_y * 8 + row][tile_x * 8 + col * 2 + 1]
                    out[off + row * 4 + col] = left | (right << 4)
    return bytes(out)


def expected_sheet(original):
    native = _source(original)
    return native[:TEXT_OFFSET] + _picture()


def patch(rom, original):
    expected = expected_sheet(original)
    stream = lz77_compress_optimal(expected, vram_safe=True)
    if len(stream) > SOURCE_LENGTH:
        raise AssertionError(f'Part 2 capture banner grew: {len(stream)} > {SOURCE_LENGTH}')
    if bytes(rom[SOURCE:SOURCE + SOURCE_LENGTH]) != bytes(original[SOURCE:SOURCE + SOURCE_LENGTH]):
        raise AssertionError('Part 2 capture banner was already modified')
    rom[SOURCE:SOURCE + SOURCE_LENGTH] = stream + bytes(SOURCE_LENGTH - len(stream))
    verify(rom, original)
    return len(stream)


def verify(rom, original):
    actual = lz77_decompress(rom, SOURCE)
    if actual is None or actual[0] != expected_sheet(original) or actual[1] > SOURCE_LENGTH:
        raise AssertionError('Part 2 capture banner round trip failed')
