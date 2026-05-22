import subprocess
import os

HARNESS_EXE = "/tmp/mgbah"
ROM_PATH = "original/Game Boy Wars Advance 1+2 (Japan).gba"
env = os.environ.copy()
env["DYLD_LIBRARY_PATH"] = "/opt/homebrew/lib"

def find_dialogue():
    p = subprocess.Popen([HARNESS_EXE, ROM_PATH], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)
    
    commands = []
    for i in range(40): # 20000 frames total
        commands.append("frames 500")
        commands.append(f"shot /tmp/shot_nav_{i:02d}.raw")
        commands.append("keys 9") # Start + A
        commands.append("frames 10")
        commands.append("keys 0")
    
    commands.append("quit")
    p.communicate("\n".join(commands))

find_dialogue()
