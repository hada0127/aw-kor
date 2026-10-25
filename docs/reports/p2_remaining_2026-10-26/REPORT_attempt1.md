BLOCKED: The nine missing terrain cards and both paired loss variants remain unverified. A candidate-only own-HQ loss was captured; the Japanese ROM rejected that historical Korean savestate. No translation fix was justified.

# Part 2 remaining-screen QA, 2026-10-26

## Identity and method

- Checkout HEAD: `7ddecc2d937264b5a031bd3a55bc4d64b3462291`.
- Japanese ROM SHA-256: `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c`.
- Existing candidate `output/game_wars_korean_gate_repro.gba` SHA-256: `4fd453daf1ac0d065ecd322fa71943e7ee53e69ba7abfd3984fd9e41c2db210d`. It was **not rebuilt in this task**; the build receipt does not record HEAD, so exact source-to-ROM correspondence is (unverified).
- Source ROM was symlinked under `original/` for the attempted workflow and removed afterward. No original ROM or tracked file was modified.
- All emulator runs used `memcap -n ... -- nice -n 15`; the sandbox reported `systemd user bus 접근 불가` and applied the shared queue without a memory cap. The runs were sequential. No `mgbah` process remained at close.
- The old Design Maps key route needed five additional `A` presses on each current ROM before reaching the map. The paired editor frames are [candidate](candidate/extra_a_04.png) / [Japanese](original/extra_a_04.png). The menu inputs and replies are in each `commands.json`.

## Screen table

| Screen | Setup and capture paths | Status |
|---|---|---|
| Terrain card: airport | The native editor toolbar showed `공항` / `空港`; the selected tile was placed on the editor map: [candidate selection](candidate/airport_map/airport_chosen.png), [placement](candidate/airport_map/airport_placed.png), [Japanese selection](original/airport_map/airport_chosen.png), [placement](original/airport_map/airport_placed.png). A native save-menu route and separate cold Versus route were attempted; [candidate category5](candidate/versus/category5.png) / [Japanese category5](original/versus/category5.png) are still prologue scenes. | **BLOCKED**: no live airport card or verified Versus map entry. A successful editor placement alone does not prove save/Versus playback. |
| Terrain card: lake | Paired toolbar scans: [candidate palette](candidate/terrain_palette_contact.png), [Japanese sequence](original/terrain_00.png) through `terrain_33.png`. | **BLOCKED**: no lake card; editor tile identity and valid placement route (unverified). |
| Terrain card: missile site | Same toolbar scan; the missile icon is visible, but no matched battle information card was reached. | **BLOCKED**: no card capture. |
| Terrain card: research lab | Same paired toolbar scan. | **BLOCKED**: no card capture; normal editor placement route (unverified). |
| Terrain card: cannon | Same paired toolbar scan. | **BLOCKED**: no card capture; normal editor placement route (unverified). |
| Terrain card: volcano | Same paired toolbar scan. | **BLOCKED**: no card capture; normal editor placement route (unverified). |
| Terrain card: lasers | Same paired toolbar scan. | **BLOCKED**: no card capture; normal editor placement route (unverified). |
| Terrain card: unidentified category 8 | The Sweep 3 report names only seven of its nine missing categories. | **BLOCKED**: exact category identity and paired card capture (unverified). |
| Terrain card: unidentified category 9 | Same inventory limit. | **BLOCKED**: exact category identity and paired card capture (unverified). |
| Loss: own HQ captured | Loaded a historical Part 2 M9 Korean savestate (segment 3793, Day 15) into the current candidate, then replayed the recorded 49 inputs. [Candidate dialogue](candidate/hq_loss/3841_A.png), [loss banner](candidate/hq_loss/3842_A.png), [contact](candidate/hq_loss/contact.png), [commands](candidate/hq_loss/commands.json), exit 0. The route is historically natural HQ capture but this replay is **savestate-assisted**. | **BLOCKED for paired comparison**: candidate Korean dialogue and `작전실패` are visible. Loading that savestate into the Japanese ROM led to illegal opcodes and a stalled emulator at segment 3835. That run was interrupted (exit 130); it provides no original loss capture. |
| Loss: day limit | Cold booted both ROMs from the same copied Part 2 M5 naval SRAM, used recorded input through the Day 1 map, then test-only wrote `w8 020231cc 07` and ended the turn through the native menu. [Candidate Day 2](candidate/day_limit/advance_14.png) / [Japanese Day 2](original/day_limit/advance_14.png), both exit 0. The write did **not** force the native day counter: both still showed Day 2. | **BLOCKED**: the run reached Day 2 tutorial dialogue, not the day-limit loss. The RAM write is cheat-assisted and is not evidence of a day-limit condition. |
| Hidden COs via natural SRAM unlock | Prior Sweep 3 used RAM substitution. No native unlock-bit edit or paired profile run was completed here. | **BLOCKED (optional)**: natural unlock remains (unverified). |

## Commands, exits, and cleanup

| Command | Exit/result |
|---|---|
| `memcap -n p2remaining-{candidate,original} -- nice -n 15 python3 temp/evidence_p2_remaining_0245/probe.py {candidate,original}` | 0 each on the final editor/palette runs. |
| `memcap -n p2-airport-{candidate,original} -- nice -n 15 python3 temp/evidence_p2_remaining_0245/airport_map.py {candidate,original}` | 0 each; save-menu inputs completed, but Versus map validity was not established. |
| `memcap -n p2-versus-{candidate,original} -- nice -n 15 python3 temp/evidence_p2_remaining_0245/versus.py {candidate,original}` | 0 each; route diverged into prologue, so objective not reached. |
| `memcap -n p2-hq-candidate -- nice -n 15 python3 temp/evidence_p2_remaining_0245/loss_replay.py candidate` | 0; 49 historical inputs replayed and candidate loss banner captured. |
| Same HQ command with `original` | Interrupted, exit 130, after repeated `Illegal opcode: 0000ea00`; the runaway emulator log was removed after stop. This is a **failed** comparison. |
| `memcap -n p2-day-{candidate,original} -- nice -n 15 python3 temp/evidence_p2_remaining_0245/day_limit.py {candidate,original}` | 0 each on final attempt; matched Day 2, no loss. |
| `git diff --check` | 0, no output. |

**Changed files:** ignored scratch scripts, captures, saves, and this report under `temp/evidence_p2_remaining_0245/` only. Tracked files: none. No source fix, new ROM build, or commit. The temporary source-ROM symlink was removed. The abandoned attempt's near-gigabyte illegal-opcode log was removed after stopping its emulator.

**Plan deviation and remaining risk:** The requested `Design Map → save → Versus → card` path was not proven; the old saved-map route diverged on this checkout. The candidate-only HQ capture cannot validate original-vs-Korean layout or text. The day-limit setup never entered the loss condition. The nine cards and both paired loss variants must remain open in the sweep inventory.
