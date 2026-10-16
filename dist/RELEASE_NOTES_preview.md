# Korean Patch Release Notes

## 2026-10-16 Release

Generated from the current `output/game_wars_korean_full.gba` build.

- Source ROM SHA-256: `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c`
- Target ROM SHA-256: `c089305111b92e4dc0c78da3bd1d699e994b4e597d875682ffca80a6acfbf9c6`
- BPS patch: `game_wars_korean_full_2026-10-16.bps`
- IPS patch: `game_wars_korean_full_2026-10-16.ips`

b38 retains the b37 unlocked Part 1 link-map name fix; it stabilizes the Part 1 name-confirm 예/아뇨 row in one Japanese-layout row, adjusts the shared campaign prompt cursor placement, renames five Part 1 tutorial lines to 어드밴스 워즈, and renames the Part 2 splash to 어드밴스 워즈 2.
The unlocked map-list and shared campaign-prompt captures used cheat-tainted saves: they verify those displays, not normal-play unlocking or progression.

The hash-bound prepackage QA checks listed in manifest.validation.qa_evidence
passed for this artifact. BPS/IPS round trips were checked during packaging.
These checks do not establish full-campaign, character-voice, or real-hardware
approval; those scopes remain tracked separately in `todo.md`.
Alternate banner-sheet and `0x804FC8` consumer reachability, natural access to 11 Part 1 help windows, normal-play Sturm CO power, and hidden locked-map names remain unverified.
