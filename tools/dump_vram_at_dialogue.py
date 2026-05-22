import subprocess
import os

HARNESS_EXE = "/tmp/mgbah"
ROM_PATH = "original/Game Boy Wars Advance 1+2 (Japan).gba"
env = os.environ.copy()
env["DYLD_LIBRARY_PATH"] = "/opt/homebrew/lib"

def dump_vram():
    # Patch ROM to have known text
    with open(ROM_PATH, "rb") as f:
        data = bytearray(f.read())
    text = "アイウエオカキクケコサシスセソタ"
    sjis = text.encode("shift-jis")
    offset = 0xDF8E16
    for i in range(len(sjis)):
        data[offset + i] = sjis[i]
    patched_rom = "/tmp/patched_vram.gba"
    with open(patched_rom, "wb") as f:
        f.write(data)

    p = subprocess.Popen([HARNESS_EXE, patched_rom], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)
    
    commands = []
    # Mash A for a long time
    for i in range(100):
        commands.append("keys 1")
        commands.append("frames 10")
        commands.append("keys 0")
        commands.append("frames 50")
    
    commands.append("dumpvram /tmp/vram.bin")
    commands.append("quit")
    
    p.communicate("\n".join(commands))

dump_vram()
