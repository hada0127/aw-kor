# Part 2 Design Maps name entry: internal feasibility RE

Research only, 2026-10-23. No ROM or source edits, build, or commit. Primary examined ROM: `output/game_wars_korean_p2_review5.gba` (the Review fix 5 candidate); it retains the native Japanese name grid. The b44 original/candidate paired captures and earlier probes are cited below. Addresses beginning `0x08` are GBA bus addresses; ROM file offsets omit the first `0x08` byte. Findings marked **(unverified)** need a runtime watch or consumer-specific capture before implementation.

## Evidence and method

- User editor screenshot: `/home/taro1/project/aw-kor/temp/user_report_2026-10-23/5.png`. Current Japanese input: `round2_routes/review5_name_candidate/sweep3_name_save_custom_final/44_A.png`; after five A presses: `.../50_A.png`; cold loaded slot: `round2_routes/review5_name_cold/sweep3_design_cold_loaded/41_NONE.png`; loaded preview: `round2_routes/review5_name_loaded/sweep3_design_load_yes/42_A.png`. Their `commands.log` files report `exit=0`.
- New read-only replay: `memcap -n name-grid-re -- nice -n 15 python3 temp/evidence_20261023/internal_re_trace.py sweep3_name_save_custom_final`, exit 0. Dumps: `internal_re_trace_sweep3_name_save_custom_final/{44,50,55}.ewram`, `commands.log`, `node_watch.log`. `memcap` reported sandbox queue-only mode, so its memory limit was unavailable. This replay uses the existing `mgbah` and route; it does not alter the ROM or original save.
- Static Thumb disassembly of this candidate used Capstone installed only under `temp/evidence_20261023/pydeps`. Existing Ghidra A3 renderer disassembly: `temp/decomp/ghidra/out/0831424C.c`; earlier probe/audit: `sweep3_name_glyphmap.json`, `review5_shared_audit.tsv`, `review5_all_glyph_compare.log`, and `REPORT.md` Review fix 5. Native code claims below come from ROM bytes, not a new decompiler function boundary.

## 1. Input state and grid

The **drawing** table is six row strings at ROM `0x83FE40, 0x83FE64, 0x83FE88, 0x83FEAC, 0x83FEC4, 0x83FEDC`. Each has `09`, 15 two-byte SJIS cells, and `00`; blanks are `0x8140`. `0x0834AB3E..0x0834ABA0` submits those rows to `0x08314EB0` at y=6,8,10,12,14,16. The first cell is `ア=83 41` at file `0x83FE41`. A separate compact **selection** table starts at `0x83FAF6`; `0x0834AFA0` indexes it as `2*(15*y+x)` with signed cursor coordinates at state `+0x20/+0x1E`. This resolves an older ambiguous note in `docs/research.md:1101`: that note concerns the **Part 1** grid. For this Part 2 grid, mutation of `0x83FE41` changed the visible first cell in the existing probe.

`0x0834AFA0..0x0834B434` is the main input routine. At `0x0834B066..0x0834B090`, key bit `8` (START) moves the cursor to `(14,5)` and calls `0x0834AED8` (confirmation validation). Bit `1` (A) dispatches by the selected table code. A normal cell calls `0x0834AE00` to copy the selected two bytes into state `+0x2C+2*length`, then increments `+0x61` only while it is below `+0x62` (`0x0834B0BC..0x0834B0E4`). The code at `0x0834AE00` uses the same cursor/index formula to fetch the pair. Special first-byte values `0x31`, `0x32`, `0x62`, `0x63`, `0x65` branch separately; their full semantics are **(unverified)**. `0x0834B1E4..0x0834B220` decrements length and zeroes the last pair for a back/delete path. `0x0834B222..0x0834B2AA` handles key bit `0x100` (R shoulder in the route key map) and can replace the last pair; its exact user meaning is **(unverified)**. At `0x0834B2BA..0x0834B3B0`, D-pad bits move x within `0..14` and y within `0..5`; `0x0834B3B0` has a special bottom-row transition. A distinct page switch was not observed in the route or this handler **(unverified)**. SELECT is not established as a page switch.

