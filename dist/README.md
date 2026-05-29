# Game Wars Korean Localization

## Overview
Game Boy Wars Advance 1+2 Korean localization full preview build.

**Current Status**
- ROM: `output/game_wars_korean_final.gba` / `output/game_wars_korean_full.gba` (16.0 MB)
- Patch: `game_wars_korean_full_preview_2026-05-27.bps`
- Korean rows written: 15,269
- Manual polish candidates: 297 overflow rows kept as original Japanese in `temp/encode_report.csv`
- Integrity: header, size, checksum, BPS/IPS round-trip verified

## Installation
Use the BPS patch with the original Japan ROM:

1. Open `game_wars_korean_full_preview_2026-05-27.bps` in Floating IPS, beat, or another BPS patcher.
2. Select `Game Boy Wars Advance 1+2 (Japan).gba` as the source ROM.
3. Run the patched ROM in mGBA, VBA-M, or compatible hardware/flashcart setup.

## Included Features
- Part 1 dialogue Korean rendering through ASM hook and reserved-code table.
- Part 2 MODE SELECT and PROLOGUE Korean rendering.
- Korean spacing support in the Part 2 renderer.
- English name grid: A-Z, a-z, 0-9.
- Dialogue wait-marker/auto-advance fix.
- Protected charset/font data denylist to avoid name-grid corruption.

## Known Limitations
- 297 rows remain original Japanese because fitting them by truncation caused broken dialogue.
- Some Japanese remains in graphics, protected data tables, or unlocalized visual assets.
- Full human playthrough on every campaign/map is still recommended before a public final release.

## Verification
- `python3 tools/build_korean_full.py`
- `python3 tools/qa_text_fit.py`
- `python3 tools/phase6_basic_test.py`
- `python3 temp/verify_grid.py output/game_wars_korean_full.gba docs/screenshots/SUCCESS_final_name_grid_2026-05-27.png`
- `python3 temp/nav_p2qa.py`

## License
Project tooling follows the repository license. This package does not include or grant rights to the original commercial ROM.

---
Version: 2026-05-27 full preview
