BLOCKED: Four of the nine remaining terrain categories still lack paired live cards: lake, generic cannon, laser, and A laser. The two requested paired loss paths were captured. No Japanese or broken Korean was observed on the reached candidate screens, so no patch change was justified.

# Part 2 remaining-screen QA, 2026-10-26

## ROM identity and method

- Checkout HEAD: `7ddecc2d937264b5a031bd3a55bc4d64b3462291`.
- Japanese ROM SHA-256, before and after: `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c`.
- Existing Korean candidate `output/game_wars_korean_gate_repro.gba` SHA-256, before and after: `4fd453daf1ac0d065ecd322fa71943e7ee53e69ba7abfd3984fd9e41c2db210d`. It was not rebuilt. Its build receipt does not prove exact correspondence to this HEAD (unverified).
- Each ROM was cold-booted with its own copied SRAM and then used only its own savestates. The emulator used `--read-only-save` for SRAM entry; copied saves and generated states remain under this evidence directory. Test-only cursor writes chose on-map tiles without changing the tile map. HQ setup also moved one purchased infantry through a test-only coordinate write, explicitly noted below.
- The source compact-label table at `tools/build_korean_full.py:6057` identifies the two unnamed Sweep 3 categories as A laser and impassable. This is a ROM-label inventory; a live A-laser card remains (unverified).

## Paired live terrain cards

| Category | Japanese / Korean capture | Native entry and status |
|---|---|---|
| Missile site | [ミサイル基地](original/cards_11_20/id_180.png) / [미사일기지](candidate/cards_11_20/id_180.png) | War Room row 20; live tile ID `0x180`. PASS. |
| Airport | [空港](original/cards_23_23/id_1cd.png) / [공항](candidate/cards_23_23/id_1cd.png) | War Room row 23; live tile ID `0x1cd`. PASS. |
| Research lab | [研究所](original/campaign_lab_turn/lab_card.png) / [연구소](candidate/campaign_lab_turn/lab_card.png) | M7 native battle. An occupying enemy unit was moved with a test-only unit-coordinate write before the native turn/menu input; terrain was not edited. PASS with this setup qualifier. |
| Volcano | [火山](original/volcano_cards/id_1a7.png) / [화산](candidate/volcano_cards/id_1a7.png) | Green Earth mission 26 native entry from copied legacy SRAM; tile ID `0x1a7`. PASS with historical save provenance (unverified). |
| Impassable | [進入不可](original/fortress_cards/id_1ae.png) / [진입불가](candidate/fortress_cards/id_1ae.png) | Fortress M10 native entry from copied legacy SRAM; tile ID `0x1ae`. PASS with historical save provenance (unverified). Runtime wording differs from the source compact label `통행불가` but is legible. |
| Cannon | [ミニキャノン](original/fortress_cards/id_183.png) / [미니캐논](candidate/fortress_cards/id_183.png) | Fortress card proves **mini cannon only**. Generic `キャノン` remains (unverified). |
| Lake; generic cannon; laser; A laser | No paired live card. | BLOCKED. The built-in War Room maps scanned here and the valid custom-map terrain palette did not expose a confirmed live card for these four. |

The [valid custom-map editor result](original/editor_valid/valid-map.png) / [Korean result](candidate/editor_valid/valid-map.png), [Versus custom-map category](original/versus_back/category_5.png) / [Korean category](candidate/versus_back/category_5.png), and [live Versus entry](original/versus_play/advance_3.png) / [Korean entry](candidate/versus_play/advance_3.png) confirm the native editor-to-battle workflow. They do not prove any of the four missing card types. A separate 180-action original cannon replay ended in a story/battle scene without a generic cannon card; its [image](original/cannon_m4_180/segment_180.png) is exploratory, not paired evidence.

## Paired loss paths

