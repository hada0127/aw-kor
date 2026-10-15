# Scene 80a — Part 1 mission 3 opening

- Candidate b32r5 ROM SHA-256: `7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a`.
- Source cartridge SRAM: `temp/release_C/work/w2b4/saves/g1_da9d97cf.sav`, SHA-256 `da9d97cfda87998c4759b162d3075ea62ba6dd0389fe531f705f6c966834f45a`. Claimed source ROM SHA-256: `51b10dcf48204be4762c3c262c6a9de0de87fb014d7e0043742e7db02fff7d98`; its origin is unverified. All descendant frames are `cheat_tainted=true`.
- `inputs.txt` cold boots that SRAM, surrenders the ongoing Part 1 mission 3, confirms the loss, and retries from the campaign map. `cheats.txt` is empty: no RAM writes were made along this route.
- Full replay `temp/release_C/w2b6e_80a_fullreplay/` closed at core 6193 with emulator exit code 0. Selected checkpoint `0046_A_0006193.checkpoint.json`; visible text **「이런 곳에 레드스타의 부대가 / 나타날 줄이야.」** matches the `0xE00166` dialogue group. The frame's decoded RGB SHA-256 is `fcfffec1514082b173b9081e003fe7d08677739a194ab2c2e03423e9c7193019` and matches the earlier segmented capture at core 6194. Permanent PNG: `docs/screenshots/w2b6_b32r5_2026-10-15/scene_80a_campaign_story_early.png`, SHA-256 `46bad71618d7d29b9206398dcde25512fcf217ee2c99ce47c206a840a1022069`.
- This screen verifies the mission 3 opening only. The later Max-arrival line `0xE0075A` has no verified b32r5 frame.

Replay from the repository root, choosing a new output directory:

```sh
memcap -n aw-kor-w2b6e -- nice -n 15 python3 tools/playthrough_capture.py \
  --rom output/game_wars_korean_candidate_20261015_b32r5.gba \
  --harness temp/mgbah_linux --out temp/release_C/80a_campaign_story_early_replay_NEW \
  --import-legacy-game-save temp/release_C/work/w2b4/saves/g1_da9d97cf.sav \
  --legacy-save-sha256 da9d97cfda87998c4759b162d3075ea62ba6dd0389fe531f705f6c966834f45a \
  --legacy-source-rom-sha256 51b10dcf48204be4762c3c262c6a9de0de87fb014d7e0043742e7db02fff7d98 \
  --legacy-provenance-note 'W2b4 legacy SRAM; unverified origin; cheat-tainted' \
  --no-contact-sheets --gzip-emulator-log --lossless-palette-frames \
  < tools/scene_routes/80a_campaign_story_early/inputs.txt
```
