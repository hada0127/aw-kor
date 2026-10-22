"""Part 1 map editor's small raw OBJ captions (observed on b44 editor screen).

The live Part 1 objects at OAM 20/21, 24, 33/34 read the B7 raw tiles below.
The similarly named Part 2 editor labels at 0x458xxx are separate assets.
"""
import hashlib

from item7_part2_editor_labels import _ink


# Source offset, tile width, Korean caption, original SHA-256, palette ink.
LABELS = (
    (0xB7F190, 2, '가로', '7f8d8f28c1243c5734a03e47c89c4ab624dbce8f301cd008f1035c362b2ec5ba', 9),
    (0xB7F150, 2, '세로', 'ece57c8b009af2b6e210d3c7ccd82281cbe25f9490d1e98adddd018e66f1a621', 9),
    (0xB7E0F0, 3, '남은', 'ba41d40b510b740ee77162d37ad6132294f3a8809592d79cb85b01217800e677', 1),
    (0xB7EA50, 4, '지형', '552c9dca2016b47f0e9cc2588593a8066808528a91ee3dc65f3afb9ec83a7b0f', 1),
)
HEADER_OFFSET = 0xB7EDD0
HEADER_SHA256 = 'f9f5c7345890e2c9a51c1d0d839ec12c879605fed77c02672a8c2e4576a52615'


def _render_header(original):
    """Keep the native SELECT key art and redraw only its Japanese right caption."""
    raw = bytearray(original[HEADER_OFFSET:HEADER_OFFSET + 512])
    if hashlib.sha256(raw).hexdigest() != HEADER_SHA256:
        raise AssertionError('Part 1 editor SELECT header source changed')

    def put(x, y, value):
        # Two adjacent 32x16 OBJ cells, each arranged in 4x2 tiles.
        i = (x // 32) * 256 + ((y // 8) * 4 + (x % 32) // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
        shift = 4 * (x % 2)
        raw[i] = (raw[i] & ~(15 << shift)) | (value << shift)

    glyph, width = _ink('메뉴')
    if width > 24:
        raise AssertionError('Part 1 editor menu caption overflows')
    for y in range(4, 12):
        for x in range(37, 62):
            put(x, y, 1)
    left = 37 + (25 - width) // 2
    for x, y in glyph:
        put(left + x, 4 + y, 5)
    return bytes(raw)


def _render(original, offset, tiles, caption, ink_index):
    width = tiles * 8
    raw = bytearray(original[offset:offset + tiles * 32])
    if len(raw) != tiles * 32:
        raise AssertionError('Part 1 editor OBJ truncated')

    def put(x, y, value):
        if not 0 <= x < width or not 0 <= y < 8:
            return
        i = (x // 8) * 32 + y * 4 + (x % 8) // 2
        shift = 4 * (x % 2)
        raw[i] = (raw[i] & ~(15 << shift)) | (value << shift)

    glyph, text_width = _ink(caption)
    if text_width > width:
        raise AssertionError(f'Part 1 editor label overflows: {caption}')
    if ink_index == 9:
        # The coordinate labels are dark text on an opaque light plate.
        for y in range(8):
            for x in range(width):
                put(x, y, 1)
        left = (width - text_width) // 2
        for x, y in glyph:
            put(left + x, y, ink_index)
    else:
        # The remaining/terrain words are transparent OBJ text with a pale rim.
        for y in range(8):
            for x in range(width):
                put(x, y, 0)
        left = (width - text_width) // 2
        points = {(left + x, y) for x, y in glyph}
        for x, y in points:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                put(x + dx, y + dy, 5)
        for x, y in points:
            put(x, y, ink_index)
    return bytes(raw)


def expected_regions(original):
    regions = [(HEADER_OFFSET, _render_header(original))]
    for offset, tiles, caption, digest, ink_index in LABELS:
        source = original[offset:offset + tiles * 32]
        if hashlib.sha256(source).hexdigest() != digest:
            raise AssertionError(f'Part 1 editor OBJ source changed at {offset:#x}')
        regions.append((offset, _render(original, offset, tiles, caption, ink_index)))
    return regions


def patch(rom, original):
    regions = expected_regions(original)
    for offset, raw in regions:
        old = bytes(original[offset:offset + len(raw)])
        if bytes(rom[offset:offset + len(raw)]) not in (old, raw):
            raise AssertionError(f'Part 1 editor OBJ conflicts at {offset:#x}')
    for offset, raw in regions:
        rom[offset:offset + len(raw)] = raw
    return len(regions)


def verify(rom, original):
    for offset, raw in expected_regions(original):
        if bytes(rom[offset:offset + len(raw)]) != raw:
            raise AssertionError(f'Part 1 editor OBJ overwritten at {offset:#x}')
