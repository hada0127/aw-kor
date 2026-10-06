"""Part 1 player rank card: the white 'RANK' tag -> 랭크.

Evidence (2026-10-06 fixH): LZ77 0xBEF0D8 (3072 B; literal 0xDFA5DC, the only
reference) holds the rank card as a 64x64 OBJ (tiles 0..63, 1D) + 32x64 OBJ
(tiles 64..95).  Savestate
output/qa/part1_2026-10-01/measured_live_tty/2070_A_0499059.ss0 (+ .png, the
map-result screen with the WIN!/LOSE.. banners) shows OAM39 64x64 x140 y56 and
OAM40 32x64 x204 y56, palette 13 (1 white, 15 near-black, 14 grey), tiles equal
to this block; seen in 24 Part 1 savestates.  The tag is a black box
(index 15) x5..29, rows 25..31 with white 5px letters RANK; byte-identical in
candidate5.  The 'RS' emblem above it is the army mark and is kept.

Korean 랭크 (part1_result_rank_word.py 랭크 strip; ランク -> 랭크 in dialogue
0x00DFAA43).  Style = part1_obj_header_labels: black box rows 25..31, white
Galmuri7 rows 25..31, centred in the native box width.
On-screen result unverified (static render only).
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
SOURCE = 0xBEF0D8
LITERAL = 0xDFA5DC
SIZE = 3072
CAPACITY = 887
SOURCE_SHA256 = 'c993b51004367c22a4a0cdfff13eaf96d04bcceed8a70ebe0a01d44228421f67'
TEXT = '랭크'
BOX, INK = 15, 1
BOX_X0, BOX_X1, BOX_Y0, BOX_Y1 = 5, 30, 25, 32     # half-open
SPRITE_W = 64


def _get(data, x, y):
    t = (y // 8) * (SPRITE_W // 8) + x // 8
    return (data[t * 32 + (y % 8) * 4 + (x % 8) // 2] >> (4 * (x % 2))) & 15


def _set(data, x, y, v):
    t = (y // 8) * (SPRITE_W // 8) + x // 8
    i = t * 32 + (y % 8) * 4 + (x % 8) // 2
    shift = 4 * (x % 2)
    data[i] = (data[i] & ~(15 << shift) & 0xFF) | (v << shift)


@lru_cache(maxsize=1)
def _font():
    font, _ = load_bdf(str(ROOT / 'reference/fonts/Galmuri7.bdf'))
    return font


def source_guard(original):
    if struct.unpack_from('<I', original, LITERAL)[0] != SOURCE + ROM_BASE:
        raise AssertionError('rank card literal changed')
    if original.count(struct.pack('<I', SOURCE + ROM_BASE)) != 1:
        raise AssertionError('rank card has foreign reference')
    decoded = lz77_decompress(original, SOURCE)
    if (decoded is None or len(decoded[0]) != SIZE or decoded[1] != CAPACITY
            or hashlib.sha256(decoded[0]).hexdigest() != SOURCE_SHA256):
        raise AssertionError('rank card source changed')
    return decoded[0]


def sheet(original):
    data = bytearray(source_guard(original))
    edges = [_get(data, x, y) for x in range(BOX_X0, BOX_X1) for y in (BOX_Y0, BOX_Y1 - 1)]
    if edges.count(BOX) < len(edges) - 2 or _get(data, BOX_X0 - 1, BOX_Y0 + 3) == BOX:
        raise AssertionError('rank card tag box not where expected')
    for y in range(BOX_Y0, BOX_Y1):
        for x in range(BOX_X0, BOX_X1):
            _set(data, x, y, BOX)
    font, glyphs = _font(), []
    for char in TEXT:
        glyphs.append(glyph_grid(font[ord(char)]))
    width = sum(g[1] for g in glyphs) + len(glyphs) - 1
    cursor = BOX_X0 + (BOX_X1 - BOX_X0 - width) // 2
    for grid, w, h, xo, yo in glyphs:
        top = BOX_Y0 + 7 - h - yo
        for gy in range(h):
            for gx in range(w):
                if grid[gy][gx]:
                    x, y = cursor + gx + xo, top + gy
                    if not (BOX_X0 <= x < BOX_X1 and BOX_Y0 <= y < BOX_Y1):
                        raise AssertionError('rank card glyph clipped')
                    _set(data, x, y, INK)
        cursor += w + 1
    return bytes(data)


@lru_cache(maxsize=2)
def _stream(data):
    return lz77_compress_optimal(data, vram_safe=True)


def expected_regions(original):
    stream = _stream(sheet(original))
    if len(stream) > CAPACITY:
        raise AssertionError(f'rank card overflow: {len(stream)} > {CAPACITY}')
    return ((SOURCE, stream + bytes(CAPACITY - len(stream))),)


def _fixed(original):
    return ((LITERAL, bytes(original[LITERAL:LITERAL + 4])),)


def patch(rom, original):
    regions = expected_regions(original)
    for address, raw in _fixed(original):
        if bytes(rom[address:address + 4]) != raw:
            raise AssertionError('rank card literal changed in ROM')
    for address, new in regions:
        if bytes(rom[address:address + len(new)]) not in (bytes(original[address:address + len(new)]), new):
            raise AssertionError(f'rank card {address:06X} modified by another writer')
    for address, new in regions:
        rom[address:address + len(new)] = new
    decoded = lz77_decompress(rom, SOURCE)
    if decoded is None or decoded[0] != sheet(original):
        raise AssertionError('rank card round trip failed')
    return len(regions)


def capture(rom, original):
    from part1_mission_titles import verify_vram_stream
    source_guard(original)
    for address, raw in _fixed(original):
        if bytes(rom[address:address + 4]) != raw:
            raise AssertionError('rank card final literal changed')
    decoded = lz77_decompress(rom, SOURCE)
    if decoded is None or len(decoded[0]) != SIZE or decoded[1] > CAPACITY:
        raise AssertionError('rank card final stream invalid')
    verify_vram_stream(bytes(rom[SOURCE:SOURCE + CAPACITY]), SIZE, 'rank card')
    return ((SOURCE, bytes(rom[SOURCE:SOURCE + CAPACITY])),) + _fixed(original)


def verify(rom, regions):
    if tuple(address for address, _ in regions) != (SOURCE, LITERAL):
        raise AssertionError('rank card snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'rank card overwritten after editor at {address:06X}')


def generated_matches(rom, original):
    decoded = lz77_decompress(rom, SOURCE)
    return decoded is not None and decoded[0] == sheet(original)


PALETTE13 = ((136, 128, 72), (248, 248, 248), (248, 248, 232), (240, 240, 216), (240, 240, 200),
             (240, 232, 176), (232, 232, 160), (232, 224, 144), (120, 120, 120), (152, 112, 176),
             (248, 176, 120), (248, 112, 72), (64, 56, 168), (184, 80, 64), (136, 128, 136), (48, 32, 24))


def preview(data, scale=4):
    """The 64x64 + 32x64 card side by side (PIL RGB)."""
    from PIL import Image
    image = Image.new('RGB', (96, 64), (40, 40, 40))
    for y in range(64):
        for x in range(96):
            if x < 64:
                v = _get(data, x, y)
            else:
                t = 64 + (y // 8) * 4 + (x - 64) // 8
                v = (data[t * 32 + (y % 8) * 4 + ((x - 64) % 8) // 2] >> (4 * (x % 2))) & 15
            if v:
                image.putpixel((x, y), PALETTE13[v])
    return image.resize((96 * scale, 64 * scale), Image.NEAREST)
