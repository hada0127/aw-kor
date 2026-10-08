"""Part 2 newspaper headline "WAR IS OVER!" (BG) -> 전쟁은 / 끝났다!.

Static RE (original ROM, 2026-10-06 fixH):
- Loader 0x0836BD56..0x0836BE00 decompresses 0x5B5D10 (shared newspaper
  paper/masthead sheet) to 0x06008000, this sheet LZ77 0x508EC0 (7008 B =
  219 tiles, consumed 3722, single literal 0x36BEA0) to 0x0600CC00 (= tile 608
  of char base 0x8000) and the 32x32 tilemap LZ77 0x509D6C (single literal
  0x36BEA8) into two map buffers; palettes 0x5B771C (bank 0), 0x509D4C
  (bank 4), 0x48F228 (bank 3).
- Tilemap: photo = map cols 1-11 rows 4-15 (palette 4); headline = cols 15-26
  rows 4-13, palette 0: WAR rows 4-6 cols 16-25, IS rows 7-10 cols 19-22,
  OVER! rows 11-13 cols 15-26; every other headline-area cell is the shared
  paper tile 232 (from 0x5B5D10).  The 82 headline tiles (608 + n) are each
  referenced exactly once, unflipped.  Ink = index 14 with 7/9/11 AA, paper =
  the 8x8 pattern of tile 232 (indices 3/5/6).

Korean headline, two lines: 전쟁은 on the WAR band (rows 4-6) and 끝났다! on
the OVER! band (rows 11-13); the IS cells (rows 7-10) become plain paper
("the war is over"; candidate7 review6 #1: 은 alone on a line read badly).
A two-line layout cannot use one band taller than the native 24 px lines, so
the glyph size is unchanged.  No translation row exists for this English-only
graphic; 끝났- follows the ending/clear dialogue usage (e.g. 0x00A17950
なんとか終わったぜ -> 어떻게든 끝났어).  Glyphs: OkDanDan-Bold, largest size whose line fits 24 px (2026-10-08
font rule; was Galmuri11-Bold 12 px scaled 2x), ink 14 on the original tile-232 paper pattern,
centred on each line's cells.  Only the 82 exclusive headline tiles are
rewritten; the tilemap, the photo tiles and 0x5B5D10 stay untouched.
On-screen result unverified (no savestate of this screen; consumer screen
identity — Part 2 ending/war-over newspaper — inferred from the art).
"""
import hashlib
import struct
from functools import lru_cache
from pathlib import Path

import aw_fonts
from lz77_scan import lz77_decompress
from lz77_compress import lz77_compress_optimal

ROOT = Path(__file__).resolve().parent.parent
ROM_BASE = 0x08000000
SOURCE, SOURCE_POINTER = 0x508EC0, 0x36BEA0
CAPACITY, FOLLOWING = 3722, 0x509D4C        # 0x509D4A..0x509D4B padding kept
SIZE = 7008
SOURCE_SHA256 = '939658d9f905c77adaf6782da17d0c6bdfada07ac736ff2881019618ab92c585'
TILEMAP, TILEMAP_POINTER = 0x509D6C, 0x36BEA8
TILEMAP_SHA256 = 'ba92978d6cf37d5b75b68cd69b3bde0a3184c7534daee42830a77c1ff92e6930'
PAPER_SHEET, PAPER_TILE = 0x5B5D10, 232
PAPER_TILE_SHA256 = 'e9dcb999ba14014f89cc7bb947631509913ccf28b0e4076575973a58970eb2b4'
TILE0 = 608                                  # VRAM tile of decoded tile 0
RECT_COL, RECT_ROW, RECT_W, RECT_H = 15, 4, 12, 10
INK = 14
# (text, rect y of the line top, line height, first col, last col exclusive) in map cells
LINES = (('전쟁은', 0, 24, 16, 26), ('끝났다!', 56, 24, 15, 27))
GAP = 2


def _u32(rom, address):
    return struct.unpack_from('<I', rom, address)[0]


def _entries(original):
    data = lz77_decompress(original, TILEMAP)
    if data is None or hashlib.sha256(data[0]).hexdigest() != TILEMAP_SHA256:
        raise AssertionError('war-over tilemap changed')
    return [struct.unpack_from('<H', data[0], 2 * i)[0] for i in range(1024)]


