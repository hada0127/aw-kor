#!/usr/bin/env python3
import subprocess, sys, time, struct

HARNESS="/tmp/mgbah"
ROM="original/Game Boy Wars Advance 1+2 (Japan).gba"
LOG_FILE="/tmp/trace.log"

def run_experiment():
    p = subprocess.Popen([HARNESS, ROM], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         env={"DYLD_LIBRARY_PATH":"/opt/homebrew/lib"}, text=True)
    
    def cmd(c):
        p.stdin.write(c + "\n")
        p.stdin.flush()
        res = p.stdout.readline().strip()
        # print(f"CMD: {c} -> {res}")
        return res

    def press(mask, frames_hold=6, frames_after=60):
        cmd(f"keys {mask}")
        cmd(f"frames {frames_hold}")
        cmd(f"keys 0")
        cmd(f"frames {frames_after}")

    # Navigation
    print("Navigating...")
    cmd("frames 320")
    press(8, 6, 120) # Start
    press(1, 6, 60)  # A
    press(1, 6, 60)  # A
    press(1, 6, 60)  # A
    press(8, 6, 60)  # Start
    press(1, 6, 60)  # A
    press(1, 6, 120) # A - Should be at dialogue

    # Set Watchpoints
    print("Setting watchpoints...")
    # Font ROM Read (first 24 slots = 768 bytes)
    cmd(f"watchaddr 0x08B98000 768 r {LOG_FILE}")
    # VRAM Write (Dialogue text area)
    cmd(f"watchaddr 0x06003940 100 w KEEP")

    print("Running frames to capture blitter...")
    # Run 60 frames (1 second) while dialogue is typing
    cmd("frames 60")

    cmd("quit")
    p.wait()
    print("Experiment finished.")

if __name__ == "__main__":
    run_experiment()
