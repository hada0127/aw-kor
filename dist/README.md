# Game Boy Wars Advance 1+2 Korean Patch

This directory contains patch-only distribution artifacts. ROM files are not
distributed here; build outputs stay under `output/`.

## Current Release

- Patch set: `game_wars_korean_full_2026-10-19.bps` / `game_wars_korean_full_2026-10-19.ips`
- Target ROM SHA-256: `1c23b09160a9f7e491c8d2de8782e80200a13fb4238aec92999728b0282b1fbf`
- Target size: 16777216 bytes
- Candidate: b42; b40 uses the wide 예/아뇨 row for every Part 1 prompt; b41 reflows dialogue windows without losing text; b42 restores natural word spacing and applies consistent spacing to names and titles.

Apply the BPS patch to `Game Boy Wars Advance 1+2 (Japan).gba`. IPS is included
for compatibility, but BPS is preferred because it records source/target CRCs.

## Verification

`tools/prepare_patch_distribution.py` regenerates both patches and verifies:

- BPS round-trip: original ROM + BPS == latest Korean ROM
- IPS round-trip: original ROM + IPS == latest Korean ROM
- Only the canonical `output/game_wars_korean_full.gba` ROM is produced
