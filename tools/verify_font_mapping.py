import os
from PIL import Image

FONT_BASE = 0xB974D0
SJIS_TABLE = 0xBE717A
NUM_GLYPHS = 256 # Just a sample

def dump_font():
    with open('original/Game Boy Wars Advance 1+2 (Japan).gba', 'rb') as f:
        f.seek(FONT_BASE)
        font_data = f.read(NUM_GLYPHS * 32)
        
        f.seek(SJIS_TABLE)
        sjis_data = f.read(NUM_GLYPHS * 2)

    # 4bpp, 8x8 tiles
    # We'll create a 16x16 grid of glyphs
    img = Image.new('L', (16*8, 16*8))
    pixels = img.load()
    
    for i in range(NUM_GLYPHS):
        glyph_bytes = font_data[i*32 : (i+1)*32]
        gx = i % 16
        gy = i // 16
        
        for y in range(8):
            for x in range(4):
                b = glyph_bytes[y*4 + x]
                # Low nibble first? Or high?
                p1 = (b & 0x0F) * 16
                p2 = (b >> 4) * 16
                pixels[gx*8 + x*2, gy*8 + y] = p1
                pixels[gx*8 + x*2 + 1, gy*8 + y] = p2
    
    img.save('/tmp/font_dump.png')
    print("Font dumped to /tmp/font_dump.png")

dump_font()
