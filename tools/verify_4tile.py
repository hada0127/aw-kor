
import subprocess, struct, os
from PIL import Image, ImageFont, ImageDraw

HARNESS = "/tmp/mgbah"
ROM_PATH = "original/Game Boy Wars Advance 1+2 (Japan).gba"
FONT_BASE = 0x08B974D0
TEXT_ADDR = 0xDF8E16

# Slots for 'エ' (SJIS 0x8347) relative to 'ア' at slot 128
SLOTS = {
    "top_extra": 294,
    "top":         131,
    "bottom":      147,
    "bot_extra":   310
}

def render_4tiles(ch, ink=10):
    # Render 11x8 glyph
    img = Image.new("L", (8, 11), 0)
    d = ImageDraw.Draw(img)
    # Use a standard font
    try:
        f = ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", 10)
    except:
        f = ImageFont.load_default()
    
    d.text((0, -1), ch, fill=255, font=f)
    px = img.load()
    
    def make_tile(): return bytearray(32)
    def setv(t, r, c, v):
        bi = r * 4 + c // 2
        if c % 2 == 0: t[bi] = (t[bi] & 0xF0) | v
        else: t[bi] = (t[bi] & 0x0F) | (v << 4)

    t_ex = make_tile()
    t_top = make_tile()
    t_bot = make_tile()
    t_bex = make_tile()
    
    for c in range(8):
        # Row 0 of glyph -> Row 7 of TopExtra
        v = ink if px[c, 0] > 128 else 0
        setv(t_ex, 7, c, v)
        
        # Rows 1-4 of glyph -> Rows 0-3 of Top
        for r in range(4):
            v = ink if px[c, r+1] > 128 else 0
            setv(t_top, r, c, v)
            
        # Rows 5-8 of glyph -> Rows 0-3 of Bottom
        for r in range(4):
            v = ink if px[c, r+5] > 128 else 0
            setv(t_bot, r, c, v)
            
        # Rows 9-10 of glyph -> Rows 0-1 of BotExtra
        for r in range(2):
            v = ink if px[c, r+9] > 128 else 0
            setv(t_bex, r, c, v)
            
    return bytes(t_ex), bytes(t_top), bytes(t_bot), bytes(t_bex)

def verify():
    # 1. Generate tiles
    tiles = render_4tiles("한")
    
    # 2. Patch ROM
    with open(ROM_PATH, "rb") as f:
        rom = bytearray(f.read())
    
    # Rewrite text to focus on 'エ'
    # 'エ' is at index 3 in the string we used.
    # We'll use "エエエエエ" to be sure.
    text = "エエエエエ".encode("shift-jis")
    rom[TEXT_ADDR:TEXT_ADDR+len(text)] = text
    
    # Patch slots
    for key, slot in SLOTS.items():
        offset = FONT_BASE - 0x08000000 + slot * 32
        rom[offset:offset+32] = tiles[list(SLOTS.keys()).index(key)]
        
    out_rom = "/tmp/verify_hangul.gba"
    with open(out_rom, "wb") as f:
        f.write(rom)
        
    # 3. Run and take shot
    swi_log = open("/tmp/swi_verify.log", "w")
    p = subprocess.Popen([HARNESS, out_rom], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=swi_log,
                       env={"DYLD_LIBRARY_PATH":"/opt/homebrew/lib"}, text=True)
    
    def cmd(c):
        p.stdin.write(c + "\n")
        p.stdin.flush()
        return p.stdout.readline().strip()

    cmd("frames 120")
    for _ in range(3): # Skip logos and title
        cmd("keys 8"); cmd("frames 10"); cmd("keys 0"); cmd("frames 120")
    for _ in range(2): # Select and start dialogue
        cmd("keys 1"); cmd("frames 10"); cmd("keys 0"); cmd("frames 150")
    cmd("frames 300")
    
    cmd("shot verify_hangul.png.raw")
    cmd("quit")
    p.wait()
    
    # Convert raw to png (reuse raw2png logic or just use PIL)
    d = open("verify_hangul.png.raw", "rb").read()
    w, h = struct.unpack("<HH", d[:4])
    cs = d[4]
    px = d[5:]
    img = Image.new("RGB", (w, h))
    o = img.load()
    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * cs
            o[x, y] = (px[idx], px[idx+1], px[idx+2])
    img.save("verify_hangul.png")
    print("Verification shot saved to verify_hangul.png")

if __name__ == "__main__":
    verify()
