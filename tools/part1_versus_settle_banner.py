"""Part 1 versus-result title 決着 -> 결판 (two 32x32 OBJ cells).

Evidence (2026-10-06 fixH): savestate
output/qa/part1_2026-10-01/measured_live_tty/8439_A_1217721.ss0 (+ .png): the
versus result screen (1P / 2P rows with captured-building counts) shows
OAM30 x72 y0 and OAM29 x136 y0, 32x32, whose VRAM tiles equal LZ77 0xBFC270
(1024 B = two 32x32 1D cells 決 / 着; literal 0x08B5121C, the only
reference).  The block is byte-identical in candidate5 (still Japanese).

Native style: outline 14 around the body, body indices by row
(9 rows 0..5, 8 rows 6..8, 7 rows 9..11, 6 rows 12..14, 5 rows 15..16,
4 rows 17..19, 3 rows 20..22, 2 rows 23..25, 1 rows 26..31), light
anti-aliasing 10..13 on diagonal edges, transparent elsewhere.
Korean: 결판 (決着 in dialogue: 0x00A06BDC 必ず決着をつけてやる -> 반드시 결판을
내고 말겠어, 0x00A0726D -> 결판을 내주마).  Glyphs: OkDanDan-Bold on the 결판 line (2026-10-08 font rule; was Galmuri11-Bold 2x) (the
campaign-clear banner renderer) thickened 1px horizontally, gradient body + 1px
outline 14, no AA.
On-screen result unverified (static render only).
"""
import hashlib
import struct
from functools import lru_cache
from pathlib import Path

from lz77_scan import lz77_decompress
from lz77_compress import lz77_compress_optimal

ROOT = Path(__file__).resolve().parent.parent
ROM_BASE = 0x08000000
SOURCE = 0xBFC270
LITERAL = 0xB5121C
SIZE = 1024
CAPACITY = 650
SOURCE_SHA256 = 'a5a8fd8aaa4960943ea0e215f6857a23d521fb6baca8f77440dce454809d742a'
TEXT = '결판'
OUTLINE = 14
# (first row, index): body index from this row down to the next entry
GRADIENT = ((0, 9), (6, 8), (9, 7), (12, 6), (15, 5), (17, 4), (20, 3), (23, 2), (26, 1))


def _row_index(y):
    value = GRADIENT[0][1]
    for first, index in GRADIENT:
        if y >= first:
            value = index
    return value


# Live OBJ bank 3 of the 決着 OBJs (R15a CHEAT settle capture, JP and
# candidate frame 26160, OAM 32/33 palette 3): 1..4 orange -> 5 white ->
# 6..9 lilac fill, 10..13 the JP edge AA steps, 14 brown outline.
LIVE_BANK3 = ((230, 115, 82), (255, 131, 41), (255, 164, 98), (255, 197, 148), (255, 222, 205),
              (255, 255, 255), (222, 230, 255), (189, 189, 255), (164, 164, 255), (139, 148, 255),
              (230, 98, 8), (148, 16, 0), (106, 106, 172), (65, 65, 131), (90, 65, 41), (49, 32, 16))
GLYPH_BOX = 28     # JP 決/着 ink fills the cell; ours keeps the outline off the border
                   # (qa_obj_title_cells: per-glyph cells must not touch the cell edge)
AA_MIN = 48        # partial coverage that becomes an AA edge pixel


@lru_cache(maxsize=1)
def _coverages():
    """R15a: Hada Sans Black (JP 決着 is the same heavy squared gothic as 戰績,
    2026-11-05 rule), largest size whose common 결판 line and widths fit
    GLYPH_BOX.  Was OkDanDan through the campaign-clear glyph helper."""
    from part1_record_screen import _hada_title_coverage
    for size in range(48, 8, -1):
        images = _hada_title_coverage(TEXT, size)
        if all(im.width <= GLYPH_BOX and im.height <= GLYPH_BOX for im in images.values()):
            return size, images
    raise AssertionError('settle banner glyphs cannot fit')