def paper_pattern(original):
    data = lz77_decompress(original, PAPER_SHEET)
    if data is None:
        raise AssertionError('newspaper paper sheet invalid')
    tile = data[0][PAPER_TILE * 32:PAPER_TILE * 32 + 32]
    if hashlib.sha256(tile).hexdigest() != PAPER_TILE_SHA256:
        raise AssertionError('newspaper paper tile changed')
    return tile


def source_guard(original):
    for pointer, target in ((SOURCE_POINTER, SOURCE), (TILEMAP_POINTER, TILEMAP)):
        if _u32(original, pointer) != target + ROM_BASE:
            raise AssertionError(f'war-over pointer changed {pointer:06X}')
        if original.count(struct.pack('<I', target + ROM_BASE)) != 1:
            raise AssertionError(f'war-over block has foreign reference {target:06X}')
    decoded = lz77_decompress(original, SOURCE)
    if (decoded is None or decoded[1] != CAPACITY or len(decoded[0]) != SIZE
            or hashlib.sha256(decoded[0]).hexdigest() != SOURCE_SHA256):
        raise AssertionError('war-over sheet source changed')
    return decoded[0], _entries(original)


def headline_cells(entries):
    """{(cx, cy): decoded tile} for the exclusive headline cells (rect coords)."""
    use = {}
    for entry in entries:
        use[entry & 0x3FF] = use.get(entry & 0x3FF, 0) + 1
    cells = {}
    for cy in range(RECT_H):
        for cx in range(RECT_W):
            entry = entries[(RECT_ROW + cy) * 32 + RECT_COL + cx]
            tile = entry & 0x3FF
            if tile == PAPER_TILE:
                continue
            if tile < TILE0 or entry & 0xFC00 or use[tile] != 1:
                raise AssertionError(f'war-over headline cell not exclusive: {entry:#06x}')
            cells[(cx, cy)] = tile - TILE0
    return cells


LINE_CHARS = '전쟁은끝났다!'
BODY_ROWS = 24   # the native 24 px line (old Galmuri 12px x 2 body)


@lru_cache(maxsize=None)
def glyph_mask(char):
    """OkDanDan-Bold glyph on the common line (2026-10-08 font rule; was
    Galmuri11-Bold 12px scaled 2x). Returns (set, width, line height)."""
    return aw_fonts.okdandan_glyph(char, aw_fonts.okdandan_fit_line(BODY_ROWS, LINE_CHARS),
                                   chars=LINE_CHARS)


def ink_points():
    points = set()
    for text, top, height, col0, col1 in LINES:
        glyphs = [glyph_mask(c) for c in text]
        total = sum(w for _, w, _ in glyphs) + GAP * (len(glyphs) - 1)
        tall = max(h for _, _, h in glyphs)
        left = (col0 - RECT_COL) * 8 + ((col1 - col0) * 8 - total) // 2
        y0 = top + (height - tall) // 2
        for mask, w, h in glyphs:
            points |= {(x + left, y + y0 + (tall - h)) for x, y in mask}
            left += w + GAP
    return points


