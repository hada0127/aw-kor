"""Render Hangul (or any) char -> GBA 8x8 4bpp tile (32 bytes), ink index configurable."""
from PIL import Image, ImageFont, ImageDraw
_FONT_PATH="/System/Library/Fonts/AppleSDGothicNeo.ttc"
def render_tile(ch, ink=10, size=8, fontsize=8, yoff=0, xoff=0, thresh=90):
    # Render large, autocrop to ink bbox, scale to fill the 8x8 cell -> denser/legible.
    BIG=44
    big=Image.new("L",(BIG,BIG),0)
    d=ImageDraw.Draw(big)
    f=ImageFont.truetype(_FONT_PATH, 34)
    bb=d.textbbox((0,0),ch,font=f)
    d.text((-bb[0]+2,-bb[1]+2),ch,fill=255,font=f)
    cb=big.getbbox()
    if cb: big=big.crop(cb)
    glyph=big.resize((size,size),Image.LANCZOS)
    px=glyph.load()
    tile=bytearray(32)
    for r in range(8):
        for c in range(8):
            on = 1 if px[c,r]>=thresh else 0
            v = ink if on else 0
            bi=r*4 + c//2
            if c%2==0: tile[bi]=(tile[bi]&0xF0)|v
            else: tile[bi]=(tile[bi]&0x0F)|(v<<4)
    return bytes(tile)
def split_tiles(ch, ink=10):
    """Render Hangul for a COMPOSITE dialogue cell (8x16 = 2 vertically-stacked 8x8 tiles).
    Game geometry (verified 2026-05-22): top tile shows its rows 0-3 at screen y124-127;
    bottom tile shows its rows 4-7 at y128-131. Returns (top_tile, bottom_tile) 32B each.
    Caller writes top_tile to the cell's upper slot, bottom_tile to the lower slot."""
    base=render_tile(ch,ink=ink)
    def gv(r,c):
        bi=r*4+c//2; return (base[bi]&0xF) if c%2==0 else (base[bi]>>4)
    def setv(t,r,c,v):
        bi=r*4+c//2
        if c%2==0: t[bi]=(t[bi]&0xF0)|v
        else: t[bi]=(t[bi]&0x0F)|(v<<4)
    top=bytearray(32); bot=bytearray(32)
    for r in range(4):
        for c in range(8):
            setv(top,r,c,gv(r,c))
            setv(bot,r+4,c,gv(r+4,c))
    return bytes(top),bytes(bot)
def preview(ch, fontsize=8, yoff=0):
    t=render_tile(ch,ink=1,fontsize=fontsize,yoff=yoff)
    out=[]
    for r in range(8):
        line=''
        for c in range(8):
            bi=r*4+c//2
            v=(t[bi]&0xF) if c%2==0 else (t[bi]>>4)
            line+='#' if v else '.'
        out.append(line)
    return out
if __name__=="__main__":
    import sys
    for ch in (sys.argv[1] if len(sys.argv)>1 else "게임보이가나다한글"):
        print("'%s' fs8:"%ch)
        for ln in preview(ch,8): print("  "+ln)
