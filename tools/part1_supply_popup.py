"""Translate the unit event bubbles (supply / encounter) without changing frames/icons.

Recorded public VRAM/OAM evidence: 5821_NONE_0914907, OAM16, tile397,
64x32 4bpp 1D, palette3, identity affine matrix31 (left-pointing supply bubble
0xBD0F90).  2026-10-06 (fixG): the enemy-turn supply bubble seen in
output/qa/part1_2026-10-06/m20_cand_ea4c/0019_A_0002371.ss0 is OAM16
x104 y104 64x32 tile429 pal3; its 1024 VRAM bytes equal the right-pointing
copy 0xBD1390 byte for byte (and nothing else in the ROM).

The four raw 1024-byte bubbles are contiguous in Part 1 OBJ data:
  0xBD0790 ソウグウ! (encounter, points left)   -> 조우!
  0xBD0B90 ソウグウ! (encounter, points right)  -> 조우!
  0xBD0F90 ホキュウ! (supply, points left)      -> 보급!
  0xBD1390 ホキュウ! (supply, points right)     -> 보급!
The same 4096 bytes (four bubbles in this order) also exist as one LZ77 block:
Part 2's sheet 0x4704D4 (pointer 0x327A50) and five pointerless archive copies
(0x92BF3C, 0x965BC4, 0x99E468, 0x9D6D0C, 0xEE7720) that sibling patches
(battle-start overlays) also rewrite.  All copies are recompressed in place.

Korean terms: 보급 = existing command/menu term (translation_for_import
0x008052A8 / 0x00805394), 조우 = existing dialogue term for ソウグウ
(0x00A0EEA7, 0x00D9E0E1, ...).  Glyphs: Galmuri7, black ink (5) with a
gray (3) drop shadow on the native white (1) interior, like the first fix.
Patched live pixels remain unverified on screen.
"""
import hashlib
import struct
from functools import lru_cache
from pathlib import Path

from bdf import load_bdf, glyph_grid

ROOT = Path(__file__).resolve().parent.parent
ROM_BASE = 0x08000000
SIZE = 1024
INTERIOR, SHADOW, INK = 1, 3, 5

# (source, Korean, text box (x0, y0, x1, y1) covering the native outlined kana
#  plus their pill ends, original sha256)
BUBBLES = (
    (0xBD0790, '조우!', (19, 12, 53, 20),
     'c2ad6049cafefc9784c956b8a86ff643013f3c5c284ed6b3876bb7809b685877'),
    (0xBD0B90, '조우!', (10, 12, 45, 20),
     '67fafe8df87d5aa49580b64fb074e2074cb65fd2e67581a984b5dca29ffbaba6'),
    (0xBD0F90, '보급!', (22, 12, 53, 20),
     '466d77039a491789a742bcf8e1e349f16cf86ced31bd89ebf9515c362440d755'),
    (0xBD1390, '보급!', (10, 12, 43, 20),
     '1cf7659e6f3eed89b9c9b6baee84a10d39a123a42da594c55a8e21ef6e71923c'),
)
# Back-compatible names for the first (left supply) bubble.
SOURCE = 0xBD0F90
SOURCE_SHA256 = BUBBLES[2][3]
TEXT_BOX = BUBBLES[2][2]

SHEET_SHA256 = '7aadd60fb5097f25afbca3e25a0ce55a88d9282286c20037444cd7aa284eef74'
SHEET_SIZE = 4096
# (LZ77 offset, compressed capacity, pointers)
LZ_COPIES = (
    (0x4704D4, 1063, (0x327A50,)),
    (0x92BF3C, 1063, ()),
    (0x965BC4, 1063, ()),
    (0x99E468, 1063, ()),
    (0x9D6D0C, 1063, ()),
    (0xEE7720, 1063, ()),
)


