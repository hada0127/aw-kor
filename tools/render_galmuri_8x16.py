#!/usr/bin/env python3
"""Galmuri11-Condensed BDF에서 ASCII/한글 글리프를 8x16 셀로 변환.

- ASCII (A-Z, a-z, 0-9): Galmuri 4-7px 폭, 10px 높이 → 8x16 셀 좌측-수직중앙
- 한글: Galmuri 7px 폭, 11px 높이 → 8x16 셀 수직중앙

각 셀은 top tile (8x8) + bot tile (8x8) = 8x16 픽셀.
4bpp packed, ink = palette index 10.

Vertical positioning:
  ASCII (10 height): rows 3-12 of cell (top rows 0-2 pad + char rows 0-4 in top rows 3-7, char rows 5-9 in bot rows 0-4, bot rows 5-7 pad)
  Korean (11 height): rows 3-13 of cell (similar but extends 1 row into bot)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from bdf import load_bdf, glyph_grid

INK = 10
_font_cache = None

def _load():
    global _font_cache
    if _font_cache is None:
        font, _ = load_bdf('reference/fonts/Galmuri11-Condensed.bdf')
        _font_cache = font
    return _font_cache

def render_char(ch, ink=INK, top_pad=3, x_offset=1):
    """Render character to (top_tile, bot_tile) - two 32-byte 8x8 tiles, 4bpp packed.

    top_pad: pixels of empty space at top of cell before glyph starts (default 3 → centers 10px char in 16px cell)
    x_offset: horizontal offset from cell left edge (default 1 → 1px left padding)
    """
    font = _load()
    if ord(ch) not in font:
        return bytes(32), bytes(32)
    g = font[ord(ch)]
    grid, w, h, xo, yo = glyph_grid(g)

    top = bytearray(32)
    bot = bytearray(32)

    def setpix(tile, row, col, val):
        if not (0 <= row < 8 and 0 <= col < 8):
            return
        bi = row * 4 + col // 2
        if col % 2 == 0:
            tile[bi] = (tile[bi] & 0xF0) | val
        else:
            tile[bi] = (tile[bi] & 0x0F) | (val << 4)

    for r in range(h):
        cell_row = top_pad + r  # row in 16-row cell
        for c in range(w):
            cell_col = x_offset + c + xo  # col in 8-col cell
            if grid[r][c]:
                if cell_row < 8:
                    setpix(top, cell_row, cell_col, ink)
                else:
                    setpix(bot, cell_row - 8, cell_col, ink)
    return bytes(top), bytes(bot)

if __name__ == "__main__":
    ch = sys.argv[1] if len(sys.argv) > 1 else 'A'
    top, bot = render_char(ch)
    def show(name, t):
        print(f'--- {name} ---')
        for r in range(8):
            line = ''
            for c in range(8):
                bi = r*4 + c//2
                v = (t[bi] & 0xF) if c%2 == 0 else (t[bi] >> 4)
                line += '#' if v else '.'
            print(f'  {line}')
    show(f'{ch} top', top)
    show(f'{ch} bot', bot)
