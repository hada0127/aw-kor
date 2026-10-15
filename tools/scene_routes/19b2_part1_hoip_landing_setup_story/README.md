# Scene 19b2 — Part 1 Hoip landing setup

- Candidate SHA-256: `7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a`.
- Source save SHA-256: **none**. Fresh cartridge cold boot, Part 1 Operation Room, select `도그 파이트!` with nine DOWN inputs.
- Inputs: `inputs.txt`; cheat list: `cheats.txt` (empty). The route was recorded in clean same-ROM segments `w2b6e_p1_operation/`, `w2b6e_p1_stage10_select/`, and `w2b6e_p1_stage10_follow/`.
- Selected core 6082 `temp/release_C/w2b6e_p1_stage10_follow/0021_A_0006082.checkpoint.json`; emulator exit code 0. I visually inspected **「호이프 부대가 상륙하기 전 / 먼저 배치했어.」** (0xD9A26A dialogue group) with no visible clipping or replacement glyph. The preceding frame says **「아무래도 늦지 않았네!」**.
- Permanent PNG: `docs/screenshots/w2b6_b32r5_2026-10-15/scene_19b2_part1_hoip_landing_setup_story.png`, SHA-256 `05e8d7062bd476ec02a8f151253640cd0465e0b827b8e3e837219888283618a6`.

Replay from repository root:

```sh
memcap -n aw-kor-w2b6e -- nice -n 15 python3 tools/playthrough_capture.py \
  --rom output/game_wars_korean_candidate_20261015_b32r5.gba \
  --harness temp/mgbah_linux --out temp/release_C/scene19b2_replay_NEW \
  --no-contact-sheets --gzip-emulator-log --lossless-palette-frames \
  < tools/scene_routes/19b2_part1_hoip_landing_setup_story/inputs.txt
```
