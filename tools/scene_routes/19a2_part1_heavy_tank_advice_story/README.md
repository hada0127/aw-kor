# Scene 19a2 — Part 1 heavy tank advice

- Candidate SHA-256: `7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a`.
- Source save SHA-256: **none**. Fresh cartridge cold boot, Part 1 Operation Room, select `지상 최강? 중전차!` with five DOWN inputs.
- Inputs: `inputs.txt`; cheat list: `cheats.txt` (empty). The route was recorded in three same-ROM segments: `w2b6e_p1_operation/`, `w2b6e_p1_training_select/`, and `w2b6e_p1_train6_follow/`.
- Selected core 6061 `temp/release_C/w2b6e_p1_train6_follow/0022_A_0006061.checkpoint.json`; emulator exit code 0. I visually inspected **「하지만, 전투는 정면승부만 / 있는 게 아니에요.」** (0xD965DE) with no visible clipping or replacement glyph. The prior frames show **「중전차?!」** (0xD9650F).
- Permanent PNG: `docs/screenshots/w2b6_b32r5_2026-10-15/scene_19a2_part1_heavy_tank_advice_story.png`, SHA-256 `c634f5cfaeaa29a7a2c855bce17896c7c742fb150aeedf9d0249b619e20d0a45`.

Replay from repository root:

```sh
memcap -n aw-kor-w2b6e -- nice -n 15 python3 tools/playthrough_capture.py \
  --rom output/game_wars_korean_candidate_20261015_b32r5.gba \
  --harness temp/mgbah_linux --out temp/release_C/scene19a2_replay_NEW \
  --no-contact-sheets --gzip-emulator-log --lossless-palette-frames \
  < tools/scene_routes/19a2_part1_heavy_tank_advice_story/inputs.txt
```
