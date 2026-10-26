# W12 live-pointer Link ticker capture (2026-10-26)

## Method and scope

`cheat_messages.py` copied W7's two-cartridge route, then corrected its ROM cheat. For each source slot, it finds the **unique** original-ROM pointer-table site containing `0x08000000 + source`, reads that same word in the ROM under test, and writes that **live value** to the temporary test ROM's host ticker entry at `0xA38A60`. It rejects missing/ambiguous sites and pointers outside the ROM. The original and candidate source ROMs were not edited. Each run's `receipt.json` records the site, patched value, source SHA-256, test ROM SHA-256, harness SHA-256, BIOS SHA-256, command transcript, and emulator exit code.

Each of the 18 cold-booted runs captured 32 ticker frames at 20-frame intervals (640 scrolling frames). The [paired sheets](paired_A350B4.png) and corresponding `ticker_ADDRESS.png` strips include complete repeated lines, so entering/leaving the screen edge is not mistaken for clipping. All 18 runs exited 0; all 576 expected ticker PNGs and nine paired sheets exist. The test exercises the real ticker renderer through a **CHEAT** pointer redirect. Native state-machine reachability for IDs 3250–3256 remains **(unverified)**.

Source ROMs: original SHA-256 `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c`; candidate SHA-256 `01f65b11d0dfa65c95b76558bd7997b761133aaf9abe68442bc608c4791b262e`. Reused `w7/bin/mgba_link_harness` and the real BIOS identified in each receipt.

## Results

`PASS` below means the complete candidate ticker is Korean, readable, and conveys the original line's action/warning; no Japanese, broken ticker glyph, or persistent ticker clipping was seen. Individual frames can cut a line at the left/right edge during normal horizontal scrolling. `Background observation` below applies to every candidate sheet.

| ID | Source slot / original pointer site | Live pointer original / candidate | Decision and candidate meaning | Paired sheet |
|---:|---|---|---|---|
| 3242 | `A34F70` / `A38A5C` | `08A34F70` / `08A5CAA8` | **PASS** — joining; wait briefly | [paired](paired_A34F70.png) |
| 3243 | `A34F98` / `A38A60` | `08A34F98` / `08A34F98` | **PASS** — press Start once friends gather | [paired](paired_A34F98.png) |
| 3250 | `A3508C` / `A38A7C` | `08A3508C` / `08A5CB9C` | **PASS** — sending the map; wait | [paired](paired_A3508C.png) |
| 3251 | `A350B4` / `A38A80` | `08A350B4` / `08A5CBC8` | **PASS** — receiving the map; wait. The W7 Japanese CHEAT result was a stale-slot artifact. | [paired](paired_A350B4.png) |
| 3252 | `A350DC` / `A38A84` | `08A350DC` / `08A350DC` | **PASS** — finished; starting | [paired](paired_A350DC.png) |
| 3253 | `A350F8` / `A38A88` | `08A350F8` / `08A350F8` | **PASS** — finished; returning to menu | [paired](paired_A350F8.png) |
| 3254 | `A3511C` / `A38A8C` | `08A3511C` / `08A5CBF4` | **PASS** — saving the map; do not turn off power | [paired](paired_A3511C.png) |
| 3255 | `A3514C` / `A38A90` | `08A3514C` / `08A5CC28` | **PASS** — preparing download; wait | [paired](paired_A3514C.png) |
| 3256 | `A3517C` / `A38A94` | `08A3517C` / `08A3517C` | **PASS** — cannot connect; returning to menu | [paired](paired_A3517C.png) |

**Background observation:** the candidate Link screen's green backdrop looks damaged/fragmented compared with the original in all nine paired sheets. The ticker text itself remains readable. Whether this background difference is an existing candidate defect, an intentional asset change, or a consequence of this CHEAT route is **(unverified)**; no background-root-cause work was in W12's scope.

## Commands and result

```sh
memcap -n aw-w12 -- nice -n 15 python3 temp/unseen_20261026/w12/cheat_messages.py > temp/unseen_20261026/w12/cheat_messages.stdout 2>&1
# exit 0; 18 DONE lines, 18 emulator EXIT 0 lines
python3 temp/unseen_20261026/w12/make_sheets.py
# 9 paired sheets
python3 temp/unseen_20261026/w12/make_ticker_strips.py
# 9 ticker strips
```

Receipt audit checked 18 `DONE` records against `receipt.json`: every run had exit 0, exactly 32 ticker PNGs, and matching pointer site/patch value; nine paired sheets were present. No tracked file was edited; no commit or local CI was needed for this temp-only QA capture.
