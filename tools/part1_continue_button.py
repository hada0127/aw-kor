"""Part 1 'つづきから' pill button LZ77 sheet at 0xC06FDC (single pointer 0xB4B63C).

The sheet decodes to 384 bytes = a 32x16 OBJ cell (tiles 0..7, 4x2, 1D) plus a
16x16 cell (tiles 8..11, 2x2): one 48x16 pill button (white border 10, black
interior 15, red drop shadow 9, white text 10 with grey 12 edges).  Static
evidence: the kana read cleanly only in that layout
(temp/claude_2026-10-06/fixA/work/c06fdc_48x16.png).

Only the text rectangle x 5..40, y 3..10 is redrawn: it is cleared to the
interior black and '계속하기' (the existing Part 1 menu translation of
つづきから, build_title_hangul.py MENU label 'continue' 0xC051DC) is drawn in
Galmuri7 with ink 10.  Border, shadow and padding stay byte-identical.  The
stream is recompressed in place inside the original 221-byte allocation.
The live screen that shows this button was not captured (unverified).
"""
import hashlib
import struct
from functools import lru_cache
from pathlib import Path

from bdf import load_bdf, glyph_grid
from lz77_scan import lz77_decompress
from lz77_compress import lz77_compress_optimal

ROOT = Path(__file__).resolve().parent.parent
ROM_BASE = 0x08000000
SOURCE, POINTER, FOLLOWING, CAPACITY, SIZE = 0xC06FDC, 0xB4B63C, 0xC070BC, 221, 384
SOURCE_SHA = '94cda72dfb6215b5a54b765df29f637d845e24b2f45e2dc9bf018023ce386c11'
TEXT = '계속하기'
RECT = (5, 3, 40, 10)  # inclusive text area inside the pill
FILL, INK = 15, 10


def source_guard(original):
    decoded = lz77_decompress(original, SOURCE)
    if (decoded is None or len(decoded[0]) != SIZE or decoded[1] != CAPACITY
            or hashlib.sha256(decoded[0]).hexdigest() != SOURCE_SHA
            or not 0 <= FOLLOWING - SOURCE - CAPACITY < 4
            or original.count(struct.pack('<I', SOURCE + ROM_BASE)) != 1
            or struct.unpack_from('<I', original, POINTER)[0] != SOURCE + ROM_BASE):
        raise AssertionError('Part 1 continue button source/allocation changed')
    return bytes(decoded[0])


def _offset(x, y):
    tile = ((y // 8) * 4 + x // 8) if x < 32 else 8 + (y // 8) * 2 + (x - 32) // 8
    return tile * 32 + (y % 8) * 4 + (x % 8) // 2, 4 * (x % 2)


def get_pixel(data, x, y):
    index, shift = _offset(x, y)
    return (data[index] >> shift) & 15


def _set_pixel(data, x, y, value):
    index, shift = _offset(x, y)
    data[index] = (data[index] & ~(15 << shift)) | (value << shift)


@lru_cache(maxsize=None)
def _render(original_decoded):
    data = bytearray(original_decoded)
    x0, y0, x1, y1 = RECT
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if get_pixel(data, x, y) not in (FILL, INK, 12):
                raise AssertionError('Part 1 continue button text area changed')
            _set_pixel(data, x, y, FILL)
    font, _ = load_bdf(str(ROOT / 'reference/fonts/Galmuri7.bdf'))
    glyphs = [glyph_grid(font[ord(char)]) for char in TEXT]
    total = sum(xoffset + width for _, width, _, xoffset, _ in glyphs) + len(glyphs) - 1
    cursor = x0 + (x1 - x0 + 1 - total) // 2
    for grid, width, height, xoffset, yoffset in glyphs:
        top = y0 + 7 - height - yoffset
        for y in range(height):
            for x in range(width):
                if grid[y][x]:
                    px, py = cursor + xoffset + x, top + y
                    if not (x0 <= px <= x1 and y0 <= py <= y1):
                        raise AssertionError('Part 1 continue button glyph exceeds text area')
                    _set_pixel(data, px, py, INK)
        cursor += xoffset + width + 1
    return bytes(data)


def render(original):
    return _render(source_guard(original))


def compressed(original):
    stream = lz77_compress_optimal(render(original), vram_safe=True)
    if len(stream) > CAPACITY:
        raise AssertionError(f'Part 1 continue button compressed allocation overflow: {len(stream)} > {CAPACITY}')
    return stream


def patch(rom, original):
    source_guard(original)
    if (bytes(rom[POINTER:POINTER + 4]) != original[POINTER:POINTER + 4]
            or bytes(rom[SOURCE:FOLLOWING]) != original[SOURCE:FOLLOWING]):
        raise AssertionError('Part 1 continue button already modified by another writer')
    stream = compressed(original)
    rom[SOURCE:SOURCE + CAPACITY] = stream + bytes(CAPACITY - len(stream))
    decoded = lz77_decompress(rom, SOURCE)
    if decoded is None or decoded[0] != render(original):
        raise AssertionError('Part 1 continue button round trip failed')
    return 1


def capture(rom, original):
    from part1_mission_titles import verify_vram_stream
    source_guard(original)
    decoded = lz77_decompress(rom, SOURCE)
    if (decoded is None or len(decoded[0]) != SIZE or decoded[1] > CAPACITY
            or bytes(rom[POINTER:POINTER + 4]) != original[POINTER:POINTER + 4]
            or bytes(rom[SOURCE + CAPACITY:FOLLOWING]) != original[SOURCE + CAPACITY:FOLLOWING]):
        raise AssertionError('Part 1 continue button final allocation changed')
    verify_vram_stream(bytes(rom[SOURCE:SOURCE + CAPACITY]), SIZE, 'Part 1 continue button')
    return ((SOURCE, bytes(rom[SOURCE:FOLLOWING])), (POINTER, bytes(rom[POINTER:POINTER + 4])))


def verify(rom, regions):
    if tuple(p for p, _ in regions) != (SOURCE, POINTER):
        raise AssertionError('Part 1 continue button snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError('Part 1 continue button overwritten after editor')


def generated_matches(rom, original):
    decoded = lz77_decompress(rom, SOURCE)
    return decoded is not None and decoded[0] == render(original)
