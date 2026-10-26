# Part 2 unseen-screen capture, 2026-10-26

## Artifact identity and limits

- Original ROM SHA-256: `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c`.
- Candidate ROM SHA-256: `4fd453daf1ac0d065ecd322fa71943e7ee53e69ba7abfd3984fd9e41c2db210d`.
- Every harness process used one ROM. Every loaded state was created with that same ROM; no cross-ROM savestate load. Existing candidate `WK` states are valid because `WK/candidate/maps/commands.json` records the exact candidate SHA above. Harness processes exited `0` (individual command replies and exit codes are in each `commands.json`).
- Screens reached through RAM writes are **CHEAT** evidence of rendering only. They do not prove natural map access, save persistence, or intended unlock progression. The source state contains the same mission/map on both ROMs, but language assets differ as expected.
- The card at the cursor after R is a different renderer from the small map cursor label. Captures before R are named `*_popup.png`. For RAM-substituted tiles the compact cursor label did not visibly resolve at the selected cell, so the compact labels `湖`, `キャノン`, `レーザー`, `Hレーザー` remain unverified in live play.

## Results

| Item | Status | Paired observation / reason | Evidence |
|---|---|---|---|
| T1 lake `湖`, type `0x09` | **BLOCKED** | Natural M10 tile `0x1a4` gave `進入不可` / `진입불가`; natural volcano type-9 tiles gave `火山` / `화산`. CHEAT type `0x09` with tile `0x1a4` gave `海` / `해`, not the `湖` label. Thus no lake card or compact lake label was reached. | [terrain pair](terrain_paired.png), per-ROM `terrain/commands.json` |
| T1 generic cannon, type `0x1a` | **PASS (CHEAT rendering only)** | Substitution of type `0x1a`, tile `0x187` gave original `キャノン` and candidate `캐논`, readable without clipping. Natural type `0x15` tile `0x182` and CHEAT `0x15` tile `0x183` gave `ミニキャノン` / `미니캐논`, so they must not stand in for generic cannon. No natural tile `0x187` existed in the paired `WK` dumps. | [terrain pair](terrain_paired.png) |
| T1 laser, type `0x19` | **PASS (CHEAT rendering only)** | Substitution of type `0x19`, tile `0x181` gave original `レーザー砲` and candidate `레이저포`; text and card fit. The paired `WK` dump scan found no `0x181`, so natural route remains unverified. | [terrain pair](terrain_paired.png) |
| T1 H laser, type `0x1e` | **DEFECT (CHEAT rendering)** | Original R card reads `ヘルレーザー`; candidate R card reads `A레이저`. The candidate changes the weapon name to “A laser”; the original meaning is Hell Laser. Both cards fit. R card text source address is **(unverified)**; the compact label art for index 22 starts at ROM `0x08466368`, but this was not shown to be the R card's text source. | [terrain pair](terrain_paired.png), `cheat_a_laser_card.png` in both ROM folders |
| T2 14-day campaign own-HQ loss, `0xA1703C` block | **BLOCKED** | The script block is consistent with *Two-Week Test* / 14-day defense (mission identification from local guide and dialogue is **(unverified in the game)**). No save/state for that mission was found. M7 campaign was tried as a separate fallback: CHEAT enemy infantry coordinates `0x020225EE=00 09` put a blue infantry on the Orange Star HQ, followed by two native End Turn actions. The unit remained there; HQ terrain byte stayed `0x28` (owner 1, type 8); no capture/loss dialogue or result screen appeared. Initial trial at `0x020225A6` moved an allied unit and was discarded as a wrong-owner probe. No screen from `0xA1703C` was reached, so this is not a PASS. | per-ROM `hq_m7_enemy_attempt/`, `hq_m7_enemy_dialogue/`, `hq_m7_enemy_second_turn/` contacts and command logs |
| T3 hidden CO unlock list | **BLOCKED** | CHEAT `0x02027EEA |= 0x84` before entry and at earlier route checkpoints persisted as `0xff`, yet the roster at `0x03005A70` remained 17 COs with row counts `4/3/3/3/4`. Neither hidden CO was added by that bit write. The CO select roster builder's additional condition or true unlock flag is **(unverified)**. | per-ROM `hidden_co/roster.bin`, `co_probe/commands.json`, [initial list](candidate/hidden_co/contact.png) |
| T3 hidden CO `0x0f` Hachi select/profile | **PASS (CHEAT direct roster substitution)** | Writing ID `0x0f` into the first IWRAM roster slot `0x03005A70`, then refreshing selection, showed `ハチ` / `하치`, its profile text pages, and unit info. Candidate Hangul is legible without obvious clipping or broken glyphs. This proves profile rendering, not unlock. | [paired select/profile](hidden_co_substitute_paired.png), [paired pages](hidden_co_pages_paired.png) |
| T3 hidden CO `0x0a` Hellbouze select/profile | **PASS (CHEAT direct roster substitution)** | Same method with ID `0x0a` showed `ヘルボウズ` / `헬보우즈`, profile pages, and unit info. Candidate Hangul is legible without obvious clipping or broken glyphs. This proves profile rendering, not unlock. | [paired select/profile](hidden_co_substitute_paired.png), [paired pages](hidden_co_pages_paired.png) |

