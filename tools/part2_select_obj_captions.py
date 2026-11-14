"""Part 2 SYOGUN SELECT OBJ captions: button hints and the people counter.

Raw OBJ family 2 (base 0x456114, sizes 0x8071C0, see item7_part2_editor_labels):
  95  0x456BB4 1 tile  人          -> 명   (roster box "のこり 1人" -> "남은 1명")
  98  0x456C74 8 tiles A:OK!       -> A:확인
  101 0x456F74 8 tiles B:BACK      -> B:뒤로
  103 0x457174 8 tiles R:INFO      -> R:정보
Evidence: temp/fix_20261104/gfx/R19b/cap/go_jp/syogun_sel3 (CHEAT SAV) OAM
16 (tile 870 = 0x456BB4), OAM 38..43 (32x8 pairs at x=185/217 = IDs 103,
98, 101 in screen order).  JP rows: key letter + colon at x 19..28 (white
key, coloured colon), word from x=29 in the colon colour, all six-row ink
with a 1px dark outline (15).  The JP key/colon pixels are kept as they are;
only the word is replaced, in six-row Galmuri cuts with the same outline.
"""
import hashlib

import galmuri6

OUTLINE = 15
WORD_X = 29
# Six-row cuts local to these captions (Galmuri7 row dropped; see galmuri6).
DROP_ROW = {'확': 5, '인': 2, '뒤': 6, '명': 4}  # 확: bar row doubles as the ㄱ top; 인 as R20a galmuri6
# (offset, tiles, original sha256, Korean word, word colour = JP colon colour)
PROMPTS = (
    (0x457174, 8, '7e46a0c1014db844964778c9e5b6ffe3d9a31bba804ab0cf387825abbec0ae0e', '정보', 2),
    (0x456C74, 8, 'a97837764bdc37b0efd47c73f6336a8cc13c9d298ef114bea6ccc8fda1f419b9', '확인', 6),
    (0x456F74, 8, '9cb8eeaa79804dfcfbddf5940f8ba840b6378594c625d66e0969c045702795b2', '뒤로', 9),
)
COUNTER = (0x456BB4, 1, 'cc5b285d8cd4eb1d0c44c6520e8ebd9bf7401bfb96c345b06db5a4462abee38a', '명', 1)


def glyph(char):
    if char not in DROP_ROW:
        return galmuri6.glyph(char)
    from bdf import glyph_grid
    grid, _, height, xoffset, _ = glyph_grid(galmuri6._font()[ord(char)])
    rows = ['.' * xoffset + ''.join('#' if bit else '.' for bit in row) for row in grid]
    if height != 7:
        raise AssertionError(f'unexpected Galmuri7 height for {char!r}')
    del rows[DROP_ROW[char]]
    return tuple(rows)


def word_ink(text):
    """(x, y) ink, y in 0..5, glyphs one pixel apart; and the total width."""
    pixels, cursor = [], 0
    for char in text:
        rows = glyph(char)
        columns = [x for row in rows for x, c in enumerate(row) if c == '#']
        left, right = min(columns), max(columns)
        pixels += [(cursor + x - left, y) for y, row in enumerate(rows)
                   for x, c in enumerate(row) if c == '#']
        cursor += right - left + 2
    return pixels, cursor - 2


def decode(raw, width):
    return [[(raw[x // 8 * 32 + y * 4 + x % 8 // 2] >> (4 * (x % 2))) & 15 for x in range(width)]
            for y in range(8)]


def draw_outlined(pixels, ink, left, colour):
    """Ink at rows 1..6 from x=left; 8-way outline only on empty pixels."""
    width = len(pixels[0])
    body = {(left + x, y + 1) for x, y in ink}
    for x, y in body:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if not 0 <= x + dx < width:
                    raise AssertionError('caption exceeds its OBJ cell')
                if pixels[y + dy][x + dx] == 0:
                    pixels[y + dy][x + dx] = OUTLINE
    for x, y in body:
        pixels[y][x] = colour


def render_prompt(source, text, colour):
    pixels = decode(source, 64)
    for row in pixels:
        row[WORD_X:] = [0] * (64 - WORD_X)
    ink, width = word_ink(text)
    if WORD_X + width + 1 > 55:          # x >= 55 is past the screen edge (OAM x=185)
        raise AssertionError(f'button hint word too wide: {text}')
    draw_outlined(pixels, ink, WORD_X, colour)
    return galmuri6.tiles_4bpp(pixels)


def render_counter(text, colour):
    ink, width = word_ink(text)
    if width > 6:
        raise AssertionError(f'counter glyph too wide: {text}')
    pixels = [[0] * 8 for _ in range(8)]
    draw_outlined(pixels, ink, (8 - width) // 2, colour)
    return galmuri6.tiles_4bpp(pixels)


def expected_regions(rom):
    """Regions rendered from the JP bytes; raises if a source was changed."""
    out = []
    for offset, tiles, digest, text, colour in PROMPTS + (COUNTER,):
        source = bytes(rom[offset:offset + tiles * 32])
        if hashlib.sha256(source).hexdigest() != digest:
            raise AssertionError(f'Part 2 select caption source changed at {offset:06X}')
        if tiles == 1:
            out.append((offset, render_counter(text, colour)))
        else:
            out.append((offset, render_prompt(source, text, colour)))
    return out


def patch(rom, original):
    regions = expected_regions(original)
    for offset, new in regions:
        if bytes(rom[offset:offset + len(new)]) not in (bytes(original[offset:offset + len(new)]), new):
            raise AssertionError(f'Part 2 select caption {offset:06X} conflicts with an earlier writer')
    for offset, new in regions:
        rom[offset:offset + len(new)] = new
    return len(regions)


def generated_matches(rom, original):
    return all(bytes(rom[a:a + len(n)]) == n for a, n in expected_regions(original))
