# Scene 19e7 — Part 1 Climate Status briefing

- Candidate ROM: `output/game_wars_korean_candidate_20261015_b32r5.gba`, SHA-256 `7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a`.
- Source save SHA-256: **none**. This route starts from a clean cartridge cold boot, creates a new Part 1 name, opens the Operation Room, and selects its Climate Status mission. It imports no SRAM or savestate.
- Input file: `inputs.txt`, SHA-256 `34eb63593f378229479f5606efb8a2d6a85453d3d06572a4f8aa2baa79c42724`.
- Cheat list: **empty**. The selected frame is `cheat_tainted: false`.
- Selected b32r5 endpoint: `temp/release_C/w2b6e_19e7_cold/0044_A_0005096.checkpoint.json`, core frame **5096**. The recorder closed with emulator exit code 0. I inspected the selected PNG directly. It reads **`오늘은 작전 전에 호이프 사령관에 대해 / 사령관님께 말할게요`**, matching CSV rows `0xDF7452` and `0xDF7482`; no visible clipping or replacement glyph. The registered PNG is `docs/screenshots/w2b6_b32r5_2026-10-15/scene_19e7_part1_hoip_co_weather_help.png`, SHA-256 `3393e8adb4f2df7a5da0702228bd2940b535a1045f591b3b226cdc4ab491f107`.

Replay from the repository root:

```sh
memcap -n aw-kor-w2b6e -- nice -n 15 python3 tools/playthrough_capture.py \
  --rom output/game_wars_korean_candidate_20261015_b32r5.gba \
  --harness temp/mgbah_linux --out temp/release_C/scene19e7_replay_NEW \
  --no-contact-sheets --gzip-emulator-log --lossless-palette-frames \
  < tools/scene_routes/19e7_part1_hoip_co_weather_help/inputs.txt
```

The dialogue is a mission selection briefing. This frame proves its Korean rendering; it does not prove a battle victory or later weather event.
