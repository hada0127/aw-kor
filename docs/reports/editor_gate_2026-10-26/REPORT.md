# Gate review fix 1 — 2026-10-26 02:20 KST

ROM: `output/game_wars_korean_gate_r3_0126.gba` · SHA-256 `4fd453daf1ac0d065ecd322fa71943e7ee53e69ba7abfd3984fd9e41c2db210d`. Build1031 comparison SHA-256 `b4e41398a1b87ae35e913cb54b9a9f1a06da070eed818dbf18a124370ec18a9f`. No rebuild or commit. The tracked changes are one test file and an assembly comment; reassembly still produces the installed 236-byte payload, SHA-256 `9d9662da832257e0b14528f25566ae7a9d846b4d11cb2b7b2bfd800fcd11cc80`.

## Review findings

| Finding | Status | Evidence and change together |
|---|---|---|
| B1, actual Thumb execution | **fixed** | [Unicorn fixture](../../../tools/gate_thumb_fixture.py) maps the exact 16 MiB final ROM plus EWRAM/IWRAM/VRAM and executes **140** bounded Thumb cases. [Case summary with assertion-based register checks](thumb_cases.json) records all 40 pool slots on both source/row entries, six parent states, F80/FE0 source→exact lookup→row, invalid pool pointers including `03000DA0`, isolated owner/destination/post/source failures, row/column endpoints, odd and underflow cells, and six native parent branches. Four full paths execute source gate→ROM lookup→row gate→ROM glyph/tilemap continuation to `F306DC`. Two additional cases execute the original `F306DC` pop on accepted/rejected paths and assert restored r4–r7 and SP. Stops and checks cover SP/LR, live r1–r3/r5/r6/high registers, source r4/r7, r2/r3 sentinels at gate boundaries, branch outcomes, and all write addresses. Every gate rejection writes stack only; accepted row cases write exactly their expected tilemap halfwords. No payload defect was exposed. Fixture/evidence/report changed together; ASM/payload/pins did not change. |
| B2, private tile lifetime | **fixed** | Normal input on candidate and build1031 using the same copied SRAM reaches editor menu → exit → Part 1 Records map screen → Trial map list → Versus map selection → editor reentry → Part 1 name entry → cancel Yes → editor menu. Every emulator process exited 0. [Candidate and baseline representative captures](route/) (full VRAM dumps, BG registers, and command traces remain in temporary evidence) cover each named state; [automated audit](route_audit.json) compares them. At Records, the complete `0x280..0x2EF` tile-byte range is identical between ROMs (0 differing bytes), after the candidate's editor menu had 704 differing bytes there. Trial and Versus retain the identical range and pixel-identical screens. Name entry has pixel-identical screens and zero active charblock-0 references to `0x280..0x2CF`; stale tile bytes are not consumed. Editor reentry and post-name return redraw the 22 intended BG0 caption cells; candidate/build1031 pixel differences remain confined to the menu. [Assembly ownership comment](../../../tools/asm/part1_editor_compact_gate.s) and this report changed together. No allocation/index/pin change was needed. |
| F1, isolated rejection tests | **fixed** | [Focused test](../../../tools/test_part1_editor_compact_labels.py) now calls `predicate()` directly for owner/destination/post-source failures and uses column 2 for `consume()`; row rejections change one coordinate or column from the passing tuple. The B1 fixture uses corresponding isolated vectors. Test file and fixture vectors changed together. |

The route used the verified source SRAM SHA-256 `d1210b1d8fe444a3cc84eb8ae272c0076375107f93ce97b37d786f0efc2e9d51`. The existing headless mGBA harness SHA-256 was `ca6fc8e5eb6285375194ca574873e2349ead2f95d94f1888bdfcd72f7ab293d9`. Both ROM runs used the same scripted normal inputs and produced their own capture/VRAM files under `temp/gate_b2_probe/{candidate,build1031}/`; representative PNGs are preserved in [route/](route/); route command count and exit codes are in `route_audit.json`. Representative captures: `record_map_a.png`, `trial_a.png`, `versus_next.png`, `reentry_menu.png`, `name_entry_a.png`, `name_return_menu.png`; corresponding `*-vram.bin` files contain full 96 KiB VRAM dumps. The repeated route's name cancel reaches the editor again on both ROMs.

## Commands and exact result excerpts

Python `3.14.7`; project-local `temp/gate_pydeps` installed with `python3 -m pip install --target temp/gate_pydeps unicorn==2.1.4 capstone==5.0.6 --disable-pip-version-check --quiet`. Unicorn `2.1.4`, Capstone `5.0.6`. No system Python package changed.

