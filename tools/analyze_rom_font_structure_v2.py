#!/usr/bin/env python3
"""
PHASE 5-3: ROM font structure automatic analysis

Analyzes font data location and structure from Game Wars ROM using Python only.
Output is written to a file to avoid console encoding issues.
"""

import sys
import struct
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Tuple, Dict


class ROMFontAnalyzer:
    """GBA ROM font structure analyzer"""

    def __init__(self, rom_path: str):
        self.rom_path = rom_path
        self.rom_data = None
        self.rom_size = 0
        self.findings = {
            'potential_font_regions': [],
            'repeated_patterns': [],
            'bitmap_regions': [],
            'pointer_patterns': [],
            'text_clusters': []
        }
        self.output_lines = []

    def log(self, msg: str):
        """Log message to output"""
        self.output_lines.append(msg)
        try:
            print(msg)
        except:
            print(msg.encode('ascii', errors='replace').decode('ascii'))

    def load_rom(self) -> bool:
        """Load ROM file"""
        try:
            with open(self.rom_path, 'rb') as f:
                self.rom_data = f.read()
            self.rom_size = len(self.rom_data)
            self.log(f"[INFO] ROM loaded: {self.rom_size:,} bytes ({self.rom_size/1024/1024:.1f}MB)")
            return True
        except Exception as e:
            self.log(f"[ERROR] ROM load failed: {e}")
            return False

    def find_repeated_patterns(self, min_size=16, min_count=50) -> List[Tuple]:
        """Find repeated patterns (potential bitmap glyphs)"""
        self.log("\n[ANALYSIS 1] Searching for repeated patterns (bitmap glyph candidates)...")

        patterns = defaultdict(list)
        chunk_size = 8  # 8-byte chunks

        for i in range(0, len(self.rom_data) - chunk_size, chunk_size):
            chunk = self.rom_data[i:i+chunk_size]
            patterns[chunk].append(i)

        # Filter to sufficiently repeated patterns
        repeated = []
        for pattern, addresses in patterns.items():
            if len(addresses) >= min_count:
                entropy = self._calculate_entropy(pattern)
                if entropy > 2:
                    repeated.append({
                        'pattern': pattern.hex(),
                        'count': len(addresses),
                        'first_address': hex(addresses[0]),
                        'entropy': entropy
                    })

        # Sort by frequency
        repeated.sort(key=lambda x: x['count'], reverse=True)

        self.log(f"[RESULT] Found {len(repeated)} repeated patterns")
        for i, item in enumerate(repeated[:10], 1):
            self.log(f"  {i}. Pattern: {item['pattern'][:16]}... Freq: {item['count']} Entropy: {item['entropy']:.2f}")

        self.findings['repeated_patterns'] = repeated
        return repeated

    def find_bitmap_regions(self) -> List[Dict]:
        """Find bitmap data regions"""
        self.log("\n[ANALYSIS 2] Searching for bitmap data regions...")

        regions = []
        region_start = None
        region_entropy = 0

        # Sliding window entropy calculation
        window_size = 128

        for i in range(0, len(self.rom_data) - window_size, window_size):
            window = self.rom_data[i:i+window_size]
            entropy = self._calculate_entropy(window)

            # High entropy = bitmap likely
            if entropy > 5:
                if region_start is None:
                    region_start = i
                    region_entropy = entropy
            else:
                if region_start is not None:
                    regions.append({
                        'start': hex(region_start),
                        'end': hex(i),
                        'size': i - region_start,
                        'avg_entropy': region_entropy
                    })
                    region_start = None

        self.log(f"[RESULT] Found {len(regions)} potential bitmap regions")
        for i, region in enumerate(regions[:5], 1):
            size_kb = region['size'] / 1024
            self.log(f"  {i}. {region['start']} ~ {region['end']} ({size_kb:.1f}KB, entropy: {region['avg_entropy']:.2f})")

        self.findings['bitmap_regions'] = regions
        return regions

    def find_shift_jis_patterns(self) -> List[Dict]:
        """Find Shift-JIS text patterns (text clusters)"""
        self.log("\n[ANALYSIS 3] Searching for Shift-JIS text clusters...")

        clusters = []
        i = 0

        while i < len(self.rom_data) - 1:
            b1 = self.rom_data[i]

            # Check Shift-JIS first byte
            if (0x81 <= b1 <= 0x9F) or (0xE0 <= b1 <= 0xEF):
                if i + 1 < len(self.rom_data):
                    b2 = self.rom_data[i + 1]

                    # Check Shift-JIS second byte
                    if (0x40 <= b2 <= 0x7E) or (0x80 <= b2 <= 0xFC):
                        cluster_start = i
                        cluster_data = bytearray()
                        char_count = 0

                        # Collect consecutive Shift-JIS characters
                        while i < len(self.rom_data) - 1:
                            b1 = self.rom_data[i]
                            if (0x81 <= b1 <= 0x9F) or (0xE0 <= b1 <= 0xEF):
                                if i + 1 < len(self.rom_data):
                                    b2 = self.rom_data[i + 1]
                                    if (0x40 <= b2 <= 0x7E) or (0x80 <= b2 <= 0xFC):
                                        cluster_data.append(b1)
                                        cluster_data.append(b2)
                                        i += 2
                                        char_count += 1
                                    else:
                                        break
                                else:
                                    break
                            else:
                                break

                        # Record only sufficiently long clusters
                        if char_count >= 5:
                            try:
                                decoded = cluster_data.decode('shift_jis', errors='ignore')
                                clusters.append({
                                    'address': hex(cluster_start),
                                    'length': len(cluster_data),
                                    'char_count': char_count,
                                    'text': decoded[:50] if len(decoded) > 50 else decoded
                                })
                            except:
                                pass
                        continue

            i += 1

        # Sort by size
        clusters.sort(key=lambda x: x['length'], reverse=True)

        self.log(f"[RESULT] Found {len(clusters)} text clusters")
        for i, cluster in enumerate(clusters[:10], 1):
            self.log(f"  {i}. {cluster['address']}: {cluster['char_count']} chars ({cluster['length']}bytes)")

        self.findings['text_clusters'] = clusters
        return clusters

    def find_pointer_arrays(self) -> List[Dict]:
        """Find pointer arrays (character-wise font offsets)"""
        self.log("\n[ANALYSIS 4] Searching for pointer arrays...")

        pointer_regions = []

        # Look for potential pointers in 4-byte units
        for i in range(0, len(self.rom_data) - 4, 4):
            # Interpret as little-endian pointer
            ptr_value = struct.unpack('<I', self.rom_data[i:i+4])[0]

            # Check if within valid ROM range
            if ptr_value < self.rom_size and ptr_value > 0x8000:
                # Check if multiple pointers appear consecutively
                consecutive_pointers = 0
                start_addr = i

                j = i
                while j < len(self.rom_data) - 4:
                    ptr = struct.unpack('<I', self.rom_data[j:j+4])[0]
                    if ptr < self.rom_size and ptr > 0x8000:
                        consecutive_pointers += 1
                        j += 4
                    else:
                        break

                # Pointer array condition: minimum 10 consecutive pointers
                if consecutive_pointers >= 10:
                    pointer_regions.append({
                        'address': hex(start_addr),
                        'pointer_count': consecutive_pointers,
                        'range': f"{hex(start_addr)} - {hex(start_addr + consecutive_pointers * 4)}",
                        'first_target': hex(struct.unpack('<I', self.rom_data[start_addr:start_addr+4])[0])
                    })

                    # Skip already processed area
                    i = j - 1

        self.log(f"[RESULT] Found {len(pointer_regions)} pointer arrays")
        for i, region in enumerate(pointer_regions[:10], 1):
            self.log(f"  {i}. {region['address']}: {region['pointer_count']} pointers -> {region['first_target']}")

        self.findings['pointer_patterns'] = pointer_regions
        return pointer_regions

    def estimate_glyph_size(self) -> Dict:
        """Estimate glyph size"""
        self.log("\n[ANALYSIS 5] Estimating glyph size...")

        # Estimate from repeated patterns
        if self.findings['repeated_patterns']:
            pattern_size = len(bytes.fromhex(self.findings['repeated_patterns'][0]['pattern']))
            self.log(f"[ESTIMATE] Repeated pattern size: {pattern_size} bytes")

            # Common GBA glyph sizes
            # 8x8: 8bytes, 16x16: 32bytes, 8x16: 16bytes
            possible_sizes = {
                8: "8x8 glyph (1bpp bitmap)",
                16: "8x16 or 16x8 glyph (1bpp)",
                32: "16x16 glyph (1bpp)",
                64: "16x16 glyph (2bpp) or 32x8"
            }

            for size_bytes, description in possible_sizes.items():
                if pattern_size == size_bytes:
                    self.log(f"[ESTIMATE] {description}")

            return {'estimated_glyph_bytes': pattern_size, 'description': possible_sizes.get(pattern_size, "Unknown")}

        return {}

    def generate_analysis_report(self) -> str:
        """Generate analysis report"""
        self.log("\n" + "="*60)
        self.log("PHASE 5-3: ROM Font Structure Analysis Report")
        self.log("="*60)

        report = f"""
ROM ANALYSIS RESULTS
========================================================

ROM Information:
  File: {self.rom_path}
  Size: {self.rom_size:,} bytes ({self.rom_size/1024/1024:.1f}MB)

Findings:
========================================================

[1] Repeated Patterns (Bitmap Glyph Candidates)
    Found: {len(self.findings['repeated_patterns'])}
    {self._format_patterns()}

[2] Bitmap Regions
    Found: {len(self.findings['bitmap_regions'])}
    {self._format_regions()}

[3] Shift-JIS Text Clusters
    Found: {len(self.findings['text_clusters'])}
    (Content output skipped due to encoding)

[4] Pointer Arrays
    Found: {len(self.findings['pointer_patterns'])}
    {self._format_pointers()}

Next Steps:
========================================================

1. Select font candidate from analysis results above
2. Verify with hex editor at identified addresses
3. Record the following information:
   - font_start_address: Font data start address
   - font_end_address: Font data end address
   - glyph_width, glyph_height: Glyph pixel dimensions
   - glyph_size_bytes: Bytes per glyph
   - encoding_type: Character encoding (Shift-JIS confirmed)
   - num_chars: Number of characters in font

Recommendations:
  - Check pointer array addresses for glyph data location
  - Text clusters are game data, font is separate
"""
        return report

    def _format_patterns(self) -> str:
        if self.findings['repeated_patterns']:
            lines = []
            for i, item in enumerate(self.findings['repeated_patterns'][:3], 1):
                lines.append(f"    {i}. Pattern: {item['pattern'][:16]}... Freq: {item['count']}")
            return "\n".join(lines)
        return "    None"

    def _format_regions(self) -> str:
        if self.findings['bitmap_regions']:
            lines = []
            for i, region in enumerate(self.findings['bitmap_regions'][:3], 1):
                size_kb = region['size'] / 1024
                lines.append(f"    {i}. {region['start']} ~ {region['end']} ({size_kb:.1f}KB)")
            return "\n".join(lines)
        return "    None"

    def _format_pointers(self) -> str:
        if self.findings['pointer_patterns']:
            lines = []
            for i, ptr in enumerate(self.findings['pointer_patterns'][:3], 1):
                lines.append(f"    {i}. {ptr['address']}: {ptr['pointer_count']} pointers")
            return "\n".join(lines)
        return "    None"

    @staticmethod
    def _calculate_entropy(data: bytes) -> float:
        """Calculate data entropy (randomness measure)"""
        if not data:
            return 0
        counter = Counter(data)
        entropy = 0
        for count in counter.values():
            p = count / len(data)
            entropy -= p * (p and __import__('math').log2(p))
        return entropy

    def run_analysis(self):
        """Run complete analysis"""
        if not self.load_rom():
            return False

        self.log("\n" + "="*60)
        self.log("Game Wars ROM Font Structure Analysis Started")
        self.log("="*60)

        self.find_repeated_patterns()
        self.find_bitmap_regions()
        self.find_shift_jis_patterns()
        self.find_pointer_arrays()
        self.estimate_glyph_size()

        report = self.generate_analysis_report()
        self.log(report)

        return True

    def save_report(self, output_path: str):
        """Save report to file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(self.output_lines))
        self.log(f"\n[INFO] Report saved to: {output_path}")


def main():
    """Main program"""
    if len(sys.argv) < 2:
        print("Usage: python analyze_rom_font_structure_v2.py <rom_file>")
        return 1

    rom_path = sys.argv[1]

    if not Path(rom_path).exists():
        print(f"[ERROR] ROM file not found: {rom_path}")
        return 1

    analyzer = ROMFontAnalyzer(rom_path)
    success = analyzer.run_analysis()

    if success:
        output_path = Path(rom_path).parent.parent / "docs" / "PHASE5_3_ROM_FONT_ANALYSIS.md"
        analyzer.save_report(str(output_path))

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
