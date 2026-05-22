
import subprocess, sys, struct, os

HARNESS = "/tmp/mgbah"
ROM_PATH = "original/Game Boy Wars Advance 1+2 (Japan).gba"
BASE_FONT = 0x08B974D0
TEXT_ADDR = 0xDF8E16
# We use a known string to make mapping easy
TEST_TEXT = "アイウエオカキクケコサシスセソタ".encode("shift-jis")

def cmd(p, c):
    p.stdin.write(c + "\n")
    p.stdin.flush()
    return p.stdout.readline().strip()

def run_probe(slot):
    # Patch ROM
    with open(ROM_PATH, "rb") as f:
        rom = bytearray(f.read())
    
    # Rewrite text
    rom[TEXT_ADDR:TEXT_ADDR+len(TEST_TEXT)] = TEST_TEXT
    
    # Patch slot with marker
    offset = BASE_FONT - 0x08000000 + slot * 32
    rom[offset:offset+32] = b"\xAA" * 32
    
    tmp_rom = f"/tmp/probe_{slot}.gba"
    with open(tmp_rom, "wb") as f:
        f.write(rom)
    
    # Run mGBA
    swi_log = open("/dev/null", "w")
    p = subprocess.Popen([HARNESS, tmp_rom], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=swi_log,
                       env={"DYLD_LIBRARY_PATH":"/opt/homebrew/lib"}, text=True)
    
    # Skip to dialogue
    cmd(p, "frames 120")
    for _ in range(3): # Skip logos and title
        cmd(p, "keys 8"); cmd(p, "frames 10"); cmd(p, "keys 0"); cmd(p, "frames 120")
    for _ in range(2): # Select and start dialogue
        cmd(p, "keys 1"); cmd(p, "frames 10"); cmd(p, "keys 0"); cmd(p, "frames 150")
    
    # Wait for typewriter to finish
    cmd(p, "frames 300")
    
    vram_file = f"/tmp/vram_{slot}.bin"
    cmd(p, f"dumpvram {vram_file}")
    cmd(p, "quit")
    p.wait()
    os.remove(tmp_rom)
    
    # Analyze VRAM
    with open(vram_file, "rb") as f:
        vram = f.read()
    os.remove(vram_file)
    
    affected_tiles = []
    marker = b"\xAA" * 32
    idx = vram.find(marker)
    while idx != -1:
        affected_tiles.append(idx // 32)
        idx = vram.find(marker, idx + 1)
    
    return affected_tiles

if __name__ == "__main__":
    results = {}
    # Sample a few slots from each predicted range
    # Main Top: 128+, Main Bot: 144+
    # Extra Top: 291+, Extra Bot: 307+
    slots_to_probe = list(range(128, 135)) + list(range(144, 151)) + list(range(291, 298)) + list(range(307, 314))
    
    print("Slot | Affected VRAM Tiles | Interpretation")
    print("-" * 50)
    for s in slots_to_probe:
        tiles = run_probe(s)
        interp = ""
        for t in tiles:
            if t >= 20:
                char_idx = (t - 20) // 2
                part = "Main Top" if (t-20)%2==0 else "Main Bot"
                interp += f"Char {char_idx} {part}, "
            else:
                char_idx = t // 2
                part = "Extra Top" if t%2==0 else "Extra Bot"
                interp += f"Char {char_idx} {part}, "
        print(f"{s:4} | {tiles} | {interp}")
