# Part 2 Single-Pak surrender investigation — 2026-10-26

## Finding

The 2026-10-26 gate ROM **does reach `작전성공` and return its host to the lobby** when the complete W2 input route is run continuously from a cold boot. W2's frozen-map observation is reproducible only with its separate linked-core savestate reload stages. Under that staged replay, b43 and b44 fail exactly like gate; b42 and earlier tested b35/b40 pass. The byte that changes this staged outcome is the host welcome line at ROM `0xA34F98`: b43 adds one full-width space (`81 40`) after the comma. Reverting only its fixed 46-byte slot in b43 makes the staged replay pass; transplanting only the b43 slot into b42 makes it fail. This is a **replay/snapshot-sensitive failure**, not evidence that the gate ROM's native uninterrupted link battle is broken. The exact mGBA/custom-driver restore mechanism is **(unverified)**.

## Environment and procedure

- Harness: `temp/unseen_20261026/w2/bin/mgba_link_harness`, SHA-256 `df9cb2f84e867a767bf8cf113a3d5a4760c05dd5d2e1f8b930d87c20ba07a597`; BIOS `temp/bios/gba_bios.bin`, SHA-256 `fd2547724b505f487e6dcb29ec2ecff3af35a841a77ab2e85fd87350abd36570`.
- Each tested released ROM was cold-booted with an empty client cartridge slot, receiving the native MultiBoot image. `staged.py` follows W2's `run_link.py` inputs, captures, ROM-specific states, and `run_continuation.py` tokens. Every load was guarded by same-ROM SHA, BIOS SHA, state hash, producer receipt, and `cheat_tainted: false`. Every listed emulator run exited `0`.
- `diagnose.py gatevisual` follows the same inputs and captures in one uninterrupted linked session, omitting only the intermediate savestate loads and link-off/on transitions. Its host shows `작전성공` at frame 8097 and lobby by frame 9597; the client also returns. Its receipt is `gatevisual/receipt.json`; the decisive images are `gatevisual/host_01_p0.png` and `gatevisual/host_late_0_p0.png`.
- `diagnose.py candidate` reloads W2's candidate `battle_part2_host_endturn/{host,client}_end.ss0` and runs 7,200 additional host frames after frame 8997. Through frame **16197**, the host picture remains the same map (`host_late_11_p0.png`); the client is in the lobby. This confirms a persistent crash in that replay, not a slow result animation.

## ROM bisect

`OK` = host reaches result/lobby. `CRASH` = host stays on map and enters undefined-instruction exception during staged replay. All SHA values are for the ROM actually loaded.

| ROM | SHA-256 | Staged W2 route | Uninterrupted route |
| --- | --- | --- | --- |
| Original Japanese | `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c` | OK (W2) | (unverified) |
| b35, 2026-10-15 | `7e4a3a9e6602b3fe1b82853420ee6ff46ed43b5c6ef2f0d058b71b97eb1c0a36` | OK | (unverified) |
| b40, 2026-10-18 | `f1f183347e68480c55061377e74e21dbb8b86b95403c9db5d19ef072305c8be3` | OK | (unverified) |
| b42, 2026-10-19 | `1c23b09160a9f7e491c8d2de8782e80200a13fb4238aec92999728b0282b1fbf` | OK | (unverified) |
| b43, 2026-10-19 | `488094f77a823648907c48e1647d2f53f356c5d70dfd39a8d1c3b4419aa03e34` | **CRASH** | (unverified) |
| b44, 2026-10-21 | `1ac68443d8fa48ef50a5a73290f94d65ff90997b4e6f38bc60410c9d424c6f02` | **CRASH** | OK (`b44/receipt.json`) |
| 2026-10-23 int | `c9969d84434d43526ffdf5d289189138c185a60d813d33d3518842a924739b03` | (unverified) | OK |
| 2026-10-23 sweep | `db0d07c221359f1be839942de3d0cab77e2699cea3ed30cf9ec502d07c786f46` | (unverified) | OK |
| 2026-10-26 gate | `4fd453daf1ac0d065ecd322fa71943e7ee53e69ba7abfd3984fd9e41c2db210d` | **CRASH** | **OK** (`gatevisual/receipt.json`) |