| Command | Exit | Output / retained log |
|---|---:|---|
| `PYTHONPATH=temp/gate_pydeps python3 -B temp/gate_thumb_fixture.py temp/evidence_gate_fix1_0220/thumb_cases.json` | 0 | `PASS 140 real Thumb cases, ROM 4fd453daf1ac0d065ecd322fa71943e7ee53e69ba7abfd3984fd9e41c2db210d`; log (`temp/evidence_gate_fix1_0220/thumb.log`, temporary). |
| `memcap -n aw-gate-b2 -- nice -n 15 python3 -B temp/gate_b2_probe.py` | 0 | `candidate 0`, `build1031 0`; route traces (`temp/gate_b2_probe/`, temporary). |
| `python3 -B temp/evidence_gate_fix1_0220/audit_routes.py` | 0 | `PASS record renderer resets full 0x280..0x2EF range; trial/versus equal; name has no charblock0 private refs; editor redraws 22`; [audit](route_audit.json). |
| `clang --target=arm-none-eabi -mcpu=arm7tdmi -mthumb -c ...`; `ld.lld --threads=1 -Ttext=0x08F31E00 ...`; `python3 -B temp/evidence_gate_fix1_0220/verify_gate_asm.py` | 0/0/0 | `PASS linked 236B; 224B code; 0B alignment; 12B literals; no relocation/thunk; 2 BL predicates; 4 tilemap stores; exact native fallback branch`; log (`temp/evidence_gate_fix1_0220/asm.log`, temporary). |
| `python3 -B tools/test_part1_editor_compact_labels.py`; `python3 -B tools/test_part1_record_map_labels.py`; `python3 -B tools/test_d821f0_contract.py` | 0/0/0 | `Ran 7 tests ... OK`; `Ran 8 tests ... OK`; `Ran 9 tests ... OK`; logs (`temp/evidence_gate_fix1_0220/editor_test.log`, temporary), record (`temp/evidence_gate_fix1_0220/record_test.log`, temporary), D821F0 (`temp/evidence_gate_fix1_0220/d821f0_test.log`, temporary). |
| `python3 -B tools/phase6_basic_test.py <ROM>` | 0 | `[OK] ROM passed pre-flight checks`; log (`temp/evidence_gate_fix1_0220/phase6.log`, temporary). |
| `python3 -B tools/qa_integrity_map.py --rom <ROM> --map temp/integrity_map.json --byte-only` | 0 | `40006 writes`; `576950` expected bytes, mismatch `0`; log (`temp/evidence_gate_fix1_0220/integrity_bytes.log`, temporary). |
| Same integrity command without `--byte-only` | 1 | Pre-existing content failure: punctuation loss `3082` rows, import middle-dot residual `1036`; byte integrity passed; log (`temp/evidence_gate_fix1_0220/integrity_full.log`, temporary). |
| `python3 -B tools/qa_text_fit.py --rom <ROM> --map temp/integrity_map.json --manifest temp/repoint_manifest.json` | 0 | `no_ko: 0`, protected non-Korean `0/485`, existing layout-loss fallbacks `151`; log (`temp/evidence_gate_fix1_0220/text_fit.log`, temporary). |
| `python3 -B tools/qa_bteam_drift.py --rom <ROM> --map temp/integrity_map.json --repoint-manifest temp/repoint_manifest.json --json temp/evidence_gate_fix1_0220/bteam.json` | 0 | Actual/listed/deferred/unlisted `93/82/11/0`, drift `0`; log (`temp/evidence_gate_fix1_0220/bteam.log`, temporary). |
| `git diff --check` | 0 | No output. |

The first text-fit/B-team attempt exited 1 because this worktree had no `original/` input. The rerun used a temporary symlink to the verified immutable source ROM and removed it in `finally`; the commands then exited 0. [Machine-readable check results](checks.json) retain the initial exit codes. `memcap` admitted the emulator and QA jobs but reported that this sandbox could apply its queue only, without a systemd memory cap. No heat delay occurred.

## Changed files and limits

- `tools/test_part1_editor_compact_labels.py`: isolated rejection vectors.
- `tools/asm/part1_editor_compact_gate.s`: evidence-backed tile lifetime comment only; linked bytes unchanged.
- At this historical review, the fixture and evidence were still under `temp/`. The fixture and compact evidence are now preserved with this report; `gate_b2_probe.py`, dependencies, and larger route dumps remain temporary.

PLAN deviation: none for B1/B2/F1; the approved ROM remained unchanged because no production instruction changed. Full-integrity content failures remain as previously recorded. Real hardware and Link remain (unverified); this is a bounded gate review fix, not a release claim.

RECEIPT: model=unknown effort=unknown role=code
