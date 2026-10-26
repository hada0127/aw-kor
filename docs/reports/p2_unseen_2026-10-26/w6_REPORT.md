# W6 paired capture report — 2026-10-26

ROMs: original SHA-256 `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c`; candidate `01f65b11d0dfa65c95b76558bd7997b761133aaf9abe68442bc608c4791b262e`. Each emulator started cold from a read-only cartridge save. All `.ss0` states created here were loaded only with their own ROM. All scratch and images are under `temp/unseen_20261026/w6/`. No tracked file, ROM, or pre-existing output artifact was edited by this worker.

| Item | Status | Paired evidence and judgment |
|---|---|---|
| L. M10 lake/type-9 label and card | **BLOCKED** for `湖` / `호수`; **PASS** for the actual type-9 screen | Fresh cold replay from `WK/{original,candidate}/fortress_entry/input.sav` (WK = `output/archive_worktrees_20261026/weekend/temp/evidence_p2_remaining2_0252`). D-pad moved natively from `(29,14)` to `(10,4)`; no cursor RAM write. Both RAM dumps show map `30×15`, tile `0x01A4`, type `0x09`. The live compact label says `進入不可` / `진입불가`; R card says the same. Neither `湖` nor `호수` appeared. The candidate card is legible, fits, and has no visible Japanese residue or broken glyph. [Paired sheet](lake_paired.png); individual [original](original/lake/contact.png), [candidate](candidate/lake/contact.png), and per-ROM `commands.json`. The `0x08465568` index-8 art exists, but this natural tile's runtime UI selects the impassable label instead. Thus the art's live reachability remains unverified. |
| H. Campaign own-HQ capture loss | **BLOCKED** | **CHEAT**: used W4's checksummed SRAM map-ID `0x96` save, which still carries old M7 units. Cold boot gave a `15×10` C12 map. The actual player HQ is `(6,1)`, terrain owner/type `0x28`; the first probe incorrectly used `(0,9)` (`0x46`, a different property), then a second probe placed enemy infantry record `0x020225EC` at `(6,1)` via `w8 020225EE 0601`. Native End Turn and enemy AI ran on both ROMs. After 16×180 frames, the HQ remained `0x28` and the unit remained at `(6,1)`; no capture animation, loss dialogue, or `작전 실패` result occurred. [Paired sheet](hq_paired.png); per-ROM `hq_target/commands.json`, `hq_terrain.bin`, `hq_after.bin`, `enemy_unit_before.bin`, `enemy_after.bin`. This is no native-capture PASS. W4's forced event/result images remain separate CHEAT evidence and are not claimed here. |
| S. Shop purchase and persistent hidden COs | **PASS (CHEAT points/rank/unlock prerequisites; native purchase/save)** | **CHEAT** before shop entry: `0x02027EBC |= 0x06` for prerequisite flags and `w16 0200C430 ffff` for points/rank. In both source ROMs, A presses opened native Hellbouze and Hachi descriptions, native Yes/No confirmations, and purchase messages. Exit by B reached the game's own save prompt; A confirmed it. Before that prompt, dumped SRAM was byte-identical to input; after confirmation, original SRAM differed by 207 bytes. Fresh cold boot from each ROM's `save_exit/confirmed_00.sav`, with **no RAM writes after reboot**, produced unlock byte `0x02027EE7 = ff` and native roster IDs `...0f...0a`, group counts `05 03 03 03 05`. Both COs were selected and profiled. The candidate's `헬보우즈` and `하치` labels, dialog text, and profiles are legible and fit, without visible Japanese residue, broken glyphs, or clipping on these captured screens. [Paired sheet](shop_paired.png); per-ROM `shop/`, `save_exit/`, `reboot_saved/` contacts and `commands.json`. Inheritance of the CHEAT setup is explicit; the purchase and cartridge-save transition itself is native. |

## Commands and process results

Every emulator command below ran serially under `memcap -n aw-w6 -- nice -n 15`; `memcap` admitted each run after queue waits. It reported `systemd user bus 접근 불가(샌드박스?) — 메모리 상한 없이 대기열만 적용`, so its memory cap was unavailable. Temperatures checked before work were below 80°C. Complete in-emulator commands and replies are in each `commands.json` (`exit: 0`). Process output:

```text
original lake exit 0 images 13
candidate lake exit 0 images 13
original shop exit 0 images 7
candidate shop exit 0 images 7
original save_exit exit 0 images 13
candidate save_exit exit 0 images 13
original reboot_saved exit 0 images 8
candidate reboot_saved exit 0 images 8
candidate hq exit 0 images 20
candidate hq_target exit 0 images 20
original hq_target exit 0 images 20
```

The first `candidate save_exit` retry returned `ERR dumpsave size=131072` because its own existing `save_00.sav` conflicted with the harness's exclusive-create rule; the W6 save files for that retry were removed and the clean rerun above passed. The earlier `original shop` over-advanced through extra stock items and was replaced by the targeted rerun above. `python3 -m py_compile temp/unseen_20261026/w6/capture.py` exited `0`. The worktree has tracked edits from other concurrent workers; this W6 task made none.

## Remaining risk

The type-9 compact art's intended live route is still unknown. C12's checksummed-save route changes map ID but retains M7 unit/turn data; the AI's failure to capture may reflect that mixed state. No unmodified campaign save at C12, native capture animation, or native HQ-loss result was captured. These remain **BLOCKED**, not candidate-screen PASS claims.
