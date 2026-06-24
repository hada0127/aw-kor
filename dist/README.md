# Game Boy Wars Advance 1+2 Korean Patch

This directory contains patch-only distribution artifacts. ROM files are not
distributed here; build outputs stay under `output/`.

## Current Release

- Patch set: `game_wars_korean_full_2026-06-24.bps` / `game_wars_korean_full_2026-06-24.ips`
- Target ROM SHA-256: `371944c8e069270f531d5df80139afa3e9585a629152b3104f22f40c050fbe43`
- Target size: 16777216 bytes

Apply the BPS patch to `Game Boy Wars Advance 1+2 (Japan).gba`. IPS is included
for compatibility, but BPS is preferred because it records source/target CRCs.

## Verification

`tools/prepare_patch_distribution.py` regenerates both patches and verifies:

- BPS round-trip: original ROM + BPS == latest Korean ROM
- IPS round-trip: original ROM + IPS == latest Korean ROM
- `full`, `final`, and `title_test` output ROMs have identical SHA-256