def sheet(original):
    native, entries = source_guard(original)
    paper = paper_pattern(original)
    cells = headline_cells(entries)
    ink = ink_points()
    for x, y in ink:
        if (x // 8, y // 8) not in cells:
            raise AssertionError('war-over headline glyph outside its exclusive cells')
    out = bytearray(native)
    for (cx, cy), tile in cells.items():
        raw = bytearray(paper)
        for y in range(8):
            for x in range(8):
                if (cx * 8 + x, cy * 8 + y) in ink:
                    i = y * 4 + x // 2
                    raw[i] = (raw[i] & ~(15 << (4 * (x % 2)))) | (INK << (4 * (x % 2)))
        out[tile * 32:tile * 32 + 32] = raw
    return bytes(out)


@lru_cache(maxsize=2)
def _stream(sheet_bytes):
    return lz77_compress_optimal(sheet_bytes, vram_safe=True)


def expected_regions(original):
    stream = _stream(sheet(original))
    if len(stream) > CAPACITY:
        raise AssertionError(f'war-over sheet overflow: {len(stream)} > {CAPACITY}')
    return ((SOURCE, stream + bytes(CAPACITY - len(stream))),)


def _fixed(original):
    return ((SOURCE_POINTER, bytes(original[SOURCE_POINTER:SOURCE_POINTER + 4])),
            (TILEMAP_POINTER, bytes(original[TILEMAP_POINTER:TILEMAP_POINTER + 4])),
            (SOURCE + CAPACITY, bytes(original[SOURCE + CAPACITY:FOLLOWING])))


def patch(rom, original):
    regions = expected_regions(original)
    for address, raw in _fixed(original):
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'war-over pointer/padding changed {address:06X}')
    if lz77_decompress(rom, TILEMAP) != lz77_decompress(original, TILEMAP):
        raise AssertionError('war-over tilemap modified by another writer')
    for address, new in regions:
        current = bytes(rom[address:address + len(new)])
        if current not in (bytes(original[address:address + len(new)]), new):
            raise AssertionError(f'war-over {address:06X} already modified by another writer')
    for address, new in regions:
        rom[address:address + len(new)] = new
    decoded = lz77_decompress(rom, SOURCE)
    if decoded is None or decoded[0] != sheet(original):
        raise AssertionError('war-over sheet round trip failed')
    return len(regions)


def capture(rom, original):
    from part1_mission_titles import verify_vram_stream
    source_guard(original)
    for address, raw in _fixed(original):
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'war-over final pointer/padding changed {address:06X}')
    decoded = lz77_decompress(rom, SOURCE)
    if decoded is None or len(decoded[0]) != SIZE or decoded[1] > CAPACITY:
        raise AssertionError('war-over final sheet invalid')
    verify_vram_stream(bytes(rom[SOURCE:SOURCE + CAPACITY]), SIZE, 'war-over sheet')
    return ((SOURCE, bytes(rom[SOURCE:SOURCE + CAPACITY])),) + _fixed(original)


def expected_region_addresses():
    return (SOURCE, SOURCE_POINTER, TILEMAP_POINTER, SOURCE + CAPACITY)


def verify(rom, regions):
    if tuple(address for address, _ in regions) != expected_region_addresses():
        raise AssertionError('war-over snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'war-over overwritten after editor at {address:06X}')


def generated_matches(rom, original):
    decoded = lz77_decompress(rom, SOURCE)
    return decoded is not None and decoded[0] == sheet(original)


PALETTE_BANK0 = 0x5B771C


def preview(rom, original=None, rows=16):
    """Static BG composition (PIL RGB 256 x rows*8) of this newspaper from `rom`.

    Uses rom's 0x5B5D10 paper sheet (so candidate builds show their shared-sheet
    state) and the tilemap of `original` (or rom)."""
    from PIL import Image
    vram = bytearray(0x8000)
    paper = lz77_decompress(rom, PAPER_SHEET)[0]
    vram[:len(paper)] = paper
    head = lz77_decompress(rom, SOURCE)[0]
    vram[TILE0 * 32:TILE0 * 32 + len(head)] = head
    entries = _entries(original or rom)
    pal = []
    for i in range(16):
        c = struct.unpack_from('<H', rom, PALETTE_BANK0 + 2 * i)[0]
        pal.append(((c & 31) * 8, (c >> 5 & 31) * 8, (c >> 10 & 31) * 8))
    photo = [(16 * k, 16 * k, 0) for k in range(16)]  # bank 4 stand-in (photo)
    image = Image.new('RGB', (256, rows * 8))
    for cell in range(32 * rows):
        entry = entries[cell]
        tile, hflip, vflip, bank = entry & 0x3FF, entry & 0x400, entry & 0x800, entry >> 12
        p = pal if bank == 0 else photo
        for y in range(8):
            for x in range(8):
                sx, sy = (7 - x if hflip else x), (7 - y if vflip else y)
                v = (vram[tile * 32 + sy * 4 + sx // 2] >> (4 * (sx % 2))) & 15
                image.putpixel(((cell % 32) * 8 + x, (cell // 32) * 8 + y), p[v])
    return image
