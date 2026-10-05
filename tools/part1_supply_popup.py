"""Translate the observed supply bubble without changing its native frame/icon.

Recorded public VRAM/OAM evidence: 5821_NONE_0914907, OAM16, tile397,
64x32 4bpp 1D, palette3, identity affine matrix31. The full 1024-byte asset
matches the original ROM exactly once. Patched live pixels remain unverified.
"""
import hashlib
from pathlib import Path

from bdf import load_bdf, glyph_grid

ROOT = Path(__file__).resolve().parent.parent
SOURCE = 0xBD0F90
SIZE = 1024
SOURCE_SHA256 = '466d77039a491789a742bcf8e1e349f16cf86ced31bd89ebf9515c362440d755'
TEXT_BOX = (22, 12, 52, 20)


def pixel(raw, x, y):
    index = ((y // 8) * 8 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
    return (raw[index] >> (4 * (x % 2))) & 15


def replacement(original):
    raw = bytes(original[SOURCE:SOURCE + SIZE])
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('Part1 supply popup source changed')
    output = bytearray(raw)
    x0, y0, x1, y1 = TEXT_BOX

    def put(x, y, value):
        if not (x0 <= x < x1 and y0 <= y < y1):
            raise ValueError('Supply glyph exceeds native text area')
        index = ((y // 8) * 8 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
        shift = 4 * (x % 2)
        output[index] = (output[index] & ~(15 << shift)) | (value << shift)

    for y in range(y0, y1):
        for x in range(x0, x1):
            put(x, y, 1)  # Native white interior.
    font, _ = load_bdf(str(ROOT / 'reference/fonts/Galmuri7.bdf'))
    ink = set()
    for column, char in enumerate('보급'):
        grid, width, height, xoffset, _ = glyph_grid(font[ord(char)])
        for y in range(height):
            for x in range(width):
                if grid[y][x]:
                    ink.add(((x0 + x1 - 16) // 2 + column * 8 + x + xoffset, y0 + y))
    for x, y in ink:
        put(x + 1, y + 1, 3)  # Native gray shadow, then black ink.
    for x, y in ink:
        put(x, y, 5)
    return bytes(output)


def patch(rom, original):
    expected = replacement(original)
    if bytes(rom[SOURCE:SOURCE + SIZE]) not in (bytes(original[SOURCE:SOURCE + SIZE]), expected):
        raise ValueError('Part1 supply popup conflicts with an earlier writer')
    rom[SOURCE:SOURCE + SIZE] = expected
    return 1


def verify(rom, original):
    if bytes(rom[SOURCE:SOURCE + SIZE]) != replacement(original):
        raise ValueError('Part1 supply popup overwritten')
