"""デザインマップ (design map) 80x64 BG panel -> 디자인 / 맵.

0x5BB8B0 (Part 2; pointers 0x3877D8 and 0x3879B8) and its byte-identical copy
0xBF5D84 (Part 1; pointer 0xB44F48) decode to 80 tiles (2560 bytes).

Consumers (static RE, original ROM):
  Part 2 0x3877BC / 0x387956: LZ77-decompress to BG char block
    (0x0300200C BGCNT shadow) + 0x06004000; 0x38796A..0x38799E then writes a
    10x8 tilemap, entry = 0x6000 | (0x200 + n), n row-major -> the panel is a
    80x64 image, 10 tiles wide (palette 6).  0x387950 only runs this when the
    map byte at [r4] > 0xB3 (design-map slots).
  Part 1 0xB44E8C: decompresses the same data to BG VRAM at tile [obj+0x48].
On-screen display is unverified (no savestate of the design-map screen; a
2455-state VRAM sample never held these tiles).

Korean term: 디자인 맵 (translation_for_import 0x00A2CC2C / 0x00B81CC0
デザインマップ).  Native style kept: white ink 1, gray shadow 12 (C) at the
lower right, background 9, corner brackets (rows 0..7 and 56..63) untouched.
Glyphs: Galmuri11-Bold 12px (pixel font, no AA) scaled 2x.
"""
import hashlib
import struct
from functools import lru_cache
from pathlib import Path

from lz77_compress import lz77_compress_optimal
from lz77_scan import lz77_decompress

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / 'reference/fonts/Galmuri11-Bold.ttf'
ROM_BASE = 0x08000000
SIZE = 2560
CAPACITY = 630
SOURCE_SHA256 = '92fe349b48d1b11324c7f8d5c3ddd19f20e3d74ccf6a7639d3ba9b4afaac213e'
# (LZ77 offset, pointers)
COPIES = ((0x5BB8B0, (0x3877D8, 0x3879B8)), (0xBF5D84, (0xB44F48,)))
WIDTH, HEIGHT, TILES_WIDE = 80, 64, 10
BG, INK, SHADOW = 9, 1, 12
TEXT_ROWS = (8, 56)          # rows cleared to background (corners live outside)
LINES = (('디자인', 9), ('맵', 32))  # (text, top row)