The current native max is **8 characters**: live state base `0x02003010` has length at `+0x61 = 0x02003071` (5 after five A presses), max at `+0x62 = 0x02003072` (`08`), byte capacity at `+0x63` (`10`), and the name at `+0x2C = 0x0200303C`. `0x0834AE90` clears `2*max`; `0x0834AE60` zeroes the pair at the current end. `0x0834AED8..0x0834AF70` compares the buffer with a blank code and enters distinct confirm states. The visible button art already says Korean 취소/뒤로/확인 in b44; exact cancel versus back behavior and empty-name fallback require a focused button replay **(unverified)**. START and A on the OK cell are observable route paths; B and page behavior require separate traces **(unverified)**.

## 2. Buffer, persistence, and redisplay

At snapshot 50, `0x0200303C` contains `83 41` five times, then `00 00`. At snapshot 55, a second copy appears at `0x0200B09C`; the state `+0x5C` points to it. `0x0834AFA0` copies the current name to that pointer during a transition (`0x0834B00C..0x0834B040`). The precise ownership/lifetime of the second copy is **(unverified)**.

The native save captured as `sweep3_name_custom_original_final.sav` is 128 KiB. Its unique `83 41` ×5 sequence begins at **SRAM file offset `0x1E504`**, followed by `00 00`; the surrounding name field is 16 bytes (eight two-byte codes). In the prior blank-map save `sweep3_design_original.sav`, the same field holds eight SJIS pairs of a default Japanese name. The two saves differ in 13 bytes, including name and neighboring metadata. This is one observed slot; other slot offsets, checksum/commit ordering, and delete behavior are **(unverified)**. A Korean composed syllable should be stored as one two-byte reserved code, keeping the 8-unit field and terminator. Storing raw jamo instead would consume one slot per jamo and would not satisfy eight syllables.

Observed saved-name consumers:

| Consumer | Evidence | Renderer / Korean-code readiness |
| --- | --- | --- |
| Name-entry box and typed preview | `44_A.png`, `50_A.png`, live node read trace | Native A3-linked glyph nodes. Changing the grid's SJIS cell to a reserved Korean code made preview `?????` in `round2_routes/sweep3_probe_hangul/sweep3_design_name_typing/50_A.png`; direct table substitution is **not ready**. A name-only KOR_BASE cache/renderer path is needed. |
| Design Maps save/load list and map preview | cold and loaded screenshots cited above; native `ア` in earlier original comparison | The prior glyph-pixel probe made both display a surrogate Korean picture (`sweep3_name_persistence_contact.png`), proving the kana code persisted, but that probe modified shared A3 nodes. Korean reserved-code support in these consumers is **(unverified)**; the current candidate shows `?????` for this custom name. |
| Editor title/HUD after load | `sweep3_name_persistence_contact.png` bottom row (historical candidate) | A native name reaches the loaded editor; renderer and reserved-code support are **(unverified)**. |
| Versus / Link lists and map preview | No custom-name route trace found | **(unverified)**. Do not infer support from the Design Maps list. |

The generic A3 parser is at `0x0831424C` and its glyph path at `0x08A3C7E4`; `tools/build_korean_full.py` already hooks A3 at `0x08F30280` and KOR_BASE at `0x08F00000`. That does **not** prove every saved-name consumer enters the hooked branch. Existing test with a reserved Korean code in the grid produced `?` preview, so at least one name path rejects or misses it. A required next trace is a Korean-code injection into a **copy** of the 16-byte name field, then read/VRAM watchpoints and paired captures at editor title, save/load, Versus and Link. This is research-only and was not performed.

## 3. Glyph supply and preview

