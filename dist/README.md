# Game Boy Wars Advance 1+2 Korean Patch

This directory contains patch-only distribution artifacts. ROM files are not
distributed here; build outputs stay under `output/`.

## Current Release

- Patch set: `game_wars_korean_full_2026-10-16.bps` / `game_wars_korean_full_2026-10-16.ips`
- Target ROM SHA-256: `c8a9468cd0bb7673705f1d3a1532610ec32f17eb608fe25d0d586f4244dfa5e8`
- Target size: 16777216 bytes
- Candidate: b37; b37 fixes missing names in the unlocked Part 1 link map list.

Apply the BPS patch to `Game Boy Wars Advance 1+2 (Japan).gba`. IPS is included
for compatibility, but BPS is preferred because it records source/target CRCs.

## Verification

`tools/prepare_patch_distribution.py` regenerates both patches and verifies:

- BPS round-trip: original ROM + BPS == latest Korean ROM
- IPS round-trip: original ROM + IPS == latest Korean ROM
- Only the canonical `output/game_wars_korean_full.gba` ROM is produced