def _offset(x, y):
    tile = (y // 8) * TILES_WIDE + x // 8
    return tile * 32 + (y % 8) * 4 + (x % 8) // 2


def get(data, x, y):
    return (data[_offset(x, y)] >> (4 * (x % 2))) & 15


def _put(data, x, y, value):
    i = _offset(x, y)
    shift = 4 * (x % 2)
    data[i] = (data[i] & ~(15 << shift)) | (value << shift)


def source_guard(original):
    for offset, pointers in COPIES:
        decoded = lz77_decompress(original, offset)
        if (decoded is None or len(decoded[0]) != SIZE or decoded[1] != CAPACITY
                or hashlib.sha256(decoded[0]).hexdigest() != SOURCE_SHA256):
            raise AssertionError(f'design map panel source changed {offset:06X}')
        if original.count(struct.pack('<I', offset + ROM_BASE)) != len(pointers):
            raise AssertionError(f'design map panel has foreign reference {offset:06X}')
        for pointer in pointers:
            if struct.unpack_from('<I', original, pointer)[0] != offset + ROM_BASE:
                raise AssertionError(f'design map panel pointer changed {pointer:06X}')
    return lz77_decompress(original, COPIES[0][0])[0]


@lru_cache(maxsize=None)
def _mask(text):
    """2x-scaled Galmuri11-Bold mask; returns (set of (x, y)), width, height."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(str(FONT), 12)
    cells = []
    for char in text:
        image = Image.new('L', (16, 16), 0)
        ImageDraw.Draw(image).text((0, 0), char, font=font, fill=255)
        box = image.getbbox()
        if box is None:
            raise AssertionError(f'design map glyph missing {char}')
        pixels = {(x - box[0], y) for y in range(16) for x in range(box[0], box[2])
                  if image.getpixel((x, y)) > 127}
        cells.append((pixels, box[2] - box[0]))
    ink, cursor = set(), 0
    for pixels, width in cells:
        for x, y in pixels:
            for dx in (0, 1):
                for dy in (0, 1):
                    ink.add((cursor + 2 * x + dx, 2 * (y - 1) + dy))
        cursor += 2 * width + 2
    width = cursor - 2
    height = max(y for _, y in ink) + 1
    return frozenset(ink), width, height


def decoded_replacement(original):
    data = bytearray(source_guard(original))
    y0, y1 = TEXT_ROWS
    for y in range(y0, y1):
        for x in range(WIDTH):
            _put(data, x, y, BG)
    for text, top in LINES:
        ink, width, height = _mask(text)
        left = (WIDTH - width - 1) // 2
        points = {(left + x, top + y) for x, y in ink}
        for x, y in points:
            for sx, sy in ((x + 1, y), (x, y + 1), (x + 1, y + 1)):
                if (sx, sy) not in points:
                    if not (0 <= sx < WIDTH and y0 <= sy < y1):
                        raise AssertionError(f'design map shadow clipped: {text}')
                    _put(data, sx, sy, SHADOW)
        for x, y in points:
            if not (2 <= x < WIDTH - 2 and y0 <= y < y1):
                raise AssertionError(f'design map glyph clipped: {text}')
            _put(data, x, y, INK)
    return bytes(data)


@lru_cache(maxsize=1)
def _payload(original):
    expected = decoded_replacement(original)
    stream = lz77_compress_optimal(expected, vram_safe=True)
    if len(stream) > CAPACITY:
        raise AssertionError(f'design map panel LZ77 grew: {len(stream)} > {CAPACITY}')
    check = lz77_decompress(stream, 0)
    if check is None or check[0] != expected:
        raise AssertionError('design map panel LZ77 round trip failed')
    return stream + bytes(CAPACITY - len(stream))


def compressed_replacement(original):
    return _payload(bytes(original))


def patch(rom, original):
    payload = compressed_replacement(original)
    for offset, pointers in COPIES:
        current = bytes(rom[offset:offset + CAPACITY])
        if current not in (bytes(original[offset:offset + CAPACITY]), payload):
            raise AssertionError(f'design map panel {offset:06X} conflicts with an earlier writer')
        for pointer in pointers:
            if rom[pointer:pointer + 4] != original[pointer:pointer + 4]:
                raise AssertionError(f'design map panel pointer repointed {pointer:06X}')
    for offset, _ in COPIES:
        rom[offset:offset + CAPACITY] = payload
    return len(COPIES)


def generated_matches(rom, original):
    payload = compressed_replacement(original)
    return all(bytes(rom[o:o + CAPACITY]) == payload for o, _ in COPIES)


def capture(rom, original):
    from part1_mission_titles import verify_vram_stream
    source_guard(original)
    regions = []
    for offset, pointers in COPIES:
        decoded = lz77_decompress(rom, offset)
        if decoded is None or len(decoded[0]) != SIZE or decoded[1] > CAPACITY:
            raise AssertionError(f'design map panel final block invalid {offset:06X}')
        verify_vram_stream(bytes(rom[offset:offset + CAPACITY]), SIZE, 'design map panel')
        regions.append((offset, bytes(rom[offset:offset + CAPACITY])))
        regions.extend((p, bytes(rom[p:p + 4])) for p in pointers)
    return tuple(regions)


def verify(rom, regions):
    expected = tuple(a for o, ps in COPIES for a in (o,) + ps)
    if tuple(a for a, _ in regions) != expected:
        raise AssertionError('design map panel snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'design map panel overwritten at {address:06X}')
