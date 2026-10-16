# Korean Patch Release Notes

## 2026-10-16 Release

Generated from the current `output/game_wars_korean_full.gba` build.

- Source ROM SHA-256: `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c`
- Target ROM SHA-256: `c8a9468cd0bb7673705f1d3a1532610ec32f17eb608fe25d0d586f4244dfa5e8`
- BPS patch: `game_wars_korean_full_2026-10-16.bps`
- IPS patch: `game_wars_korean_full_2026-10-16.ips`

b37 fixes missing names in the unlocked Part 1 link map list.
The unlocked map-list captures used a cheat-tainted save: they verify display with maps unlocked, not normal-play unlocking.

The hash-bound prepackage QA checks listed in manifest.validation.qa_evidence
passed for this artifact. BPS/IPS round trips were checked during packaging.
These checks do not establish full-campaign, character-voice, or real-hardware
approval; those scopes remain tracked separately in `todo.md`.
Alternate banner-sheet and `0x804FC8` consumer reachability, natural access to 11 Part 1 help windows, normal-play Sturm CO power, and hidden locked-map names remain unverified.
