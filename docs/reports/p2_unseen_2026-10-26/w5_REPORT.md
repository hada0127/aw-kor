BLOCKED: The unchanged Thumb fixture cannot verify this candidate: it hardcodes `output/game_wars_korean_gate_r3_0126.gba`, which is absent, and asserts the previous ROM SHA. The first attempt also lacked `unicorn`; installing it locally under `temp/gate_pydeps` exposed the missing-ROM failure. No fixture pin was changed.

# Type 0x1e Hell Laser label, 2026-10-26

## Change and artifact

- `tools/build_korean_full.py`: compact terrain label at `0x466368`, `A레이저` → `헬레이저` (four 8 px glyphs in 32 px).
- `data/objlabel_sprites.json`: the builder regenerated the matching sprite metadata, `A레이저` → `헬레이저`. This is the only tracked data change; no unexpected builder rewrite was found. Existing untracked `.mcp.json` was untouched.
- Search of `tools` for `A레이저`, `0x1e`, and `A laser` found no second R-card source with the old text. The runtime capture below confirms the changed asset reaches both the R card and small cursor label.
- Built with `nice -n 15 python3 tools/build_korean_full.py --out output/game_wars_korean_candidate_20261026_hlaser.gba --no-sync-outputs --report temp/encode_report.csv`; exit `0`, [build log](../w5_build.log).
- New ROM: `output/game_wars_korean_candidate_20261026_hlaser.gba`, SHA-256 `01f65b11d0dfa65c95b76558bd7997b761133aaf9abe68442bc608c4791b262e` (16 MiB).
- Previous candidate SHA-256 `4fd453daf1ac0d065ecd322fa71943e7ee53e69ba7abfd3984fd9e41c2db210d`; ROM diff is **46 bytes, all within `0x466368..0x466467`**, the one 256-byte label block. No bytes outside that block differ.
- Source diff: two one-line replacements above. No commit or push.

## Gates

| Command | Exit | Actual result |
| --- | ---: | --- |
| `python3 tools/phase6_basic_test.py output/game_wars_korean_candidate_20261026_hlaser.gba` | 0 | `[OK] ROM passed pre-flight checks`; [log](../w5_phase6.log) |
| `python3 tools/qa_integrity_map.py --rom output/game_wars_korean_candidate_20261026_hlaser.gba --byte-only` | 0 | `기대 576950바이트 중 불일치 0`; [log](../w5_integrity_byte.log) |
| `python3 tools/qa_integrity_map.py --rom output/game_wars_korean_candidate_20261026_hlaser.gba` | 1 | Byte mismatch 0; punctuation-loss **3082** rows and import middle-dot **1036** rows, exactly RC1's known counts; full gate remains FAIL; [log](../w5_integrity_full.log) |
| `python3 tools/qa_text_fit.py --rom output/game_wars_korean_candidate_20261026_hlaser.gba` | 0 | `overflow 277`, protected non-Korean `0/485`; [log](../w5_text_fit.log) |
| `python3 tools/qa_bteam_drift.py --rom output/game_wars_korean_candidate_20261026_hlaser.gba` | 0 | mismatch/listed/deferred/unlisted = **93/82/11/0**, drift 0; [log](../w5_bteam.log) |
| `PYTHONPATH=temp/gate_pydeps python3 -B tools/gate_thumb_fixture.py temp/unseen_20261026/w5/gate_thumb.json` | 1 | First run: `ModuleNotFoundError: unicorn`. After local install: `FileNotFoundError` for pinned previous-ROM path. The fixture's hardcoded SHA is the prior candidate SHA; it cannot attest the new candidate. No `gate_thumb.json` was produced; [final log](../w5_gate_thumb.log), [dependency install log](../w5_pip_unicorn.log). |

There is no `scripts/local-ci.sh` in this checkout; the requested gates above were run directly. The two full-integrity count failures are unchanged from RC1 and outside this label-only task.

## Paired CHEAT capture

Ran `memcap -n aw-w5 -- nice -n 15 python3 temp/unseen_20261026/w5/capture_hlaser.py`; process exit `0`, [run log](../w5_capture.log). All three emulator sessions exited `0` (see per-session `commands.json`). `memcap` admitted the work through its queue but reported that its memory cap was unavailable in this sandbox.

The new candidate was cold-booted with the recorded game save (SHA-256 `6123d7dd10466992b3bcbe6949d7d31f7b8938265fcd204a9cacad667d2f74b6`), replayed through the same war-records route, and saved as a **new ROM-bound** [row20 state](candidate/route/row20.ss0). [Route transcript](candidate/route/commands.json) records the ROM hash and every command. The original used its existing row20 state, whose recorded ROM hash matches the original (`a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c`). No state was loaded across ROMs.

At cell `(4,4)` on the 16×12 row20 map, the script wrote terrain type `0x1e`, tile `0x181` in two RAM copies, and the cursor position, then pressed R. The original [card](original/terrain/card.png) reads `ヘルレーザー`; the candidate [card](candidate/terrain/card.png) reads `헬레이저`, legibly within the card. The original [small label](original/terrain/popup.png) reads `Hレーザー`; the candidate [small label](candidate/terrain/popup.png) reads `헬레이저`, legibly in the popup. See [original transcript](original/terrain/commands.json) and [candidate transcript](candidate/terrain/commands.json).

These RAM-write captures prove rendering on this route only. Natural reachability, save persistence, and hardware behavior remain **(unverified)**. The Thumb fixture also remains **(unverified for this ROM)** because its prior-ROM pin cannot be used as a per-build parameter.

## 2026-10-26 coordinator follow-up (Astra review APPROVE, Nit corrections)
- Big R card reads `헬 레이저` from the separate B-team text entry 0xA29A94 (unchanged); only the compact popup uses the 0x466368 asset now `헬레이저`. Terminology consistent; they are not the same asset.
- Thumb fixture: after restoring its pinned ROM path (hard link from output/archive_worktrees_20261026/weekend/output/), `gate_thumb_fixture.py` PASS 140 cases on 4fd453da; coordinator recomputed the ROM diff: 46 bytes, 0x466371..0x4663ff only, so gate bytes are identical in 01f65b11.
