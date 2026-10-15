# Scene 80a — Max arrival (group 0xE0075A)

- Target ROM: `output/game_wars_korean_full.gba`, SHA-256 `7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a`.
- Reuse the complete cartridge-SRAM cold-boot route `tools/scene_routes/19c2_part1_fog_map_story/inputs.txt` (SHA-256 `b54fcebf3f311a3eeed1687a2423e0e2d113d14bd8aba8db167a1e65c9936ec7`). It begins at the legacy Part 1 M3 save, wins M3 by actual HQ capture after logged position writes, then enters the Max-arrival campaign dialogue. The later M4 and M5M actions are irrelevant to this claim.
- Existing b32r5 replay: `temp/release_C/w2b6f_scene19c2_cold2/`, emulator exit 0, full route endpoint core 56131. The target frame is core **12873**, checkpoint `0105_A_0012873.checkpoint.json`, ledger RGB SHA-256 `b511d4fb8c3decded4927d41ffd619384f5905612c86d5ea6e2715d4c42b837d`. The cartridge SRAM source and all frames are **cheat-tainted**. No cross-ROM savestate is used in the replay.
- Selected screen: `docs/screenshots/verify1_2026-10-15/scene_80a_max_arrival.png`, PNG SHA-256 `79f3914b71284c2377549c77f90ab9d67d41e12d2850c4480cc2130d9e30ab1c`. I read the visible line exactly as **`많이 기다렸지!`**. This equals `data/dialogue_groups.json` group `g_00E0075A` (`0x00E0075A`, Japanese `またせたな！`). No replacement glyph or clipping is visible. Direct runtime text read-watch is (unverified).
- The earlier `80a_campaign_story_early` frame at core 6193 proves the distinct `0xE00166` M3 opening. The present frame extends the same scene's coverage to Max's later arrival.

Replay command: use the command in `tools/scene_routes/19c2_part1_fog_map_story/README.md` with `--rom output/game_wars_korean_full.gba` and a new `temp/` output directory.
