# Game Boy Wars Advance 1+2 Korean Patch

This directory contains patch-only distribution artifacts. ROM files are not
distributed here; build outputs stay under `output/`.

## Current Release

- Patch set: `game_wars_korean_full_2026-07-06.bps` / `game_wars_korean_full_2026-07-06.ips`
- Target ROM SHA-256: `83ae254bf25fc938bb5dd7825955637ebbce2c7370c0d615c89cebf65b2ba646`
- Target size: 16777216 bytes

Apply the BPS patch to `Game Boy Wars Advance 1+2 (Japan).gba`. IPS is included
for compatibility, but BPS is preferred because it records source/target CRCs.

## Verification

`tools/prepare_patch_distribution.py` regenerates both patches and verifies:

- BPS round-trip: original ROM + BPS == latest Korean ROM
- IPS round-trip: original ROM + IPS == latest Korean ROM
- Only the canonical `output/game_wars_korean_full.gba` ROM is produced
