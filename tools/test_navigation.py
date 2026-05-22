import subprocess
import os

HARNESS_EXE = "/tmp/mgbah"
ROM_PATH = "original/Game Boy Wars Advance 1+2 (Japan).gba"
env = os.environ.copy()
env["DYLD_LIBRARY_PATH"] = "/opt/homebrew/lib"

def run_nav_test():
    # Patch ROM first
    with open(ROM_PATH, "rb") as f:
        data = bytearray(f.read())
    text = "アイウエオカキクケコサシスセソタ"
    sjis = text.encode("shift-jis")
    offset = 0xDF8E16
    for i in range(len(sjis)):
        data[offset + i] = sjis[i]
    patched_rom = "/tmp/patched.gba"
    with open(patched_rom, "wb") as f:
        f.write(data)

    p = subprocess.Popen([HARNESS_EXE, patched_rom], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)
    
    commands = []
    for i in range(60): # 60 * 110 = 6600 frames
        commands.append("keys 1")
        commands.append("frames 10")
        commands.append("keys 0")
        commands.append("frames 100")
    
    commands.append("dumpmem 03000000 32768 /tmp/iwram.bin")
    commands.append("dumpmem 02000000 262144 /tmp/ewram.bin")
    commands.append("quit")
    
    stdout, stderr = p.communicate("\n".join(commands))
    print(stdout)

run_nav_test()
