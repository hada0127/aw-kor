BLOCKED: Natural C12 HQ capture and the live compact lake label were not reached; the paired captures use CHEAT access and the lake finding is static.

# Part 2 unseen screens: RE and paired capture (2026-10-26)

## Artifact identity and method

- Original ROM SHA-256: `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c`.
- Candidate ROM SHA-256: `4fd453daf1ac0d065ecd322fa71943e7ee53e69ba7abfd3984fd9e41c2db210d`.
- One emulator at a time. Every loaded `.ss0` was produced with the exact ROM used for that run. Both game-save inputs were cold-booted and read-only. No tracked file, source ROM, candidate ROM, or existing `output/` file was edited.
- **CHEAT scope:** test-only checksummed SRAM selected map `0x96`; separate test ROMs called the **existing C12 loss dialogue** and then native `Event_VictoryDefeat(2)`. Their SHA-256 values are `2fd4a7da40b60d1cc3b63c1afbdb13d79f43ff849b63a58f546a4bc889b37d60` (original-based) and `c139beb44f582404b000809fb6bf128b717fc08ecf1cb4c2f1d377e1cb4edc6e` (candidate-based). This proves renderer behavior for those native scripts; it **does not** prove that ordinary HQ capture reaches them or that the reused M7 battle state is a valid C12 playthrough. Exact edits and source hashes: `{original,candidate}/event_cheat.json` and `save_map96_checks.json`.

## A. Own-HQ loss dialogue and result

**PASS (CHEAT native script/result rendering); BLOCKED (natural HQ-capture trigger).**

- The local AW2 event reference `temp/aw2_mod_reference/event/campaign/c12_twoweektest/c12_5_event_1.asm` identifies the C12 loss script with text IDs `0x044F..0x0451`. This matches the Japanese ROM dialogue pointer table `0x08A357B4`: ID `0x044F` points to `0x08A1703C` (`ああ、守りきれなかった・・・`). The Japanese ROM map data for *Two-Week Test* is byte-identical to the reference mapfile at `0x0853DD8C`; map header `0x089F33D0` is entry 150 (`0x96`) of the `0x089EFDE8` table, stride `0x5C`. Its event table is `0x08829BF8`, loss trigger at `0x08829BD0`, and loss event at `0x08829A68`. The event data contains IDs `0x044F`, `0x0450`, `0x0451` in order. The event-condition function is `0x08338B64`.
- The live map loader `0x08317720` copies the working map ID to IWRAM `0x030040D2`. The prior M7 save held ID `0x90` in validated SRAM blocks `0x1A000` and `0x1C000`, relative byte `0x194`. Both copies were changed to `0x96` **with their native 4 KiB checksums recomputed**, in new files under `w4/`. A direct `w8 02000142 96` before mission entry was overwritten; the checksummed SRAM edit made the displayed/current ID `0x96` on both ROMs. This changes the map while old M7 unit and turn data persists, so it is only a screen-access route.
- The unmodified C12 loss event, forced as a day-3 event, displayed all three native dialogue IDs on the original ROM. It returned to the map with no result because the artificial call did not arise from a defeat condition. For result-screen QA, a **test-only copied event script** at `0x08FFF000` appends native `Event_VictoryDefeat(2)` after the original loss-event commands; C12's day-3 trigger points to that copy. The original and candidate both displayed the dialogue and the native failure banner/result transition. This appended call is part of the CHEAT, not evidence of natural defeat.
- Paired images: [loss dialogue and result](hq_paired.png); individual frames `{original,candidate}/hq_pages/advance_*.png`; full command transcripts `{original,candidate}/{map_trace_event,hq_event,hq_pages}/commands.json`. The candidate reads `아아, 지켜 내지 못했다...` and shows `작전 실패`. The Korean pages, faces, and failure banner are legible and fit, with no visible residual Japanese or broken glyph in the targeted screens. The post-result campaign map is reached, but its progress/save behavior is CHEAT-tainted.
- **Remaining risk:** actual HQ capture/capture-point decrement was not reproduced. The earlier W1 M7 infantry-on-HQ attempt did not capture. The C12 event call and result were deliberately forced; do not count this as natural loss or campaign progress.

