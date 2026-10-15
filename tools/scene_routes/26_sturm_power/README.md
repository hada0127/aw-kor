# Scene 26 — Sturm Super CO Power quote

- Target ROM: `output/game_wars_korean_full.gba`, SHA-256 `7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a`.
- Cold-boot source: `temp/release_C/work/w2b4/saves/gen_53cc6670.sav`, SHA-256 `53cc66707c25a62430fd769ae01f2acb6fd49780c40ce103498126bff07accc6`; declared legacy source ROM SHA-256 `6ae381d560ae55de469cc1ecb709468eff668a38e8a428bd195e8e0b135b5cb3`. Source checkpoint is unavailable. The entire run is **cheat-tainted**.
- `inputs.txt` SHA-256 `4779b0806c655db4a11e34b5cc957e0f09ce476294b30ff6a3ff0722ce0d0d2f`. It changes the friendly CO ID at `0x020231CD` to `0x0A` and writes **both 32-bit** charge fields `0x020231D0` and `0x0202320C` to `0x0001FFFF` with logged two-halfword `w16` operations (`FFFF0100`). No cross-ROM savestate is used. The earlier `0xFFFF` probes changed only the low halfwords (maximum `65535`); the 10-star Sturm Super Power remained unavailable. ROM CO record `0x9FC418 + 10*260` has regular-power star count `0` at `+0x0C` and Super star count `10` at `+0x10`. The exact numerical charge threshold is (unverified).
- Full replay: `temp/release_C/verify1_sturm/full_meter_probe/`, core 2746, emulator exit 0, no input errors. Core 2621 shows the enabled `S브레이크` menu item; PNG `docs/screenshots/verify1_2026-10-15/scene_26_sturm_super_available.png`, SHA-256 `8db112c17dbe7dddf7502c8a5931eea7694f1430f2713c6e0cd3adecd458a373`.
- Core 2724 shows Sturm and the exact visible Korean quote **`살아 돌아가지 못해!`**; PNG `docs/screenshots/verify1_2026-10-15/scene_26_sturm_super_quote.png`, SHA-256 `94b5b248e99b60bb180b1f2728c2f49e162bf4d40a035c99d5dc7a7c5853ca99`. The line matches `data/dialogue_map.json` row `0xA30AFC`; candidate ROM pointer `0xA38610 → 0x08A30AFC`. Direct runtime text read-watch is (unverified). No replacement glyph or clipping is visible.
- This proves Sturm's quote renders under a synthetic friendly CO ID and full charge. It does not prove native playable unlock or normal-play progression.

Replay from repository root, with a new output directory:

```sh
memcap -n aw-kor-verify1 -- nice -n 15 python3 tools/playthrough_capture.py \
  --rom output/game_wars_korean_full.gba \
  --harness temp/mgbah_linux --out temp/release_C/verify1_sturm/replay_NEW \
  --import-legacy-game-save temp/release_C/work/w2b4/saves/gen_53cc6670.sav \
  --legacy-save-sha256 53cc66707c25a62430fd769ae01f2acb6fd49780c40ce103498126bff07accc6 \
  --legacy-source-rom-sha256 6ae381d560ae55de469cc1ecb709468eff668a38e8a428bd195e8e0b135b5cb3 \
  --legacy-provenance-note 'VERIFY-1 inherited P2 SRAM; source checkpoint unavailable; charge and CO-ID writes; screen QA only' \
  --no-contact-sheets --gzip-emulator-log --lossless-palette-frames \
  < tools/scene_routes/26_sturm_power/inputs.txt
```
