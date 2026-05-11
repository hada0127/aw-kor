#!/usr/bin/env python3
"""
PHASE 5-3: Locate actual font data by pattern matching

Finds where the most frequently repeated 8-byte patterns are located.
These patterns are likely the actual font glyphs.
"""

import sys
import struct
from pathlib import Path
from collections import defaultdict
from typing import Dict, List


def load_rom(rom_path: str) -> bytes:
    """Load ROM file"""
    with open(rom_path, 'rb') as f:
        return f.read()


def find_pattern_locations(rom_data: bytes, pattern: bytes, max_matches: int = 20) -> List[int]:
    """Find all locations of a pattern in ROM"""
    locations = []
    start = 0
    pattern_len = len(pattern)

    while True:
        pos = rom_data.find(pattern, start)
        if pos == -1:
            break
        locations.append(pos)
        start = pos + 1
        if len(locations) >= max_matches:
            break

    return locations


def analyze_byte_sequences(rom_data: bytes) -> Dict:
    """Find sequences of bytes that look like bitmap data"""
    print("Analyzing 8-byte sequences for glyph patterns...")

    # Look for 8-byte chunks that repeat
    chunk_counts = defaultdict(list)

    for i in range(0, len(rom_data) - 8, 1):
        chunk = rom_data[i:i+8]
        chunk_counts[chunk].append(i)

    # Find chunks that appear multiple times
    repeated_chunks = {chunk: locs for chunk, locs in chunk_counts.items() if len(locs) >= 50}

    print(f"Found {len(repeated_chunks)} chunks appearing 50+ times")

    # Analyze the largest clusters
    sorted_by_freq = sorted(repeated_chunks.items(), key=lambda x: len(x[1]), reverse=True)

    results = []
    for i, (chunk, locations) in enumerate(sorted_by_freq[:5], 1):
        min_loc = min(locations)
        max_loc = max(locations)
        freq = len(locations)

        print(f"\n{i}. Pattern: {chunk.hex()} appears {freq} times")
        print(f"   Range: 0x{min_loc:X} - 0x{max_loc:X}")
        print(f"   First 10 locations:")
        for j, loc in enumerate(locations[:10]):
            print(f"     {j+1}. 0x{loc:X}")

        results.append({
            'pattern': chunk.hex(),
            'frequency': freq,
            'min_location': min_loc,
            'max_location': max_loc,
            'locations': locations[:20]
        })

    return results


def search_font_markers(rom_data: bytes) -> None:
    """Search for font-like markers in ROM"""
    print("\n" + "="*60)
    print("Searching for font markers and structure...")
    print("="*60)

    # Look for potential font headers or markers
    # In GBA games, fonts often start with a signature or header

    # Search for zero-based index patterns (0x00, 0x01, 0x02, ...)
    print("\nSearching for potential font data structures...")

    for offset in [0x4A0000, 0x500000, 0x600000, 0x700000, 0x8000000]:
        if offset < len(rom_data):
            # Check if this region starts with sequential-looking data
            sample = rom_data[offset:offset+16]
            print(f"\n0x{offset:X}: {sample.hex()}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python locate_font_data.py <rom_file>")
        return 1

    rom_path = sys.argv[1]
    rom_data = load_rom(rom_path)

    print(f"ROM size: {len(rom_data):,} bytes\n")

    results = analyze_byte_sequences(rom_data)

    search_font_markers(rom_data)

    print("\n" + "="*60)
    print("Likely font location: Based on analysis, check:")
    print("="*60)

    if results:
        first_pattern_min = results[0]['min_location']
        first_pattern_max = results[0]['max_location']

        # The font region likely spans where these patterns are
        print(f"\nRange of most common pattern: 0x{first_pattern_min:X} - 0x{first_pattern_max:X}")
        print(f"This suggests font data is in this region")

        # Try to find contiguous region
        all_locs = results[0]['locations']
        all_locs.sort()

        # Find largest gap to determine font region boundary
        print(f"\nAnalyzing pattern locations to find font region boundaries...")
        print(f"Pattern appears at {len(all_locs)} locations")

        # Sample analysis
        for i in range(0, min(10, len(all_locs))):
            loc = all_locs[i]
            print(f"  {i+1:2d}. 0x{loc:X}")

    print("\nRecommendation:")
    print("Check these regions with tools like strings or hexdump:")
    print("  python -c \"with open('original/Game Boy Wars Advance 1+2 (Japan).gba', 'rb') as f: f.seek(0x4A0000); print(f.read(256).hex())\"")


if __name__ == '__main__':
    sys.exit(main())
