"""Render Hangul into a Game Wars dialogue cell as 11px-tall glyph across 4 tiles.
Cell vertical tile structure (verified 2026-05-22, cell0): screen y123-133 maps to
  y123      -> top_extra tile row7
  y124-127  -> top      tile rows0-3
  y128-131  -> bottom   tile rows4-7
  y132-133  -> bot_extra tile rows0-1
Font ink palette index = 10. Glyph: Galmuri11-Condensed (7x11), fits 8px cell width."""
import sys; sys.path.insert(0, 'tools')
from bdf import load_bdf, glyph_grid
INK=10
_gl=None
def _load():
    global _gl
    if _gl is None: _gl,_=load_bdf('reference/fonts/Galmuri11-Condensed.bdf')
    return _gl
def cell_bitmap(ch, xshift=0):
    g=_load()[ord(ch)]; grid,w,hh,xo,yo=glyph_grid(g)
    bm=[[0]*8 for _ in range(11)]
    for r in range(min(11,len(grid))):
        for c in range(w):
            if grid[r][c]:
                x=c+xo+xshift
                if 0<=x<8: bm[r][x]=1
    return bm
def make_tiles(ch, xshift=0):
    """Return dict {role: 32-byte tile} for roles top_extra,top,bottom,bot_extra."""
    bm=cell_bitmap(ch,xshift)
    topx=bytearray(32);top=bytearray(32);bot=bytearray(32);botx=bytearray(32)
    def sp(t,r,c,v):
        bi=r*4+c//2
        if c%2==0:t[bi]=(t[bi]&0xF0)|v
        else:t[bi]=(t[bi]&0x0F)|(v<<4)
    for c in range(8):
        if bm[0][c]: sp(topx,7,c,INK)
        for i,gr in enumerate(range(1,5)):
            if bm[gr][c]: sp(top,i,c,INK)
        for i,gr in enumerate(range(5,9)):
            if bm[gr][c]: sp(bot,4+i,c,INK)
        for i,gr in enumerate(range(9,11)):
            if bm[gr][c]: sp(botx,i,c,INK)
    return {'top_extra':bytes(topx),'top':bytes(top),'bottom':bytes(bot),'bot_extra':bytes(botx)}
