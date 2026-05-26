# Codex Part2 findings (2026-05-26)

## Confirmed renderers

### 0x08313xxx Advance 2 tilemap writer

Source ROM `0x08313F8C..0x08313FFA` is a SJIS-to-tilemap renderer, not a per-character glyph blitter.

Important instructions:

- `0x08313F90`: loads kanji table start literal `0x083902E4` (`@0x08313FFC`).
- `0x08313F9E`: loads table end literal `0x08390F74` (`@0x08314000`).
- `0x08313FA0..0x08313FAA`: linear search on 6-byte entries.
- `0x08313FB8..0x08313FBE`: `ldrh top_idx; orr attrs; strh [tilemap]`.
- `0x08313FC8..0x08313FCE`: same for bottom tile.

The table is byte-identical to `0x08B80B7C..0x08B8180C` and has 536 entries.

### 0x08B11Cxx common tilemap writer

Source ROM `0x08B11BB0..0x08B11E22` has the same table-output shape:

- `0x08B11E24`: original table start `0x08B80B7C`.
- `0x08B11E28`: original table end `0x08B8180C`.
- `0x08B11DC8..0x08B11DD2`: linear search.
- `0x08B11DE0..0x08B11DE6`: top `ldrh; orr attrs; strh [tilemap]`.
- `0x08B11DF0..0x08B11DF6`: bottom `ldrh; orr attrs; strh [tilemap]`.

### MODE SELECT description renderer

MODE SELECT bottom description text at `0x08A2C040` is read by a third path:

- width/control reads: `0x0831425A`, `0x08314336`.
- runtime IWRAM reads: `0x03006088`, LR `0x0831BBED`.
- IWRAM `0x03005EC0` maps to ROM source `0x08A3C624`.
- IWRAM `0x03006080` maps to ROM source `0x08A3C7E4`.

This path has a local glyph cache / linked glyph table and falls back to `0x8148` (`?`) before the tilemap writers above can help. This is why MODE SELECT still shows `?` even after patching 0x313/0xB11.

Additional RE for the actual glyph-cache function:

- Function source starts at `0x08A3C7C0` and is copied to IWRAM `0x0300605C`.
- Hookable byte-load site: ROM `0x08A3C7E8` / IWRAM `0x03006084`.
- Replaced original instructions at `0x08A3C7E8`: `ldrb r4,[r0]; ldrb r0,[r0,#1]; ldr r2,[pc,#0x38]; cmp r0,#0x3f`.
- Glyph-cache lookup:
  - `0x08A3C7F6..0x08A3C81A` indexes pointer table `0x0852F960`, walks linked glyph entries, and compares the high byte at `[entry+4]`.
  - `0x08A3C820..0x08A3C824` is the real fallback: set code to `0x8148` and branch back to lookup.
  - `0x08A3C82C..0x08A3C924` copies two 8x8 tiles to `0x06000000 + tile_index*0x20`, applying palette nibble substitution for the original glyph-cache format.

## Implemented in tools/build_korean_full.py

1. Repointed both tilemap renderers to the existing relocated Korean table at `0x08F20000..0x08F224B4`:
   - `0x08313FFC/0x08314000`
   - `0x08B11E24/0x08B11E28`

2. Added four ARM7TDMI Thumb hooks in ROM `0x08F30100..0x08F30277`:
   - 0x313 top/bottom hooks return to `0x08313FC1`, `0x08313FD1`.
   - 0xB11 top/bottom hooks return to `0x08B11DE9`, `0x08B11DF9`.

3. Hook behavior:
   - Read table entry.
   - If bit15 is clear, preserve original tilemap write.
   - If bit15 is set, strip marker, copy `KOR_BASE + local*0x20` to dynamic VRAM tile `0x300 + ((tilemap_dest >> 1) & 0x7f)`, then write that real tile id plus original attrs to the tilemap.
   - This prevents the bit15 Korean marker from becoming a BG palette/attribute bit.

4. Replaced the previous late/experimental A3 miss hook with an early glyph-cache hook:
   - ROM patch site: `0x08A3C7E8`.
   - Trampoline bytes: `00 4A 10 47 <0x08F30281>`, using `r2` so the original `r0` text pointer survives.
   - Hook body: `0x08F30280..0x08F30323`.
   - Non-Korean path replays the four replaced instructions and returns to IWRAM `0x0300608D`, preserving condition flags for the original `bls/bhi` branch.
   - Korean path checks reserved SJIS range `0x8840..0x9369`, searches relocated table `0x08F20000..0x08F224B4`, requires bit15 marker, strips it, copies `KOR_BASE + local*0x20` top/bottom tiles into `0x06000000 + tile_index*0x20` and `+0x20`, then jumps to IWRAM epilogue `0x030061C1`.

## Verification

- `python3 tools/build_korean_full.py` succeeds.
- Output: `output/game_wars_korean_full.gba`.
- Byte checks after build:
  - `0xEFE970 = 0x08F20000`, `0xEFE974 = 0x08F224B4`.
  - `0xB11E24 = 0x08F20000`, `0xB11E28 = 0x08F224B4`.
  - `0x313FFC = 0x08F20000`, `0x314000 = 0x08F224B4`.
  - `0xA3C7E8 = 00 4A 10 47 81 02 F3 08`.
- Headless mGBA navigation to Advance 2 title and MODE SELECT does not white-screen/crash.
- Breakpoint at `0x08F30280` fires on MODE SELECT text source `0x08A2C040`, LR `0x0831BBED`, tile indices `0x40,0x42,...`.
- New screenshots:
  - `temp/part2b_mode_or_prologue.png`: MODE SELECT bottom description renders Korean instead of `?????`.
  - `temp/part2b_pro_0.png`..`temp/part2b_pro_5.png`: Advance 2 setup/prologue/map screens advance without crash; A3-path Korean text is visible in the mode/setup captions.

## Residual notes

- The A3 hook copies raw `KOR_BASE` 4bpp tiles and does not run the original glyph-cache palette nibble substitution. This matches the existing Korean glyph blob convention used by Part 1 and the 0x313/0xB11 tilemap hooks.
- The older `0x08A3C6BC` miss-loop hook is intentionally retired; that site is after lookup failure and cannot prevent `0x8148` substitution reliably.