## B. Hidden COs and shop

**PASS (CHEAT availability flags through native roster builder, paired shop/item and roster screens); native purchase/save persistence unverified.**

- W1 wrote `0x02027EEA |= 0x84`, but its roster stayed at 17. Runtime watchpoints showed that this menu uses roster builder `0x08380200`, which calls `0x0833D010`. The latter reads `0x02027EBC + 0x2A + (CO_ID >> 3)`, so IDs `0x0F` (Hachi) and `0x0A` (Hellbouze) use **`0x02027EE7` bits `0x80` and `0x04`**, respectively. `0x083451A4`/`0x0833D02C` use the other byte (`0x02027EEA`) and were not hit on this CO-select route. The menu's ROM list at `0x08A3B820` includes both IDs. Writing `0x02027EE7 |= 0x84` after save loading but before entry gave native roster IDs `01 02 04 00 0F ... 0B 0C 0D 0E 0A` and group counts **`5/3/3/3/5`** on both ROMs. No roster slot was directly substituted in W4.
- [Paired roster and shop](hidden_paired.png); per-ROM roster/profile captures `{original,candidate}/co_capture/`; builder watch and every RAM command `{original,candidate}/co_timing/commands.json`. Hachi/하치 and Hellbouze/헬보우즈 names and profile pages are readable and fit.
- Both items exist in the native shop table: Hellbouze record `0x0881ACFC`, 4,000 points, item ID `0x0A`; Hachi record `0x0881AD14`, 5,000 points, item ID `0x0F`. Their setter is `0x0833CED4`, which writes the same `0x02027EE7` availability bits. Shop checks: `0x0833CAE4`/`0x0833CA84` for Hellbouze (campaign flag `0x21` plus rank 5), `0x0833CB18` for Hachi (flag `0x22`). The read-only source save already had those campaign flags (`0x02027EBC=0x7B`), but score `0x010C` gave rank 4. A CHEAT write `0x0200C430=0x0120` made Hellbouze's item visible. Shop list and descriptions were captured on **both** source ROMs (no test ROM): `{original,candidate}/shop_hidden/{open_08,open_09,hachi_select,hachi_description}.png`, command logs alongside. Candidate labels and descriptions are Korean, legible, and not clipped.
- **Remaining risk:** the source save was opened read-only and the items were not purchased/saved. The native purchase UI and persistent unlock across reboot are unverified. The roster proof is the game building from CHEAT flags, not a purchase receipt.

## C. Lake `湖` compact label

**PASS (static mapping and map-data reachability); BLOCKED (live compact label screenshot and big-card `湖`).**

- `0x0832ACE8` selects compact label art as `0x08464D68 + ((u16[0x08815CFC + terrain_type*4] & 0x7F) * 0x100)`. At terrain type `0x09`, the table bytes are `08 00 02 00`, so the selected art index is **8 (`湖` in the original, `호수` in the candidate)**. Callers `0x0830299C` and `0x0832AD9C` mask the type with `0x1F` before the call. Therefore this label is not dead solely by lookup-table analysis.
- A natural, paired M10 map dump (`output/archive_worktrees_20261026/weekend/temp/evidence_p2_remaining2_0252/{original,candidate}/fortress_continue_25/ewram.bin`) has a `30×15` map and tile `0x01A4` at `(10,4)`, with terrain type `0x09` in both ROMs. Thus actual Part 2 map data contains the type that resolves to label index 8. W1's R-card for that natural tile showed `進入不可`/`진입불가`, and its RAM-substituted type-9 R-card showed `海`/`해`; the R-card follows a distinct text path. No native compact `湖`/`호수` image was visibly resolved, and no big-card `湖` was reached. Do **not** mark the compact asset unreachable; the big-card route remains (unverified).

