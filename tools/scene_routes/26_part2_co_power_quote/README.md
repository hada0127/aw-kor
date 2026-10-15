# Scene 26 — Part 2 CO Power quote (Kanbei)

- ROM: `output/game_wars_korean_candidate_20261015_b32r5.gba`, SHA-256 `7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a`.
- Cold-boot source: `temp/release_C/work/w2b4/saves/gen_80a9e74a.sav`, SHA-256 `80a9e74acea62d653dde291a2becd5b490d16c5067a4cc2bc01eff64a78f4f57`, legacy source ROM SHA-256 `e49637655dea5d81c76f358e967ba38383298f68edaa74d5c0738373e408ecdf`. Source chain is unavailable; every frame is cheat-tainted.
- Route: `inputs.txt`, SHA-256 `a8928d2d73cf5fe4fa13f2bd97b54177343c77e061cb5d3c0b739a0f9e58e60d`. It reproduces the earlier same-ROM battle path from the cartridge save, writes two damage-derived CO gauge counters (`cheat w16 020231D0 FFFF`, `cheat w16 0202320C FFFF`), opens the global menu, selects regular CO Power, and records the quote. Every intervention is in the recorder `actions.jsonl`. No cross-ROM savestate is used in this cold-boot replay.
- Run: `temp/release_C/w2b6f_scene26_kanbei_sourcefix/`, closed at core 15167, emulator exit 0, no input errors. Selected `0133_A_0015167.checkpoint.json` and permanently registered PNG `docs/screenshots/w2b6_b32r5_2026-10-15/scene_26_part2_battle_labels.png` have SHA-256 `af7db3d2ffd773417322cd7c506b819c40a72086be50f8b758cf0de90972e7be`. By eye the full visible quote reads `간다! 각오해라!`; the ensuing cut-in reads `일도양단`. The quote matches `data/dialogue_map.json` row `0xA306EC` and the candidate ROM pointer at `0xA385AC → 0x08A306EC`; direct read-watch is `(unverified)`. This proves one CO quote, not the full catalog range.

Replay from the repository root:

```sh
memcap -n aw-kor-w2b6f -- nice -n 15 python3 tools/playthrough_capture.py \
  --rom output/game_wars_korean_candidate_20261015_b32r5.gba \
  --harness temp/mgbah_linux --out temp/release_C/scene26_replay_NEW \
  --import-legacy-game-save temp/release_C/work/w2b4/saves/gen_80a9e74a.sav \
  --legacy-save-sha256 80a9e74acea62d653dde291a2becd5b490d16c5067a4cc2bc01eff64a78f4f57 \
  --legacy-source-rom-sha256 e49637655dea5d81c76f358e967ba38383298f68edaa74d5c0738373e408ecdf \
  --legacy-provenance-note 'Inherited w2b4 P2 battle SRAM; source checkpoint unavailable; screen QA only' \
  --no-contact-sheets --gzip-emulator-log --lossless-palette-frames \
  < tools/scene_routes/26_part2_co_power_quote/inputs.txt
```

## Sensei native CO quote

The same-ROM b32r5 lineage from `gen_53cc6670.sav` has native CO ID `0x12` (Sensei). `sensei_inputs.txt` replays that lineage from a cartridge-save cold boot, writes the two measured gauge counters, and activates regular `브레이크`. Route SHA-256: `37bf4a435a171f8620f6121e984dc618a7b074666e948aa852af80f68db284b4`. `temp/release_C/w2b6f_scene26_sensei_sourcefix/` closed at core 2746, emulator exit 0, without input errors. The visually inspected PNG `docs/screenshots/w2b6_b32r5_2026-10-15/scene_26_part2_co_power_sensei.png` reads `홋홋호 / 이쯤서 크게 승부다`, matching rows `0xA31368`/`0xA31374` by exact text. Direct runtime read-watch is `(unverified)`.

```sh
memcap -n aw-kor-w2b6f -- nice -n 15 python3 tools/playthrough_capture.py \
  --rom output/game_wars_korean_candidate_20261015_b32r5.gba \
  --harness temp/mgbah_linux --out temp/release_C/scene26_sensei_replay_NEW \
  --import-legacy-game-save temp/release_C/work/w2b4/saves/gen_53cc6670.sav \
  --legacy-save-sha256 53cc66707c25a62430fd769ae01f2acb6fd49780c40ce103498126bff07accc6 \
  --legacy-source-rom-sha256 6ae381d560ae55de469cc1ecb709468eff668a38e8a428bd195e8e0b135b5cb3 \
  --legacy-provenance-note 'Inherited w2b4 P2 SRAM; source checkpoint unavailable; screen QA only' \
  --no-contact-sheets --gzip-emulator-log --lossless-palette-frames \
  < tools/scene_routes/26_part2_co_power_quote/sensei_inputs.txt
```

