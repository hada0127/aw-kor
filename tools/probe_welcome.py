
import subprocess, sys, struct, time, os
from PIL import Image

HARNESS="/tmp/mgbah"
ROM="original/Game Boy Wars Advance 1+2 (Japan).gba"
KEYS=dict(A=1,B=2,SEL=4,START=8,RIGHT=16,LEFT=32,UP=64,DOWN=128,R=256,L=512)

def run_to_welcome(rom_path, out_shot):
    swi_log = open("/tmp/swi_probe.log", "w")
    p = subprocess.Popen([HARNESS, rom_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=swi_log,
                       env={"DYLD_LIBRARY_PATH":"/opt/homebrew/lib"}, text=True)
    
    def cmd(c):
        p.stdin.write(c+"\n")
        p.stdin.flush()
        return p.stdout.readline().strip()

    def press(mask, hold=10, after=60):
        cmd(f"keys {mask}")
        cmd(f"frames {hold}")
        cmd("keys 0")
        cmd(f"frames {after}")

    # Wait for initial load
    cmd("frames 120")
    
    # Skip logos
    press(KEYS['START'], after=120)
    press(KEYS['START'], after=120)
    press(KEYS['START'], after=180) # Title screen
    
    # Select New Game? Or just mash A
    press(KEYS['A'], after=120)
    press(KEYS['A'], after=120)
    press(KEYS['A'], after=300) # Should be in dialogue now
    
    # Take shot
    cmd(f"shot {out_shot}.raw")
    cmd("quit")
    p.wait()
    
    # Convert raw to png
    raw2png(f"{out_shot}.raw", out_shot)

def raw2png(raw, out):
    d = open(raw, 'rb').read()
    if len(d) < 5: return
    w, h = struct.unpack("<HH", d[:4])
    cs = d[4]
    px = d[5:]
    img = Image.new('RGB', (w, h))
    o = img.load()
    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * cs
            # libmgba color_t is often ABGR or ARGB
            # Let's assume RGB for now and fix if colors are weird
            o[x, y] = (px[idx+0], px[idx+1], px[idx+2])
    img.save(out)

if __name__ == "__main__":
    run_to_welcome(ROM, "welcome_probe.png")
