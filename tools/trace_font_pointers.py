#!/usr/bin/env python3
"""
PHASE 5-3: Trace pointer arrays to find font data

Follows pointer arrays to identify where font bitmap data is located.
"""

import sys
import struct
from pathlib import Path
from typing import List, Dict, Tuple


def load_rom(rom_path: str) -> bytes:
    """Load ROM file"""
    with open(rom_path, 'rb') as f:
        return f.read()


def trace_pointer_array(rom_data: bytes, array_start: int, num_pointers: int) -> List[Tuple[int, int]]:
    """Trace a pointer array to find targets"""
    rom_size = len(rom_data)
    targets = []

    for i in range(num_pointers):
        ptr_offset = array_start + (i * 4)
        if ptr_offset + 4 > rom_size:
            break

        ptr_value = struct.unpack('<I', rom_data[ptr_offset:ptr_offset+4])[0]
        targets.append((ptr_offset, ptr_value))

    return targets


def analyze_target_region(rom_data: bytes, address: int, size: int = 128) -> Dict:
    """Analyze a target region to see if it looks like bitmap data"""
    if address + size > len(rom_data):
        size = len(rom_data) - address

    data = rom_data[address:address+size]

    # Calculate entropy
    byte_counts = [0] * 256
    for byte in data:
        byte_counts[byte] += 1

    entropy = 0
    for count in byte_counts:
        if count > 0:
            p = count / len(data)
            import math
            entropy -= p * math.log2(p)

    # Check for repetition
    repetition_score = 0
    for i in range(0, len(data) - 8, 8):
        chunk = data[i:i+8]
        for j in range(i+8, len(data) - 8, 8):
            if data[j:j+8] == chunk:
                repetition_score += 1

    return {
        'entropy': entropy,
        'repetition_score': repetition_score,
        'byte_range': (min(data), max(data)),
        'zero_count': data.count(0),
        'zero_ratio': data.count(0) / len(data)
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python trace_font_pointers.py <rom_file>")
        return 1

    rom_path = sys.argv[1]
    rom_data = load_rom(rom_path)
    rom_size = len(rom_data)

    print(f"ROM loaded: {rom_size:,} bytes")
    print()

    # Check key pointer arrays found in analysis
    candidate_arrays = [
        (0x13524, 93),  # From analysis: 93 pointers
        (0x13528, 92),  # 92 pointers
        (0x1352c, 91),  # 91 pointers
    ]

    for array_addr, num_ptrs in candidate_arrays:
        print(f"\n{'='*60}")
        print(f"Pointer Array at 0x{array_addr:X} ({num_ptrs} pointers)")
        print(f"{'='*60}")

        targets = trace_pointer_array(rom_data, array_addr, min(10, num_ptrs))

        print(f"First 10 pointers:")
        for offset, target in targets:
            in_range = target < rom_size
            status = "VALID" if in_range else "OUT OF RANGE"
            print(f"  0x{offset:X}: -> 0x{target:08X} [{status}]")

        # Check where pointers tend to go
        valid_targets = [t for _, t in targets if t < rom_size and t > 0x8000]
        if valid_targets:
            min_target = min(valid_targets)
            max_target = max(valid_targets)
            avg_target = sum(valid_targets) // len(valid_targets)

            print(f"\nTarget range: 0x{min_target:X} - 0x{max_target:X}")
            print(f"Average target: 0x{avg_target:X}")

            # Analyze the target region
            analysis = analyze_target_region(rom_data, min_target, 256)
            print(f"\nTarget region analysis:")
            print(f"  Entropy: {analysis['entropy']:.2f}")
            print(f"  Repetition score: {analysis['repetition_score']}")
            print(f"  Byte range: 0x{analysis['byte_range'][0]:02X} - 0x{analysis['byte_range'][1]:02X}")
            print(f"  Zero bytes: {analysis['zero_count']} ({analysis['zero_ratio']*100:.1f}%)")

            # Try to estimate font region
            if analysis['repetition_score'] > 5 and 0 < analysis['entropy'] < 5:
                print(f"  -> Likely font data region!")

    print("\n" + "="*60)
    print("Font candidate regions to verify:")
    print("="*60)

    # Try common GBA font locations
    print("\nCommon GBA font locations (for verification):")
    common_locations = [
        (0x4A0000, "Typical game asset area 1"),
        (0x500000, "Typical game asset area 2"),
        (0x600000, "ROM data area"),
        (0x700000, "Extended ROM area"),
    ]

    for addr, desc in common_locations:
        if addr < rom_size:
            analysis = analyze_target_region(rom_data, addr, 256)
            print(f"\n0x{addr:X}: {desc}")
            print(f"  Entropy: {analysis['entropy']:.2f}, Zero ratio: {analysis['zero_ratio']*100:.1f}%")


if __name__ == '__main__':
    sys.exit(main())
