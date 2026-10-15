# Scene 19b1 — Part 1 Hoip ambush opening

- Candidate SHA-256: `7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a`.
- Source save SHA-256: **none**. Fresh cartridge cold boot, Part 1 Operation Room, `백운의 세계` mission.
- Inputs: `inputs.txt`; cheat list: `cheats.txt` (empty). The scene was recorded as clean same-ROM segments `w2b6e_19e7_cold/` and `w2b6e_p1_stage12_follow/`.
- Selected core 6270 `temp/release_C/w2b6e_p1_stage12_follow/0016_A_0006270.checkpoint.json`; emulator exit code 0. I visually inspected **「안 좋은 예감이 들어요.」** (0xD9CBCE), with no visible clipping or replacement glyph. The following frames show Hoip's ambush dialogue; the Snow White weather turn was observed separately.
- Permanent PNG: `docs/screenshots/w2b6_b32r5_2026-10-15/scene_19b1_part1_hoip_ambush_weather_story.png`, SHA-256 `f5b19e4c78d8e8b7ec80609168e692d091e643755ea135cb6d21bb5eb716bceb`.

Replay from repository root:

```sh
memcap -n aw-kor-w2b6e -- nice -n 15 python3 tools/playthrough_capture.py \
  --rom output/game_wars_korean_candidate_20261015_b32r5.gba \
  --harness temp/mgbah_linux --out temp/release_C/scene19b1_replay_NEW \
  --no-contact-sheets --gzip-emulator-log --lossless-palette-frames \
  < tools/scene_routes/19b1_part1_hoip_ambush_weather_story/inputs.txt
```
