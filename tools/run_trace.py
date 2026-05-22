import subprocess
import os

HARNESS_EXE = "/tmp/mgbah"
ROM_PATH = "/tmp/patched.gba"
env = os.environ.copy()
env["DYLD_LIBRARY_PATH"] = "/opt/homebrew/lib"

def run_trace():
    p = subprocess.Popen([HARNESS_EXE, ROM_PATH], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)
    
    commands = [
        "break 08B12AB6 /tmp/trace.log",
        "break 08B12ADE KEEP",
    ]
    for i in range(50):
        commands.append("keys 1")
        commands.append("frames 10")
        commands.append("keys 0")
        commands.append("frames 100")
    
    commands.append("quit")
    p.communicate("\n".join(commands))

run_trace()