| Path | Evidence and inputs | Result |
|---|---|---|
| Own HQ captured | Both ROMs cold-booted independently from copied Free Battle SRAM (`ece0b0c8740ca7620b6ee49f65313ec34557a4da00501e06fd4d266455ce03df`). Native team setting changed the second side from CPU to player 2: [Japanese](original/hq_setup/team_two_human.png) / [Korean](candidate/hq_setup/team_two_human.png). Side 1 ended its turn; side 2 bought infantry. A test-only `w8 02022882 0107` positioned that infantry on side 1 HQ; native end-turn and Capture inputs completed both capture turns. [Japanese success banner](original/hq_second/capture_second.png) / [Korean success banner](candidate/hq_second/capture_second.png), then [Japanese result](original/hq_post/after_01.png) / [Korean result](candidate/hq_post/after_01.png) show side 2 WIN and side 1 LOSE. | PASS for independent two-human Versus HQ-capture loss on both ROMs. Campaign-specific failure dialogue remains (unverified). |
| Actual day limit | Source mission condition at `data/translation_for_import.csv:10187` says occupy the laboratory within seven days or eliminate all enemies. Each ROM cold-booted independently from copied M7 Day 2 SRAM (`f7368561a4f4145dfd99f5c8a0893c062264af988488176ddf43a46014f936c8`); [Japanese live timer](original/day_entry/08_A.png) / [Korean live timer](candidate/day_entry/08_A.png) showed six days remaining. Native End Turn advanced days without a day-counter write; [one day left](original/day_wait_day7/wait_11.png) / [Korean](candidate/day_wait_day7/wait_11.png) preceded expiry. [Japanese loss](original/day_dialogue_day_dialogue_day_turns_day7_8_16/advance_00.png) / [Korean loss](candidate/day_dialogue_day_dialogue_day_turns_day7_8_16/advance_00.png) show `作戦失敗` / `작전실패`. | PASS for this M7 day-limit failure on both ROMs. The historical SRAM's original creation is (unverified); no timer cheat was used in this replay. |

Natural CO unlock was deferred as requested.

## Commands, exits, and cleanup

- Paired War Room entry: `memcap -n p2-* -- nice -n 15 python3 temp/evidence_p2_remaining2_0252/scan_maps.py {original,candidate} 11 20` and `21 28`; targeted `scan_cards.py` for rows 20 and 23. All final runs exit 0. Per-ROM input, emulator reply, ROM SHA, and exit are in `original/maps/commands.json`, `candidate/maps/commands.json`, and each card directory's `commands.json`.
- Paired campaign terrain: `volcano_entry.py`, `volcano_continue.py`, `volcano_cards.py`, `fortress_cards.py`, and `campaign_lab_turn.py` for each ROM under `memcap -n p2-* -- nice -n 15 python3 ...`; all final runs exit 0. The entry and card `commands.json` files record input sequences and source-save hashes. The fortress and volcano legacy saves may carry prior cheats; no claim of untouched campaign progression is made.
- Paired HQ path: `hq_setup.py`, `hq_turn2.py`, `hq_buy.py`, `hq_cycle.py`, `hq_capture_finish.py`, `hq_second.py`, `hq_post.py` for each ROM under the same `memcap` wrapper; all final runs exit 0. Each `commands.json` records exact emulator commands and replies. Earlier exploratory states under `original/team/` and `original/hq_capture/` did not establish the loss and are not counted.
- Paired day-limit path: `day_entry.py`, `day_turns.py`, `day_dialogue.py`, and `day_wait.py` for each ROM under the same wrapper; all authoritative runs exit 0. `day_turns_day5/` opened Save because the CO Break menu item changed the index; `day_turns_day5_power/` used the corrected native End Turn selection and is authoritative. The exact inputs and replies are in each `commands.json`.
- `sha256sum` on both ROMs: exit 0, hashes match those above. `git status --short --branch`: exit 0, only `## hada0127/weekend-aw-kor-residual-20261024` and no changed tracked files. `git diff --check`: exit 0, no output. `git rev-parse HEAD`: exit 0, `7ddecc2d937264b5a031bd3a55bc4d64b3462291`.
- Heavy emulator jobs ran sequentially at low priority. `memcap` reported `systemd user bus 접근 불가(샌드박스?) — 메모리 상한 없이 대기열만 적용`; its shared queue still applied. No repository build or local CI was run because no code, data, or ROM was changed. No commit was made.

**Changed files:** ignored scripts, copied saves, logs, emulator states, screenshots, and this report under `temp/evidence_p2_remaining2_0252/` only. No tracked-file change. **Plan deviation:** four terrain categories remain open because no native card path was established in the available maps or valid editor palette. The mini-cannon card must not be treated as the generic cannon card. **Remaining risk:** visual inspection covers only reached screens; original save provenance and exact candidate build-to-HEAD relation are (unverified).

RECEIPT: model=gpt-6.1-sol effort=unknown role=code
