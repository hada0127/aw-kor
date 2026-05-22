import subprocess
import os
import time

ROM_PATH = "original/Game Boy Wars Advance 1+2 (Japan).gba"
HARNESS_EXE = "/tmp/mgbah"
OUTPUT_DIR = "/tmp/font_samples"
os.makedirs(OUTPUT_DIR, exist_ok=True)

TEXT_OFFSET = 0xDF8E16
FONT_BASE = 0x08B974D0

TEST_SEQUENCES = [
    "アイウエオカキクケコサシスセソタ",
    "あいうえおかきくけこさしすせそた",
    "１２３４５６７８９０！？。、：",
    "日一国会人年大十二本中長出三同政"
]

def patch_rom(target_path, text):
    with open(ROM_PATH, "rb") as f:
        data = bytearray(f.read())
    sjis = text.encode("shift-jis")
    # Fill with 32 bytes of our sequence
    for i in range(min(len(sjis), 32)):
        data[TEXT_OFFSET + i] = sjis[i]
    with open(target_path, "wb") as f:
        f.write(data)

def run_harness(rom_path, log_path):
    cmd = [HARNESS_EXE, rom_path]
    env = os.environ.copy()
    env["DYLD_LIBRARY_PATH"] = "/opt/homebrew/lib"
    
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)
    
    # Constant mashing for 5000 frames
    commands = [
        f"watchfont {FONT_BASE:08X} 1000 {log_path}",
    ]
    for i in range(50):
        commands.append("keys 1")
        commands.append("frames 10")
        commands.append("keys 0")
        commands.append("frames 100")
    
    commands.append("quit")
    stdout, stderr = p.communicate("\n".join(commands))
    return stdout, stderr

def parse_watch_log(log_path, text):
    if not os.path.exists(log_path): return []
    with open(log_path, "r") as f:
        lines = f.readlines()
    
    hits = []
    for line in lines:
        if "addr=" not in line: continue
        parts = line.split()
        regs = {}
        for p in parts:
            if "=" in p:
                k, v = p.split("=")
                regs[k] = int(v, 16)
        hits.append(regs)
    
    if not hits: return []
    
    sjis_bytes = text.encode("shift-jis")
    distinct_slots = []
    last_slot = -1
    for h in hits:
        slot = (h['addr'] - FONT_BASE) // 32
        if slot != last_slot:
            distinct_slots.append(slot)
            last_slot = slot
            
    samples = []
    for i, slot in enumerate(distinct_slots):
        if i >= len(text): break
        sjis = (sjis_bytes[i*2] << 8) | sjis_bytes[i*2+1]
        samples.append((sjis, slot))
        
    return samples

all_samples = []
for i, text in enumerate(TEST_SEQUENCES):
    rom_variant = os.path.join(OUTPUT_DIR, f"test_{i}.gba")
    log_variant = os.path.join(OUTPUT_DIR, f"test_{i}.log")
    print(f"Testing sequence: {text}")
    patch_rom(rom_variant, text)
    run_harness(rom_variant, log_variant)
    samples = parse_watch_log(log_variant, text)
    print(f"  Captured {len(samples)} samples")
    all_samples.extend(samples)

print("\nCollected Samples (SJIS | Slot):")
unique_samples = sorted(list(set(all_samples)))
for sjis, slot in unique_samples:
    print(f"0x{sjis:04X} | {slot}")

import csv
with open("data/sjis_slot_samples.csv", "w", newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["sjis", "slot"])
    for sjis, slot in unique_samples:
        writer.writerow([f"0x{sjis:04X}", slot])
