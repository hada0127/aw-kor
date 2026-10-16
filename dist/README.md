# Game Boy Wars Advance 1+2 Korean Patch

This directory contains patch-only distribution artifacts. ROM files are not
distributed here; build outputs stay under `output/`.

## Current Release

- Patch set: `game_wars_korean_full_2026-10-16.bps` / `game_wars_korean_full_2026-10-16.ips`
- Target ROM SHA-256: `c089305111b92e4dc0c78da3bd1d699e994b4e597d875682ffca80a6acfbf9c6`
- Target size: 16777216 bytes
- Candidate: b38; b38 retains the b37 unlocked Part 1 link-map name fix; it stabilizes the Part 1 name-confirm 예/아뇨 row in one Japanese-layout row, adjusts the shared campaign prompt cursor placement, renames five Part 1 tutorial lines to 어드밴스 워즈, and renames the Part 2 splash to 어드밴스 워즈 2.

Apply the BPS patch to `Game Boy Wars Advance 1+2 (Japan).gba`. IPS is included
for compatibility, but BPS is preferred because it records source/target CRCs.

## Verification

`tools/prepare_patch_distribution.py` regenerates both patches and verifies:

- BPS round-trip: original ROM + BPS == latest Korean ROM
- IPS round-trip: original ROM + IPS == latest Korean ROM
- Only the canonical `output/game_wars_korean_full.gba` ROM is produced
