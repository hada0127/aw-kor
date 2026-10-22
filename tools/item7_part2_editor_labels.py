"""Part 2 map-editor OBJ captions (raw OBJ family 2, table 0x807190).

Native IDs (family 2 base 0x456114, sizes from 0x8071C0):
  142 0x458774 8x2 tiles (two 32x16 cells)       SELECT メニュー -> SELECT 메뉴
  143 0x458974 6x2 tiles (32x16 cell + 16x16 cell) プレイOK! -> 플레이 OK!
  144 0x458AF4 4x1 tiles (32x8)                     タテ      -> 세로
  145 0x458B74 4x1 tiles (32x8)                     ヨコ      -> 가로
Evidence: temp/full_audit_2026-09-15/part2_editor/editor.ss0 OAM22 (x206,y24,
32x8, tile 812 = ID144) and OAM23 (x206,y14, tile 816 = ID145); screenshot
part2_editor/03_start.png shows "ヨコ 8 / タテ 5" (cursor X/Y) at the top
right.  ID143 is loaded at OBJ tile 836 in the same editor states but was not
seen in OAM (display unverified).  The raw bytes are rewritten in place.

ヨコ/タテ: the plate grows from 13..16 px to 17..20 px (still inside the
native 32x8 OBJ; digits sit at x>=+24).  Galmuri7 glyphs need 7 rows, so the
ink uses rows 1..7 of the 8-row plate (native ink rows 1..6).
"""
import hashlib
import struct
from functools import lru_cache
from pathlib import Path

from bdf import load_bdf, glyph_grid

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / 'reference/fonts/Galmuri7.bdf'
SIZE_TABLE, FAMILY_TABLE, FAMILY = 0x8071C0, 0x807178, 2
# (native id, offset, tiles, original sha256, Korean)
LABELS = (
    (143, 0x458974, 12, 'bfa3dbce83493db73f6a7a71e582890e6588f76f59a981dddea515a0578cf323', '플레이 OK!'),
    (144, 0x458AF4, 4, 'bfa262a54274c262cca69f458421204d71187aa366c3af1a90c28637094465b6', '세로'),
    (145, 0x458B74, 4, '3c728daf6e3ebab581a7bb9d70c6faa880f2a0006556aaf1947c4075ccd18f61', '가로'),
)
PLATE, TAB_INK = 1, 14
BUTTON_BG, BUTTON_INK, BUTTON_OUTLINE = 12, 1, 15
SELECT_CAPTION_OFFSET = 0x458774
SELECT_CAPTION_SHA256 = 'f18a60acab9b9c777258a2aa3abf4bf39d05c261676702dea3b9e2fcd72154e4'
SMALL_CAPTIONS = (
    (84, 0x456A14, 3, '73a65905c910bedc22d29f9bf9d9a904fe425137cdf80fc99dc1aa9d50209006', '남음'),
    (169, 0x45A4B4, 4, 'c24259816e31c275a5a959055145258fd9ba60203e987980e85208e60b38d337', '지형'),
)


@lru_cache(maxsize=1)
def _font():
    return load_bdf(str(FONT))[0]


def _ink(text):
    """Galmuri7 ink, top-aligned by the BDF baseline (row 0 = glyph top line)."""
    ink, cursor = set(), 0
    for char in text:
        if char == ' ':
            cursor += 2
            continue
        grid, width, height, xoffset, yoffset = glyph_grid(_font()[ord(char)])
        top = 7 - height - yoffset
        for y in range(height):
            for x in range(width):
                if grid[y][x]:
                    ink.add((cursor + x + xoffset, top + y))
        cursor += width + 1
    return ink, cursor - 1


