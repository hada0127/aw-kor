"""English / kana chips in the Part 1 OBJ atlas (table 0xD8D504, bank 0xBE743C).

Loader 0x08B304A8(vram_tile, entry) copies entry.width*entry.height tiles
(1D, row-major) from 0xBE743C + entry.tile*32 to OBJ VRAM.  Static callers
(BL 0x08B304A8 with an immediate entry number, 2026-10-06 fixH scan):
  48 In / 49 G / 50 Day   0x08B418E4..0x08B41900 (BATTLE INFO window)
  50 Day / 51 Point       0x08B44D3A..0x08B44D58
  49 G                    0x08B47310 / 0x08B4731E (map HUD funds)
  98..101 1P..4P, 104 CP, 103 Play   0x08B6FDAA..0x08B6FE0A, 0x08B77D4C..0x08B77DAC
  98..101                 0x08B51B7C..0x08B51BB2 (versus result 決着 screen)
  102 Com, 88 ポイント     no immediate caller found (index may be computed)
Observed on screen: In / G / Day chips in
output/qa/part1_2026-10-01/round32_recovery/0252_A_0059704.ss0 (BATTLE INFO:
OAM23 x138 y40 In, OAM21 x176 y24 Day, palette 6 = 1 white, 3 grey,
5 black, 6 yellow) and G in 211 savestates (OAM x162 y8, HUD funds).
Point, ポイント, Com, Play, CP were not seen in any savestate (unverified).

Korean (style: yellow chip, black frame, black Galmuri7 text; 16px chips have
no room for side frames, so only top/bottom frame lines are drawn):
  In 수입 (収入 -> 수입: 0x00A04D13, 0x00A0AB50)
  G  자금 (Part 2 battle HUD funds G -> 자금: build patch_part2_battle_funds_hud_label)
  Day 일차 (day counter label; '3일째' style needs the number first, so the label form 일차 is used)
  Point 포인트 (0x00A06CB5 ポイントとランクが -> 포인트와 랭크가)
  ポイント 포인트 (white Galmuri7 + black shadow, same as the 랭크 strip
  part1_result_rank_word.py next to it)
  Com 컴, Play 사람 (icon text strip, white on black), CP 컴 (badge in the
  1P..4P style: white body, black outline; 1P..4P stay as player-number
  badges).
On-screen result unverified (static renders only).
"""
import hashlib
from functools import lru_cache
from pathlib import Path

from bdf import load_bdf, glyph_grid

ROOT = Path(__file__).resolve().parent.parent
WHITE, GREY, BLACK, YELLOW = 1, 3, 5, 6

# (entry, address, width tiles, height tiles, original sha256, Korean, kind, original text)
ENTRIES = (
    (48, 0xBE8FBC, 2, 2, '2817f03f7acca5287c5380471f87754921494be4ee098253cdb3ebc1ccde0fe4', '수입', 'chip', 'In'),
    (49, 0xBE903C, 2, 2, '80bd328b486dba85ee2d002c7cdbc4d7a17501c35ee57dd0ba515db3c4ada5de', '자금', 'chip', 'G'),
    (50, 0xBE90BC, 4, 2, '859419075098014d8c886a6e87be620adde2fc230e3b4bed86224a3e88e5c262', '일차', 'chip', 'Day'),
    (51, 0xBE91BC, 4, 2, '15e7f3b43a9bc3287a4fc04a63ce91b9ab281175f7ae50e85f1951c31424873d', '포인트', 'chip', 'Point'),
    (88, 0xBEB17C, 4, 1, '58778d5cd451cbc498ebb078996d118e9c56c53c33250ef085405ce25b21c566', '포인트', 'strip', 'ポイント'),
    (102, 0xBEB9BC, 2, 2, '1aefd1f6f667265682ce969486dd94e4f741d672f54c385f828d2ffb28919de8', '컴', 'icon', 'Com'),
    (103, 0xBEBA3C, 2, 2, 'ba06e49c5b2b0456df9d306154ea4159bf4b0929e1a5b85a3461cdee0c5f4f58', '사람', 'icon', 'Play'),
    (104, 0xBEBABC, 2, 2, '525e6af42086d6afd2da523d6285960a5bc0614ee075f24e2721a60ed7fe29c7', '컴', 'badge', 'CP'),
)
TABLE = 0xD8D504
GEOMETRY = {48: 'dc00020204000000', 49: 'e000020204000000', 50: 'e400040204000000',
            51: 'ec00040204000000', 88: 'ea01040103000000', 102: '2c02020204000000',
            103: '3002020204000000', 104: '3402020204000000'}


