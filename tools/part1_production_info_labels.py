"""Part 1 production-menu unit info panel OBJ labels (LZ77 0xBC7C00).

The block decompresses to 82 4bpp tiles (1D OBJ mapping, 2624 bytes):
  tiles 0-3    32x8  SPEC        -> 정보 (patched by build_korean_full)
  tiles 8-9    16x8  ガス         -> 연료
  tiles 14-17  32x8  サクテキ     -> 색적
  tiles 18-81  8 x 32x16 movement-type icons; bottom row carries イドウ -> 이동
Terms follow the established UI/dialogue wording (이동, 색적 = サクテキ, 연료 = 燃料/ガス).
Only label pixels are rewritten. The イドウ pixels are the ones identical in
all 8 icon variants (bottom 8 rows); icon pixels differ per variant and stay.
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


# Approved edit box inside every 32x16 movement sprite: the old イドウ plate
# spans x 6..25, rows 8..15; the new 이동 plate x 8..23 rows 8..15 plus a
# one-pixel outline on row 7. Nothing outside this box may change.
MOVE_LABEL_BOX = (5, 7, 27, 16)   # x0, y0, x1 (excl), y1 (excl)


def _in_box(x, y):
    x0, y0, x1, y1 = MOVE_LABEL_BOX
    return x0 <= x < x1 and y0 <= y < y1


def _move_labels(buf, font, text='이동'):
    starts = [MOVE_FIRST + 8 * k for k in range(MOVE_COUNT)]
    common = []
    for y in range(8, 16):
        for x in range(32):
            vals = set()
            for s in starts:
                t, px, py = _sprite_px(buf, s, 4, x, y)
                vals.add(_get(buf, t, px, py))
            if len(vals) == 1 and vals != {0}:
                common.append((x, y))
    if len(common) < 60:
        raise AssertionError(f'イドウ label mask too small: {len(common)}')
    cells, width = _glyph_cells(font, text)
    x0 = 16 - width // 2
    top = 8
    plate = set()
    for y in range(top, 16):
        for x in range(x0 - 1, x0 + width + 1):
            plate.add((x, y))
    white = {(x0 + cx, top + cy) for cx, cy in cells}
    if any(y >= 15 for _, y in white):
        raise AssertionError('이동 glyph overflows the plate')
    outline = {(x + dx, y - 1) for x, y in white if y == top for dx in (-1, 0, 1)}
    before = bytes(buf)
    if any(not _in_box(x, y) for x, y in set(common) | plate | outline):
        raise AssertionError('movement label edit leaves the approved box')
    for s in starts:
        for x, y in common:
            t, px, py = _sprite_px(buf, s, 4, x, y)
            _put(buf, t, px, py, 0)
        for x, y in plate | outline:
            t, px, py = _sprite_px(buf, s, 4, x, y)
            _put(buf, t, px, py, 0xF)
        for x, y in white:
            t, px, py = _sprite_px(buf, s, 4, x, y)
            _put(buf, t, px, py, 1)
    covered = {}
    for k, s in enumerate(starts):
        changed_outside = 0
        covered[k] = 0
        for y in range(16):
            for x in range(32):
                t, px, py = _sprite_px(buf, s, 4, x, y)
                if _get(buf, t, px, py) == _get(before, t, px, py):
                    continue
                if not _in_box(x, y):
                    changed_outside += 1
                elif (x, y) not in common:
                    covered[k] += 1   # variant-specific icon pixel under the new plate
        if changed_outside:
            raise AssertionError(f'movement variant {k} changed outside the approved box')
    return len(common), covered


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
    mask, covered = _move_labels(buf, font)
    return [{'text': '연료', 'tile_ids': [8, 9]},
            {'text': '색적', 'tile_ids': [14, 15, 16, 17]},
            {'text': '이동', 'tile_ids': [MOVE_FIRST + 8 * k + 4 + i for k in range(MOVE_COUNT) for i in range(4)],
             'mask_pixels': mask, 'variant_pixels_covered': covered}]
