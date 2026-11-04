"""Korean-style 、(0x8141) / 。(0x8142) glyph images shared by the builder and QA.

Only the glyph images change (temp/fix_20261104/punct_glyph_research.md option a);
the text bytes stay 0x8141/0x8142. P1 per-char path: symbol-table top is the
shared blank slot 95 (never touched), bottom is a private FONT_BASE slot. P2 A3
glyph cache: a private node whose 64 pixel bytes start at node+6.
"""

FONT_BASE = 0xB974D0
TOP_BLANK_SLOT = 95
P1_BOTTOM_SLOT = {0x8141: 286, 0x8142: 285}
A3_NODE = {0x8141: 0x807BE8, 0x8142: 0x807D50}
INK = 10  # same nibble as the native marks and the A3 keyword colour remap
# Hangul baseline is cell row 13; marks sit at x=1..2 next to the previous glyph.
PIXELS = {
    0x8141: ((2, 12), (1, 13)),                    # Galmuri ',' (.x / x.)
    0x8142: ((1, 12), (2, 12), (1, 13), (2, 13)),  # 2x2 period (1x1 vanishes)
}


def bottom_tile(code):
    """4bpp 8x8 bottom tile (cell rows 8-15) for 0x8141/0x8142."""
    tile = bytearray(32)
    for x, y in PIXELS[code]:
        tile[(y - 8) * 4 + x // 2] |= INK << (4 * (x % 2))
    return bytes(tile)


def expected_symbol_tile(code, delta, original_tile):
    """Tile a symbol-table entry (delta 0 = top, 8 = bottom) should show."""
    if code in PIXELS and delta == 8:
        return bottom_tile(code)
    return bytes(original_tile)


def symbol_tile_ok(code, delta, tile, original_tile):
    """QA: the native tile, or the Korean redraw for 0x8141/0x8142 bottoms."""
    tile = bytes(tile)
    return tile == bytes(original_tile) or tile == expected_symbol_tile(code, delta, original_tile)
