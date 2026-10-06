"""Part 1 production-menu unit info panel OBJ labels (LZ77 0xBC7C00).

The block decompresses to 82 4bpp tiles (1D OBJ mapping, 2624 bytes):
  tiles 0-3    32x8  SPEC        -> 정보 (patched by build_korean_full)
  tiles 8-9    16x8  ガス         -> 연료
  tiles 14-17  32x8  サクテキ     -> 색적
  tiles 18-81  8 x 32x16 movement-type icons; bottom row carries イドウ -> 이동
Terms follow the established UI/dialogue wording (이동, 색적 = サクテキ, 연료 = 燃料/ガス).
Only label pixels are rewritten. イドウ is replaced by white 이동 with a 1px
dark outline (original kana style, no plate); per variant only the literal
OLD_LABEL pixels and the new glyph/outline may change, checked pixel by pixel.
"""
import hashlib

TILE = 32
FUEL_TILES = (8, 2)          # first tile, width in tiles (16x8)
SCOUT_TILES = (14, 4)        # 32x8
MOVE_FIRST, MOVE_COUNT = 18, 8   # 32x16 sprites, 8 tiles each

# sha256 of the original (pre-patch) bytes for each rewritten tile range.
SOURCE_HASHES = {
    'fuel': 'a81163607cb6a1aab3ae3c003c3c32d8a9632353e4bc70f4dc4c30f03747b13d',
    'scout': '959a4f33e9b4a2004355b068693ca07780b7529d0ec795d70529007bac019360',
    'move': '1dea2375c5af55c7ca843aa6b73dcf1396e43f248304b675027072eec61e5e9c',
}