def pixel(raw, x, y):
    index = ((y // 8) * 8 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
    return (raw[index] >> (4 * (x % 2))) & 15


@lru_cache(maxsize=1)
def _font():
    font, _ = load_bdf(str(ROOT / 'reference/fonts/Galmuri7.bdf'))
    return font


def _ink(text):
    """Top-aligned Galmuri7 ink pixels, 1px gap between glyphs."""
    font = _font()
    ink, cursor = set(), 0
    for char in text:
        grid, width, height, xoffset, _ = glyph_grid(font[ord(char)])
        for y in range(height):
            for x in range(width):
                if grid[y][x]:
                    ink.add((cursor + x + xoffset, y))
        cursor += width + 1
    return ink, cursor - 1


def render_bubble(raw, text, box):
    output = bytearray(raw)
    x0, y0, x1, y1 = box

    def put(x, y, value):
        if not (x0 <= x < x1 and y0 <= y < y1):
            raise ValueError('Popup glyph exceeds native text area')
        index = ((y // 8) * 8 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
        shift = 4 * (x % 2)
        output[index] = (output[index] & ~(15 << shift)) | (value << shift)

    for y in range(y0, y1):
        for x in range(x0, x1):
            put(x, y, INTERIOR)
    ink, width = _ink(text)
    left = x0 + (x1 - x0 - (width + 1)) // 2
    for x, y in ink:
        put(left + x + 1, y0 + y + 1, SHADOW)
    for x, y in ink:
        put(left + x, y0 + y, INK)
    return bytes(output)


def _check_source(original, source, digest):
    raw = bytes(original[source:source + SIZE])
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f'Popup bubble source changed {source:06X}')
    return raw


def bubble(original, source):
    for row_source, text, box, digest in BUBBLES:
        if row_source == source:
            return render_bubble(_check_source(original, source, digest), text, box)
    raise KeyError(f'{source:06X}')


def replacement(original):
    """Left supply bubble 0xBD0F90 (original API)."""
    return bubble(original, SOURCE)


def sheet(original):
    """4096-byte LZ77 sheet = the four localized bubbles in ROM order."""
    return b''.join(bubble(original, row[0]) for row in BUBBLES)


def _lz_guard(original):
    from lz77_scan import lz77_decompress
    native = b''.join(bytes(original[s:s + SIZE]) for s, *_ in BUBBLES)
    for offset, capacity, pointers in LZ_COPIES:
        decoded = lz77_decompress(original, offset)
        if (decoded is None or decoded[1] != capacity or decoded[0] != native
                or hashlib.sha256(decoded[0]).hexdigest() != SHEET_SHA256):
            raise ValueError(f'Popup LZ77 copy changed {offset:06X}')
        if original.count(struct.pack('<I', offset + ROM_BASE)) != len(pointers):
            raise ValueError(f'Popup LZ77 copy has foreign reference {offset:06X}')
        for pointer in pointers:
            if struct.unpack_from('<I', original, pointer)[0] != offset + ROM_BASE:
                raise ValueError(f'Popup LZ77 pointer changed {pointer:06X}')


@lru_cache(maxsize=2)
def _stream(sheet_bytes):
    from lz77_compress import lz77_compress_optimal
    return lz77_compress_optimal(sheet_bytes, vram_safe=True)


def expected_regions(original):
    """[(address, bytes)] for every region this module owns."""
    regions = [(row[0], bubble(original, row[0])) for row in BUBBLES]
    _lz_guard(original)
    stream = _stream(sheet(original))
    for offset, capacity, _ in LZ_COPIES:
        if len(stream) > capacity:
            raise ValueError(f'Popup LZ77 overflow {offset:06X}: {len(stream)} > {capacity}')
        regions.append((offset, stream + bytes(capacity - len(stream))))
    return regions


def patch(rom, original):
    regions = expected_regions(original)
    for address, new in regions:
        current = bytes(rom[address:address + len(new)])
        if current not in (bytes(original[address:address + len(new)]), new):
            raise ValueError(f'Popup bubble {address:06X} conflicts with an earlier writer')
    for offset, _, pointers in LZ_COPIES:
        for pointer in pointers:
            if bytes(rom[pointer:pointer + 4]) != bytes(original[pointer:pointer + 4]):
                raise ValueError(f'Popup LZ77 pointer repointed {pointer:06X}')
    for address, new in regions:
        rom[address:address + len(new)] = new
    from lz77_scan import lz77_decompress
    expected_sheet = sheet(original)
    for offset, _, _ in LZ_COPIES:
        decoded = lz77_decompress(rom, offset)
        if decoded is None or decoded[0] != expected_sheet:
            raise ValueError(f'Popup LZ77 round trip failed {offset:06X}')
    return len(regions)


def verify(rom, original):
    for address, new in expected_regions(original):
        if bytes(rom[address:address + len(new)]) != new:
            raise ValueError(f'Popup bubble {address:06X} overwritten')
