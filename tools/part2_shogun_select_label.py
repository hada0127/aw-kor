"""Part 2 campaign-map 'SYOGUN / SELECT' BG label (LZ77 0x547A8C).

Evidence (2026-10-06 fixH): savestate
output/qa/part2_2026-09-23/round8_m7_live/0191_A_0051822.ss0 (+ .png, campaign
map with the CO-select box "SYOGUN SELECT" left of the briefing text): BG0
(BGCNT 0x0E00, char base 0) cells (1..6, 6..9) = tiles 70..93 palette 1, whose
VRAM bytes equal the 24 decoded tiles of 0x547A8C in order (6 tiles per row).
So the block is one 48x32 picture: SYOGUN in rows 1..14 and SELECT in rows
15..29, white (1) 12px letters, dark band/outline 14, anti-alias 9/10.
The block is referenced once (literal 0x0837802C).

Korean = SHOGUN -> 사령관 (project policy, part1_obj_header_labels SHOGUN PROFILE
-> 사령관 프로필; data/proper_nouns.json common_terms 사령관 브레이크),
SELECT -> 선택: 사령관 / 선택 on two lines, left aligned like the English, in
Galmuri11-Bold at its native 12px (11px Hangul, the same height class as the
native 12px Latin), white 1 on a rounded dark band 14 built from the text
box + 1px (the native band shape).  Unverified on screen.
"""
import hashlib
import struct
from functools import lru_cache
from pathlib import Path

from lz77_scan import lz77_decompress
from lz77_compress import lz77_compress_optimal

ROOT = Path(__file__).resolve().parent.parent
ROM_BASE = 0x08000000
SOURCE = 0x547A8C
POINTER = 0x37802C
SIZE = 768
CAPACITY = 387
SOURCE_SHA256 = 'd6bffc33ba821a9447466b92da5119c593a8aab2b1c4b6f38b12c2d6281033f5'
WIDTH, HEIGHT, COLS = 48, 32, 6
INK, BAND = 1, 14
FONT = ROOT / 'reference/fonts/Galmuri11-Bold.ttf'
# (text, glyph top row) ; band = glyph box +-1 (rows top-1 .. top+11)
LINES = (('사령관', 2), ('선택', 17))
LEFT = 2


@lru_cache(maxsize=None)
def text_mask(text):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(str(FONT), 12)
    image = Image.new('L', (64, 16), 0)
    ImageDraw.Draw(image).text((0, 0), text, font=font, fill=255)
    box = image.getbbox()
    if box is None:
        raise AssertionError(f'shogun select glyph missing: {text}')
    x0, y0, x1, y1 = box
    return frozenset((x - x0, y - y0) for y in range(y0, y1) for x in range(x0, x1)
                     if image.getpixel((x, y)) >= 128), x1 - x0, y1 - y0


def decode(data):
    return [[(data[((y // 8) * COLS + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2] >> (4 * (x % 2))) & 15
             for x in range(WIDTH)] for y in range(HEIGHT)]


def encode(pixels):
    raw = bytearray(SIZE)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            raw[((y // 8) * COLS + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2] |= pixels[y][x] << (4 * (x % 2))
    return bytes(raw)


def source_guard(original):
    if struct.unpack_from('<I', original, POINTER)[0] != SOURCE + ROM_BASE:
        raise AssertionError('shogun select pointer changed')
    if original.count(struct.pack('<I', SOURCE + ROM_BASE)) != 1:
        raise AssertionError('shogun select has foreign reference')
    decoded = lz77_decompress(original, SOURCE)
    if (decoded is None or decoded[1] != CAPACITY or len(decoded[0]) != SIZE
            or hashlib.sha256(decoded[0]).hexdigest() != SOURCE_SHA256):
        raise AssertionError('shogun select source changed')
    return decoded[0]


def render_pixels():
    pixels = [[0] * WIDTH for _ in range(HEIGHT)]
    for text, top in LINES:
        mask, width, height = text_mask(text)
        if height > 12:
            raise AssertionError(f'shogun select glyph too tall: {text}')
        bx0, bx1, by0, by1 = LEFT - 1, LEFT + width + 1, top - 1, top + height + 1
        if bx0 < 0 or bx1 > WIDTH or by0 < 0 or by1 > HEIGHT:
            raise AssertionError(f'shogun select line too large: {text}')
        for y in range(by0, by1):
            for x in range(bx0, bx1):
                if y in (by0, by1 - 1) and x in (bx0, bx1 - 1):
                    continue            # rounded corners like the native band
                pixels[y][x] = BAND
        for x, y in mask:
            pixels[top + y][LEFT + x] = INK
    return pixels


def sheet(original):
    source_guard(original)
    return encode(render_pixels())


@lru_cache(maxsize=2)
def _stream(data):
    return lz77_compress_optimal(data, vram_safe=True)


def expected_regions(original):
    stream = _stream(sheet(original))
    if len(stream) > CAPACITY:
        raise AssertionError(f'shogun select overflow: {len(stream)} > {CAPACITY}')
    return ((SOURCE, stream + bytes(CAPACITY - len(stream))),)


def _fixed(original):
    return ((POINTER, bytes(original[POINTER:POINTER + 4])),)


def patch(rom, original):
    regions = expected_regions(original)
    for address, raw in _fixed(original):
        if bytes(rom[address:address + 4]) != raw:
            raise AssertionError('shogun select pointer changed in ROM')
    for address, new in regions:
        if bytes(rom[address:address + len(new)]) not in (bytes(original[address:address + len(new)]), new):
            raise AssertionError('shogun select already modified by another writer')
    for address, new in regions:
        rom[address:address + len(new)] = new
    decoded = lz77_decompress(rom, SOURCE)
    if decoded is None or decoded[0] != sheet(original):
        raise AssertionError('shogun select round trip failed')
    return len(regions)


def capture(rom, original):
    from part1_mission_titles import verify_vram_stream
    regions = expected_regions(original)
    for address, raw in _fixed(original):
        if bytes(rom[address:address + 4]) != raw:
            raise AssertionError('shogun select final pointer changed')
    decoded = lz77_decompress(rom, SOURCE)
    if decoded is None or len(decoded[0]) != SIZE or decoded[1] > CAPACITY:
        raise AssertionError('shogun select final block invalid')
    verify_vram_stream(bytes(rom[SOURCE:SOURCE + CAPACITY]), SIZE, 'shogun select')
    return tuple((a, bytes(rom[a:a + len(n)])) for a, n in regions) + _fixed(original)


def expected_region_addresses():
    return (SOURCE, POINTER)


def verify(rom, regions):
    if tuple(a for a, _ in regions) != expected_region_addresses():
        raise AssertionError('shogun select snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'shogun select overwritten after editor at {address:06X}')


def generated_matches(rom, original):
    decoded = lz77_decompress(rom, SOURCE)
    return decoded is not None and decoded[0] == sheet(original)
