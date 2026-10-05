"""Translate the native remaining-days OBJ labels; leave digits and layout alone."""
import hashlib
import struct
from pathlib import Path

from bdf import load_bdf, glyph_grid

ROOT = Path(__file__).resolve().parent.parent
SOURCE = 0x483D14
SIZE = 96
SOURCE_SHA = '9440da5bd729e5413733f13d902300ea11e194f4f07230f18c4f6cc99a0488fd'
LOADER = (0x343DCE, bytes.fromhex('094809496022cef748f8'))
LITERALS = (0x343DF4, struct.pack('<II', 0x08000000 + SOURCE, 0x06010840))
# Native copy is exactly 96 bytes: OBJ tiles 0x42..0x44. The 16x8 prefix
# and 8x8 suffix surround a separately drawn numeric OBJ (observed tile 0x3D7).


def validate(original, rom):
    if hashlib.sha256(original[SOURCE:SOURCE + SIZE]).hexdigest() != SOURCE_SHA:
        raise AssertionError('remaining-days source changed')
    for address, expected in (LOADER, LITERALS):
        if original[address:address + len(expected)] != expected or rom[address:address + len(expected)] != expected:
            raise AssertionError('remaining-days native loader changed')


def render_labels():
    font, _ = load_bdf(str(ROOT / 'reference/fonts/Galmuri7.bdf'))
    ink = set()
    for cell, char in enumerate('남은일'):
        if ord(char) not in font:
            raise AssertionError(f'remaining-days glyph missing: {char}')
        grid, width, height, xoffset, yoffset = glyph_grid(font[ord(char)])
        if (width, height, xoffset, yoffset) != ((6 if cell == 2 else 7), 7, 0, 0):
            raise AssertionError('remaining-days glyph geometry changed')
        for y in range(height):
            for x in range(width):
                if grid[y][x]:
                    # Shift 남 right for its left outline; 일 has room on both
                    # sides. 은 ends at x=14: x=15 must remain transparent.
                    px = cell * 8 + x + (1 if cell in (0, 2) else 0)
                    ink.add((px, y))
    pixels = [[0] * 24 for _ in range(8)]
    # Original OBJ palette 1: white=1, dark green outline=15, muted shadow=7.
    # Seven-pixel Hangul keeps the native y=6 baseline in an eight-pixel OBJ:
    # top outlines, and 은's right outline at the digit overlap, are clipped.
    for x, y in ink:
        # Prefix and suffix are separate OBJs, with the digit between them.
        # Native prefix column 15 is transparent where the digit overlaps it.
        left, right = (0, 15) if x < 16 else (16, 24)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if left <= x + dx < right and 0 <= y + dy < 8:
                    pixels[y + dy][x + dx] = 15
    for x, y in ink:
        right = 15 if x < 16 else 24
        if x + 1 < right and y + 1 < 8:
            pixels[y + 1][x + 1] = 7
    for x, y in ink:
        pixels[y][x] = 1
    raw = bytearray(SIZE)
    for y in range(8):
        for x in range(24):
            offset = x // 8 * 32 + y * 4 + x % 8 // 2
            raw[offset] |= pixels[y][x] << (4 * (x % 2))
    return bytes(raw)


def patch(rom, original):
    validate(original, rom)
    if rom[SOURCE:SOURCE + SIZE] != original[SOURCE:SOURCE + SIZE]:
        raise AssertionError('remaining-days asset already modified')
    rom[SOURCE:SOURCE + SIZE] = render_labels()
    return 2  # Two native labels: prefix and suffix; numeric OBJ is unchanged.


def capture_regions(rom, original):
    validate(original, rom)
    # The registered sprite-editor overlay owns these final pixels. Freeze its
    # accepted result, rather than requiring the generated Galmuri default.
    regions = ((SOURCE, bytes(rom[SOURCE:SOURCE + SIZE])), LOADER, LITERALS)
    verify_regions(rom, regions)
    return regions


def verify_regions(rom, regions):
    if (not isinstance(regions, tuple) or len(regions) != 3
            or not isinstance(regions[0], tuple) or len(regions[0]) != 2
            or regions[0][0] != SOURCE or not isinstance(regions[0][1], bytes)
            or len(regions[0][1]) != SIZE or regions[1:] != (LOADER, LITERALS)):
        raise AssertionError('remaining-days final evidence invalid')
    for address, expected in regions:
        if rom[address:address + len(expected)] != expected:
            raise AssertionError('remaining-days asset overwritten after final overlay')