## Commands and results

All emulator commands were serial through `memcap -n aw-w4 -- nice -n 15 ...`; each `commands.json` records every in-emulator command and `exit: 0`. Relevant process output (verbatim):

```text
original exit 0 before 0x7b last [15, 'A', 255, '010204000f0305100809110607120b0c0d0e0a00', '0503030305'] builder hits 37
candidate exit 0 before 0x7b last [15, 'A', 255, '010204000f0305100809110607120b0c0d0e0a00', '0503030305'] builder hits 37
original hq_event 0 22
original hq_pages 0 27
candidate hq_event 0 22
candidate hq_pages 0 27
original exit 0 old_flags 0x7b old_score 0c01 images 14
candidate exit 0 old_flags 0x7b old_score 0c01 images 14
```

Key exact commands (each `kind` was run serially as `original` and `candidate`):

```sh
XDG_CONFIG_HOME=$PWD/temp/unseen_20261026/w4/config tools/ghidra/decomp.sh 0x083451A4 0x0833D02C 0x0832ACE8
XDG_CONFIG_HOME=$PWD/temp/unseen_20261026/w4/config tools/ghidra/decomp.sh 0x08380200 0x0838021A 0x083854D0
XDG_CONFIG_HOME=$PWD/temp/unseen_20261026/w4/config tools/ghidra/decomp.sh 0x0833D010 0x083801E0
XDG_CONFIG_HOME=$PWD/temp/unseen_20261026/w4/config tools/ghidra/decomp.sh 0x08338B64
memcap -n aw-w4 -- nice -n 15 python3 temp/unseen_20261026/w4/co_timing.py original
memcap -n aw-w4 -- nice -n 15 python3 temp/unseen_20261026/w4/co_timing.py candidate
memcap -n aw-w4 -- nice -n 15 python3 temp/unseen_20261026/w4/co_capture.py original
memcap -n aw-w4 -- nice -n 15 python3 temp/unseen_20261026/w4/co_capture.py candidate
memcap -n aw-w4 -- nice -n 15 python3 temp/unseen_20261026/w4/map_trace.py original temp/unseen_20261026/w4/original/save_map96_checks.sav temp/unseen_20261026/w4/original/event_cheat.gba
memcap -n aw-w4 -- nice -n 15 python3 temp/unseen_20261026/w4/map_trace.py candidate temp/unseen_20261026/w4/candidate/save_map96_checks.sav temp/unseen_20261026/w4/candidate/event_cheat.gba
memcap -n aw-w4 -- nice -n 15 python3 temp/unseen_20261026/w4/hq_loss.py original event
memcap -n aw-w4 -- nice -n 15 python3 temp/unseen_20261026/w4/hq_loss.py candidate event
memcap -n aw-w4 -- nice -n 15 python3 temp/unseen_20261026/w4/hq_pages.py original
memcap -n aw-w4 -- nice -n 15 python3 temp/unseen_20261026/w4/hq_pages.py candidate
memcap -n aw-w4 -- nice -n 15 python3 temp/unseen_20261026/w4/shop_hidden.py original
memcap -n aw-w4 -- nice -n 15 python3 temp/unseen_20261026/w4/shop_hidden.py candidate
```

The Ghidra launch needed `XDG_CONFIG_HOME=$PWD/temp/unseen_20261026/w4/config` because the default home config was read-only; it reported each targeted function `OK`. `memcap` admitted the jobs but reported `systemd user bus 접근 불가(샌드박스?) — 메모리 상한 없이 대기열만 적용`. The last `rtk git status --short` showed only pre-existing untracked `.mcp.json` and no tracked changes. No commit or push was made.

RECEIPT: model=unknown effort=unknown role=code
