import subprocess
import os

HARNESS_EXE = "/tmp/mgbah"
ROM_PATH = "original/Game Boy Wars Advance 1+2 (Japan).gba"
env = os.environ.copy()
env["DYLD_LIBRARY_PATH"] = "/opt/homebrew/lib"

def run_watch_text():
    p = subprocess.Popen([HARNESS_EXE, ROM_PATH], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)
    
    commands = [
        "watchaddr DF8E16 32 r /tmp/text_access.log",
        "frames 5000",
    ]
    for i in range(50):
        commands.append("keys 1")
        commands.append("frames 10")
        commands.append("keys 0")
        commands.append("frames 100")
    
    commands.append("quit")
    p.communicate("\n".join(commands))

run_watch_text()
