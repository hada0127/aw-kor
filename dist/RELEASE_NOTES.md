# Game Wars Korean Full Preview - Release Notes

## Release Date
2026-05-27

## Included Files
- `game_wars_korean_full_preview_2026-05-27.bps` - recommended patch
- `game_wars_korean_full_preview_2026-05-27.ips` - alternate patch
- `manifest.json` / `manifest_preview.json` - hashes and build metadata
- `output/game_wars_korean_final.gba` - local generated ROM

## Translation Status
- Full build rows written: 15,269
- Encoding overflow skips: 297, kept as original Japanese for stability
- Rule-shortened rows: 64
- Truncated fit fallback rows: 0
- Protected skips: 36, covering name-grid/font/system data and v56 handled strings

## Technical Changes
- Rebuilt the full Korean ROM from `output/v56_polished.gba`.
- Preserved original font base for the English name grid while routing Korean reserved codes to `KOR_BASE`.
- Added Part 2 tilemap/glyph-cache renderer hooks.
- Added Part 2 ASCII-space handling.
- Disabled final truncation fallback after real-game screenshots showed broken dialogue.
- Short yes/no strings are encoded as `예/아▼` to fit the original 8-byte slot.
- Name-grid visible rows now keep the original selectable gaps so preview output matches the selected lowercase letter.
- Updated Phase 6 checksum validation to use the correct GBA header checksum formula.

## Verification
- ROM size: 16,777,216 bytes
- Patched ROM SHA1: `1264fcab27d0e349b6caf461fd0247380e981c53`
- BPS SHA1: `640c2053c3fc8b4213ca640c3ca17b35f4b2196a`
- IPS SHA1: `5d3798f13e01cab55d4dc17c2f46a07fd750acca`
- `tools/phase6_basic_test.py`: pass
- BPS/IPS round-trip: pass
- Headless screenshots refreshed:
  - `docs/screenshots/SUCCESS_final_name_grid_2026-05-27.png`
  - `docs/screenshots/SUCCESS_final_part2_prologue_2026-05-27.png`

## Known Issues
- The 297 overflow rows remain Japanese until manually shortened.
- Graphics-rendered labels can still contain Japanese where they are not text-engine strings.
- A full campaign playthrough on real hardware remains release-candidate QA, not a build blocker.
