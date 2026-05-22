#!/usr/bin/env python3
"""Automated discovery of SJIS-to-slot mapping for katakana.
For each katakana, modify welcome dialog to start with that char, capture blitter source ROM addr.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import subprocess
import json

# All katakana SJIS codes
KATAKANA = [
    ('ア', 0x8341), ('イ', 0x8343), ('ウ', 0x8345), ('エ', 0x8347), ('オ', 0x8349),
    ('カ', 0x834A), ('キ', 0x834C), ('ク', 0x834E), ('ケ', 0x8350), ('コ', 0x8352),
    ('サ', 0x8354), ('シ', 0x8356), ('ス', 0x8358), ('セ', 0x835A), ('ソ', 0x835C),
    ('タ', 0x835E), ('チ', 0x8360), ('ツ', 0x8362), ('テ', 0x8364), ('ト', 0x8366),
    ('ナ', 0x8369), ('ニ', 0x836A), ('ヌ', 0x836C), ('ネ', 0x836D), ('ノ', 0x836E),
    ('ハ', 0x836F), ('ヒ', 0x8371), ('フ', 0x8374), ('ヘ', 0x8376), ('ホ', 0x8378),
    ('マ', 0x837D), ('ミ', 0x837E), ('ム', 0x8380), ('メ', 0x8381), ('モ', 0x8382),
    ('ヤ', 0x8384), ('ユ', 0x8386), ('ヨ', 0x8388),
    ('ラ', 0x8389), ('リ', 0x838A), ('ル', 0x838B), ('レ', 0x838C), ('ロ', 0x838D),
    ('ワ', 0x838E), ('ヲ', 0x8392), ('ン', 0x8393),
]

def build_test_rom(sjis_code, output):
    """Build ROM with welcome dialog FIRST char replaced by given SJIS code."""
    rom = bytearray(open("original/Game Boy Wars Advance 1+2 (Japan).gba", "rb").read())
    # Welcome dialog at 0xDF8E16. Replace first 2 bytes (= first char).
    rom[0xDF8E16] = sjis_code >> 8
    rom[0xDF8E17] = sjis_code & 0xFF
    chk = (-(0x19 + sum(rom[0xA0:0xBD]))) & 0xFF
    rom[0xBD] = chk
    open(output, "wb").write(rom)

def capture_first_blitter(rom_path):
    """Run ROM through navigation to welcome dialog, BP at blitter, capture first r7 source."""
    p = subprocess.Popen(["/tmp/mgbah", rom_path, "/tmp/cap.log"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        env={"DYLD_LIBRARY_PATH": "/opt/homebrew/lib"}, text=True)
    def cmd(c):
        p.stdin.write(c + "\n")
        p.stdin.flush()
        return p.stdout.readline().strip()
    def press(m, h=6, a=50):
        cmd(f"keys {m}")
        cmd(f"frames {h}")
        cmd("keys 0")
        cmd(f"frames {a}")
    cmd("frames 320")
    press(8)  # start
    press(1); press(1); press(1)  # A x3
    press(8)  # start
    press(1); press(1)  # A x2 → welcome dialog
    # BP at blitter
    cmd("break 03006744 /tmp/cap_bp.txt")
    cmd("frames 60")  # let typewriter run
    cmd("quit")
    # Read BP captures
    lines = open("/tmp/cap_bp.txt").readlines()
    if not lines:
        return None
    # First line has the first capture
    d = dict(x.split('=') for x in lines[0].split() if '=' in x)
    return d.get('r7')

def main():
    os.makedirs("/tmp/kata_test", exist_ok=True)
    results = {}
    for kana, sjis in KATAKANA:
        rom_path = f"/tmp/kata_test/{sjis:04X}.gba"
        build_test_rom(sjis, rom_path)
        src = capture_first_blitter(rom_path)
        if src:
            results[kana] = {"sjis": f"0x{sjis:04X}", "rom_src": src}
            print(f"  {kana} (0x{sjis:04X}) → {src}")
        else:
            print(f"  {kana} (0x{sjis:04X}) → NO CAPTURE")
        # Save partial results
        with open("output/katakana_slot_mapping.json", "w") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nTotal mapped: {len(results)}")

if __name__ == "__main__":
    main()
