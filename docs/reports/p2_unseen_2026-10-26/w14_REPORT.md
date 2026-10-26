# Part 2 LINK MODE background and original-capture audit

## Result

The newspaper damage is a pre-existing build defect in `patch_part2_menu_newspaper_bg`, not an `hlaser` change. The function at `tools/build_korean_full.py:6968-7067` replaces the complete 256-tile LZ77 sheet at ROM offset `0x5B5D10` with a 128×128 image encoded in sequential tile order, while leaving its **nonsequential** 32×32 tilemap at `0x5B58E0` unchanged. The LINK MODE BG3 loader places the sheet at VRAM `0x06008000` and that map at `0x0600F800`. Thus the menu displays its newspaper as scattered parts of the new image. Other loaders sharing this sheet may have the same issue; their screens were not rechecked here.

The claimed Hangul in the original W2 ticker is a side-by-side image-reading error. `bg_check.png` joins the 240-pixel Japanese original pane (x=0–239) and the 240-pixel Korean candidate pane (x=240–479). The original file `w2/original/entry_wait_host_p0.png` itself has Japanese only. Its receipt names the verified original ROM SHA-256 `a8ad7c7d2a48b4ce4d7a5da408121e9640206ed9f040c0ac967b6c6b2413831c`, a cold route, no state loads, `cheat_tainted: false`, and emulator exit 0. No W2 wrong-ROM/state contamination was found.

## Reproduction and isolation

I ran `memcap -n aw-w14 -- nice -n 15 python3 temp/unseen_20261026/w14/probe.py original b10 b35 b44 hlaser` using the W2 mGBA link harness. Each run started a new emulator process, booted the named ROM, navigated to Part 2 LINK MODE without a linked client, captured the menu and entry ticker, and dumped VRAM/palette/display registers. All five receipts say `emulator_exit_code: 0` and `cheat_tainted: false`. Screens are in each named subdirectory; [comparison.png](comparison.png) displays the five menus in that order.

| ROM | Menu background | Decompressed sheet `0x5B5D10` SHA-256 prefix | VRAM `0x8000..0x9FFF` SHA-256 prefix |
| --- | --- | --- | --- |
| Original | intact newspaper | `77faf085047a` | `77faf085047a` |
| 2026-10-12 b10 | fragmented | `1a782bf54b0f` | `1a782bf54b0f` |
| 2026-10-15 b35 | fragmented | `1a782bf54b0f` | `1a782bf54b0f` |
| 2026-10-21 b44 | fragmented | `1a782bf54b0f` | `1a782bf54b0f` |
| 2026-10-26 hlaser | fragmented | `1a782bf54b0f` | `1a782bf54b0f` |

Static inspection of all archived `candidate_20261012_b2` through `candidate_20261021_b44` ROMs found the same replacement-sheet hash. b10 is the earliest build cold-booted in this probe; b2 through b9 were checked statically only. `git blame` identifies the original implementation in commit `33f6781` (2026-06-16); the newer shared-loader comment is from `e591242` (2026-10-06).

The original and all four candidate menu dumps have identical BG3 control `0x1F0B` (charblock 2, screenblock 31), identical BG3 tilemap SHA-256 `9d6ac65a1f8161d4…`, and identical other checked display controls. The map has 1,024 entries and 255 distinct tile IDs, with repeated entries (the first 31 entries are tile 227); it is not a sequential 16×16 image map. All 256 sheet tiles differ in the candidates. The only palette-entry difference is OBJ index 399, which cannot explain this BG3 damage.

For a causal check, I made scratch `w14/restored.gba` from `hlaser` with **only** the 6,666-byte original compressed sheet copied back at `0x5B5D10`. `memcap -n aw-w14 -- nice -n 15 python3 temp/unseen_20261026/w14/probe.py restored` exited 0. Its BG3 tile and tilemap hashes exactly match the original, and [restored/link_menu_p0.png](restored/link_menu_p0.png) shows the intact newspaper behind the Korean labels. This scratch ROM is diagnostic, not a product fix: it restores the original Latin newspaper art.

## Minimal fix proposal (not applied)

Keep the existing tilemap and redraw `0x5B5D10` **by native tile ID and map placement**. Start from the original decompressed sheet, replace the English newspaper text tiles with Korean or neutral graphic tiles at their actual tile IDs, and preserve/reuse photo, border, and texture tiles. Where a tile ID appears in multiple map cells, its replacement must be valid at every use; allocate a distinct tile ID and update only the necessary tilemap cells if unique content is required. Then verify all ten collage-map consumers, the separately repointed WAR IS OVER consumer, and cold LINK MODE before promoting a build. The code should not treat the 256 native tile IDs as a sequential 128×128 canvas. Restoring the source sheet alone is a valid proof of cause but would leave Latin art and violate the project's residual-text goal.

## Evidence provenance

- W2 original capture: `w2/original/receipt.json` points to the original ROM, W2 harness, exit 0, no save state load, no cheat; its PNG SHA-256 is `9ed090ff9180be88c1046ec69b53b0f42fb2be28c0cb71cf0ac94e58c37e6fd2`. Direct viewing shows Japanese only. The apparent Hangul begins at the x=240 candidate pane of `bg_check.png`.
- W7 native original routes (`native_alt`, `multi`, `multi_result`) and W2 follow-up original routes have original-ROM receipts with no cheat flag; no evidence here invalidates them. W7 and W12 `msg_*` original captures explicitly use a ROM pointer redirect at `0xA38A60`, are `cheat_tainted: true`, and identify the original source ROM SHA. They are valid **forced-message comparisons**, not evidence that those messages were reached naturally. W12 reuses W7's harness and reproduces W7's original ticker captures; this is documented by their receipts. No wrong-ROM contamination was found in these receipts.
- Limits: this audit did not inspect every W2/W7/W12 image pixel or independently rerun every forced-message route. Their visual findings remain bounded by the respective receipt and cheat provenance.

Tracked files were not edited. No repository CI was run because this task was read-only and proposed, rather than applied, a fix.
