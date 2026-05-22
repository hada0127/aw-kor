#!/usr/bin/env python3
"""
Font configuration for Game Wars ROM Korean localization
Generated from PHASE 5-3 analysis
"""

from font_preparation_framework import (
    GBAFontInfo, FontAnalyzer, KoreanGlyphGenerator,
    FontInsertionEngine, FontEncodingConverter
)

# Game Wars font configuration
GAME_WARS_FONT = GBAFontInfo(
    rom_path='original/Game Boy Wars Advance 1+2 (Japan).gba',
    font_start_address=0x400000,
    font_end_address=0x500000,
    glyph_width=8,
    glyph_height=8,
    glyph_size_bytes=8,
    encoding_type='shift_jis',
    num_chars=256
)

# Generate Korean glyphs
korean_gen = KoreanGlyphGenerator()
korean_glyphs = korean_gen.generate_complete_hangul()
print(f"Generated {len(korean_glyphs)} Korean glyphs")

# Prepare font insertion
font_engine = FontInsertionEngine(GAME_WARS_FONT)
# Font insertion will be performed after text is finalized
# See: import_text_enhanced.py for text insertion workflow

print("Font configuration loaded and ready for PHASE 5-4 (text insertion)")
