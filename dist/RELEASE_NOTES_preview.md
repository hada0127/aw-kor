# Korean Patch Release Notes

## 2026-10-18 Release

Generated from the current `output/game_wars_korean_full.gba` build.

- Source ROM SHA-256: `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c`
- Target ROM SHA-256: `7e00df656ffe7b1b0b8b236c24e30c178467860f8ff92e2072071a0497c7f217`
- BPS patch: `game_wars_korean_full_2026-10-18.bps`
- IPS patch: `game_wars_korean_full_2026-10-18.ips`

b39 retains the b38 changes and fixes the Part 1 name-confirm / first-time 예/아뇨 row shaking when the WARS intro is skipped.
The unlocked map-list and shared campaign-prompt captures used cheat-tainted saves: they verify those displays, not normal-play unlocking or progression.
On iPhone RetroArch mGBA c758314, five b39 r2 confirmations covered the Part 1 name-confirm and first-time prompts after both a skipped and full WARS intro (`docs/screenshots/b39_name_prompts_2026-10-18/receipt.json`). Only those screens were checked on device; real GBA hardware remains unverified.

The hash-bound prepackage QA checks listed in manifest.validation.qa_evidence
passed for this artifact. BPS/IPS round trips were checked during packaging.
These checks do not establish full-campaign, character-voice, or real-hardware
approval; those scopes remain tracked separately in `todo.md`.
Alternate banner-sheet and `0x804FC8` consumer reachability, natural access to 11 Part 1 help windows, normal-play Sturm CO power, and hidden locked-map names remain unverified.
