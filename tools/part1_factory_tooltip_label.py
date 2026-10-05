"""Translate the Part 1 map cursor tooltip plates 生産/処分 inside their native OBJ block.

Recorded public VRAM/OAM evidence (2026-10-06, play ROM ab9627..., state
output/qa/part1_2026-10-05/m20_claude/0142_DOWN_0702126.ss0): the factory-cursor
tooltip is OAM35 (x156,y60, 16x16, tile 956) + OAM36 (x172,y60, 16x16, tile 952),
OBJ palette 1, 1D mapping.  The LZ77 block at 0xBA4948 (single pointer 0xB20A2C)
decodes to 88 tiles loaded at OBJ tile 872, so 生 = block tiles 84..87 (left
plate half) and 産 = 80..83 (right half).  The same block also carries the torn
処分 plate: 処 = 76..79 (left), 分 = 72..75 (right); its live OAM was not observed.

Only the text interior of each 16x16 half is redrawn (native fill 9, white ink 1,
black drop shadow 15); frame, rivets, torn edges and every other tile stay
byte-identical.  The block is recompressed in place with the project's optimal
VRAM-safe LZ77 encoder and must not grow past the original compressed span.
"""
import hashlib
import struct
from pathlib import Path

from bdf import load_bdf, glyph_grid
from lz77_compress import lz77_compress_optimal
from lz77_scan import lz77_decompress

ROOT = Path(__file__).resolve().parent.parent
OFFSET = 0xBA4948
POINTER = 0xB20A2C
COMPRESSED_SIZE = 1082
DECODED_SIZE = 2816
SOURCE_SHA256 = 'd8c4ca077df75e816e2d7a6fa26d92551fcc52a6be640f6b4832bb707391046c'
FILL, INK, SHADOW = 9, 1, 15
# (first tile of the 16x16 half, syllable, text rect x0,y0,x1,y1 inclusive, glyph x, glyph y)
HALVES = (
    (84, '생', (7, 3, 15, 13), 7, 4),
    (80, '산', (0, 3, 9, 13), 1, 4),
    (76, '처', (6, 3, 15, 13), 7, 4),
    (72, '분', (0, 3, 10, 13), 1, 4),
)
LABELS = (('생산', (84, 80)), ('처분', (76, 72)))


def _pixel_index(tile, x, y):
    # 16x16 sprite in 1D mapping: TL, TR, BL, BR tiles.
    t = tile + (y // 8) * 2 + x // 8
    return t * 32 + (y % 8) * 4 + (x % 8) // 2, 4 * (x % 2)


def get_pixel(data, tile, x, y):
    index, shift = _pixel_index(tile, x, y)
    return (data[index] >> shift) & 15


def _set_pixel(data, tile, x, y, value):
    index, shift = _pixel_index(tile, x, y)
    data[index] = (data[index] & ~(15 << shift)) | (value << shift)


def source_block(original):
    raw = bytes(original[OFFSET:OFFSET + COMPRESSED_SIZE])
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise AssertionError('Part1 factory tooltip LZ77 source changed')
    if struct.unpack_from('<I', original, POINTER)[0] != OFFSET + 0x08000000:
        raise AssertionError('Part1 factory tooltip source pointer changed')
    decoded = lz77_decompress(original, OFFSET)
    if decoded is None or len(decoded[0]) != DECODED_SIZE or decoded[1] != COMPRESSED_SIZE:
        raise AssertionError('Part1 factory tooltip LZ77 source does not decode natively')
    return bytes(decoded[0])


def decoded_replacement(original):
    data = bytearray(source_block(original))
    font, _ = load_bdf(str(ROOT / 'reference/fonts/Galmuri9.bdf'))
    for tile, syllable, (x0, y0, x1, y1), gx, gy in HALVES:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                _set_pixel(data, tile, x, y, FILL)
        grid, width, height, xoffset, _ = glyph_grid(font[ord(syllable)])
        ink = {(gx + x + xoffset, gy + y) for y in range(height) for x in range(width) if grid[y][x]}
        for x, y in ink:
            if not (x0 <= x <= x1 and y0 <= y <= y1):
                raise AssertionError(f'factory tooltip glyph {syllable} exceeds native text area')
        for x, y in ink:
            for sx, sy in ((x + 1, y), (x, y + 1), (x + 1, y + 1)):
                if (sx, sy) not in ink and x0 <= sx <= x1 and y0 <= sy <= y1:
                    _set_pixel(data, tile, sx, sy, SHADOW)
        for x, y in ink:
            _set_pixel(data, tile, x, y, INK)
    return bytes(data)


def compressed_replacement(original):
    payload = lz77_compress_optimal(decoded_replacement(original), vram_safe=True)
    if len(payload) > COMPRESSED_SIZE:
        raise AssertionError(f'Part1 factory tooltip LZ77 grew: {len(payload)} > {COMPRESSED_SIZE}')
    check = lz77_decompress(payload, 0)
    if check is None or bytes(check[0]) != decoded_replacement(original):
        raise AssertionError('Part1 factory tooltip LZ77 round-trip failed')
    return payload + b'\x00' * (COMPRESSED_SIZE - len(payload))


def patch(rom, original):
    expected = compressed_replacement(original)
    current = bytes(rom[OFFSET:OFFSET + COMPRESSED_SIZE])
    if current not in (bytes(original[OFFSET:OFFSET + COMPRESSED_SIZE]), expected):
        raise AssertionError('Part1 factory tooltip conflicts with an earlier writer')
    if rom[POINTER:POINTER + 4] != original[POINTER:POINTER + 4]:
        raise AssertionError('Part1 factory tooltip live pointer changed')
    rom[OFFSET:OFFSET + COMPRESSED_SIZE] = expected
    return len(LABELS)


def generated_matches(rom, original):
    return bytes(rom[OFFSET:OFFSET + COMPRESSED_SIZE]) == compressed_replacement(original)


def capture_regions(rom, original):
    source_block(original)
    if rom[POINTER:POINTER + 4] != original[POINTER:POINTER + 4]:
        raise AssertionError('Part1 factory tooltip final pointer changed')
    decoded = lz77_decompress(rom, OFFSET)
    if decoded is None or len(decoded[0]) != DECODED_SIZE or decoded[1] > COMPRESSED_SIZE:
        raise AssertionError('Part1 factory tooltip final LZ77 block invalid')
    return ((OFFSET, bytes(rom[OFFSET:OFFSET + COMPRESSED_SIZE])),
            (POINTER, bytes(rom[POINTER:POINTER + 4])))


def verify_regions(rom, regions):
    if len(regions) != 2:
        raise AssertionError('Part1 factory tooltip evidence missing')
    for address, expected in regions:
        if bytes(rom[address:address + len(expected)]) != expected:
            raise AssertionError('Part1 factory tooltip overwritten')
