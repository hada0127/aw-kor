import subprocess
import os

HARNESS_EXE = "/tmp/mgbah"
ROM_PATH = "/tmp/patched.gba" # Use the patched one from previous step
env = os.environ.copy()
env["DYLD_LIBRARY_PATH"] = "/opt/homebrew/lib"

def run_watch_ewram():
    p = subprocess.Popen([HARNESS_EXE, ROM_PATH], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)
    
    commands = [
        "watchaddr 02010CEC 32 r /tmp/ewram_access.log",
    ]
    for i in range(60):
        commands.append("keys 1")
        commands.append("frames 10")
        commands.append("keys 0")
        commands.append("frames 100")
    
    commands.append("quit")
    p.communicate("\n".join(commands))

run_watch_ewram()
