#!/usr/bin/env python3
import subprocess, sys, time, struct

HARNESS="/tmp/mgbah"
ROM="original/Game Boy Wars Advance 1+2 (Japan).gba"

def take_shot(p, cmd, fn):
    print(f"Taking screenshot: {fn}")
    cmd(f"shot {fn}")

def run_experiment():
    p = subprocess.Popen([HARNESS, ROM], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         env={"DYLD_LIBRARY_PATH":"/opt/homebrew/lib"}, text=True)
    
    def cmd(c):
        p.stdin.write(c + "\n")
        p.stdin.flush()
        res = p.stdout.readline().strip()
        return res

    def press(mask, frames_hold=6, frames_after=60):
        cmd(f"keys {mask}")
        cmd(f"frames {frames_hold}")
        cmd(f"keys 0")
        cmd(f"frames {frames_after}")

    # Navigation
    print("Navigating...")
    cmd("frames 320")
    take_shot(p, cmd, "/tmp/shot1.raw")
    press(8, 6, 120) # Start
    take_shot(p, cmd, "/tmp/shot2.raw")
    press(1, 6, 60)  # A
    press(1, 6, 60)  # A
    press(1, 6, 60)  # A
    take_shot(p, cmd, "/tmp/shot3.raw")
    press(8, 6, 60)  # Start
    press(1, 6, 60)  # A
    press(1, 6, 120) # A
    take_shot(p, cmd, "/tmp/shot4.raw")

    cmd("quit")
    p.wait()

if __name__ == "__main__":
    run_experiment()