@lru_cache(maxsize=None)
def render_cell(char):
    """Gradient body (native row profile), palette-index AA on partially
    covered edge pixels (nearest of fill/10..13/14 in the live bank) and the
    1px outline 14 around both."""
    from sprite_text_aa import palette_blend_index
    image = _coverages()[1][char]
    left, top = (32 - image.width) // 2, (32 - image.height) // 2
    cov = {(x + left, y + top): image.getpixel((x, y))
           for y in range(image.height) for x in range(image.width)}
    body = {p for p, v in cov.items() if v >= 128}
    near4 = lambda p: ((p[0] + 1, p[1]), (p[0] - 1, p[1]), (p[0], p[1] + 1), (p[0], p[1] - 1))
    edge = {p for p, v in cov.items() if AA_MIN <= v < 128 and any(q in body for q in near4(p))}
    ring = {(x + dx, y + dy) for x, y in body | edge for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - body - edge
    pixels = [[0] * 32 for _ in range(32)]
    for x, y in body | edge | ring:
        if not (0 <= x < 32 and 0 <= y < 32):
            raise AssertionError(f'settle banner glyph clipped: {char}')
    for x, y in ring:
        pixels[y][x] = OUTLINE
    for x, y in body:
        pixels[y][x] = _row_index(y)
    for x, y in edge:
        fill = _row_index(y)
        pixels[y][x] = palette_blend_index(OUTLINE, fill, cov[(x, y)], (fill, 10, 11, 12, 13, OUTLINE),
                                           (LIVE_BANK3,))
    return tuple(tuple(row) for row in pixels)


def _cell_bytes(pixels):
    raw = bytearray(512)
    for y in range(32):
        for x in range(32):
            raw[((y // 8) * 4 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2] |= pixels[y][x] << (4 * (x % 2))
    return bytes(raw)


def source_guard(original):
    if struct.unpack_from('<I', original, LITERAL)[0] != SOURCE + ROM_BASE:
        raise AssertionError('settle banner literal changed')
    if original.count(struct.pack('<I', SOURCE + ROM_BASE)) != 1:
        raise AssertionError('settle banner has foreign reference')
    decoded = lz77_decompress(original, SOURCE)
    if (decoded is None or len(decoded[0]) != SIZE or decoded[1] != CAPACITY
            or hashlib.sha256(decoded[0]).hexdigest() != SOURCE_SHA256):
        raise AssertionError('settle banner source changed')
    return decoded[0]


def sheet(original):
    source_guard(original)
    return b''.join(_cell_bytes(render_cell(char)) for char in TEXT)


@lru_cache(maxsize=2)
def _stream(data):
    return lz77_compress_optimal(data, vram_safe=True)


def expected_regions(original):
    stream = _stream(sheet(original))
    if len(stream) > CAPACITY:
        raise AssertionError(f'settle banner overflow: {len(stream)} > {CAPACITY}')
    return ((SOURCE, stream + bytes(CAPACITY - len(stream))),)


def _fixed(original):
    return ((LITERAL, bytes(original[LITERAL:LITERAL + 4])),)


def patch(rom, original):
    regions = expected_regions(original)
    for address, raw in _fixed(original):
        if bytes(rom[address:address + 4]) != raw:
            raise AssertionError('settle banner literal changed in ROM')
    for address, new in regions:
        if bytes(rom[address:address + len(new)]) not in (bytes(original[address:address + len(new)]), new):
            raise AssertionError(f'settle banner {address:06X} modified by another writer')
    for address, new in regions:
        rom[address:address + len(new)] = new
    decoded = lz77_decompress(rom, SOURCE)
    if decoded is None or decoded[0] != sheet(original):
        raise AssertionError('settle banner round trip failed')
    return len(regions)


def capture(rom, original):
    from part1_mission_titles import verify_vram_stream
    source_guard(original)
    for address, raw in _fixed(original):
        if bytes(rom[address:address + 4]) != raw:
            raise AssertionError('settle banner final literal changed')
    decoded = lz77_decompress(rom, SOURCE)
    if decoded is None or len(decoded[0]) != SIZE or decoded[1] > CAPACITY:
        raise AssertionError('settle banner final stream invalid')
    verify_vram_stream(bytes(rom[SOURCE:SOURCE + CAPACITY]), SIZE, 'settle banner')
    return ((SOURCE, bytes(rom[SOURCE:SOURCE + CAPACITY])),) + _fixed(original)


def verify(rom, regions):
    if tuple(address for address, _ in regions) != (SOURCE, LITERAL):
        raise AssertionError('settle banner snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'settle banner overwritten after editor at {address:06X}')


def generated_matches(rom, original):
    decoded = lz77_decompress(rom, SOURCE)
    return decoded is not None and decoded[0] == sheet(original)
