# Game Boy Wars Advance 1+2 Korean Patch

This directory contains patch-only distribution artifacts. ROM files are not
distributed here; build outputs stay under `output/`.

## Current Release

- Patch set: `game_wars_korean_full_2026-10-18.bps` / `game_wars_korean_full_2026-10-18.ips`
- Target ROM SHA-256: `7e00df656ffe7b1b0b8b236c24e30c178467860f8ff92e2072071a0497c7f217`
- Target size: 16777216 bytes
- Candidate: b39; b39 retains the b38 changes and fixes the Part 1 name-confirm / first-time 예/아뇨 row shaking when the WARS intro is skipped.

Apply the BPS patch to `Game Boy Wars Advance 1+2 (Japan).gba`. IPS is included
for compatibility, but BPS is preferred because it records source/target CRCs.

## Verification

`tools/prepare_patch_distribution.py` regenerates both patches and verifies:

- BPS round-trip: original ROM + BPS == latest Korean ROM
- IPS round-trip: original ROM + IPS == latest Korean ROM
- Only the canonical `output/game_wars_korean_full.gba` ROM is produced