def _get(buf, t, x, y):
    b = buf[t * TILE + y * 4 + x // 2]
    return (b >> 4) if x & 1 else (b & 0x0F)


def _put(buf, t, x, y, v):
    i = t * TILE + y * 4 + x // 2
    if x & 1:
        buf[i] = (buf[i] & 0x0F) | ((v & 0x0F) << 4)
    else:
        buf[i] = (buf[i] & 0xF0) | (v & 0x0F)


def _sprite_px(buf, first, w, x, y):
    """Pixel accessor for a w-tiles-wide sprite in 1D mapping."""
    return first + (y // 8) * w + x // 8, x % 8, y % 8


def _glyph_cells(font, text, gap=1):
    from bdf import glyph_grid
    cells, cursor = [], 0
    for ch in text:
        grid, w, h, xo, yo = glyph_grid(font[ord(ch)])
        for row in range(h):
            for col in range(w):
                if grid[row][col]:
                    cells.append((cursor + col + xo, row + yo))
        cursor += w + xo + gap
    return cells, cursor - gap


def _boxed_label(buf, first, wtiles, text, font, box_x0, box_x1, rows=(1, 8), glyph_top=1):
    """Solid box (color 5) + white text (color 1), same style as SPEC->정보."""
    cells, width = _glyph_cells(font, text)
    x0 = box_x0 + ((box_x1 - box_x0) - width) // 2
    for y in range(rows[0], rows[1]):
        for x in range(wtiles * 8):
            t, px, py = _sprite_px(buf, first, wtiles, x, y)
            _put(buf, t, px, py, 5 if box_x0 <= x < box_x1 else 0)
    for cx, cy in cells:
        x, y = x0 + cx, glyph_top + cy
        if not (box_x0 <= x < box_x1 and rows[0] <= y < rows[1]):
            raise AssertionError(f'label {text!r} does not fit its box')
        t, px, py = _sprite_px(buf, first, wtiles, x, y)
        _put(buf, t, px, py, 1)


# Original イドウ lettering shared by all 8 movement sprites (rows 8..15 of the
# 32x16 OBJ): '1'/'2'/'3' glyph ink, 'f' its dark outline, '.' not lettering.
# patch() checks every variant against this literal before touching it.
OLD_LABEL_ROWS = {
    8:  '...............fffff............',
    9:  '..........ffffff1f1f.fff........',
    10: '.......fff311f1f1f1fff1fff......',
    11: '.......f1113ff1fffff11111f......',
    12: '.......fff1f.f1112ff1fff1f......',
    13: '.........f1f.f1fffffffff1f......',
    14: '.........f1f.f1f....f1113f......',
    15: '.........fff.fff....fffff.......',
}
OLD_LABEL = {(x, y): int(ch, 16) for y, row in OLD_LABEL_ROWS.items()
             for x, ch in enumerate(row) if ch != '.'}
MOVE_GLYPH_TOP = 8          # new glyph rows 8..14, outline rows 7..15


def move_label_pixels(font, text='이동'):
    """(glyph, outline) pixel sets of the new label, centred like the old one."""
    cells, width = _glyph_cells(font, text)
    x0 = 16 - width // 2
    glyph = {(x0 + cx, MOVE_GLYPH_TOP + cy) for cx, cy in cells}
    outline = {(x + dx, y + dy) for x, y in glyph for dx in (-1, 0, 1) for dy in (-1, 0, 1)
               if (x + dx, y + dy) not in glyph}
    if any(not (0 <= x < 32 and 0 <= y < 16) for x, y in glyph | outline):
        raise AssertionError('이동 label leaves the 32x16 sprite')
    return glyph, outline


def _move_labels(buf, font, text='이동'):
    """White 이동 with a 1px dark outline, no plate (original kana style).

    Per variant only OLD_LABEL pixels (cleared to transparent unless reused)
    and the new glyph/outline pixels may change; anything else that differs
    from the source variant fails the build.
    """
    starts = [MOVE_FIRST + 8 * k for k in range(MOVE_COUNT)]
    before = bytes(buf)
    for k, s in enumerate(starts):
        for (x, y), value in OLD_LABEL.items():
            t, px, py = _sprite_px(buf, s, 4, x, y)
            if _get(buf, t, px, py) != value:
                raise AssertionError(f'movement variant {k}: lettering pixel {x},{y} is not the source イドウ')
    glyph, outline = move_label_pixels(font, text)
    allowed = set(OLD_LABEL) | glyph | outline
    report = []
    for k, s in enumerate(starts):
        for x, y in OLD_LABEL:
            t, px, py = _sprite_px(buf, s, 4, x, y)
            _put(buf, t, px, py, 0)
        for x, y in outline:
            t, px, py = _sprite_px(buf, s, 4, x, y)
            _put(buf, t, px, py, 0xF)
        for x, y in glyph:
            t, px, py = _sprite_px(buf, s, 4, x, y)
            _put(buf, t, px, py, 1)
        changed = cleared = icon_covered = 0
        for y in range(16):
            for x in range(32):
                t, px, py = _sprite_px(buf, s, 4, x, y)
                old, new = _get(before, t, px, py), _get(buf, t, px, py)
                if old == new:
                    continue
                if (x, y) not in allowed:
                    raise AssertionError(f'movement variant {k} changed pixel {x},{y} outside the label')
                changed += 1
                if (x, y) in OLD_LABEL and (x, y) not in glyph | outline:
                    cleared += 1
                elif (x, y) not in OLD_LABEL and old != 0:
                    icon_covered += 1
        report.append({'variant': k, 'changed': changed, 'old_label_cleared': cleared,
                       'icon_pixels_covered': icon_covered})
    return report


def region_hashes(buf):
    def h(first, count):
        return hashlib.sha256(bytes(buf[first * TILE:(first + count) * TILE])).hexdigest()
    return {'fuel': h(FUEL_TILES[0], FUEL_TILES[1]),
            'scout': h(SCOUT_TILES[0], SCOUT_TILES[1]),
            'move': h(MOVE_FIRST, MOVE_COUNT * 8)}


def patch(buf, font):
    """Rewrite the three labels in a decompressed 0xBC7C00 buffer in place."""
    if len(buf) != 82 * TILE:
        raise AssertionError(f'unexpected production info block size {len(buf)}')
    actual = region_hashes(buf)
    for key, expected in SOURCE_HASHES.items():
        if expected is not None and actual[key] != expected:
            raise AssertionError(f'unexpected production info {key} tiles: {actual[key]}')
    _boxed_label(buf, FUEL_TILES[0], FUEL_TILES[1], '연료', font, 0, 16, rows=(0, 8))
    _boxed_label(buf, SCOUT_TILES[0], SCOUT_TILES[1], '색적', font, 4, 28)
    move_report = _move_labels(buf, font)
    return [{'text': '연료', 'tile_ids': [8, 9]},
            {'text': '색적', 'tile_ids': [14, 15, 16, 17]},
            {'text': '이동', 'tile_ids': [MOVE_FIRST + 8 * k + 4 + i for k in range(MOVE_COUNT) for i in range(4)],
             'variants': move_report}]
