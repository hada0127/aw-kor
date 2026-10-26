BLOCKED: Native campaign HQ Capture and its loss dialogue/result/post screen were not reached. The lake compact label was reached by CHEAT on both ROMs; a distinct lake R-card title is absent from the inspected native title table.

# W10 RE and paired QA, 2026-10-26

## Identity and evidence

- Original: `original/Game Boy Wars Advance 1+2 (Japan).gba`, SHA-256 `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c`.
- Candidate: `output/game_wars_korean_candidate_20261026_hlaser.gba`, SHA-256 `01f65b11d0dfa65c95b76558bd7997b761133aaf9abe68442bc608c4791b262e`.
- Every forced state below is **CHEAT**. Test states and captures live only in `temp/unseen_20261026/w10/`. Each emulator used one matching ROM and read-only cartridge save; no cross-ROM state load, tracked edit, commit, push, or output artifact edit.
- [CHEAT lake pair](lake_paired.png), [CHEAT lake label zoom](lake_label_zoom_paired.png), [CHEAT human enemy turn pair](hq_paired.png), [CHEAT failed native Capture pair](hq_failed_capture_paired.png). Each per-ROM directory has its source state, command/reply log, ROM/save SHA, exit code, and individual screenshots.

## L. Lake compact label and R card

**PASS, CHEAT compact label rendering. BLOCKED, natural accessibility. No native `湖` R-card title found.**

- The empty natural M10 type-9/tile-`0x01A4` cell still displays `進入不可` / `진입불가` on the R card. Runtime watchpoints in `lake_watch/art_watch.log` show the original R-card title pointer read at `0x08A37CC0` by PC `0x08346F12` and text read at `0x08A29AA4`; the type-9 compact-art table and lake art have **zero** reads on that empty-cell path. The R-card title table at `0x08A37C7C` has 18 entries: `海` at index 0 and `進入不可` at index 17, with no `湖` title. A distinct `湖` big-card text was not found there. The existing larger lake graphic at original offset `0xB93FD0` is a separate asset, not proof of a lake R-card title.
- On the valid M7 battle map, **CHEAT** `w8 0201F7D7 09` placed terrain type 9 under a native unit at `(11,6)`. Its compact terrain/status panel rendered original `湖` and candidate `호수` live in [the pair](lake_label_zoom_paired.png). The candidate label is legible, fits, and has no visible Japanese residue or broken glyph. Both per-ROM `lake_status/lake_art_watch.log` files record reads of type-9 table `0x08815D20` at PC `0x0832ACF4` and art `0x08465568` copied toward VRAM `0x060138E0`. The unit R card shows unit information, not a lake title.
- Normal-play reachability of the compact lake label is **(unverified)**: the M10 natural type-9 tile is impassable and no unmodified route with a unit standing on type 9 was shown. The table and asset are live when that condition is forced. A native lake big-card title was not established.

## H. Own-HQ loss by native Capture

**BLOCKED.** The enemy turn is human controllable by CHEAT in a valid campaign state, but no native Capture option, animation, failure dialogue, result, or post screen was reached on either ROM.

- Versus team-setting RAM diff identified `0x02023207`: CPU `02`, human `01`. The initial Versus option also changes `0x02017B4A` `02→01`, but that setup byte does not control the campaign enemy turn. In the valid M7 map, `w8 02023207 01` before End Turn yielded a stationary Black Hole human turn on both ROMs; `m7_enemy/{army_before,army_after}.bin` proves `02→01`. Candidate menus and map UI in [the pair](hq_paired.png) are legible, without obvious clipping, broken glyphs, or residual Japanese in those captured screens.
- W6's `0x020225EC` record was the wrong side for this purpose. Clicking its red units `(11,6)` and `(12,6)` on the Black Hole turn only showed a movement preview. A 15×10 cursor scan on the original found controllable Black Hole units at `(10,0)`, `(2,2)`, and `(5,3)`: `m7_grid_scan/` has all 150 scores and the native selection/confirmation screenshots. At `(2,2)`, second A opened the native `待機` action menu.
- **CHEAT** changed the live `(2,2)` unit at `0x020228E0` from type 7 to infantry type 0 and substituted the original player-HQ terrain type/tile at `(2,2)` (`0x0201F792=28`, `0x02003052=01C5`, `0x0201EDA2=01C5`). The soldier sprite appeared, but the native action menu offered `待機` only, with no Capture. Applying the same writes before the enemy turn did not change that result. Changing the property owner byte to `48` also did not expose Capture. These are test-only probes, not valid natural map edits.
- **CHEAT** then moved the live controllable unit's three matching record copies (`0x02000458`, `0x020024AA`, `0x020228E0`) to the actual M7 player HQ `(0,9)` and changed its type to infantry. On both ROMs, the unit was not selectable at the HQ; A opened the map menu, not a unit action menu ([failed pair](hq_failed_capture_paired.png)). Merely writing coordinates does not establish the native occupancy/action state. The C12 map-ID save is mixed with M7 unit data and gave the same limitation; its campaign human-turn probe is in `original/hq_capture_army/`.
- The exact remaining requirement is to move or spawn a Black Hole infantry through the game's active unit/occupancy path onto the actual player HQ, then select native Capture twice (or set real capture points) and record animation, loss dialogue, result, and post screen on each ROM. W4's forced event/result remains separate CHEAT evidence and is **not** a native Capture pass.

## Commands and verification

Every emulator invocation ran serially with `memcap -n aw-w10 -- nice -n 15 python3 temp/unseen_20261026/w10/probe.py <task> <ROM>`; exact commands, replies, and exit codes are saved per task in `commands.json`. Representative completed stdout (verbatim):

```text
original lake_status exit 0 images 4
candidate lake_status exit 0 images 4
original m7_enemy exit 0 images 7
candidate m7_enemy exit 0 images 7
original m7_native_teleport exit 0 images 5
candidate m7_native_teleport exit 0 images 5
```

`memcap` admitted the jobs but printed `systemd user bus 접근 불가(샌드박스?) — 메모리 상한 없이 대기열만 적용`; its memory cap was unavailable in this sandbox. The pre-work temperature check was below 80°C. No test ROM copies were created.

RECEIPT: model=unknown effort=unknown role=code
