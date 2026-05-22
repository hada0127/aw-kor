#!/usr/bin/env python3
"""8x16 셀에 풀크기로 알파벳/숫자 렌더링 → top+bottom 페어 8x8 타일로 분할."""
from PIL import Image, ImageDraw, ImageFont

_FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"

def render_8x16(ch, ink=10):
    """8x16 픽셀로 글자 렌더링, top tile (8x8) + bot tile (8x8) 반환."""
    BIG = 64
    big = Image.new("L", (BIG, BIG), 0)
    d = ImageDraw.Draw(big)
    # 큰 폰트로 그리고 8x16 영역에 맞게 LANCZOS 리사이즈
    f = ImageFont.truetype(_FONT_PATH, 48)
    bb = d.textbbox((0, 0), ch, font=f)
    d.text((-bb[0]+2, -bb[1]+2), ch, fill=255, font=f)
    cb = big.getbbox()
    if cb:
        big = big.crop(cb)
    # 8x16 으로 리사이즈
    glyph = big.resize((8, 16), Image.LANCZOS)
    px = glyph.load()

    def make_tile(rows):
        t = bytearray(32)
        for r in range(8):
            for c in range(8):
                on = 1 if px[c, rows[r]] >= 90 else 0
                v = ink if on else 0
                bi = r*4 + c//2
                if c%2 == 0: t[bi] = (t[bi]&0xF0) | v
                else: t[bi] = (t[bi]&0x0F) | (v<<4)
        return bytes(t)

    top = make_tile(list(range(0, 8)))    # 위 8행
    bot = make_tile(list(range(8, 16)))   # 아래 8행
    return top, bot

if __name__ == "__main__":
    import sys
    ch = sys.argv[1] if len(sys.argv) > 1 else 'A'
    top, bot = render_8x16(ch)
    def show(name, t):
        print(f'--- {name} ---')
        for r in range(8):
            line = ''
            for c in range(8):
                bi = r*4 + c//2
                v = (t[bi]&0xF) if c%2==0 else (t[bi]>>4)
                line += '#' if v else '.'
            print(f'  {line}')
    show('top', top)
    show('bot', bot)
