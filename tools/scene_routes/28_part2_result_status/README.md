# Scene 28 — campaign failure overlay

- Candidate: `output/game_wars_korean_candidate_20261015_b32r5.gba`, SHA-256 `7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a`.
- Cold-boot save: `temp/release_C/w2b6b/I2battle_legacy/game.sav`, 131072 bytes, SHA-256 `09112f41228b4bbb161987a97f9f975c421473167c06d03cd2aeca309a6097de`. Its declared source ROM SHA-256 is `effc6ee8680a98057b87d3d2acd95b1de8a613dd60ba4310a9b76b271faa74cb`. Recheck the full save SHA before replay. The source chain is unavailable, so import as `legacy_unverified_sram`; all resulting frames are `cheat_tainted` and are screen evidence only.
- Input: `inputs.txt` SHA-256 `0d240c5e0dc07db67e49b58f5f118bf4a424e087b755f25a2d9110a3204a2072`. It includes the cold-boot navigation, `시스템` → `항복한다` → `예`, and the loss dialogue. There are no new RAM writes in this route; inherited source taint remains.
- b32r5 target: core frame **6224**, checkpoint `temp/release_C/w2b6c_scene28_cold/0043_A_0006224.checkpoint.json`. I inspected the selected endpoint PNG directly (SHA-256 `ecee9fa99508e68bd47278fd3620e8590eb366e692511a0815c4ce71a3876f5b`). Its RGB pixels exactly match the registered ledger/permanent PNG (SHA-256 `4a66bfec64d8aa06db0d92b775c25b45848b28835f7fe2167fb8d30cd4b72ae8`). The exact visible Korean is **`작전실패`**. This is an OBJ overlay, so no `dialogue_overrides.json` or translation CSV line corresponds to the rendered text. The settled core 6250 is the selected visual evidence below.
- Recorder output: `temp/release_C/w2b6c_scene28_cold/`, `exit.json` status `closed`, emulator exit 0. The source save was verified byte for byte at cold boot. No savestate is used in this recipe.

Replay on b32r5 from the repository root after checking both SHA-256 values:

```sh
memcap -n aw-kor-w2b6c -- nice -n 15 python3 tools/playthrough_capture.py \
  --rom output/game_wars_korean_candidate_20261015_b32r5.gba \
  --harness temp/mgbah_linux \
  --out temp/release_C/scene28_replay_NEW \
  --import-legacy-game-save temp/release_C/w2b6b/I2battle_legacy/game.sav \
  --legacy-save-sha256 09112f41228b4bbb161987a97f9f975c421473167c06d03cd2aeca309a6097de \
  --legacy-source-rom-sha256 effc6ee8680a98057b87d3d2acd95b1de8a613dd60ba4310a9b76b271faa74cb \
  --legacy-provenance-note 'Inherited M21 cartridge SRAM; source checkpoint unavailable; screen QA only' \
  --no-contact-sheets --gzip-emulator-log --lossless-palette-frames \
  < tools/scene_routes/28_part2_result_status/inputs.txt
```

For a later candidate, change only `--rom` and `--out`; keep the save bytes and `inputs.txt` unchanged. Check the new target frame and PNG visually before registering that candidate. The frame number is an observed b32r5 result, not a guarantee of identical timing after a ROM change.

## W2b6-F settled visual review

`inputs_settled.txt` extends the same cold-boot route by 180 neutral frames. Replay `temp/release_C/w2b6f_scene28_extended/` closed at core 6404, exit 0, with every frame preserved and legacy-save taint. The animation introduces the four glyphs from cores 6135–6170. The selected settled frame is core **6250**, `docs/screenshots/w2b6_b32r5_2026-10-15/scene_28_part2_result_status_settled_PASS.png` (PNG SHA-256 `e8bb592d3622c79ffe66434b57ab55c26b41e97900d0580f12f7227d968f8561`). Exact displayed text: `작전실패`. This is a PASS for the settled visual comparison.

The prior 13 px measurement came from unused sheets at ROM offsets `0xBFBB54` and `0xEE8F68`; that diagnosis is superseded. The live result sheet is at `0x45EC74`. Its four white glyph faces are each 25 px high, and affine y origins 64/62/60/64 match the Japanese settled wave. The old PNG is retained as `scene_28_part2_result_status_settled_superseded_not_defect.png` with the same SHA-256; it is not active defect evidence.
