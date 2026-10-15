# Scene 19c2 — Part 1 mission 5M fog-map opening

- Candidate: `output/game_wars_korean_candidate_20261015_b32r5.gba`, SHA-256 `7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a`.
- Cartridge save: `temp/release_C/work/w2b4/saves/g1_da9d97cf.sav`, SHA-256 `da9d97cfda87998c4759b162d3075ea62ba6dd0389fe531f705f6c966834f45a`, declared legacy source ROM SHA-256 `51b10dcf48204be4762c3c262c6a9de0de87fb014d7e0043742e7db02fff7d98`. Source chain unavailable; every frame is cheat-tainted.
- Route: `inputs.txt`, SHA-256 `b54fcebf3f311a3eeed1687a2423e0e2d113d14bd8aba8db167a1e65c9936ec7`. Cold boot, load Part 1 mission 3, move infantry to enemy HQ by logged unit-table writes, capture HQ twice, choose Max branch, move mech to mission 4 HQ, capture four times, and advance to mission 5M. Logged enemy unit HP writes in mission 4 protect the capturing unit; unit wipe was not counted as victory.
- Verified run: `temp/release_C/w2b6f_scene19c2_cold2/`, exit 0 at core 56131; no input errors. Endpoint shows exactly `색적 맵인가・・・.` with no visible clipping or replacement glyph. Source row `0xDC4C02`; direct runtime read watch is `(unverified)`.

Replay from repository root:

```sh
memcap -n aw-kor-w2b6f -- nice -n 15 python3 tools/playthrough_capture.py \
  --rom output/game_wars_korean_candidate_20261015_b32r5.gba \
  --harness temp/mgbah_linux --out temp/release_C/scene19c2_replay_NEW \
  --import-legacy-game-save temp/release_C/work/w2b4/saves/g1_da9d97cf.sav \
  --legacy-save-sha256 da9d97cfda87998c4759b162d3075ea62ba6dd0389fe531f705f6c966834f45a \
  --legacy-source-rom-sha256 51b10dcf48204be4762c3c262c6a9de0de87fb014d7e0043742e7db02fff7d98 \
  --legacy-provenance-note 'Inherited w2b4 P1 mission-3 SRAM; source checkpoint unavailable; screen QA only' \
  --no-contact-sheets --gzip-emulator-log --lossless-palette-frames \
  < tools/scene_routes/19c2_part1_fog_map_story/inputs.txt
```
