# 30g2_part2_green_earth_volcano_lava_story — b32r5 volcano branch

- Candidate ROM SHA-256: `7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a`.
- Source SRAM: `temp/release_C/work/w2b4/saves/anchor_run16.sav`, SHA-256 `fff21a3cf8e21e5151ad323d974b509275afa665a61eda9f3417044b105ce3d9`; declared source ROM SHA-256 `effc6ee8680a98057b87d3d2acd95b1de8a613dd60ba4310a9b76b271faa74cb`. Legacy provenance is unverified and all descendants are `cheat_tainted=true`.
- Input route: `inputs.txt`; no RAM writes, as recorded in `cheats.txt`. The actual capture was split into same-ROM recorder segments with verified parent checkpoints.
- Selected frame: `temp/release_C/w2b6e_volcano_day2dialog/0001_NONE_0008033.checkpoint.json`, visually inspected Korean: **「화산에서 뿜는 용암은 / 일정한 패턴이 있는 듯해.」**. Emulator exit code 0.
- Permanent PNG: `docs/screenshots/w2b6_b32r5_2026-10-15/scene_30g2_part2_green_earth_volcano_lava_story.png`.

Replay from repository root with a fresh output directory:

```sh
memcap -n aw-kor-w2b6e -- nice -n 15 python3 tools/playthrough_capture.py \
  --rom output/game_wars_korean_candidate_20261015_b32r5.gba \
  --harness temp/mgbah_linux --out temp/release_C/30g2_part2_green_earth_volcano_lava_story_replay_NEW \
  --import-legacy-game-save temp/release_C/work/w2b4/saves/anchor_run16.sav \
  --legacy-save-sha256 fff21a3cf8e21e5151ad323d974b509275afa665a61eda9f3417044b105ce3d9 \
  --legacy-source-rom-sha256 effc6ee8680a98057b87d3d2acd95b1de8a613dd60ba4310a9b76b271faa74cb \
  --legacy-provenance-note 'W2b4 legacy SRAM; unverified origin; cheat-tainted' \
  --no-contact-sheets --gzip-emulator-log --lossless-palette-frames \
  < tools/scene_routes/30g2_part2_green_earth_volcano_lava_story/inputs.txt
```

A full cold-boot replay of `inputs.txt` closed at core 8033 with emulator exit code 0 in `temp/release_C/w2b6e_g2_fullreplay/`. Its selected frame RGB SHA-256 is `787c6f4d605525e7e75465ce3cd918e36852f9b11a65f9408ea6b99e6e314353`, identical to the registered segmented recorder frame. The PNG byte SHA differs because the two captures used different lossless PNG encodings; decoded RGB pixels are identical.
