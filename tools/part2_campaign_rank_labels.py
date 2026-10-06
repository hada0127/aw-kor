"""Part 2 CAMPAIGN / RANK speech-bubble OBJ label (LZ77 0x519764).

Static RE (original ROM, 2026-10-06 fixH):
- The block (1024 B, consumed 335) is referenced once, by the literal at
  0x0836CCEC: the routine around 0x0836CC9C..0x0836CCD2 loads the palettes
  0x088FD6E8 / 0x085198B4 and decompresses 0x08519764 into VRAM 0x06011A00
  (OBJ tile 208).  The 32 tiles are one 64x32 1D OBJ (8 tiles per row):
  a balloon (border 10 rows 4-5 and 21-22, fill 12, shade 15 right/bottom,
  tail rows 23-27) holding two dark bands (15) with white (1) 5px text:
  CAMPAIGN (rows 8-12) and RANK (rows 14-18).
- Galmuri7 Hangul is 7px tall, so the two bands do not fit on separate lines
  inside the balloon (interior rows 6..20).  The label becomes one band
  "캠페인 랭크" (same wording as the Part 1 strips, part1_campaign_clear_banner
  RANK_STRIPS) centred in the balloon: band rows 9..17, text rows 10..16.
  Balloon outline, shading and tail are kept byte-for-byte.
Terms: 캠페인 (translation_for_import 0x00A2D894 하드 캠페인), 랭크 (0x00A06CB5).
Consumer screen not observed in any savestate: on-screen result unverified.
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
SOURCE = 0x519764
POINTER = 0x36CCEC
SIZE = 1024
CAPACITY = 335
SOURCE_SHA256 = '820b0e10f9f0c622423399c74297b6fab51fedf008a4b0f95282ee10c42ada32'
TEXT = '캠페인 랭크'
WIDTH, HEIGHT = 64, 32
FILL, BAND, INK = 12, 15, 1
INTERIOR_X = (7, 57)              # x range [7, 57) of the balloon fill (x=57 is the shade column)
INTERIOR_Y = (6, 21)              # rows [6, 21)
BAND_Y = (9, 18)                  # band rows [9, 18), text rows 10..16
SPACE = 3


@lru_cache(maxsize=1)
def _font():
    font, _ = load_bdf(str(ROOT / 'reference/fonts/Galmuri7.bdf'))
    return font


def decode(data):
    return [[(data[((y // 8) * 8 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2] >> (4 * (x % 2))) & 15
             for x in range(WIDTH)] for y in range(HEIGHT)]


def encode(pixels):
    raw = bytearray(SIZE)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            raw[((y // 8) * 8 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2] |= pixels[y][x] << (4 * (x % 2))
    return bytes(raw)


def _ink(text):
    font, ink, cursor = _font(), [], 0
    for char in text:
        if char == ' ':
            cursor += SPACE
            continue
        grid, w, h, xo, yo = glyph_grid(font[ord(char)])
        top = 7 - h - yo
        for gy in range(h):
            for gx in range(w):
                if grid[gy][gx]:
                    ink.append((cursor + gx + xo, top + gy))
        cursor += w + 1
    return ink, cursor - 1


def source_guard(original):
    if struct.unpack_from('<I', original, POINTER)[0] != SOURCE + ROM_BASE:
        raise AssertionError('campaign rank label pointer changed')
    if original.count(struct.pack('<I', SOURCE + ROM_BASE)) != 1:
        raise AssertionError('campaign rank label has foreign reference')
    decoded = lz77_decompress(original, SOURCE)
    if (decoded is None or decoded[1] != CAPACITY or len(decoded[0]) != SIZE
            or hashlib.sha256(decoded[0]).hexdigest() != SOURCE_SHA256):
        raise AssertionError('campaign rank label source changed')
    return decoded[0]


def sheet(original):
    pixels = decode(source_guard(original))
    x0, x1 = INTERIOR_X
    y0, y1 = INTERIOR_Y
    for y in range(y0, y1):
        for x in range(x0, x1):
            pixels[y][x] = FILL
    ink, width = _ink(TEXT)
    band_w = width + 4
    bx0 = x0 + (x1 - x0 - band_w) // 2
    bx1 = bx0 + band_w
    if bx0 < x0 + 2 or bx1 > x1 - 2:
        raise AssertionError('campaign rank label too wide')
    for y in range(*BAND_Y):
        for x in range(bx0, bx1):
            if y in (BAND_Y[0], BAND_Y[1] - 1) and x in (bx0, bx1 - 1):
                continue                    # rounded corners like the native bands
            pixels[y][x] = BAND
    for x, y in ink:
        px, py = bx0 + 2 + x, BAND_Y[0] + 1 + y
        if not (bx0 < px < bx1 - 1 and BAND_Y[0] < py < BAND_Y[1] - 1):
            raise AssertionError('campaign rank glyph clipped')
        pixels[py][px] = INK
    return encode(pixels)


@lru_cache(maxsize=2)
def _stream(data):
    return lz77_compress_optimal(data, vram_safe=True)


def expected_regions(original):
    stream = _stream(sheet(original))
    if len(stream) > CAPACITY:
        raise AssertionError(f'campaign rank label overflow: {len(stream)} > {CAPACITY}')
    return ((SOURCE, stream + bytes(CAPACITY - len(stream))),)


def _fixed(original):
    return ((POINTER, bytes(original[POINTER:POINTER + 4])),)


def patch(rom, original):
    regions = expected_regions(original)
    for address, raw in _fixed(original):
        if bytes(rom[address:address + 4]) != raw:
            raise AssertionError('campaign rank label pointer changed in ROM')
    for address, new in regions:
        if bytes(rom[address:address + len(new)]) not in (bytes(original[address:address + len(new)]), new):
            raise AssertionError('campaign rank label already modified by another writer')
    for address, new in regions:
        rom[address:address + len(new)] = new
    decoded = lz77_decompress(rom, SOURCE)
    if decoded is None or decoded[0] != sheet(original):
        raise AssertionError('campaign rank label round trip failed')
    return len(regions)


def capture(rom, original):
    from part1_mission_titles import verify_vram_stream
    regions = expected_regions(original)
    for address, raw in _fixed(original):
        if bytes(rom[address:address + 4]) != raw:
            raise AssertionError('campaign rank label final pointer changed')
    decoded = lz77_decompress(rom, SOURCE)
    if decoded is None or len(decoded[0]) != SIZE or decoded[1] > CAPACITY:
        raise AssertionError('campaign rank label final block invalid')
    verify_vram_stream(bytes(rom[SOURCE:SOURCE + CAPACITY]), SIZE, 'campaign rank label')
    return tuple((a, bytes(rom[a:a + len(n)])) for a, n in regions) + _fixed(original)


def expected_region_addresses():
    return (SOURCE, POINTER)


def verify(rom, regions):
    if tuple(a for a, _ in regions) != expected_region_addresses():
        raise AssertionError('campaign rank label snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'campaign rank label overwritten after editor at {address:06X}')


def generated_matches(rom, original):
    decoded = lz77_decompress(rom, SOURCE)
    return decoded is not None and decoded[0] == sheet(original)
