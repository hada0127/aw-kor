"""Six-row Hangul glyphs cut from Galmuri7 for 8px OBJ labels with a 1px border.

Japanese 8px labels (campaign CO names, Part 1 window headers) keep one border
row above and below the text, so text gets six rows.  Galmuri7 Hangul is six
rows for syllables with a horizontal vowel and no final consonant; those are
used as is.  Seven-row syllables drop one row: a duplicated row when there is
one (Galmuri proportions stay), otherwise the vowel tail or the gap row above
the final consonant.  Only the syllables used by the labels are listed, so a
new label text fails loudly instead of getting an unreviewed cut.
"""
from functools import lru_cache
from pathlib import Path

from bdf import load_bdf, glyph_grid

ROOT = Path(__file__).resolve().parent.parent
HEIGHT = 6
# Galmuri7 seven-row syllable -> row to drop (0 = top).
DROP_ROW = {
    '캐': 6, '서': 1, '린': 4, '이': 2, '미': 2, '빌': 2, '리': 4, '키': 6,
    '쿠': 6, '치': 6, '아': 1, '카': 6, '글': 3, '헬': 2, '우': 6,
    '사': 1, '령': 4, '관': 4, '전': 3, '투': 4, '정': 3, '생': 3,
    '산': 1, '비': 4, '용': 4,
}
# Drawn rows where dropping one row loses a stroke.  필: the ㅍ bottom bar
# joins the stem as the ㄹ top bar (Galmuri's own 빌 layout).  맥: the ㅁ
# becomes 3x3 so the gap row above the final ㄱ survives.
DRAWN = {
    '필': ('####.#', '.##..#', '######', '...###', '.##...', '.#####'),
    '맥': ('###.#.#', '#.#.###', '###.#.#', '.......', '.######', '......#'),
}
# Five-column forms for names too wide with 7px vowel bars (키쿠치요, 헬보우즈).
NARROW = {
    '쿠': ('####.', '...#.', '####.', '...#.', '#####', '..#..'),
    '요': ('.###.', '#...#', '#...#', '.###.', '.#.#.', '#####'),
    '보': ('#...#', '#####', '#...#', '#####', '..#..', '#####'),
    '우': ('.###.', '#...#', '.###.', '.....', '#####', '..#..'),
    '즈': ('#####', '..#..', '.#.#.', '#...#', '.....', '#####'),
}


@lru_cache(maxsize=1)
def _font():
    return load_bdf(str(ROOT / 'reference/fonts/Galmuri7.bdf'))[0]


@lru_cache(maxsize=None)
def glyph(char, narrow=False):
    """Return six '#'/'.' rows (top aligned like Galmuri7) for one syllable."""
    if narrow and char in NARROW:
        return NARROW[char]
    if char in DRAWN:
        return DRAWN[char]
    grid, width, height, xoffset, _ = glyph_grid(_font()[ord(char)])
    rows = [''.join('#' if bit else '.' for bit in row) for row in grid]
    if xoffset:
        rows = ['.' * xoffset + row for row in rows]
    if height == HEIGHT:
        return tuple(rows)
    if height != 7 or char not in DROP_ROW:
        raise KeyError(f'no reviewed six-row cut for {char!r}')
    del rows[DROP_ROW[char]]
    return tuple(rows)


def ink(text, narrow=False, gap=1, space=3):
    """Ink pixels (x, y), y in 0..5, and total width; glyphs abut by ink width."""
    pixels, cursor = [], 0
    for char in text:
        if char == ' ':
            cursor += space
            continue
        rows = glyph(char, narrow)
        columns = [x for row in rows for x, c in enumerate(row) if c == '#']
        left, right = min(columns), max(columns)
        pixels += [(cursor + x - left, y) for y, row in enumerate(rows)
                   for x, c in enumerate(row) if c == '#']
        cursor += right - left + 1 + gap
    return pixels, cursor - gap


def outlined(width, points, ink=1, outline=5):
    """8-row pixel rows: ink at rows 1..6, 8-way outline, 0 elsewhere."""
    pixels = [[0] * width for _ in range(8)]
    body = {(x, y + 1) for x, y in points}
    for x, y in body:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if not 0 <= x + dx < width:
                    raise AssertionError('outlined label exceeds its cell')
                pixels[y + dy][x + dx] = outline
    for x, y in body:
        pixels[y][x] = ink
    return pixels


def tiles_4bpp(pixels):
    """Pack 8-row pixel rows into 1D 4bpp 8x8 tiles, left to right."""
    width = len(pixels[0])
    raw = bytearray(width * 4)
    for y in range(8):
        for x in range(width):
            raw[x // 8 * 32 + y * 4 + x % 8 // 2] |= pixels[y][x] << (4 * (x % 2))
    return bytes(raw)
