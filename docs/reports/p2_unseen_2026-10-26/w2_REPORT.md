# T4 cable battle QA — 2026-10-26

## Scope and setup

- Original: `original/Game Boy Wars Advance 1+2 (Japan).gba`, SHA-256 `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c`.
- Candidate: `output/game_wars_korean_candidate_20261026_gate.gba`, SHA-256 `4fd453daf1ac0d065ecd322fa71943e7ee53e69ba7abfd3984fd9e41c2db210d`.
- Real BIOS: `temp/bios/gba_bios.bin`, SHA-256 `fd2547724b505f487e6dcb29ec2ecff3af35a841a77ab2e85fd87350abd36570`.
- Two-core mGBA link harness rebuilt at `temp/unseen_20261026/w2/bin/mgba_link_harness`. Each ROM was cold-booted separately. Each has its own savestates and provenance in its evidence directory; no cross-ROM state load. All receipts report `cheat_tainted: false`.
- This is native Single-Pak MultiBoot. `tools/mgba_link_harness.c:346-375` loads the host ROM on core 0, but core 1 accepts only an empty slot or a MultiBoot image. **Multi-Pak with two cartridges: BLOCKED** by this harness interface; not tested. The Single-Pak route's host menu visually says `MULTI-PAK`, but the client slot is empty and receives native MultiBoot, as verified by the receipt's transfer counts.

## Screen decisions

`P0` = host, `P1` = client. Paths below are relative to this report's directory. PASS means the reached candidate frame has legible text, no observed clipping or garbled glyph, and the visible meaning matches the original. A momentary scrolling ticker or animation frame is not a full text audit.

| Screen | Candidate decision | Paired evidence and observation |
|---|---|---|
| Part 2 link menu | **PASS**, with English branding | [original P0](original/link_menu_host_p0.png), [candidate P0](candidate/link_menu_host_p0.png). Korean `멀티팩 대전` and help text visible; `LINK MODE` remains English art. No Japanese in the captured menu body. |
| Part 2 entry/waiting | **PASS** for reached route; **BLOCKED** for other messages in IDs 3242/3243/3250–3256 (`0xA34F70..0xA3517C`) | [original P0](original/entry_wait_host_p0.png), [candidate P0](candidate/entry_wait_host_p0.png), [candidate loading P0](candidate/transfer_00_host_p0.png), [candidate loading P1](candidate/transfer_01_client_p1.png). Candidate loading warning `스위치를 끄거나 케이블을 뽑지 마세요.` is legible. Entry ticker is mid-scroll, so its full wording is (unverified). Error, map-send, and other branch messages were not triggered. |
| Part 2 map select, P0/P1 | **DEFECT** | [original P0](original/map_select_host_p0.png), [candidate P0](candidate/map_select_host_p0.png), [original P1](original/map_select_client_p1.png), [candidate P1](candidate/map_select_client_p1.png). Candidate still displays English `RED STAR`, `BLUE MOON`, `NOT CONNECTED`, `MAP1`–`MAP5`, and `WAIT`, pixel-identical in the observed labels to the original. No visual corruption, but the selection UI is untranslated. |
| Part 2 CO select | **BLOCKED** | The captured Single-Pak route goes directly from map selection to battle. No CO picker appeared. |
| Part 2 day banner, P0/P1 | **PASS** | [original P0](original/battle_part2_host_endturn/host_after_p0.png), [candidate P0](candidate/battle_part2_host_endturn/host_after_p0.png), [original P1](original/battle_part2_host_endturn/client_after_p1.png), [candidate P1](candidate/battle_part2_host_endturn/client_after_p1.png). `1일째 / 작전개시` is legible on both candidate screens; animation frame spacing differs between players. |
| Part 2 in-battle host menu | **PASS** | [original P0](original/battle_part2_host_endturn/host_menu_p0.png), [candidate P0](candidate/battle_part2_host_endturn/host_menu_p0.png). `시스템 / 종료` fits its small box and preserves the original options. |
| Part 2 in-battle client menu/choice | **PASS** for surrender choice | [original P1](original/battle_part2_result_yes/client_dialog_p1.png), [candidate P1](candidate/battle_part2_result_yes/client_dialog_p1.png), [candidate yes focus P1](candidate/battle_part2_result_yes/client_yes_focus_p1.png). Korean surrender warning and `예 / 아니오` fit and preserve the original choice. A separate client system popup was not captured. |
| Part 2 battle end/result | **DEFECT** on candidate host; **PASS** for client return | [original host result](original/battle_part2_result_yes/host_01_p0.png), [original host lobby](original/battle_part2_result_yes/host_extra_2_p0.png), [candidate host at same frame](candidate/battle_part2_result_yes/host_extra_2_p0.png), [candidate client lobby](candidate/battle_part2_result_yes/client_extra_2_p1.png). After the client confirms surrender, original host shows victory and returns to the lobby. Candidate client returns to the lobby, while candidate host remains on the battle map through host frame 10797, 1,800 frames beyond the first late result capture. A candidate host victory/result frame was **not reached**. This is a bounded functional divergence; root cause is (unverified). |
| Part 1 link menus (optional) | **PASS** for observed menu labels | [original P0](original/part1_link/link_menu_p0.png), [candidate P0](candidate/part1_link/link_menu_p0.png), [candidate Single-Pak focus](candidate/part1_link/single_pak_focus_p0.png). Main Korean labels are legible. The capture catches layered/scrolled small help text; full help text is (unverified). |

## Commands and exits

All commands below ran from repository root. `cc` and all 12 emulator stages exited **0**; the full command/response transcripts, ROM and BIOS hashes, screenshot hashes, and emulator exit codes are in each stage's `receipt.json`. No ROM or tracked source was edited.

```sh
cc -O2 -Wall -Wextra tools/mgba_link_harness.c -lmgba -o temp/unseen_20261026/w2/bin/mgba_link_harness
memcap -n aw-unseen-w2 -- nice -n 15 python3 temp/unseen_20261026/w2/run_link.py original
memcap -n aw-unseen-w2 -- nice -n 15 python3 temp/unseen_20261026/w2/run_link.py candidate
memcap -n aw-unseen-w2 -- nice -n 15 python3 temp/unseen_20261026/w2/run_continuation.py original
memcap -n aw-unseen-w2 -- nice -n 15 python3 temp/unseen_20261026/w2/run_continuation.py candidate
memcap -n aw-unseen-w2 -- nice -n 15 python3 temp/unseen_20261026/w2/run_part1_menu.py original
memcap -n aw-unseen-w2 -- nice -n 15 python3 temp/unseen_20261026/w2/run_part1_menu.py candidate
```

Continuation was rerun once for both ROMs with three extra 600-frame observations. Both reruns exited 0. Exact stdout logs: `original/{run,continue,part1}.stdout` and `candidate/{run,continue,part1}.stdout`. Rebuilt candidate savestates: `candidate/{host,client}_map_select.ss0` and `candidate/{host,client}_battle.ss0`, each with `.provenance.json` and receipt. No cheat or test-only RAM write was used.

## Remaining limits

- Multi-Pak with two loaded cartridges and a CO picker need another link-capable setup or a harness extension. No claim about those screens.
- Only the reached Single-Pak waiting/loading messages were judged. The requested alternate messages in `0xA34F70..0xA3517C` remain **BLOCKED** as runtime screens.
- The candidate host's missing victory/result after client surrender is reproducible under this deterministic route but has not been isolated to ROM logic versus harness timing (unverified).