The b42→b43 change is the first observed staged-replay failure. b43→b44 changes only 96 bytes of dialogue cursor art, so it cannot explain the first occurrence. The gate's newer patches likewise are not required for the staged failure.

## Address and restore evidence

- `staged_b43`, `staged_b44`, and `staged_gate` have identical decisive host behavior. At the end of `battle_part2_host_endturn`, the host PC is valid (`0x02014E7A`, Thumb/system mode). After the next pair load it reaches `pc=D0FCD100` and then the undefined-instruction exception (`pc` cycles around BIOS vector addresses `0x00000008..0x60`, `CPSR` low byte `9B`). `probe_candidate` places the exception within **12 host frames of the state reload**, before the client confirms surrender. The client continues to lobby. The failed host is therefore not waiting in the link receive loop; SIO transfers continue to increment while its CPU is faulted.
- The RAM code at host `0x02014E60..` is byte-identical in original and candidate state dumps. Its ROM source sequence occurs once at offset **`0x922ADC`** in original, b44, and gate. The whole Part 2 MultiBoot payload `0x90DC7C..0x9463FC` is byte-identical between b44 and gate, and between b42 and b43. There is no implicated changed MultiBoot code hook. The successful-result OBJ sheet at `0x930520` is unchanged in both comparisons.
- `tools/part2_capture_banner.py` writes the unrelated capture-complete sheet at `0x47F79C`; b44 and gate differ there, but both have the same staged failure and gate's uninterrupted result works. The success overlay path in `tools/build_korean_full.py:8596` is not reached on the failed staged host because the exception precedes surrender.
- `temp/release_C/canon10/b42_b43_static_diff.json` identifies nine approved Link status spacing edits. Within `0xA34F70..0xA351A4`, restoring all b42 bytes in a temporary b43 ROM passes. Restoring the first four rows passes; restoring the last five fails. Restoring the first two passes; restoring the map-transfer two fails. **Restoring only `0xA34F98..0xA34FC8` passes; restoring only neighboring `0xA34F70..0xA34F98` fails.** The reverse transplant, b42 with only b43's `0xA34F98..0xA34FC8`, crashes. Receipts are in `staged_hybrid*/battle_part2_result_yes/receipt.json`; all hybrid ROMs are scratch artifacts under `w3/` and were cold-booted with their own states.
- The actual b42→b43 `0xA34F98` edit adds encoded full-width space `81 40`, shifting the remaining characters two bytes inside a **46-byte fixed slot**. Both versions retain `00 00` after the slot. The text source is `data/dialogue_overrides.json:3249` (also mirrored in `tools/build_korean_full.py:1013`), written by the dialogue-override stage at `tools/build_korean_full.py:14970-15054`; `tools/build_korean_full.py:12846-12865` checks this slot. The byte edit changes staged route phase, as shown by different host/client PCs at the controls-stage save even though the host/client frame counts match. Why the mGBA pair restore converts that phase into an invalid PC is **(unverified)**. The likely boundary is `tools/mgba_link_harness.c:469-488`, which loads the two cores separately, recomputes SIO bits, and resets their time bases without serializing the driver's full shared transfer schedule.

## Proposed minimal fix (not applied)

For this QA route, replay from cold boot in one linked harness process through surrender, and judge the continuous `host_01` and lobby captures. Keep ROM-specific savestates as navigation aids only; do not use independent two-core `loadstate` as proof of native link behavior until the harness serializes/restores the shared SIO driver state and a save→load→continue comparison matches an uninterrupted run. The b43 welcome wording should not be reverted as a game fix based on this evidence alone. Native hardware behavior is **(unverified)**.

## Commands and integrity

All emulator runs used `memcap -n aw-unseen-w3 -- nice -n 15 python3 temp/unseen_20261026/w3/{diagnose,staged,probe,dump_state}.py ...` with exact stdout in `w3/*.stdout`; all completed `EXIT 0`, and receipts say `cheat_tainted: false`. `sha256sum` checked the ROM, BIOS, and harness identities. No tracked source, ROM in `output/`, or protected branch was edited; only `temp/unseen_20261026/w3/` was written. `rtk git status --short` showed only pre-existing untracked `.mcp.json`.
