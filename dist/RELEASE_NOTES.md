# Korean Patch Release Notes

## 2026-10-19 Release

Generated from the current `output/game_wars_korean_full.gba` build.

- Source ROM SHA-256: `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c`
- Target ROM SHA-256: `488094f77a823648907c48e1647d2f53f356c5d70dfd39a8d1c3b4419aa03e34`
- BPS patch: `game_wars_korean_full_2026-10-19.bps`
- IPS patch: `game_wars_korean_full_2026-10-19.ips`

b40 uses the wide 예/아뇨 row for every Part 1 prompt; b41 reflows dialogue windows without losing text; b42 restores natural word spacing and applies consistent spacing to names and titles; b43 corrects the Link status-line spacing. Remaining dialogue items retain their recorded verification limits.
The unlocked map-list and shared campaign-prompt captures used cheat-tainted saves: they verify those displays, not normal-play unlocking or progression.
On iPhone RetroArch, the b42 ROM was read back and cold-booted through the Part 1 title, mode menu, and War Room list; the existing save was preserved (`docs/screenshots/b42_iphone_2026-10-19/receipt.json`). This device check does not cover all changed dialogue or every 예/아뇨 prompt. Real GBA hardware remains unverified.

The hash-bound prepackage QA checks listed in manifest.validation.qa_evidence
passed for this artifact. BPS/IPS round trips were checked during packaging.
These checks do not establish full-campaign, character-voice, or real-hardware
approval; those scopes remain tracked separately in `todo.md`.
Alternate banner-sheet and `0x804FC8` consumer reachability, natural access to 11 Part 1 help windows, normal-play Sturm CO power, and hidden locked-map names remain unverified. For b43 dialogue, 13 unknown consumers, 16 state-dependent messages, 18 horizontal-scroll help messages, and seven withheld relocations remain outside the fixed-window pass. Forced QA is not natural-route verification.