`data/syllable_to_code_2350.json` has 2,350 completed Hangul syllables including `가`, `각`, `한`, mapped to reserved two-byte codes, but standalone `ㄱ`, `ㅏ`, `ㅑ`, `ㅣ` are absent. Thus KOR_BASE has syllable glyphs, **not a verified jamo grid repertoire**. The existing 56 kana pictures are individual 8×16 4bpp A3 nodes; first `ア` is file `0x807C36..0x807C75`, loaded into name-grid VRAM `0x520..0x55F`. `sweep3_name_glyphmap.json` records all 56 native nodes. A Galmuri jamo grid would need new 8×16 glyph tiles in a private grid atlas/cache; composing syllables can use existing KOR_BASE pairs for KS X 1001 syllables. The full 11,172 modern Hangul syllables are not present, so arbitrary two-beolsik combinations require either more glyphs/codes, a compositing renderer, or a defined rejection/fallback policy. A partially formed consonant/vowel preview also needs private jamo rendering; its behavior cannot be supplied by the current completed-syllable lookup alone.

## 4. Hook space and scratch

Current build conventions: `HOOK_FILE=0xF30000`, A3 hook at `0xF30280`, KOR_BASE at `0xF00000`, existing reserved-code mapping and guarded Thumb trampolines in `tools/build_korean_full.py:13129..13550`. In this candidate, zero runs include `0xF31FEC..0xF3F000` (53,268 bytes) and `0xF51238..0xF66000` (85,448 bytes). **These are byte observations, not allocation permission**: the builder's ownership map, other overlays and final ROM diff gate must reserve/guard any chosen span. No safe unused IWRAM/EWRAM scratch was proven. A routine can extend the known name-entry state only after confirming object size and neighboring fields; a private EWRAM allocation needs lifetime/watchpoint evidence. The present 16-byte field should remain the persisted ABI.

## 5. Isolation requirement

Review fix 5 proved that replacing the global `0x815B` A3 picture at file `0x809CD6` changes the dash in dialogue at source `0xA0A833`. `review5_shared_audit.tsv` found possible other text consumers for 42 of 56 kana codes (static scan, not execution proof). Therefore **do not edit global kana nodes**. Gate a private grid renderer by the Design Maps state/source and render jamo from private tiles; gate name preview/redisplay by name field ownership, or teach each proved consumer the reserved Korean code without redirecting general dialogue. The Review fix 5 candidate preserves all 56 b44 node pictures (`review5_all_glyph_compare.log`, 56/56 equal).

## Implementation choices and blockers

| Option | Shape | Effort / risk |
| --- | --- | --- |
| A. Full jamo grid and two-beolsik composition | Private grid tiles; hook A/select, B/back, START/OK; compose L/V/T state and write one reserved syllable code per completed slot; private partial preview; extend every proved saved-name consumer. | High. Best UX, but 2,350-glyph repertoire cannot render every possible composition. Need a defined glyph expansion or rejection policy and consumer traces. |
| B. Completed-syllable picker | Page/search through supported syllables and write existing codes. | Medium code, high interaction cost. Avoids composition but changes navigation drastically; needs human UX decision. Still needs name-consumer hooks. |
| C. Jamo grid with ROM-side composition hook | Keep native cursor/table geometry; intercept selected code and maintain L/V/T state in private scratch, replacing the last persisted pair as a syllable evolves. | Medium-high. Least layout change and likely fastest PoC; incomplete syllable preview, B/back semantics, 8-slot accounting and all consumer paths remain blockers. A private jamo atlas is still required. |

Suggested next proof: option C PoC on a copied save with `가`, `각`, `한` and an unsupported syllable; trace all reads of the 16-byte name field and capture entry, confirm, save/cold load, editor, Versus and Link. Preserve the global A3 pictures and B-team script. No option is implementation-ready until consumer ownership, full input special-cell semantics, scratch lifetime and unsupported-syllable policy are settled.

## Status

**PASS (internal feasibility only):** live Part 2 grid tables, input/append path, eight-character state limit, two-byte live and SRAM name format, and shared-glyph hazard identified. **BLOCKED / (unverified):** exact B/Cancel/page behavior, other save-slot offsets, every saved-name display renderer and Korean-code compatibility, private scratch ownership, full modern-Hangul glyph coverage, and end-to-end composition. No code or canonical ROM changed; no commit.
