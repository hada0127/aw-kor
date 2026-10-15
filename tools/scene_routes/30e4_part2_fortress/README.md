# Scene 30e4 — Part 2 Show Stopper fortress opening

- Candidate: `output/game_wars_korean_candidate_20261015_b32r5.gba`, SHA-256 `7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a`.
- Cartridge save: `temp/release_C/work/w2b4/saves/gen_346f0ab2.sav`, SHA-256 `346f0ab2a9f6341177421a8e6a7e65ac9be230960dc7e23d511867547d8b8c69`, declared legacy source ROM SHA-256 `9c925cad0a20238d44436774dc7541542d65b6c8c181c090a94b0314b0b4c863`. The source chain is unavailable; every frame is `cheat_tainted` screen evidence.
- Route: `inputs.txt`, SHA-256 `8e6a96fb6994cf61c9b156c8f634f342a06b783678ce7c4d2b5ce67f10d134a4`. Cold boot, load Part 2, move to C17's Yellow Comet flag, select the `우뚝 솟은 적 요새. 아스카의 공략 작전은` briefing, and start it. No RAM writes or cross-ROM savestate are used.
- Verified run: `temp/release_C/w2b6f_scene30e4_sourcefix/`, exit 0 at core 3029. `0031_NONE_0003029.png` shows exactly `여기에, / 적이 있는 거냐?` with no visible clipping or replacement glyph. The source row starts at `0xA202D4`, target-ROM pointer `0xA371EC → 0x08A202D4`; direct runtime read watch is `(unverified)`.

Replay from the repository root:

```sh
memcap -n aw-kor-w2b6f -- nice -n 15 python3 tools/playthrough_capture.py \
  --rom output/game_wars_korean_candidate_20261015_b32r5.gba \
  --harness temp/mgbah_linux --out temp/release_C/scene30e4_replay_NEW \
  --import-legacy-game-save temp/release_C/work/w2b4/saves/gen_346f0ab2.sav \
  --legacy-save-sha256 346f0ab2a9f6341177421a8e6a7e65ac9be230960dc7e23d511867547d8b8c69 \
  --legacy-source-rom-sha256 9c925cad0a20238d44436774dc7541542d65b6c8c181c090a94b0314b0b4c863 \
  --legacy-provenance-note 'Inherited w2b4 P2 world-map SRAM; source checkpoint unavailable; screen QA only' \
  --no-contact-sheets --gzip-emulator-log --lossless-palette-frames \
  < tools/scene_routes/30e4_part2_fortress/inputs.txt
```