All Sensei frames remain cheat-tainted from legacy SRAM and gauge writes.

## Synthetic CO ID sweep and native Max

`coNN_synthetic_inputs.txt` changes `0x020231CD` to CO ID `NN` with a logged `w8`, then writes the two gauge counters and activates regular `브레이크` from the Sensei battle save. The sweep covered IDs 0–18 except native IDs 6/18 and the unavailable ID 10; the 16 successful synthetic screenshots and exact hashes are indexed in `docs/screenshots/w2b6_b32r5_2026-10-15/scene_26_part2_co_power_gallery.json`. Each proof is cheat-tainted and establishes only quote asset rendering. ID 10 Sturm did not expose a Power choice in this friendly-side menu.

A separate native Max save, `gen_1d1e0935.sav` (SHA-256 `1d1e0935ac8a6808a67dfc0d8d84681bbb3656ca43ce1552ed480025aea4381a`, source ROM `5886d44541409fe4dd50f2113d014650311a81c79579c3479f375c5cc4eda7d5`), replays with `max_native_inputs.txt` (same route bytes as `sensei_inputs.txt`). `temp/release_C/w2b6f_scene26_max_native_sourcefix/` closed at core 2746, exit 0; core-2724 screenshot `scene_26_part2_co_power_max_native.png` reads `힘겨루기라면 지지 않아!` (row `0xA3036C`). It is cheat-tainted from legacy SRAM and gauge writes.

## Native Andy and Sami saves

The `w2b4` save inventory was cold-boot surveyed on b32r5 (`temp/release_C/w2b6f_native_survey_results.jsonl`). Battle saves exposed native CO IDs Andy 1, Max 2, Sami 4, Kanbei 6, and Sensei 18. Six survey saves with ID 0 opened on the world map; they do not establish a Nell power opportunity. Source ROM hashes for the survey come from `temp/release_C/work/w2b4/p2_unique.txt`.

- Andy: `gen_29d329d7.sav`, SHA-256 `29d329d7fa9339713a4c93eff6538d05decbbb8b1fadd903a67ebacae849829f`; source ROM `18a1b5b5911cea317db15f1da1e498307cbe58dc17cc513f572b93effb209610`. `andy_native_inputs.txt` SHA-256 `37bf4a435a171f8620f6121e984dc618a7b074666e948aa852af80f68db284b4`. Run `temp/release_C/w2b6f_scene26_andy_native/` closed at core 2746, exit 0, no input errors. Selected ledger core 2724 reads `화끈하게 가자고오-!` (row `0xA30264`), permanent `scene_26_part2_co_power_andy_native.png`.
- Sami: `gen_2f13157d.sav`, SHA-256 `2f13157d40bdb3c381a941e13a8d72cf959e095be9f226ab540858d04c740529`; source ROM `17dff0c0af7a91afcefdfe80b1bf7f4e88f0ef12da2e1b6560eaf9d591d0e0e9`. `sami_native_quote_inputs.txt` SHA-256 `12d52779ed2e71f69e22fe52960c167a07df0428ba6bbd7b36292cf788349614`. Run `temp/release_C/w2b6f_scene26_sami_native_quote2/` closed at core 2660, exit 0, no input errors. Its ledger frame reads `간다-!` (row `0xA303D8`), permanent `scene_26_part2_co_power_sami_native.png`. The longer diagnostic run advanced past this short quote; this route stops on the fully visible frame.

Both are cheat-tainted from imported legacy SRAM and logged gauge writes. For reproduction, use the same `playthrough_capture.py` command structure as Sensei above, replacing the save path, save/source SHA, output path, and route with the lines above. Direct runtime quote read-watch is `(unverified)`.

## Native Olaf from the b28 M21 save

The last three distinct P2 saves in `w2b6d_save_inventory.tsv` were cold-boot surveyed too. `I2_m21_victory/game.sav` (SHA-256 `09112f41228b4bbb161987a97f9f975c421473167c06d03cd2aeca309a6097de`, source ROM `effc6ee8680a98057b87d3d2acd95b1de8a613dd60ba4310a9b76b271faa74cb`) opened a battle with native Olaf ID 3. `olaf_native_inputs.txt` (SHA-256 `37bf4a435a171f8620f6121e984dc618a7b074666e948aa852af80f68db284b4`) cold-booted this save, wrote the two gauge counters, and activated regular `브레이크`. `temp/release_C/w2b6f_scene26_olaf_native/` closed at core 2746, exit 0, no input errors; ledger core 2724 and permanent `scene_26_part2_co_power_olaf_native.png` read `이 몸에게 덤빈 것 / 후회하게 해주마!` (rows `0xA304F0/0xA30504`). The image is cheat-tainted. Direct runtime read-watch is `(unverified)`. The other two b28 saves opened mode/rule or sound screens.
