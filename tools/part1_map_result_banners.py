"""Part 1 map-result BG banners WIN! / DRAW / LOSE.. -> 승리! / 무승부 / 패배..

Static RE (original ROM, 2026-10-06 fixH):
- Loader 0x08B4C6xx..0x08B4C7E4 (BL 0x08B0FFE4 = LZ77 to VRAM):
    LOSE..  LZ77 0xBFCF48 (literal 0xB4C7C0) -> 0x06000D80 (BG char tile 108)
    DRAW    LZ77 0xBFCBD8 (literal 0xB4C7D0) -> 0x06000180 (tile 12) when two
            surviving armies are on different teams, else
    WIN!    LZ77 0xBFC834 (literal 0xB4C980) -> 0x06000180 (tile 12)
    draw case also loads 0xBFCF3C (one all-index-4 tile) to tile 153.
- Tilemaps (u8 w, u8 h, u16 entries, +0x400C at copy time = palette 4,
  tile + 12) built by 0x08B10DDC into 0x02013544 -> 0x0600F800:
    0xBFD0B8 32x6: WIN/DRAW tiles 0..95 as a 16x6 grid at columns 14..29,
            entry 141 (fill) / 143 (blank row 0) around it;
    0xBFD23C 32x3: LOSE tiles 96..106 / 112..122 / 128..138 (11x3 grid,
            columns 2..12), 142 (fill) / 143 (blank row 0) around it.
  So WIN/DRAW are 128x48 images (16 tiles per row, all 96 tiles used) and
  LOSE is the left 88x24 of a 128x24 sheet whose tiles 13..15 of row 2 are
  the shared fill tiles 141/142/143 (kept byte for byte).
- Palette 4 (savestate output/qa/part1_2026-10-01/measured_resumed_20261001/
  0318_A_1305382.ss0): 13 red band (WIN), 4 green band (DRAW), 14 blue band
  (LOSE), 15 white letters, 10..12 / 1..3 / 7..9 light band shades used as
  anti-aliasing.  Above the band (rows 0..7) the sheet is transparent except
  for the letter tops and a band-coloured ring around them.
  Seen on screen: WIN! + LOSE.. in 274 Part 1 savestates (BG, e.g. the one
  above); DRAW not seen in any savestate (same tilemap/loader, unverified).

Korean (translation_for_import): 승리 (0x00A03F8A あなたの勝利よ -> 네 승리야!),
무승부 (引き分け; standard term, no CSV row), 패배 (standard term).
Glyphs: OkDanDan-Bold (2026-10-08 font rule; was Galmuri11-Bold 12px scaled
pixel-crisp) at the largest size whose line fits the old body height (WIN/DRAW
44 rows, LOSE 22 rows), natural aspect, thresholded,
white 15 on the band, band-coloured ring above the band, no anti-aliasing.
On-screen result unverified (static renders only).
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
INK = 15

# name, source, literal, decoded size, consumed, (unused), text, band index,
# owned (x0, y0, x1, y1), band top row, glyph top row, scale (sx, sy), ring px
BANNERS = (
    ('WIN', 0xBFC834, 0xB4C980, 3072, 929, None, '승리!', 13, (0, 0, 128, 48), 8, 2, (3, 4), 2),
    ('DRAW', 0xBFCBD8, 0xB4C7D0, 3072, 867, None, '무승부', 4, (0, 0, 128, 48), 8, 2, (3, 4), 2),
    ('LOSE', 0xBFCF48, 0xB4C7C0, 1536, 365, None, '패배..', 14, (0, 0, 88, 24), 8, 1, (3, 2), 1),
)
SOURCE_SHA256 = {
    'WIN': '10e63532006db69df1ecffc6115f1790ecb86fef86938805673da0b8b861df21',
    'DRAW': '0fd7daf175765d373a6c03087d0551b15ffef84188f646e346e0e99fda729358',
    'LOSE': '7964c2704e43ece92af2702f0c9cfbc263ce829c0a6a13daa95bb2711d3be4ee',
}
COLS = 16


def _decode(data):
    rows = len(data) // 32 // COLS * 8
    px = [[0] * (COLS * 8) for _ in range(rows)]
    for t in range(len(data) // 32):
        for y in range(8):
            for x in range(8):
                px[(t // COLS) * 8 + y][(t % COLS) * 8 + x] = (data[t * 32 + y * 4 + x // 2] >> (4 * (x % 2))) & 15
    return px


def _encode(px):
    out = bytearray(len(px) * COLS * 4)
    for y, row in enumerate(px):
        for x, v in enumerate(row):
            t = (y // 8) * COLS + x // 8
            out[t * 32 + (y % 8) * 4 + (x % 8) // 2] |= v << (4 * (x % 2))
    return bytes(out)


LINE_CHARS = '승리!무승부패배..'   # every character the three banners draw


@lru_cache(maxsize=None)
def glyph_size(sy):
    """Largest OkDanDan size whose common line fits the old 11*sy-row body."""
    return aw_fonts.okdandan_fit_line(11 * sy, LINE_CHARS)


@lru_cache(maxsize=None)
def glyph_mask(char, sx, sy):
    """OkDanDan-Bold glyph for the old 11*sy-row body (2026-10-08 font rule; was
    Galmuri11-Bold 12px scaled pixel-crisp by (sx, sy)). Natural aspect, largest
    size whose common line fits, so '.' and short syllables keep one baseline.
    Returns (set, w, h)."""
    mask, width, height = aw_fonts.okdandan_glyph(char, glyph_size(sy), chars=LINE_CHARS)
    if height > 11 * sy:
        raise AssertionError(f'banner glyph outside {11 * sy}px body: {char}')
    return mask, width, 11 * sy


def text_mask(text, sx, sy):
    pixels, cursor = set(), 0
    for i, char in enumerate(text):
        mask, width, _ = glyph_mask(char, sx, sy)
        pixels |= {(x + cursor, y) for x, y in mask}
        cursor += width + (sx if i + 1 < len(text) else 0)
    return pixels, cursor


def render(native, banner):
    name, _, _, _, _, _, text, band, owned, band_top, top, (sx, sy), ring = banner
    px = _decode(native)
    x0, y0, x1, y1 = owned
    mask, width = text_mask(text, sx, sy)
    left = x0 + (x1 - x0 - width) // 2
    letters = {(x + left, y + top) for x, y in mask}
    near = set(letters)
    for _ in range(ring):
        near |= {(x + dx, y + dy) for x, y in near for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    for y in range(y0, y1):
        for x in range(x0, x1):
            px[y][x] = band if y >= band_top or (x, y) in near else 0
    for x, y in letters:
        if not (x0 + 1 <= x < x1 - 1 and y0 + 1 <= y < y1 - 1):
            raise AssertionError(f'{name} banner glyph clipped')
        px[y][x] = INK
    return _encode(px)


def source(original, banner):
    name, src, literal, size, consumed, digest = banner[:6]
    if struct.unpack_from('<I', original, literal)[0] != src + ROM_BASE:
        raise AssertionError(f'{name} banner literal changed {literal:06X}')
    if original.count(struct.pack('<I', src + ROM_BASE)) != 1:
        raise AssertionError(f'{name} banner has foreign reference')
    decoded = lz77_decompress(original, src)
    if decoded is None or len(decoded[0]) != size or decoded[1] != consumed:
        raise AssertionError(f'{name} banner source changed')
    if hashlib.sha256(decoded[0]).hexdigest() != SOURCE_SHA256[name]:
        raise AssertionError(f'{name} banner source sha changed')
    return decoded[0]


def sheet(original, banner):
    return render(source(original, banner), banner)


@lru_cache(maxsize=8)
def _stream(data):
    return lz77_compress_optimal(data, vram_safe=True)


def expected_regions(original):
    out = []
    for banner in BANNERS:
        stream = _stream(sheet(original, banner))
        consumed = banner[4]
        if len(stream) > consumed:
            raise AssertionError(f'{banner[0]} banner overflow: {len(stream)} > {consumed}')
        out.append((banner[1], stream + bytes(consumed - len(stream))))
    return tuple(out)


def _fixed(original):
    return tuple((b[2], bytes(original[b[2]:b[2] + 4])) for b in BANNERS)


def patch(rom, original):
    regions = expected_regions(original)
    for address, raw in _fixed(original):
        if bytes(rom[address:address + 4]) != raw:
            raise AssertionError(f'map result banner literal changed {address:06X}')
    for address, new in regions:
        current = bytes(rom[address:address + len(new)])
        if current not in (bytes(original[address:address + len(new)]), new):
            raise AssertionError(f'map result banner {address:06X} modified by another writer')
    for address, new in regions:
        rom[address:address + len(new)] = new
    for banner in BANNERS:
        decoded = lz77_decompress(rom, banner[1])
        if decoded is None or decoded[0] != sheet(original, banner):
            raise AssertionError(f'{banner[0]} banner round trip failed')
    return len(regions)


def capture(rom, original):
    from part1_mission_titles import verify_vram_stream
    for address, raw in _fixed(original):
        if bytes(rom[address:address + 4]) != raw:
            raise AssertionError(f'map result banner final literal changed {address:06X}')
    for banner in BANNERS:
        source(original, banner)
        decoded = lz77_decompress(rom, banner[1])
        if decoded is None or len(decoded[0]) != banner[3] or decoded[1] > banner[4]:
            raise AssertionError(f'{banner[0]} banner final stream invalid')
        verify_vram_stream(bytes(rom[banner[1]:banner[1] + banner[4]]), banner[3], f'{banner[0]} banner')
    return tuple((b[1], bytes(rom[b[1]:b[1] + b[4]])) for b in BANNERS) + _fixed(original)


def expected_region_addresses():
    return tuple(b[1] for b in BANNERS) + tuple(b[2] for b in BANNERS)


def verify(rom, regions):
    if tuple(address for address, _ in regions) != expected_region_addresses():
        raise AssertionError('map result banner snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'map result banner overwritten after editor at {address:06X}')


def generated_matches(rom, original):
    for banner in BANNERS:
        decoded = lz77_decompress(rom, banner[1])
        if decoded is None or decoded[0] != sheet(original, banner):
            return False
    return True


PALETTE4 = ((104, 80, 64), (200, 248, 200), (144, 224, 144), (80, 208, 80), (24, 184, 24), (0, 0, 0),
            (0, 0, 0), (208, 200, 248), (168, 144, 248), (120, 96, 248), (248, 200, 200), (240, 136, 136),
            (240, 80, 80), (224, 0, 0), (80, 40, 248), (248, 248, 248))


def preview(data, banner, scale=3):
    """Owned area of one sheet as a PIL image (palette 4 from the savestate)."""
    from PIL import Image
    px = _decode(data)
    x0, y0, x1, y1 = banner[8]
    image = Image.new('RGB', (x1 - x0, y1 - y0), (60, 60, 60))
    for y in range(y0, y1):
        for x in range(x0, x1):
            if px[y][x]:
                image.putpixel((x - x0, y - y0), PALETTE4[px[y][x]])
    return image.resize((image.width * scale, image.height * scale), Image.NEAREST)
