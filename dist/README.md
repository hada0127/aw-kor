# Game Boy Wars Advance 1+2 Korean Patch

This directory contains patch-only distribution artifacts. ROM files are not
distributed here; build outputs stay under `output/`.

## Current Release

- Patch set: `game_wars_korean_full_2026-06-17.bps` / `game_wars_korean_full_2026-06-17.ips`
- Target ROM SHA-256: `1623481a72d85d24a73f76e0da75035847ad4b6f0218ea6d3bdf094c5aa5faa4`
- Target size: 16777216 bytes

Apply the BPS patch to `Game Boy Wars Advance 1+2 (Japan).gba`. IPS is included
for compatibility, but BPS is preferred because it records source/target CRCs.

## Verification

`tools/prepare_patch_distribution.py` regenerates both patches and verifies:

- BPS round-trip: original ROM + BPS == latest Korean ROM
- IPS round-trip: original ROM + IPS == latest Korean ROM
- `full`, `final`, and `title_test` output ROMs have identical SHA-256
