# W7 two-cartridge Link capture — 2026-10-26

## Scope and integrity

- Source original: `original/Game Boy Wars Advance 1+2 (Japan).gba`, SHA-256 `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c`.
- Candidate: `output/game_wars_korean_candidate_20261026_hlaser.gba`, SHA-256 `01f65b11d0dfa65c95b76558bd7997b761133aaf9abe68442bc608c4791b262e`.
- Real BIOS: `temp/bios/gba_bios.bin`, SHA-256 `fd2547724b505f487e6dcb29ec2ecff3af35a841a77ab2e85fd87350abd36570`.
- The only harness change is `w7/mgba_link_harness.c`: player 1 loads the same ROM when the second cartridge argument equals the host path. The executable is `w7/bin/mgba_link_harness`. Runs cold-booted both cores in one process; no linked-core savestate was loaded. Code and ROMs outside `temp/` were not edited by W7. Each run has `receipt.json`, emulator log, stderr, and command/response transcript in its evidence directory.
- **CHEAT** runs alter only temporary ROM copies. The pointer at ROM offset `0xA38A60` (host waiting ticker's pointer table entry) is redirected to each target string. This exercises the real ticker renderer, but does not prove that the game's normal state machine reaches that branch. The source ROM bytes remain intact. A test-only `w32 0 0200C040 08A3508C` against a live RAM text pointer did **not** redraw the ticker; its captures are `candidate/multi/contact_cheat.png`. That RAM write is not counted as evidence for ID 3250.

## Decisions

`P0` is host, `P1` client. PASS means the reached candidate frame is legible and no Japanese or broken glyph was observed in the targeted text. English raster titles (`LINK MODE`, `MAP SELECT`, `TEAM SETTING`, `RULE SETTING`) remain. Some bottom lines scroll; the 16-frame CHEAT sheets span 320 frames and show the full repeating text. Meaning was checked against the paired original and source line where legible.

| Screen | Decision | Evidence and limit |
|---|---|---|
| Part 2 Multi-Pak link menu | **PASS** | [paired route sheet](multi_paired.png), row `menu`; actual two loaded cartridges and `xfer_multi` increases after entry. |
| Entry, 1P/2P waiting | **PASS** | [paired route sheet](multi_paired.png), rows `host_enter`, `client_enter`, `wait0`, `start`. The natural candidate lines for IDs 3242/3243 scroll legibly. |
| One-player START and cancel | **PASS** | [paired native alternate sheet](native_alt_paired.png). With P1 still at cold boot, P0 START shows `통신 준비 중이야!!!`; B returns to Link menu. No wrong-count error was shown. |
| Map selection | **PASS** for rendering | [paired route sheet](multi_paired.png), row `progress0`. Candidate map list is Hangul and legible. Exact localization of the map names is (unverified). |
| Team setting / default CO portraits | **PASS** for reached screen | [paired route sheet](multi_paired.png), rows `map_confirm_host` and `map_confirm_client`; [candidate input probe](candidate/co_probe/contact.png). Faces and `사령관을 고릅니다` fit. |
| Distinct link CO selection screen | **BLOCKED** | Team setting led to rule setting after A. LEFT/RIGHT/UP/DOWN on the host team screen did not expose a separate CO roster. A distinct CO picker was not observed; whether this mode supports one is (unverified). |
| Rule setting, battle start, in-battle map | **PASS** for reached frames | [paired route sheet](multi_paired.png), rows `co_host`, `start_battle`, `battle0`. Candidate Korean labels and `개시` fit. Full rule ticker wording is (unverified). |
| Multi-Pak result | **BLOCKED** | [paired result attempt](result_attempt_paired.png), [candidate controls](candidate/multi_result/controls_contact.png). The continuous W2 end-turn/surrender inputs entered the host menu and ended the host turn on **both** ROMs, but no client surrender dialog or result appeared. Additional candidate client B/A/START probes also stayed on the map ([probe](candidate/multi_result_probe/probe_contact.png)). No result judgment is made for Multi-Pak. W2/W3's Single-Pak result evidence is separate. |

### Requested Link lines

The target names below are the addresses supplied in the task. IDs 3242/3243 were also reached natively in Multi-Pak. Every row has an original/candidate **CHEAT** paired contact sheet and 16 individual ticker PNGs per ROM under `{original,candidate}/msg_ADDRESS/`. All 18 CHEAT emulator processes exited **0**. The pointer substitution is labeled in every receipt.

| ID | ROM address | Candidate decision | Paired contact sheet |
|---|---|---|---|
| 3242 | `0xA34F70` | **PASS**; native and CHEAT | [paired](paired_A34F70.png) |
| 3243 | `0xA34F98` | **PASS**; native and CHEAT | [paired](paired_A34F98.png) |
| 3250 | `0xA3508C` | **PASS (CHEAT)**; `맵을 송신 중이야…` legible | [paired](paired_A3508C.png) |
| 3251 | `0xA350B4` | **DEFECT (CHEAT)**; candidate displays the original Japanese `マップを受信中よ、しばらく待ってね！！` in the live ticker. The candidate's slot `0xA350B4..0xA350DB` is byte-identical to the original. | [paired](paired_A350B4.png) |
| 3252 | `0xA350DC` | **PASS (CHEAT)**; Korean start line legible | [paired](paired_A350DC.png) |
| 3253 | `0xA350F8` | **PASS (CHEAT)**; Korean return-to-menu line legible | [paired](paired_A350F8.png) |
| 3254 | `0xA3511C` | **PASS (CHEAT)**; Korean save/power warning legible | [paired](paired_A3511C.png) |
| 3255 | `0xA3514C` | **PASS (CHEAT)**; Korean download-preparation line legible | [paired](paired_A3514C.png) |
| 3256 | `0xA3517C` | **PASS (CHEAT)**; Korean connection-failure line legible | [paired](paired_A3517C.png) |

[Candidate ticker overview](candidate_tickers_overview.png) shows four phases of every requested line. No other broken glyph or clipping was observed in these target frames. Native triggers for 3250–3256, including map send/receive and physical disconnect, remain **BLOCKED**: `link off` in this harness pauses P1 scheduling and does not emulate cable removal. The one-player START route displayed only the normal communication-preparation line. The CHEAT patch proves text rendering, not those failure transitions.

## Commands and exits

All commands ran from repo root. `cc`, the paired Multi-Pak runs, both native alternate runs, the paired result attempts and candidate CO probe, the RAM pointer probe, and all 18 CHEAT runs exited **0** at the emulator/process level. The first navigation probe with `syncshot` while `link off` was interrupted (exit **130**) because the client's frame counter could not advance; its replacement navigation run exited **0** and no conclusion uses the interrupted run. Exact responses and terminal output are preserved in `w7/*.stdout` and each `receipt.json`.

```sh
cc -O2 -Wall -Wextra temp/unseen_20261026/w7/mgba_link_harness.c -lmgba -o temp/unseen_20261026/w7/bin/mgba_link_harness
memcap -n aw-w7 -- nice -n 15 python3 temp/unseen_20261026/w7/multipak.py candidate
memcap -n aw-w7 -- nice -n 15 python3 temp/unseen_20261026/w7/multipak.py original
memcap -n aw-w7 -- nice -n 15 python3 temp/unseen_20261026/w7/cheat_messages.py
memcap -n aw-w7 -- nice -n 15 python3 temp/unseen_20261026/w7/native_alt.py original
memcap -n aw-w7 -- nice -n 15 python3 temp/unseen_20261026/w7/native_alt.py candidate
memcap -n aw-w7 -- nice -n 15 python3 temp/unseen_20261026/w7/multipak_result.py candidate
memcap -n aw-w7 -- nice -n 15 python3 temp/unseen_20261026/w7/multipak_result.py original
memcap -n aw-w7 -- nice -n 15 python3 temp/unseen_20261026/w7/multipak_result_probe.py candidate
memcap -n aw-w7 -- nice -n 15 python3 temp/unseen_20261026/w7/co_probe.py candidate
memcap -n aw-w7 -- nice -n 15 python3 temp/unseen_20261026/w7/ramprobe.py candidate
memcap -n aw-w7 -- nice -n 15 python3 temp/unseen_20261026/w7/ramcheat.py candidate
```

Exploration: `memcap -n aw-w7 -- nice -n 15 python3 temp/unseen_20261026/w7/probe.py candidate` exited 0, and `navigate.py candidate` first exited 130 then reran with non-synchronizing screenshots and exited 0. The first probe entered the shop and was not used for a screen decision.

No `local-ci` or commit was run: this was a QA-only worker task with no tracked code edit. Concurrent tracked changes shown by `git status` belong to other workers (unverified ownership); W7 wrote only under `temp/unseen_20261026/w7/`.
