import subprocess
import os

ROM_PATH = "original/Game Boy Wars Advance 1+2 (Japan).gba"
HARNESS_EXE = "/tmp/mgbah"
env = os.environ.copy()
env["DYLD_LIBRARY_PATH"] = "/opt/homebrew/lib"

def verify():
    with open(ROM_PATH, "rb") as f:
        data = bytearray(f.read())

    # Write marker for slot 108 (char '一')
    # base 0xB974D0 + 108*32 = 0xB98250
    offset = 0xB974D0 + 108*32
    for i in range(32):
        data[offset + i] = 0xFF

    # Rewrite Welcome dialogue at 0xDF8E16
    text_offset = 0xDF8E16
    sjis = b'\x88\xea' # '一'
    data[text_offset] = sjis[0]
    data[text_offset+1] = sjis[1]

    verify_rom = "/tmp/verify.gba"
    with open(verify_rom, "wb") as f:
        f.write(data)

    p = subprocess.Popen([HARNESS_EXE, verify_rom], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)
    
    commands = [
        "frames 2000",
        "keys 1", # A
        "frames 10",
        "keys 0",
        "frames 2000",
        "keys 1", # A
        "frames 10",
        "keys 0",
        "frames 2000",
        "shot /tmp/verify_marker.raw",
        "quit"
    ]
    
    stdout, stderr = p.communicate("\n".join(commands))
    print("Verification shot taken.")

verify()
