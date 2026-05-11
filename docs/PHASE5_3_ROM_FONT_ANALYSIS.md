[INFO] ROM loaded: 16,777,216 bytes (16.0MB)

============================================================
Game Wars ROM Font Structure Analysis Started
============================================================

[ANALYSIS 1] Searching for repeated patterns (bitmap glyph candidates)...
[RESULT] Found 98 repeated patterns
  1. Pattern: f0b557464e464546... Freq: 654 Entropy: 2.41
  2. Pattern: f0bc01bc00470000... Freq: 576 Entropy: 2.16
  3. Pattern: 10bc01bc00470000... Freq: 450 Entropy: 2.16
  4. Pattern: 38bc9846a146aa46... Freq: 335 Entropy: 2.41
  5. Pattern: 9846a146aa46f0bc... Freq: 308 Entropy: 2.41
  6. Pattern: 30bc01bc00470000... Freq: 280 Entropy: 2.16
  7. Pattern: a146aa46f0bc01bc... Freq: 273 Entropy: 2.50
  8. Pattern: aa46f0bc01bc0047... Freq: 266 Entropy: 2.75
  9. Pattern: 70bc01bc00470000... Freq: 256 Entropy: 2.16
  10. Pattern: f0b54f464646c0b4... Freq: 186 Entropy: 2.41

[ANALYSIS 2] Searching for bitmap data regions...
[RESULT] Found 5709 potential bitmap regions
  1. 0x0 ~ 0x100 (0.2KB, entropy: 6.31)
  2. 0x200 ~ 0x280 (0.1KB, entropy: 5.05)
  3. 0x400 ~ 0x680 (0.6KB, entropy: 5.04)
  4. 0x700 ~ 0x780 (0.1KB, entropy: 5.22)
  5. 0x800 ~ 0x980 (0.4KB, entropy: 5.04)

[ANALYSIS 3] Searching for Shift-JIS text clusters...
[RESULT] Found 25351 text clusters
  1. 0x805104: 126 chars (252bytes)
  2. 0xd82878: 126 chars (252bytes)
  3. 0x8057bc: 118 chars (236bytes)
  4. 0xd82f30: 118 chars (236bytes)
  5. 0x8052a8: 117 chars (234bytes)
  6. 0xd82a1c: 117 chars (234bytes)
  7. 0xd81c24: 108 chars (216bytes)
  8. 0x8055d4: 104 chars (208bytes)
  9. 0xd82d48: 104 chars (208bytes)
  10. 0x805a24: 93 chars (186bytes)

[ANALYSIS 4] Searching for pointer arrays...
[RESULT] Found 19890 pointer arrays
  1. 0x1348c: 13 pointers -> 0x5f005f
  2. 0x13490: 12 pointers -> 0x5f005f
  3. 0x13494: 11 pointers -> 0x5f005f
  4. 0x13498: 10 pointers -> 0x5f005f
  5. 0x13524: 93 pointers -> 0x5f005f
  6. 0x13528: 92 pointers -> 0x5f005f
  7. 0x1352c: 91 pointers -> 0x5f005f
  8. 0x13530: 90 pointers -> 0x5f005f
  9. 0x13534: 89 pointers -> 0x5f005f
  10. 0x13538: 88 pointers -> 0x5f005f

[ANALYSIS 5] Estimating glyph size...
[ESTIMATE] Repeated pattern size: 8 bytes
[ESTIMATE] 8x8 glyph (1bpp bitmap)

============================================================
PHASE 5-3: ROM Font Structure Analysis Report
============================================================

ROM ANALYSIS RESULTS
========================================================

ROM Information:
  File: original/Game Boy Wars Advance 1+2 (Japan).gba
  Size: 16,777,216 bytes (16.0MB)

Findings:
========================================================

[1] Repeated Patterns (Bitmap Glyph Candidates)
    Found: 98
        1. Pattern: f0b557464e464546... Freq: 654
    2. Pattern: f0bc01bc00470000... Freq: 576
    3. Pattern: 10bc01bc00470000... Freq: 450

[2] Bitmap Regions
    Found: 5709
        1. 0x0 ~ 0x100 (0.2KB)
    2. 0x200 ~ 0x280 (0.1KB)
    3. 0x400 ~ 0x680 (0.6KB)

[3] Shift-JIS Text Clusters
    Found: 25351
    (Content output skipped due to encoding)

[4] Pointer Arrays
    Found: 19890
        1. 0x1348c: 13 pointers
    2. 0x13490: 12 pointers
    3. 0x13494: 11 pointers

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
