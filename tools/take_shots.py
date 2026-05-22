import subprocess
import os

HARNESS_EXE = "/tmp/mgbah"
ROM_PATH = "original/Game Boy Wars Advance 1+2 (Japan).gba"
env = os.environ.copy()
env["DYLD_LIBRARY_PATH"] = "/opt/homebrew/lib"

def take_shot(text, filename):
    with open(ROM_PATH, "rb") as f:
        data = bytearray(f.read())
    sjis = text.encode("shift-jis")
    offset = 0xDF8E16
    for i in range(len(sjis)):
        data[offset + i] = sjis[i]
    temp_rom = "/tmp/temp.gba"
    with open(temp_rom, "wb") as f:
        f.write(data)

    p = subprocess.Popen([HARNESS_EXE, temp_rom], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)
    
    commands = []
    for i in range(50):
        commands.append("keys 1")
        commands.append("frames 10")
        commands.append("keys 0")
        commands.append("frames 100")
    
    commands.append(f"shot {filename}")
    commands.append("quit")
    p.communicate("\n".join(commands))

take_shot("アイウエオ", "/tmp/shot_test0.raw")
take_shot("あいうえお", "/tmp/shot_test1.raw")
