# Game Boy Wars Advance 1+2 Korean Patch

This directory contains patch-only distribution artifacts. ROM files are not
distributed here; build outputs stay under `output/`.

## Current Preview

- Patch set: `game_wars_korean_full_preview_2026-06-07.bps` / `game_wars_korean_full_preview_2026-06-07.ips`
- Target ROM SHA-256: `a85dc2be1320ed24ee949aea9a8a82be854dda39cf87d2d15a3bfa11fdc4f0ec`
- Target size: 16777216 bytes

Apply the BPS patch to `Game Boy Wars Advance 1+2 (Japan).gba`. IPS is included
for compatibility, but BPS is preferred because it records source/target CRCs.

## Verification

`tools/prepare_patch_distribution.py` regenerates both patches and verifies:

- BPS round-trip: original ROM + BPS == latest Korean ROM
- IPS round-trip: original ROM + IPS == latest Korean ROM
- `full`, `final`, and `title_test` output ROMs have identical SHA-256
