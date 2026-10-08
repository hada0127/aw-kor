"""Part 1 campaign-clear banner: キャンペーンクリア! / ハードキャンペーンクリア!.

Static RE (original ROM, 2026-10-06 fixG):
- LZ77 0xC43400 (6656 B, consumed 1761) is loaded by two routines:
  0x08B6D56C -> VRAM 0x06013D20 (OBJ tile 489) and 0x08B75E92 -> 0x06014200
  (OBJ tile 528).  Sheet tiles 0..31 are the English CAMPAIGN RANK /
  H.CAMPAIGN RANK strips; tiles 32..207 are eleven 32x32 kana cells (1D)
  キ ャ ン ペ ー ク リ ア ! ハ ド, i.e. OBJ tile 560 + 16*cell for the 2nd load.
- 0x08B761D0 copies a composition table into sprite objects, one per entry
  (int16 x, int16 y, u16 OBJ tile, u16 start delay), terminated by x < 0:
  normal 0x08C2A774 (10 entries + terminator, literal 0x08B761FC),
  hard   0x08C2A7CC (13 entries + terminator, literal 0x08B76200; chosen when
  byte 0x02012470+0x21 != 0).  Each object uses frame 0x08EC3598[i]: one
  32x32 affine double-size OBJ (attr0 0x03F0, attr1 0x81F0 | i << 9).
  Original: normal キャンペーン (y48, x24..154 step 26) / クリア! (y84,
  x104..182); hard ハードキャンペーン (y48, x4..196 step 24) / クリア!.

Because the original reuses ン and ー cells, Korean cannot be made by
per-cell substitution alone.  This module redraws the 11 cells as
캠 페 인 클 리 어 ! 하 드 + two blank cells and rewrites both composition
tables (same entry counts, delays and terminators) to read
캠페인 / 클리어!  and  하드 캠페인 / 클리어!.  Unused entries point at a
blank cell.  Terms: 캠페인 / 하드 캠페인 / 클리어 (translation_for_import
0x00A2D894 하드 캠페인, 0x00B845BC 하드 캠페인 모드).
Glyph style follows the native cells: body = OkDanDan-Bold 22px (2026-10-08
font rule; was Galmuri11-Bold 2x; largest size whose line fits 24 rows), interior
index 1 above row 15 and gradient 2..8 below (2 rows per step), light
outline 14 (13 where it touches the body only diagonally), outer ring 1.
Sheet tiles 0..15 / 16..31 are 128x8 1D strips CAMPAIGN RANK / H.CAMPAIGN RANK
(white 1 / black 5 outlined 5px font, same as the 0xBE801C header labels);
they become 캠페인 랭크 / 하드 캠페인 랭크 with part1_obj_header_labels.render
(black box 5, white Galmuri7), left aligned like the English.  Their consumer
(the 0x06013D20 load at 0x08B6D56C) composition was not traced: unverified.
On-screen result is unverified (no savestate of either screen).
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
SOURCE = 0xC43400
SOURCE_POINTERS = (0xB6D61C, 0xB75EF4)
CAPACITY = 1761                  # original consumed; 0xC43AE1..0xC43AE3 padding kept
FOLLOWING = 0xC43AE4
SIZE = 6656
SOURCE_SHA256 = '6df0a58aace11cc9dfbc731568fc5eac20548ccfea740086e9682a72c79ac92e'
CELL_BASE_TILE = 32              # first 32x32 cell inside the sheet
CELLS = 11
OBJ_TILE0 = 560                  # OBJ tile of cell 0 for the 0x06014200 load

NORMAL_TABLE, NORMAL_POOL, NORMAL_ENTRIES = 0xC2A774, 0xB761FC, 10
HARD_TABLE, HARD_POOL, HARD_ENTRIES = 0xC2A7CC, 0xB76200, 13
NORMAL_SHA256 = '21f3aef5170e5d567bc9b94771a267fdbf8816859cf8285b09f14943aa2126fc'
HARD_SHA256 = '1bfd5d0e3654df9396c98f2911a6f2d5e93ffb27875b895d67c48303a83dfc4c'

GLYPHS = '캠페인클리어!하드'   # cells 0..8; cells 9, 10 blank
BLANK = 9
LINE1_Y, LINE2_Y = 48, 84
LINE2 = (('클', 104), ('리', 132), ('어', 160), ('!', 180))
NORMAL_LAYOUT = (('캠', 46, LINE1_Y), ('페', 74, LINE1_Y), ('인', 102, LINE1_Y)) + tuple(
    (c, x, LINE2_Y) for c, x in LINE2)
HARD_LAYOUT = (('하', 22, LINE1_Y), ('드', 50, LINE1_Y), ('캠', 92, LINE1_Y),
               ('페', 120, LINE1_Y), ('인', 148, LINE1_Y)) + tuple((c, x, LINE2_Y) for c, x in LINE2)

OUTER, INTERIOR, OUTLINE, OUTLINE_AA = 1, 1, 14, 13
# Native gradient: rows 15..28 use 2..8 (two rows per index); below stays 8.
GRADIENT_START = 15


def _row_index(y):
    if y < GRADIENT_START:
        return INTERIOR
    return min(8, 2 + (y - GRADIENT_START) // 2)


BODY_ROWS = 24    # the old 12px x 2 Galmuri body box


@lru_cache(maxsize=None)
def glyph_mask(char, chars=GLYPHS):
    """OkDanDan-Bold glyph on the common line of `chars` (2026-10-08 font rule;
    was Galmuri11-Bold 12px scaled 2x): the largest size whose line over the
    drawn characters fits BODY_ROWS. Returns (ink set, width, line height)."""
    size = aw_fonts.okdandan_fit_line(BODY_ROWS, chars)
    return aw_fonts.okdandan_glyph(char, size, chars=chars)


@lru_cache(maxsize=None)
def render_cell(char):
    """32x32 cell pixels (row-major list of lists) in the native banner style."""
    mask, width, height = glyph_mask(char)
    if width > 28 or height > 26:
        raise AssertionError(f'campaign clear glyph too large: {char}')
    left, top = (32 - width) // 2, 4 + (24 - height) // 2
    body = {(x + left, y + top) for x, y in mask}
    near4 = lambda p: [(p[0] + dx, p[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    near8 = lambda p: [(p[0] + dx, p[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
    ring = {q for p in body for q in near8(p)} - body
    outer = {q for p in ring for q in near8(p)} - body - ring
    pixels = [[0] * 32 for _ in range(32)]
    for x, y in outer | ring | body:
        if not (0 <= x < 32 and 0 <= y < 32):
            raise AssertionError(f'campaign clear glyph clipped: {char}')
    for x, y in outer:
        pixels[y][x] = OUTER
    for x, y in ring:
        pixels[y][x] = OUTLINE if any(q in body for q in near4((x, y))) else OUTLINE_AA
    for x, y in body:
        pixels[y][x] = _row_index(y)
    return tuple(tuple(row) for row in pixels)


def _cell_bytes(pixels):
    raw = bytearray(512)
    for y in range(32):
        for x in range(32):
            index = ((y // 8) * 4 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
            raw[index] |= pixels[y][x] << (4 * (x % 2))
    return bytes(raw)


def source_guard(original):
    for pointer in SOURCE_POINTERS:
        if struct.unpack_from('<I', original, pointer)[0] != SOURCE + ROM_BASE:
            raise AssertionError(f'campaign clear sheet pointer changed {pointer:06X}')
    if original.count(struct.pack('<I', SOURCE + ROM_BASE)) != len(SOURCE_POINTERS):
        raise AssertionError('campaign clear sheet has foreign reference')
    decoded = lz77_decompress(original, SOURCE)
    if (decoded is None or decoded[1] != CAPACITY or len(decoded[0]) != SIZE
            or hashlib.sha256(decoded[0]).hexdigest() != SOURCE_SHA256):
        raise AssertionError('campaign clear sheet source changed')
    for table, pool, entries, digest in ((NORMAL_TABLE, NORMAL_POOL, NORMAL_ENTRIES, NORMAL_SHA256),
                                         (HARD_TABLE, HARD_POOL, HARD_ENTRIES, HARD_SHA256)):
        if struct.unpack_from('<I', original, pool)[0] != table + ROM_BASE:
            raise AssertionError(f'campaign clear table literal changed {pool:06X}')
        if original.count(struct.pack('<I', table + ROM_BASE)) != 1:
            raise AssertionError(f'campaign clear table has foreign reference {table:06X}')
        size = (entries + 1) * 8
        if hashlib.sha256(bytes(original[table:table + size])).hexdigest() != digest:
            raise AssertionError(f'campaign clear table changed {table:06X}')
    return decoded[0]


RANK_STRIPS = ((0, '캠페인 랭크', 'CAMPAIGN RANK'), (16, '하드 캠페인 랭크', 'H.CAMPAIGN RANK'))
STRIP_TILES = 16


def sheet(original):
    from part1_obj_header_labels import render as render_header
    native = source_guard(original)
    out = bytearray(native)
    for first_tile, text, _ in RANK_STRIPS:
        start = first_tile * 32
        out[start:start + STRIP_TILES * 32] = render_header(STRIP_TILES, text, 'left')
    for cell in range(CELLS):
        start = (CELL_BASE_TILE + cell * 16) * 32
        if cell < len(GLYPHS):
            out[start:start + 512] = _cell_bytes(render_cell(GLYPHS[cell]))
        else:
            out[start:start + 512] = bytes(512)
    return bytes(out)


def table(original, address, entries, layout):
    """Same entry count/delays/terminator; new x, y and tile per entry."""
    if len(layout) > entries:
        raise AssertionError('campaign clear layout has more glyphs than entries')
    raw = bytearray(original[address:address + (entries + 1) * 8])
    for i in range(entries):
        x, y, _, delay = struct.unpack_from('<hhHH', raw, i * 8)
        if i < len(layout):
            char, x, y = layout[i]
            tile = OBJ_TILE0 + 16 * GLYPHS.index(char)
        else:
            tile = OBJ_TILE0 + 16 * BLANK   # keep the native position, show nothing
        struct.pack_into('<hhHH', raw, i * 8, x, y, tile, delay)
    if struct.unpack_from('<h', raw, entries * 8)[0] >= 0:
        raise AssertionError('campaign clear table terminator missing')
    return bytes(raw)


@lru_cache(maxsize=2)
def _stream(sheet_bytes):
    return lz77_compress_optimal(sheet_bytes, vram_safe=True)


def expected_regions(original):
    stream = _stream(sheet(original))
    if len(stream) > CAPACITY:
        raise AssertionError(f'campaign clear sheet overflow: {len(stream)} > {CAPACITY}')
    return ((SOURCE, stream + bytes(CAPACITY - len(stream))),
            (NORMAL_TABLE, table(original, NORMAL_TABLE, NORMAL_ENTRIES, NORMAL_LAYOUT)),
            (HARD_TABLE, table(original, HARD_TABLE, HARD_ENTRIES, HARD_LAYOUT)))


def _fixed(original):
    return tuple((p, bytes(original[p:p + 4])) for p in SOURCE_POINTERS + (NORMAL_POOL, HARD_POOL)) + (
        (SOURCE + CAPACITY, bytes(original[SOURCE + CAPACITY:FOLLOWING])),)


def patch(rom, original):
    regions = expected_regions(original)
    for address, raw in _fixed(original):
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'campaign clear pointer/padding changed {address:06X}')
    for address, new in regions:
        current = bytes(rom[address:address + len(new)])
        if current not in (bytes(original[address:address + len(new)]), new):
            raise AssertionError(f'campaign clear {address:06X} already modified by another writer')
    for address, new in regions:
        rom[address:address + len(new)] = new
    decoded = lz77_decompress(rom, SOURCE)
    if decoded is None or decoded[0] != sheet(original):
        raise AssertionError('campaign clear sheet round trip failed')
    return len(regions)


def capture(rom, original):
    from part1_mission_titles import verify_vram_stream
    source_guard(original)
    for address, raw in _fixed(original):
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'campaign clear final pointer/padding changed {address:06X}')
    decoded = lz77_decompress(rom, SOURCE)
    if decoded is None or len(decoded[0]) != SIZE or decoded[1] > CAPACITY:
        raise AssertionError('campaign clear final sheet invalid')
    verify_vram_stream(bytes(rom[SOURCE:SOURCE + CAPACITY]), SIZE, 'campaign clear sheet')
    return tuple((address, bytes(rom[address:address + len(new)]))
                 for address, new in expected_regions(original)) + _fixed(original)


def expected_region_addresses():
    return (SOURCE, NORMAL_TABLE, HARD_TABLE) + SOURCE_POINTERS + (NORMAL_POOL, HARD_POOL, SOURCE + CAPACITY)


def verify(rom, regions):
    if tuple(address for address, _ in regions) != expected_region_addresses():
        raise AssertionError('campaign clear snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'campaign clear overwritten after editor at {address:06X}')


def generated_matches(rom, original):
    decoded = lz77_decompress(rom, SOURCE)
    return (decoded is not None and decoded[0] == sheet(original)
            and all(bytes(rom[a:a + len(n)]) == n for a, n in expected_regions(original)[1:]))


NORMAL_PALETTE, HARD_PALETTE = 0xC433A0, 0xC433C0


def rom_palette(rom, address):
    out = []
    for i in range(16):
        c = struct.unpack_from('<H', rom, address + 2 * i)[0]
        out.append(((c & 31) * 8, (c >> 5 & 31) * 8, (c >> 10 & 31) * 8))
    return out


def preview(sheet_bytes, table_bytes, palette=None):
    """Static composition preview (PIL RGB 240x160) from a table + sheet."""
    from PIL import Image
    pal = palette or [(0, 0, 0)] + [(40 + 13 * i, 30 + 11 * i, 20 + 7 * i) for i in range(1, 16)]
    image = Image.new('RGB', (240, 160), (24, 40, 88))
    i = 0
    while True:
        x, y, tile, _ = struct.unpack_from('<hhHH', table_bytes, i * 8)
        if x < 0:
            break
        cell = (tile - OBJ_TILE0) // 16
        base = (CELL_BASE_TILE + cell * 16) * 32
        for py in range(32):
            for px in range(32):
                v = (sheet_bytes[base + ((py // 8) * 4 + px // 8) * 32 + (py % 8) * 4 + (px % 8) // 2]
                     >> (4 * (px % 2))) & 15
                sx, sy = x + px, y + py   # affine double-size box at -16: glyph top-left = (x, y)
                if v and 0 <= sx < 240 and 0 <= sy < 160:
                    image.putpixel((sx, sy), pal[v])
        i += 1
    return image
