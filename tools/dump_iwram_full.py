#!/usr/bin/env python3
import subprocess, sys, time

HARNESS="/tmp/mgbah"
ROM="original/Game Boy Wars Advance 1+2 (Japan).gba"

def run():
    p = subprocess.Popen([HARNESS, ROM], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         env={"DYLD_LIBRARY_PATH":"/opt/homebrew/lib"}, text=True)
    def cmd(c):
        p.stdin.write(c + "\n")
        p.stdin.flush()
        return p.stdout.readline().strip()

    def press(mask, frames_hold=6, frames_after=60):
        cmd(f"keys {mask}")
        cmd(f"frames {frames_hold}")
        cmd(f"keys 0")
        cmd(f"frames {frames_after}")

    # Navigation
    cmd("frames 320")
    press(8, 6, 120) # Start
    press(1, 6, 60)  # A
    press(1, 6, 60)  # A
    press(1, 6, 60)  # A
    press(8, 6, 60)  # Start
    press(1, 6, 60)  # A
    cmd("frames 120")

    print("Dumping IWRAM from 0x03006500...")
    cmd("dumpmem 0x03006500 1024 /tmp/iwram_full.bin")
    cmd("quit")
    p.wait()

run()
