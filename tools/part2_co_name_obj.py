"""Part 2 CO name OBJ (48x16, 6 glyph columns of 8x16) in Hada Sans ExtraBold.

The 19 name blocks (table 0x81BE68, stride 0x44; written in place by
build_korean_full.patch_part2_domino_co_name_obj) are shown in the SYOGUN
SELECT roster box, on the LET'S GO cut-in and on the R:info screen.

JP names (e.g. 0x45274C リョウ), OBJ palette banks 8/9: white (1) strokes
about two pixels wide in body rows 1..12, centred in 48 px, a dark outline
(15) one pixel left/top and two pixels right/bottom, light grey (13) on inner
stroke corners and blue-grey (14) on the outline's top-right and bottom-left
corners.

Korean (R21, user: "더 산스답게"): each syllable is the real Hada Sans
ExtraBold glyph rasterised by FreeType at 13 px (hinted, so horizontal bars
and the gaps between them land on whole pixels; tallest syllables fill body
rows 1..12 like JP).  Glyphs sit one pixel apart and are condensed only when
a name is wider than 45 px.  Coverage >= 0.5 is white, a pixel darker than both
neighbours on one axis stays a gap, a partial pixel on an inner corner becomes
13, then the JP outline and corner colour.  When the LZ77 stream would not fit
the caller's slot, the corner colour and then the inner-corner grey are left
out (see ``pixels``).
"""
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

import aw_fonts
from lz77_compress import lz77_compress_optimal

WIDTH, HEIGHT = 48, 16
SIZE = 13                # px; tallest Hangul body rows 1..12 like JP katakana
TOP_REF = '헬'           # tallest syllable in the 19 names
GAP = 1                  # px between glyph bodies
MAX_W = 45               # body width: 1 px outline left, 2 px right
BODY, AA, CORNER, OUTLINE = 1, 13, 14, 15
VALLEY = 0.15            # coverage drop that marks a gap between two strokes
# (inner-corner grey, outline corner colour), tried in order until the slot fits
AA_LEVELS = ((True, True), (True, False), (False, True), (False, False))


@lru_cache(maxsize=1)
def _font():
    return ImageFont.truetype(aw_fonts.hadasans_extrabold_path(), SIZE)


def _glyph(ch):
    """Hinted coverage of one syllable: ink width x 16 rows, TOP_REF top on row 1."""
    font = _font()
    big = Image.new('L', (4 * SIZE, 4 * SIZE))
    ImageDraw.Draw(big).text((SIZE, SIZE), ch, font=font, fill=255)
    x0, _, x1, _ = big.getbbox()
    top = SIZE + font.getbbox(TOP_REF)[1] - 1
    return big.crop((x0, top, x1, top + HEIGHT))


def _coverage(name):
    """16x48 coverage (0..1) of the centred name."""
    glyphs = [_glyph(ch) for ch in name]
    gaps = GAP * (len(glyphs) - 1)
    ink = sum(g.width for g in glyphs)
    if ink + gaps > MAX_W:
        scale = (MAX_W - gaps) / ink
        glyphs = [g.resize((int(g.width * scale), HEIGHT), Image.BOX) for g in glyphs]
    width = sum(g.width for g in glyphs) + gaps
    canvas = Image.new('L', (WIDTH, HEIGHT))
    x = (MAX_W - width) // 2 + 1
    for g in glyphs:
        canvas.paste(g, (x, 0))
        x += g.width + GAP
    return [[canvas.getpixel((x, y)) / 255 for x in range(WIDTH)] for y in range(HEIGHT)]


def _open_gaps(cov):
    """A pixel darker than both neighbours on one axis is a gap, never body."""
    def at(x, y):
        return cov[y][x] if 0 <= x < WIDTH and 0 <= y < HEIGHT else 0.0

    def valley(x, y):
        v = cov[y][x]
        return (at(x, y - 1) - v >= VALLEY and at(x, y + 1) - v >= VALLEY) or \
               (at(x - 1, y) - v >= VALLEY and at(x + 1, y) - v >= VALLEY)

    return [[min(cov[y][x], 0.29) if valley(x, y) else cov[y][x] for x in range(WIDTH)]
            for y in range(HEIGHT)]


def _quantize(cov, inner_aa, corners):
    """Coverage -> palette indices; None when the body leaves the 45x13 box."""
    grid = [[BODY if v >= 0.5 else 0 for v in row] for row in cov]

    def white(x, y):
        return 0 <= x < WIDTH and 0 <= y < HEIGHT and grid[y][x] == BODY

    if inner_aa:
        for y in range(HEIGHT):
            for x in range(WIDTH):
                up, right, down, left = white(x, y - 1), white(x + 1, y), white(x, y + 1), white(x - 1, y)
                if not grid[y][x] and cov[y][x] >= 0.3 and up != down and left != right:
                    grid[y][x] = AA
    ink = {(x, y) for y in range(HEIGHT) for x in range(WIDTH) if grid[y][x]}
    if not all(1 <= x <= WIDTH - 3 and 1 <= y <= HEIGHT - 3 for x, y in ink):
        return None
    ring = {(x + a, y + b) for x, y in ink for a in (-1, 0, 1) for b in (-1, 0, 1)}
    for x, y in (ring | {(x + 1, y + 1) for x, y in ring}) - ink:
        grid[y][x] = OUTLINE
    if corners:
        def filled(x, y):
            return 0 <= x < WIDTH and 0 <= y < HEIGHT and grid[y][x] != 0

        found = [(x, y) for y in range(HEIGHT) for x in range(WIDTH) if grid[y][x] == OUTLINE and (
            (not filled(x, y - 1) and not filled(x + 1, y) and filled(x, y + 1) and filled(x - 1, y)) or
            (not filled(x, y + 1) and not filled(x - 1, y) and filled(x, y - 1) and filled(x + 1, y)))]
        for x, y in found:
            grid[y][x] = CORNER
    return grid


def _encode(grid):
    """384 bytes: glyph columns of 8x16 (top tile, bottom tile), left to right."""
    raw = bytearray(WIDTH * HEIGHT // 2)
    for y, row in enumerate(grid):
        for x, value in enumerate(row):
            tile = (x // 8) * 2 + y // 8
            raw[tile * 32 + (y % 8) * 4 + (x % 8) // 2] |= value << (4 * (x % 2))
    return bytes(raw)


def pixels(name, limit=None):
    """Richest AA level whose LZ77 stream is <= limit bytes (None: no limit)."""
    cov = _open_gaps(_coverage(name))
    for inner_aa, corners in AA_LEVELS:
        grid = _quantize(cov, inner_aa, corners)
        if grid is None:
            raise aw_fonts.FontFitError(f'CO name too large: {name}')
        if limit is None or len(lz77_compress_optimal(_encode(grid), vram_safe=True)) <= limit:
            return grid
    raise aw_fonts.FontFitError(f'CO name does not fit its slot: {name} (limit {limit})')


def render(name, limit=None):
    return _encode(pixels(name, limit))
