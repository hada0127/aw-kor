"""Translate the nine OBJ unit-type badges in the Part 1 purchase/info card.

The original 0xBD1AF0 LZ block is 12 32x32 OBJ images and three 32x8 badges.
Only the six type captions and three terrain-class captions are changed.
"""
from functools import lru_cache
import hashlib
from pathlib import Path

OFFSET = 0xBD1AF0
SLOT_SIZE = 1900
RAW_SIZE = 6528
RAW_SHA256 = 'b0dab9a9b3d476c4336af210a8becbda408f4e943943c151124e7b79e91d9906'
FONT_SHA256 = '2a6fd090ac6d24f7392d6cc49db02ce54b9d1c01048bf8c97cbcdbc5a885cb15'
FONT = Path(__file__).resolve().parents[1] / 'reference/fonts/Galmuri7.bdf'
LABELS = {6: '보병', 7: '차량', 8: '헬기', 9: '비행기', 10: '함선', 11: '잠수함',
          12: '육상', 13: '공중', 14: '해상'}


def image_spec(index):
    return (index * 512, 32) if index < 12 else (6144 + (index - 12) * 128, 8)


def decode_image(raw, index):
    offset, height = image_spec(index)
    return [[(raw[offset + ((y // 8) * 4 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2]
              >> (4 * (x % 2))) & 15 for x in range(32)] for y in range(height)]


def render(original):
    from bdf import load_bdf, glyph_grid
    if len(original) != RAW_SIZE or hashlib.sha256(original).hexdigest() != RAW_SHA256:
        raise AssertionError('Part 1 unit-type source asset changed')
    if hashlib.sha256(FONT.read_bytes()).hexdigest() != FONT_SHA256:
        raise AssertionError('Part 1 unit-type Galmuri7 font changed')
    font, _ = load_bdf(str(FONT))
    result = bytearray(original)
    for index, text in LABELS.items():
        pixels = decode_image(original, index)
        offset, height = image_spec(index)
        header = index >= 12
        if header:
            background, foreground = ((9, 6), (12, 10), (15, 13))[index - 12]
            # Keep the native white ends and colored backing. Seven-pixel Korean
            # glyphs fit rows 0..6; row 7 remains the native badge bottom.
            for y in range(7):
                for x in range(8, 24):
                    if pixels[y][x] != 1:
                        pixels[y][x] = background
            for y in range(1, 7):
                for x in range(6, 26):
                    if pixels[y][x] not in (0, 1, background):
                        pixels[y][x] = background
        else:
            # Native pictures end by row 13. Caption outline uses rows 15..23.
            for y in range(14, 32):
                pixels[y] = [0] * 32
            foreground = 1
        glyphs = [glyph_grid(font[ord(ch)]) for ch in text]
        width = sum(glyph[1] for glyph in glyphs) + len(glyphs) - 1
        if width > (16 if header else 30):
            raise AssertionError(f'unit-type caption overflow: {text}')
        cursor = (32 - width) // 2
        top = 0 if header else 16
        mask = []
        for grid, width, glyph_height, x_offset, y_offset in glyphs:
            for y in range(glyph_height):
                for x in range(width):
                    if grid[y][x]:
                        mask.append((cursor + x + x_offset, top + y + 7 - glyph_height - y_offset))
            cursor += width + 1
        if not header:
            for x, y in mask:
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1),
                               (-1, -1), (1, -1), (-1, 1), (1, 1)):
                    if 0 <= x + dx < 32 and 0 <= y + dy < height:
                        pixels[y + dy][x + dx] = 5
        for x, y in mask:
            if not (0 <= x < 32 and 0 <= y < height):
                raise AssertionError(f'unit-type glyph clipped: {text}')
            pixels[y][x] = foreground
        for y in range(height):
            for x in range(0, 32, 2):
                pos = offset + ((y // 8) * 4 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
                result[pos] = pixels[y][x] | (pixels[y][x + 1] << 4)
    return bytes(result)


@lru_cache(maxsize=1)
def _payload(original):
    from lz77_compress import lz77_compress_optimal
    from lz77_scan import lz77_decompress
    expected = render(original)
    packed = lz77_compress_optimal(expected, vram_safe=True)
    if len(packed) > SLOT_SIZE:
        raise AssertionError(f'unit-type asset exceeds original slot: {len(packed)} > {SLOT_SIZE}')
    decoded = lz77_decompress(packed, 0)
    if decoded is None or decoded[0] != expected:
        raise AssertionError('unit-type LZ roundtrip failed')
    return packed + bytes(SLOT_SIZE - len(packed)), len(packed)


def source(original_rom):
    from lz77_scan import lz77_decompress
    decoded = lz77_decompress(original_rom, OFFSET)
    if decoded is None or decoded[1] != SLOT_SIZE or hashlib.sha256(decoded[0]).hexdigest() != RAW_SHA256:
        raise AssertionError('Part 1 unit-type original ROM source changed')
    return decoded[0]


def patch(rom, original_rom):
    if len(rom) != len(original_rom) or len(rom) < OFFSET + SLOT_SIZE:
        raise AssertionError('unit-type labels require matching complete ROMs')
    original = source(original_rom)
    if bytes(rom[OFFSET:OFFSET + SLOT_SIZE]) != bytes(original_rom[OFFSET:OFFSET + SLOT_SIZE]):
        raise AssertionError('unit-type asset already changed by another writer')
    payload, packed_size = _payload(original)
    rom[OFFSET:OFFSET + SLOT_SIZE] = payload
    return {'offset': hex(OFFSET), 'labels': list(LABELS.values()), 'packed_bytes': packed_size,
            'slot_bytes': SLOT_SIZE, 'headroom': SLOT_SIZE - packed_size,
            'raw_sha256': hashlib.sha256(render(original)).hexdigest()}


def verify(rom, original_rom):
    """Validate generated labels before the sprite-editor overlay is applied."""
    expected, _ = _payload(source(original_rom))
    if bytes(rom[OFFSET:OFFSET + SLOT_SIZE]) != expected:
        raise AssertionError('unit-type asset overwritten after patch')


def capture_regions(rom, original_rom):
    """Capture the accepted editor overlay, after its own intent validation."""
    from lz77_scan import lz77_decompress
    source(original_rom)
    payload = bytes(rom[OFFSET:OFFSET + SLOT_SIZE])
    decoded = lz77_decompress(payload, 0)
    if (len(payload) != SLOT_SIZE or decoded is None or
            len(decoded[0]) != RAW_SIZE or decoded[1] > SLOT_SIZE):
        raise AssertionError('unit-type editor result is not a bounded complete asset')
    return {OFFSET: payload}


def verify_regions(rom, regions):
    """Require the final ROM to retain the accepted post-editor bytes."""
    if set(regions) != {OFFSET} or len(regions[OFFSET]) != SLOT_SIZE:
        raise AssertionError('unit-type final snapshot has the wrong extent')
    if bytes(rom[OFFSET:OFFSET + SLOT_SIZE]) != regions[OFFSET]:
        raise AssertionError('unit-type accepted asset overwritten after editor')