@lru_cache(maxsize=1)
def _font7():
    font, _ = load_bdf(str(ROOT / 'reference/fonts/Galmuri7.bdf'))
    return font


def _ink7(text, gap=1):
    font, ink, cursor = _font7(), [], 0
    for i, char in enumerate(text):
        grid, w, h, xo, yo = glyph_grid(font[ord(char)])
        top = 7 - h - yo
        ink += [(cursor + gx + xo, top + gy) for gy in range(h) for gx in range(w) if grid[gy][gx]]
        cursor += w + (gap if i + 1 < len(text) else 0)
    return ink, cursor


def _decode(raw, w, h):
    return [[(raw[((y // 8) * w + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2] >> (4 * (x % 2))) & 15
             for x in range(w * 8)] for y in range(h * 8)]


def _encode(px, w, h):
    raw = bytearray(w * h * 32)
    for y in range(h * 8):
        for x in range(w * 8):
            raw[((y // 8) * w + x // 8) * 32 + (y % 8) * 4 + (x % 8) // 2] |= px[y][x] << (4 * (x % 2))
    return bytes(raw)


def _chip(width, text):
    """Yellow rounded chip rows 2..13, black frame, grey drop shadow, black text rows 4..10."""
    px = [[0] * width for _ in range(16)]
    narrow = width == 16
    ink, text_w = _ink7(text)
    if narrow and text_w > width - 2:
        ink, text_w = _ink7(text, gap=0)   # 16px chip: 2 syllables need 14px
    if narrow and text_w > width - 2:
        raise AssertionError(f'chip label too wide: {text}')
    x0, x1 = (0, width - 1) if narrow else ((width - text_w - 6) // 2, (width - text_w - 6) // 2 + text_w + 5)
    if not narrow and (x0 < 0 or x1 > width - 2):
        raise AssertionError(f'chip label too wide: {text}')
    for y in range(2, 14):
        inset = 2 if y in (2, 13) else 1 if y in (3, 12) else 0
        for x in range(x0 + inset, x1 - inset + 1):
            edge = y in (2, 13) or (not narrow and x in (x0 + inset, x1 - inset)) or (y in (3, 12) and x in (x0 + 1, x1 - 1) and not narrow)
            px[y][x] = BLACK if edge else YELLOW
    for y in range(4 if not narrow else 3, 15):   # shadow one pixel right/down
        for x in range(x0 + 1, min(width, x1 + 2)):
            if px[y][x] == 0 and (y == 14 or x == x1 + 1) and (y - 1 >= 2 and px[y - 1][x - 1]):
                px[y][x] = GREY
    left = (width - text_w) // 2 if narrow else x0 + 3
    for x, y in ink:
        if not (x0 <= left + x <= x1 and 3 <= y + 4 <= 11) or px[y + 4][left + x] != YELLOW:
            raise AssertionError(f'chip glyph clipped: {text}')
        px[y + 4][left + x] = BLACK
    return px


def _strip(width, text):
    """White Galmuri7 with a black right/down shadow (part1_result_rank_word style)."""
    px = [[0] * width for _ in range(8)]
    ink, text_w = _ink7(text)
    if text_w + 2 > width:
        raise AssertionError(f'strip label too wide: {text}')
    for x, y in ink:
        for dx, dy in ((1, 0), (0, 1), (1, 1)):
            if y + dy < 8 and px[y + dy][1 + x + dx] == 0:
                px[y + dy][1 + x + dx] = BLACK
    for x, y in ink:
        px[y][1 + x] = WHITE
    return px


def _icon(native, text):
    """Replace the 5px text strip under the icon with a black band, white Galmuri7 (rows 7..13)."""
    px = [row[:] for row in native]
    ink, text_w = _ink7(text)
    x0, x1 = 0, 14
    if text_w > x1 - x0 + 1:
        raise AssertionError(f'icon label too wide: {text}')
    for y in range(7, 14):
        for x in range(x0, x1 + 1):
            px[y][x] = BLACK
    left = x0 + (x1 - x0 + 1 - text_w) // 2
    for x, y in ink:
        px[7 + y][left + x] = WHITE
    return px


@lru_cache(maxsize=None)
def _badge_mask(char):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(str(ROOT / 'reference/fonts/Galmuri11-Bold.ttf'), 12)
    image = Image.new('L', (16, 16), 0)
    ImageDraw.Draw(image).text((0, 0), char, font=font, fill=255)
    x0, y0, x1, y1 = image.getbbox()
    return frozenset((x - x0, y - y0) for y in range(y0, y1) for x in range(x0, x1)
                     if image.getpixel((x, y)) >= 128), x1 - x0, y1 - y0


def _badge(text):
    """1P..4P badge style: white body, 1px black outline, centred in 16x16."""
    mask, w, h = _badge_mask(text)
    left, top = (16 - w) // 2, (16 - h) // 2
    body = {(x + left, y + top) for x, y in mask}
    ring = {(x + dx, y + dy) for x, y in body for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - body
    px = [[0] * 16 for _ in range(16)]
    for x, y in ring | body:
        if not (0 <= x < 16 and 0 <= y < 16):
            raise AssertionError(f'badge glyph clipped: {text}')
    for x, y in ring:
        px[y][x] = BLACK
    for x, y in body:
        px[y][x] = WHITE
    return px


def render(native, entry):
    _, _, w, h, _, text, kind, _ = entry
    if kind == 'chip':
        px = _chip(w * 8, text)
    elif kind == 'strip':
        px = _strip(w * 8, text)
    elif kind == 'icon':
        px = _icon(_decode(native, w, h), text)
    else:
        px = _badge(text)
    return _encode(px, w, h)


def _source(original, entry):
    number, address, w, h, digest = entry[:5]
    if bytes(original[TABLE + 8 * number:TABLE + 8 * number + 8]).hex() != GEOMETRY[number]:
        raise AssertionError(f'atlas entry {number} geometry changed')
    raw = bytes(original[address:address + w * h * 32])
    if hashlib.sha256(raw).hexdigest() != digest:
        raise AssertionError(f'atlas entry {number} source changed')
    if original.count(raw) != 1:
        raise AssertionError(f'atlas entry {number} not unique')
    return raw


def expected_regions(original):
    return tuple((entry[1], render(_source(original, entry), entry)) for entry in ENTRIES)


def _geometry_region(original):
    return tuple((TABLE + 8 * e[0], bytes(original[TABLE + 8 * e[0]:TABLE + 8 * e[0] + 8])) for e in ENTRIES)


def patch(rom, original):
    regions = expected_regions(original)
    for address, raw in _geometry_region(original):
        if bytes(rom[address:address + 8]) != raw:
            raise AssertionError(f'atlas geometry {address:06X} changed')
    for address, new in regions:
        if bytes(rom[address:address + len(new)]) not in (bytes(original[address:address + len(new)]), new):
            raise AssertionError(f'atlas chip {address:06X} modified by another writer')
    for address, new in regions:
        rom[address:address + len(new)] = new
    return len(regions)


def capture(rom, original):
    expected_regions(original)  # source guards
    for address, raw in _geometry_region(original):
        if bytes(rom[address:address + 8]) != raw:
            raise AssertionError(f'atlas geometry {address:06X} changed at capture')
    return tuple((e[1], bytes(rom[e[1]:e[1] + e[2] * e[3] * 32])) for e in ENTRIES) + _geometry_region(original)


def expected_region_addresses():
    return tuple(e[1] for e in ENTRIES) + tuple(TABLE + 8 * e[0] for e in ENTRIES)


def verify(rom, regions):
    if tuple(address for address, _ in regions) != expected_region_addresses():
        raise AssertionError('atlas chip snapshot missing')
    for address, raw in regions:
        if bytes(rom[address:address + len(raw)]) != raw:
            raise AssertionError(f'atlas chip overwritten after editor at {address:06X}')


def generated_matches(rom, original):
    return all(bytes(rom[a:a + len(n)]) == n for a, n in expected_regions(original))


PALETTE6 = ((0, 0, 112), (248, 248, 248), (184, 184, 184), (128, 128, 128), (64, 64, 64), (0, 0, 0),
            (248, 240, 8), (248, 48, 32), (120, 200, 40), (72, 128, 24), (176, 112, 32), (48, 88, 232),
            (16, 40, 184), (120, 168, 248), (240, 176, 112), (128, 64, 24))


def preview(raw, entry, scale=4, background=(250, 220, 200)):
    from PIL import Image
    w, h = entry[2], entry[3]
    px = _decode(raw, w, h)
    image = Image.new('RGB', (w * 8, h * 8), background)
    for y, row in enumerate(px):
        for x, v in enumerate(row):
            if v:
                image.putpixel((x, y), PALETTE6[v])
    return image.resize((image.width * scale, image.height * scale), Image.NEAREST)
