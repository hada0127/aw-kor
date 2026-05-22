#!/usr/bin/env python3
import subprocess, sys, time

HARNESS="/tmp/mgbah"
ROM="original/Game Boy Wars Advance 1+2 (Japan).gba"
LOG_FILE="/tmp/trace.log"

def run_experiment():
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
    print("Navigating...")
    cmd("frames 320")
    press(8, 6, 120) # Start
    press(1, 6, 60)  # A
    press(1, 6, 60)  # A
    press(1, 6, 60)  # A
    press(8, 6, 60)  # Start
    press(1, 6, 60)  # A
    # Now at dialogue, wait a bit for it to settle
    cmd("frames 120")

    # Check IWRAM at this point
    print("Checking IWRAM 0x03006744...")
    cmd("dumpmem 0x03006700 256 /tmp/iwram_dialogue.bin")

    # Set Watchpoints
    print("Setting watchpoints...")
    # Font ROM Read (first 24 slots)
    cmd(f"watchaddr 0x08B98000 768 r {LOG_FILE}")
    # VRAM Write (Dialogue text area)
    cmd(f"watchaddr 0x06003940 100 w KEEP")
    # Breakpoint at H2's predicted blitter
    cmd(f"break 0x03006744 KEEP")

    print("Advancing dialogue with 'A' and capturing...")
    press(1, 6, 120) # Press A to progress/type

    cmd("quit")
    p.wait()
    print("Experiment finished.")

if __name__ == "__main__":
    run_experiment()