def _cell(native_id):
    """(x, y) -> byte index/shift inside the ID's tiles (1D OBJ order)."""
    if native_id == 143:  # 32x16 cell (tiles 0..7) + 16x16 cell (tiles 8..11)
        def index(x, y):
            tile = (y // 8) * 4 + x // 8 if x < 32 else 8 + (y // 8) * 2 + (x - 32) // 8
            return tile * 32 + (y % 8) * 4 + (x % 8) // 2
        return index, 48, 16
    def index(x, y):
        return (x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
    return index, 32, 8


def source_guard(original):
    base, _, start = struct.unpack_from('<III', original, FAMILY_TABLE + FAMILY * 12)
    end = struct.unpack_from('<III', original, FAMILY_TABLE + (FAMILY + 1) * 12)[2]
    if (base, start, end) != (0x08456114, 67, 170):
        raise AssertionError('Part 2 OBJ family 2 table changed')
    address = base - 0x08000000
    for native_id in range(start, LABELS[-1][0] + 1):
        w, h = struct.unpack_from('<BB', original, SIZE_TABLE + native_id * 4)
        for row in LABELS:
            if row[0] == native_id and (address, w * h) != (row[1], row[2]):
                raise AssertionError(f'Part 2 editor label {native_id} extent changed')
        address += w * h * 32
    for _, offset, tiles, digest, _ in LABELS:
        if hashlib.sha256(original[offset:offset + tiles * 32]).hexdigest() != digest:
            raise AssertionError(f'Part 2 editor label source changed {offset:06X}')


def render(original, native_id):
    row = next(r for r in LABELS if r[0] == native_id)
    _, offset, tiles, _, text = row
    data = bytearray(original[offset:offset + tiles * 32])
    index, width, height = _cell(native_id)

    def put(x, y, value):
        i = index(x, y)
        shift = 4 * (x % 2)
        data[i] = (data[i] & ~(15 << shift)) | (value << shift)

    ink, text_width = _ink(text)
    if native_id == 143:
        x0, y0, x1, y1 = 4, 3, 43, 12          # native black-outlined text area
        if text_width + 2 > x1 - x0:
            raise AssertionError('Part 2 play-OK caption overflow')
        for y in range(y0, y1):
            for x in range(x0, x1):
                put(x, y, BUTTON_BG)
        left = x0 + (x1 - x0 - text_width) // 2
        points = {(left + x, y0 + 1 + y) for x, y in ink}
        for x, y in points:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if (x + dx, y + dy) not in points:
                        if not (x0 <= x + dx < x1 and y0 <= y + dy < y1):
                            raise AssertionError('Part 2 play-OK outline clipped')
                        put(x + dx, y + dy, BUTTON_OUTLINE)
        for x, y in points:
            put(x, y, BUTTON_INK)
        return bytes(data)
    # Tab plate: white body, right-pointing tip (native shape shifted by 4px).
    right = (16, 17, 18, 19, 19, 18, 17, 16)
    for y in range(8):
        for x in range(32):
            put(x, y, PLATE if x <= right[y] else 0)
    for x, y in ink:
        if not (y + 1 < 8 and 0 < x + 1 < right[y + 1]):
            raise AssertionError('Part 2 editor tab glyph clipped')
        put(x + 1, y + 1, TAB_INK)
    return bytes(data)


def expected_regions(original):
    source_guard(original)
    return [(offset, render(original, native_id)) for native_id, offset, *_ in LABELS]


def patch_select_caption(rom, original):
    """Replace only the Japanese word on editor OBJ ID 142's SELECT plate."""
    source_guard(original)
    off = SELECT_CAPTION_OFFSET
    source = bytes(original[off:off + 16 * 32])
    if hashlib.sha256(source).hexdigest() != SELECT_CAPTION_SHA256:
        raise AssertionError('Part 2 editor SELECT caption source changed')
    ink, text_width = _ink('메뉴')
    if text_width > 25 or any(y > 6 for _, y in ink):
        raise AssertionError('Part 2 editor SELECT caption does not fit')
    data = bytearray(source)

    def put(x, y, value):
        cell = x // 32
        local_x = x % 32
        tile = (y // 8) * 4 + local_x // 8
        index = cell * 256 + tile * 32 + (y % 8) * 4 + (local_x % 8) // 2
        shift = 4 * (local_x % 2)
        data[index] = (data[index] & ~(15 << shift)) | (value << shift)

    # Keep the outer plate and SELECT button; redraw its 26x7 right-hand label.
    for y in range(4, 11):
        for x in range(36, 62):
            put(x, y, 1)
    left = 36 + (26 - text_width) // 2
    for x, y in ink:
        put(left + x, 4 + y, 15)
    result = bytes(data)
    if bytes(rom[off:off + len(result)]) not in (source, result):
        raise AssertionError('Part 2 editor SELECT caption conflicts with an earlier writer')
    rom[off:off + len(result)] = result
    return 1


def patch_small_captions(rom, original):
    """Replace the remaining-count and terrain captions in the editor HUD."""
    source_guard(original)
    for native_id, off, tiles, digest, text in SMALL_CAPTIONS:
        source = bytes(original[off:off + tiles * 32])
        if hashlib.sha256(source).hexdigest() != digest:
            raise AssertionError(f'Part 2 editor caption source changed: {native_id}')
        width = tiles * 8
        pixels = [[0] * width for _ in range(8)]
        ink, text_width = _ink(text)
        if text_width + 2 > width or any(y > 6 for _, y in ink):
            raise AssertionError(f'Part 2 editor caption does not fit: {native_id}')
        left = (width - text_width) // 2
        body = {(left + x, y) for x, y in ink}
        for x, y in body:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    px, py = x + dx, y + dy
                    if 0 <= px < width and 0 <= py < 8:
                        pixels[py][px] = 15
        for x, y in body:
            pixels[y][x] = 1
        result = bytearray(tiles * 32)
        for y in range(8):
            for x in range(width):
                index = (x // 8) * 32 + y * 4 + (x % 8) // 2
                result[index] |= pixels[y][x] << (4 * (x % 2))
        if bytes(rom[off:off + len(result)]) not in (source, bytes(result)):
            raise AssertionError(f'Part 2 editor caption conflicts with an earlier writer: {native_id}')
        rom[off:off + len(result)] = result
    return len(SMALL_CAPTIONS)


def patch(rom, original):
    regions = expected_regions(original)
    for address, new in regions:
        if bytes(rom[address:address + len(new)]) not in (bytes(original[address:address + len(new)]), new):
            raise AssertionError(f'Part 2 editor label {address:06X} conflicts with an earlier writer')
    for address, new in regions:
        rom[address:address + len(new)] = new
    return len(regions)


def generated_matches(rom, original):
    return all(bytes(rom[a:a + len(n)]) == n for a, n in expected_regions(original))


def capture(rom, original):
    source_guard(original)
    return tuple((offset, bytes(rom[offset:offset + tiles * 32])) for _, offset, tiles, *_ in LABELS)


def verify(rom, regions):
    if tuple(a for a, _ in regions) != tuple(r[1] for r in LABELS):
        raise AssertionError('Part 2 editor label snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'Part 2 editor label overwritten at {address:06X}')
