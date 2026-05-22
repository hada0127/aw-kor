#!/usr/bin/env python3
import subprocess, sys

HARNESS="/tmp/mgbah"
ROM="original/Game Boy Wars Advance 1+2 (Japan).gba"

def run():
    p = subprocess.Popen([HARNESS, ROM], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         env={"DYLD_LIBRARY_PATH":"/opt/homebrew/lib"}, text=True)
    def cmd(c):
        p.stdin.write(c + "\n")
        p.stdin.flush()
        return p.stdout.readline().strip()

    cmd("frames 10") # Let it boot a bit
    cmd("dumpmem 0x03006700 256 /tmp/iwram_blitter.bin")
    cmd("quit")
    p.wait()

run()