No tracked file, ROM, save, or existing `output/` artifact was modified.

## State provenance and CHEAT addresses

`WK` = `output/archive_worktrees_20261026/weekend/temp/evidence_p2_remaining2_0252`.

- Natural M10: `WK/{original,candidate}/fortress_continue_25/step_23.ss0`; cursor `(10,4)` tile `0x1a4`, `(10,8)` tile `0x182`. The script scrolls left for 180 frames before cursor/R capture.
- Natural volcano: `WK/{original,candidate}/volcano_continue_20/step_09.ss0`; cursor `(11,6)` tile `0x1a4`, `(11,5)` tile `0x1a5`.
- CHEAT terrain: `WK/{original,candidate}/maps/row20.ss0`, source dump `row20.bin` (`16x12`), cell `(4,4)`, index 68. `w8 0201F7B6` for type; `w16 0200309A` and `w16 0201EDEA` for tile copies. Values and every command are in per-ROM `terrain/commands.json`. Cursor write `w16 030034F0 4000400004000400` is a capture aid, also a RAM write. All test-only writes are CHEAT.
- CO unlock-bit CHEAT: shared SRAM source `output/archive_worktrees_20261026/p2/temp/evidence_20261023/sweep3_shop_persist_candidate.sav`, SHA `5ff97b544819de359a136898c95bf6311ae6c8b8ddc458ca6a8924d05454c9ce`; read-only save, cold boot per ROM. Source route: `route_inputs/sweep3b_profiles17_fixed_inputs.txt` first 16 steps. The last step enters CO select. EWRAM `0x02027EEA` observed `0x7b`, written `0xff`. `co_probe.py` also wrote it earlier (route indices 0, 8, 10, 12, 15), with `0xff` surviving to CO select. All writes are CHEAT.
- Direct roster substitution CHEAT: per-ROM `hidden_co/co_select_cheat.ss0` created in this run with that same ROM; `w8 03005A70 0f` or `0a`, then Right/Left to refresh. Each profile/info page captured with R then Down. This is a separate fallback from the failed unlock-bit path.
- M7 campaign fallback: `WK/{original,candidate}/day_entry/map.ss0`; source map dump `15x10`, player HQ `(0,9)` owner/type byte `0x28`. The first probe `w8 020225A6 0009` moved an allied unit and was not used as target evidence. The enemy probe `w8 020225EE 0009` moved enemy infantry record `0x020225EC`; two native End Turn selections were executed with intervening dialogue. All these are CHEAT-tainted. `hq_m7_enemy_second_turn/ewram.bin` still has unit `00 01 00 09 64 02 30...` and HQ byte `0x28` in both ROMs.

## Exact emulator commands and results

All launches were serial, one emulator at a time, through `memcap -n aw-unseen-w1 -- nice -n 15 ...`. The host temperature check before the runs showed CPU under 80°C and `memcap status` had free slots. In this sandbox memcap reported `systemd user bus 접근 불가(샌드박스?) — 메모리 상한 없이 대기열만 적용`; queue admission was applied, but the memory cap was unavailable. All listed scripts returned exit code `0`; their harness command/reply transcript and source state are in `commands.json` next to the captures.

```sh
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/capture.py original
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/capture.py candidate
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/co.py original
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/co.py candidate
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/co_probe.py original
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/co_probe.py candidate
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/co_substitute.py original
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/co_substitute.py candidate
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/co_pages.py original
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/co_pages.py candidate
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/hq_attempt.py original
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/hq_attempt.py candidate
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/hq_dialogue.py original
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/hq_dialogue.py candidate
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/hq_second_turn.py original
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/hq_second_turn.py candidate
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/hq_enemy_attempt.py original
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/hq_enemy_attempt.py candidate
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/hq_enemy_dialogue.py original
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/hq_enemy_dialogue.py candidate
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/hq_enemy_second_turn.py original
memcap -n aw-unseen-w1 -- nice -n 15 python3 temp/unseen_20261026/w1/hq_enemy_second_turn.py candidate
```

`capture.py`: `original terrain 0 18`; `candidate terrain 0 18`. `co.py`: both `co 0`, original byte `0x7b`, roster remained without IDs `0x0f`/`0x0a`. `co_probe.py`: both ROMs showed `0xff` retained through entry, roster unchanged. `co_substitute.py`: both `hidden_co_substitute 0 6`. `co_pages.py`: both `hidden_co_pages 0 14`. Each HQ stage on each ROM reported exit `0`, with 19/12/19 frames respectively for each attempt chain. These are process successes, not screen PASS claims.
