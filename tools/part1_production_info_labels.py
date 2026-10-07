"""Part 1 production-menu unit info panel OBJ labels (LZ77 0xBC7C00).

The block decompresses to 82 4bpp tiles (1D OBJ mapping, 2624 bytes):
  tiles 0-3    32x8  SPEC        -> 정보 (patched by build_korean_full)
  tiles 8-9    16x8  ガス         -> 연료  (white + outline 5, no box, like the native strip)
  tiles 14-17  32x8  サクテキ     -> 색적  (same)
  tiles 18-81  8 x 32x16 movement-type icons; bottom row carries イドウ -> 이동
Terms follow the established UI/dialogue wording (이동, 색적 = サクテキ, 연료 = 燃料/ガス).
Only label pixels are rewritten. イドウ is replaced by white 이동 with a 1px
dark outline (original kana style, no plate); per variant only the literal
OLD_LABEL pixels and the new glyph/outline may change, checked pixel by pixel.
"""
import hashlib
import json
import os

APPROVAL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'data', 'part1_move_label_exception_masks.json')

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


def _outlined_label(buf, first, wtiles, text, font, clear_rows, glyph_top=1, outline_value=5):
    """White text (1) with a 1px outline, no box: the native ガス/サクテキ style.

    The native strips are 8 rows; Galmuri7 glyphs are 7 rows, so with the glyph
    on rows 1..7 the outline below row 7 is clipped. clear_rows are the rows of
    the old lettering that are cleared first (row 0 of the 32x8 strip keeps its
    native pixels except where the new outline lands).
    """
    cells, width = _glyph_cells(font, text)
    x0 = (wtiles * 8 - width) // 2
    glyph = {(x0 + cx, glyph_top + cy) for cx, cy in cells}
    outline = {(x + dx, y + dy) for x, y in glyph for dx in (-1, 0, 1) for dy in (-1, 0, 1)
               if (x + dx, y + dy) not in glyph and 0 <= y + dy < 8}
    if any(not (0 <= x < wtiles * 8) for x, _ in glyph | outline):
        raise AssertionError(f'label {text!r} does not fit its strip')
    for y in range(*clear_rows):
        for x in range(wtiles * 8):
            t, px, py = _sprite_px(buf, first, wtiles, x, y)
            _put(buf, t, px, py, 0)
    for (x, y), value in [(p, outline_value) for p in outline] + [(p, 1) for p in glyph]:
        t, px, py = _sprite_px(buf, first, wtiles, x, y)
        _put(buf, t, px, py, value)


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


def load_approval(path=APPROVAL):
    with open(path, encoding='utf-8') as stream:
        return json.load(stream)


def _sprite_sha(buf, first):
    return hashlib.sha256(bytes(buf[first * TILE:(first + 8) * TILE])).hexdigest()


def render_move_labels(buf, font, text='이동'):
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
        covered = []
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
                    covered.append([x, y])
        report.append({'variant': k, 'first_tile': s, 'changed': changed, 'old_label_cleared': cleared,
                       'icon_pixels_covered': icon_covered, 'covered_icon_pixels': covered,
                       'result_sha256': _sprite_sha(buf, s)})
    return report


def check_move_approval(report, approval):
    """Covering icon pixels is an approved exception only for the frozen set."""
    frozen = {v['variant']: v for v in approval['variants']}
    for entry in report:
        want = frozen.get(entry['variant'])
        if (want is None or want['covered_icon_pixels'] != entry['covered_icon_pixels']
                or want['result_sha256'] != entry['result_sha256']):
            raise AssertionError(f"movement variant {entry['variant']} differs from the approved exception "
                                 f"(data/part1_move_label_exception_masks.json)")
    if set(frozen) != {entry['variant'] for entry in report}:
        raise AssertionError('approved exception variants do not match the rendered set')


def _move_labels(buf, font, text='이동', approval=None):
    report = render_move_labels(buf, font, text)
    check_move_approval(report, load_approval() if approval is None else approval)
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
    _outlined_label(buf, FUEL_TILES[0], FUEL_TILES[1], '연료', font, clear_rows=(0, 8))
    _outlined_label(buf, SCOUT_TILES[0], SCOUT_TILES[1], '색적', font, clear_rows=(1, 8))
    move_report = _move_labels(buf, font)
    return [{'text': '연료', 'tile_ids': [8, 9]},
            {'text': '색적', 'tile_ids': [14, 15, 16, 17]},
            {'text': '이동', 'tile_ids': [MOVE_FIRST + 8 * k + 4 + i for k in range(MOVE_COUNT) for i in range(4)],
             'variants': move_report}]


def verify_final_rom(rom, approval=None, offset=0xBC7C00):
    """Final-output gate after every writer (sprite overrides included).

    Decompresses the production info block from the finished ROM and requires
    the frozen fuel/scout label tiles and all 8 approved movement sprites.
    """
    from lz77_scan import lz77_decompress
    from sprite_relocations import resolve_sprite_offset
    approval = load_approval() if approval is None else approval
    decoded = lz77_decompress(rom, resolve_sprite_offset(rom, offset))
    if decoded is None or len(decoded[0]) != 82 * TILE:
        raise AssertionError('final production info block 0xBC7C00 is not the expected LZ77 asset')
    data = decoded[0]
    hashes = region_hashes(data)
    if hashes['fuel'] != approval['final_fuel_sha256'] or hashes['scout'] != approval['final_scout_sha256']:
        raise AssertionError('final ROM fuel/scout labels differ from the approved output (0xBC7C00)')
    for entry in approval['variants']:
        if _sprite_sha(data, entry['first_tile']) != entry['result_sha256']:
            raise AssertionError(f"final ROM movement variant {entry['variant']} differs from the approved "
                                 'exception (0xBC7C00, later writer or sprite override?)')
    return len(approval['variants'])
