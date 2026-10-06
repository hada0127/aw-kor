"""Movement-type icon captions in the raw OBJ bank 0xBE801C (terrain info COST list).

Evidence (2026-10-06 fixG): savestate
output/qa/part1_2026-10-01/round32_recovery/0404_R_0081944.ss0 (terrain info
of a sea tile, R button) shows OAM 44..46 = 32x16 OBJ (1D) tiles 413/421/429,
palette 14, whose VRAM tiles equal ROM 0xBE8CBC.., 0xBE8DBC.., 0xBE8EBC.. byte
for byte.  The bank stores each movement type as 8 consecutive tiles
(32x16, 1D: tiles 0..3 top half, 4..7 bottom half); seven entries from
0xBE88BC with stride 0x100.  The caption is 5px katakana (white 1 / black 15
outline) in rows 9..15 over the icon bottom.  Each entry exists once in the
ROM (no LZ77 copy).

Korean = the movement-type terms of the unit help text:
  ホヘイ 보병 (0x00A31500 歩兵タイプ -> 보병 타입), バズーカ 바주카 (0x00A061F2 바주카병),
  タイヤ 타이어 (0x00A319B0 타이어 타입), センシャ 전차 (戦車タイプ -> 전차 타입),
  フネ 배 (船タイプ -> 배 타입), ユソウ 수송 (輸送車 -> 수송차), ヒコウ 비행 (0x00DEF04E 비행 타입).
Galmuri7 glyphs (7px) need two more rows than the native 5px kana: the new
caption is a black box (rows 7..15, corners left native) with white text in
rows 8..14, centred; the old caption pixels in rows 10..15 are cleared first.
On-screen result unverified.
"""
import hashlib
from functools import lru_cache
from pathlib import Path

from bdf import load_bdf, glyph_grid

ROOT = Path(__file__).resolve().parent.parent
SIZE = 256
OUTLINE, INK, CLEAR, WATER = 15, 1, 0, 11
# (address, Korean, original kana, original sha256 of the 256-byte entry)
ENTRIES = (
    (0xBE88BC, '보병', 'ホヘイ',
     '88884a369049d1d83ebc8f93545921a7e16107ee95e68544e6c84618387726a8'),
    (0xBE89BC, '바주카', 'バズーカ',
     'c295f239dc4280143b4bb94fd4c8e7be1f57992cd249a7e39d171b52cc32118f'),
    (0xBE8ABC, '타이어', 'タイヤ',
     'efd34e966a532a0a2e763a2df31d3555b494c0fae6ccdbba122782b764625f0e'),
    (0xBE8BBC, '전차', 'センシャ',
     'd2f8fe8c3f9f6254b3b487c63b2ea03232555c368a54b308fb6761662f46b073'),
    (0xBE8CBC, '배', 'フネ',
     '21d47d8b2f4037d0a1ea6d7385bfafc6c2cee61ef9712131495fa80043f32c8d'),
    (0xBE8DBC, '수송', 'ユソウ',
     'a646327299942376f6b2ed789f68d03c7d05e69e242fbf93bd2870877ce3d9a1'),
    (0xBE8EBC, '비행', 'ヒコウ',
     '2e6eb80a855fb625c44b5825302176c05e0b28f5c5fac402d40b233a8a39c8a3'),
)


def _decode(raw):
    return [[(raw[((y // 8) * 4 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2] >> (4 * (x % 2))) & 15
             for x in range(32)] for y in range(16)]


def _encode(pixels):
    raw = bytearray(SIZE)
    for y in range(16):
        for x in range(32):
            raw[((y // 8) * 4 + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2] |= pixels[y][x] << (4 * (x % 2))
    return bytes(raw)


@lru_cache(maxsize=1)
def _font():
    font, _ = load_bdf(str(ROOT / 'reference/fonts/Galmuri7.bdf'))
    return font


def render(raw, text):
    pixels = _decode(raw)
    if not any(pixels[15][x] == OUTLINE for x in range(32)):
        raise AssertionError('move-type caption outline missing')
    # Old caption = white/gray/black pixels in rows 10..15; clear their full span.
    span = [x for y in range(10, 16) for x in range(32) if pixels[y][x] in (1, 3, OUTLINE)]
    for y in range(10, 16):
        for x in range(min(span), max(span) + 1):
            if pixels[y][x] != WATER:  # keep the ship icons' water ripples
                pixels[y][x] = CLEAR
    font = _font()
    glyphs = [glyph_grid(font[ord(ch)]) for ch in text]
    width = sum(g[1] for g in glyphs) + len(glyphs) - 1
    box0 = (32 - (width + 2)) // 2
    box1 = box0 + width + 2
    if box0 < 0 or box1 > 32:
        raise AssertionError(f'move-type caption too wide: {text}')
    for y in range(7, 16):
        for x in range(box0, box1):
            if (y in (7, 15)) and x in (box0, box1 - 1):
                continue  # rounded corners
            pixels[y][x] = OUTLINE
    cursor = box0 + 1
    for grid, w, h, xo, yo in glyphs:
        top = 8 + 7 - h - yo
        for gy in range(h):
            for gx in range(w):
                if grid[gy][gx]:
                    x, y = cursor + gx + xo, top + gy
                    if not (box0 < x < box1 - 1 and 8 <= y <= 14):
                        raise AssertionError(f'move-type glyph clipped: {text}')
                    pixels[y][x] = INK
        cursor += w + 1
    return _encode(pixels)


def _source(original, address, digest):
    raw = bytes(original[address:address + SIZE])
    if hashlib.sha256(raw).hexdigest() != digest:
        raise AssertionError(f'move-type caption source changed {address:06X}')
    if original.count(raw) != 1:
        raise AssertionError(f'move-type caption entry not unique {address:06X}')
    return raw


def expected_regions(original):
    return tuple((address, render(_source(original, address, digest), text))
                 for address, text, _, digest in ENTRIES)


def patch(rom, original):
    regions = expected_regions(original)
    for address, new in regions:
        current = bytes(rom[address:address + SIZE])
        if current not in (bytes(original[address:address + SIZE]), new):
            raise AssertionError(f'move-type caption {address:06X} modified by another writer')
    for address, new in regions:
        rom[address:address + SIZE] = new
    return len(regions)


def capture(rom, original):
    expected_regions(original)  # source guards
    return tuple((address, bytes(rom[address:address + SIZE])) for address, *_ in ENTRIES)


def verify(rom, regions):
    if tuple(address for address, _ in regions) != tuple(row[0] for row in ENTRIES):
        raise AssertionError('move-type caption snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'move-type caption overwritten after editor at {address:06X}')


def generated_matches(rom, original):
    return all(bytes(rom[a:a + SIZE]) == new for a, new in expected_regions(original))
