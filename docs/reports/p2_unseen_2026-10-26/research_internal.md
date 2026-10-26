# research-internal report: unseen Part 2 screens (2026-10-26, read-only, no emulator run)

Candidate ROM: output/game_wars_korean_candidate_20261026_gate.gba (sha 4fd453da..., same as old game_wars_korean_gate_repro.gba, so old per-ROM .ss0 states from the weekend evidence are reusable).
Prior-evidence root (call it WK): output/archive_worktrees_20261026/weekend/temp/evidence_p2_remaining2_0252/  (per-ROM states original/ candidate/ maps/row06..row28.ss0 + .bin)
Old-p2 root (P2): output/archive_worktrees_20261026/p2/temp/evidence_20261023/
STALE PATHS in the prior scripts: OLD=/home/taro1/project/aw-kor-wt/p2/temp/evidence_20261023 -> P2 above; ROM `output/game_wars_korean_gate_repro.gba` -> the 20261026_gate file; harness /home/taro1/project/aw-kor/temp/release_C/b31/mgbah (exists, 21.7K).

## 1. Terrain cards (lake / generic cannon / laser / A laser)

### 1a. Map RAM layout (derived by offline analysis of 23 EWRAM dumps WK/candidate/maps/row06..28.bin, `dumpmem 02000000 0x40000`)
- Map size: u16 w @ EWRAM 0x0201E340, u16 h @ 0x0201E342 (scan_cards.py:7 reads `<HH` at file offset 0x1e340). (verified)
- Display tile-ID array: u16 @ 0x02003012, row-major, index = y*w + x (stride w cells = 2w bytes), IDs < 0x200 (scan_cards.py:9). A second identical u16 copy @ 0x0201ED62 (equal in all 23 dumps). (verified)
- **Terrain-type byte array: u8 @ 0x0201F772, 1 byte/cell, same stride w (index y*w+x).** Found by search: it is the only 192/..-cell array that is a pure function of tile ID in every dump. code = (owner<<5)|type, type = code & 0x1f (owner 0 neutral, 1/2/3/4 = armies, e.g. 0x46/0x66/0x86 city of 3 armies). (verified from dumps; that the card reads it at runtime is (unverified), see 1d)
- Cursor: IWRAM 0x030034F0 = 4 x u16 {pixel_x, pixel_y, tile_x, tile_y}; prior worker wrote `w16 030034F0 <pack('<4H',x*16,y*16,x,y)>` then `keys 256` (R) `frames 3` `keys 0` `frames 30` -> native card (scan_cards.py:34-36). Fortress run also pressed LEFT (keys 32) x180f first to scroll the camera, then wrote cursor, then R (fortress_cards.py:18-21).
- How 0x180 etc. were "read live": tile IDs read from the dump above (scan_cards.py tiles()). Prior test-only tile write (P2/sweep3b_terrain_both_probe.py, log in sweep3b_terrain_both_candidate/commands.log) wrote only `w16 02003020` and `w16 0201ED70` (the two TILE arrays) and the card did not change. It never wrote the TYPE byte 0x0201F772+. That is the likely missing piece. (unverified)

### 1b. Type -> label (static ROM)
- Compact label art (32x16 4bpp, 0x100 B each): base 0x08464D68 + idx*0x100; names/order at tools/build_korean_full.py:6057-6082 (idx 0 plain,1 river,2 mtn,3 forest,4 road,5 city,6 sea,7 HQ,8 湖/호수,9 airport,10 port,11 bridge,12 shoal,13 factory,14 pipe,15 missile,16 reef,17 lab,18 キャノン/캐논,19 volcano,20 レーザー,21 ファクトリー,22 Hレーザー/A레이저,23 進入不可). I rendered the ORIGINAL ROM art: idx 8 = 湖, 18 = キャノン, 20 = レーザー, 22 = Hレーザー, 23 = 進入不可. (verified)
- Index lookup: ROM table at 0x08815CFC (4 B entries indexed by type; label = low u16 & 0x7f), consumed by thumb fn 0x0832ACE8 (`base 0x08464D68 + ((tbl[idx*4] <<3)&0x3ff)<<5`; literals at 0x32AD00/04/08). (verified statically; who calls it / that arg=type is (unverified))
- Table result (type -> label): 01->0, 02->1 river, 03->2 mtn, 04->3 forest, 05->4 road, 06->5 city, 07->6 sea, 08->7 HQ, **09->8 lake(湖)**, 0a->9 airport, 0b->10 port, 0c->11 bridge, 0d->12 shoal, 0e->13 factory, 0f/10->14 pipe, 11/12->15 missile, 13->16 reef, 14->17 lab, **15,16,17,18,1a,1b->18 cannon**, **19->20 laser**, 1c->19 volcano, 1d->21 factory(Black Hole), **1e->22 A laser**, 1f->23 impassable.
- Cross-check with live evidence: 0x180=type 0x11 (missile, PASS card), 0x1cd=0x4a (airport), 0x1a7=0x1c (volcano), lab tile 0x1db=0x54 (type 0x14), 0x182..0x185=types 15..18 -> prior card = ミニキャノン (so lab18 popup/card text = mini cannon on those tiles).

### 1c. Where each target already exists in saved EWRAM dumps (tile id, type, cells (x,y))
| target | dump (w x h) | tile / type / cells |
|---|---|---|
| laser (type 0x19) | temp/screenqa_p2_syn_20261012/c1/ew.bin (27x14; work.sav+run.json beside it) | tile 0x181, (6,3),(14,6) |
| laser | temp/release_C/w2b6e_run15_units/ewram.bin (28x28) | tile 0x181, (5,5),(16,6),(17,16)+1 |
| generic cannon candidate (type 0x1a, lab18) | temp/full_audit_2026-09-15/unit_snapshots/ewram_41512.bin (18x15) | tile 0x187, (4,1) |
| mini cannon (types 15-18) | WK ... aw-normal-replay-task_e25112cb700a/r10/ewram.bin (30x15, M10 fortress, save output/qa/part2_2026-10-06/anchor_m10_day6/game.sav) | tiles 0x182-0x185 at (10,8)(13,8)(10,3)(13,3)(9,4)(9,7)(14,4)(14,7) |
| type 0x09 (lake label candidate) | same r10 dump | tile 0x1a4 x12 e.g. (10,4)(11,4)(12,4); also 0x1ae/0x1b0/0x1b1 |
| type 0x09 | w2b6e_volcano_units (25x15) | 0x1a4,0x1a5,0x1a6,0x1a8,0x1a9 around volcano 0x1a7 (11,7) |
| type 0x09 + 0x1d factory | w2b6e_i2_units (18x20); aw-remaining r12(M8 save round13_m8_cold_live) & r25 (round27_bomber_cold) (20x15) | 0x18c,0x18e type 9 around 0x18d type 0x1d at (8,4)/(5,4) |
| type 0x09, 0x1a | ewram_41512 | 0x186,0x188 around 0x187 |
A laser (type 0x1e): no tile seen in any of 55 distinct dumps scanned (only the 3-wide structures above). Tile ID unknown (unverified).
IMPORTANT CONFLICT: type 0x09 is labelled 湖 in the table, but the big card for tiles 0x1ae/0x1b0/0x1b1 (type 9, M10) showed 進入不可 (WK/original/fortress_cards/contact.png). So the big card (R) is not purely type->compact label; the compact label popup (cursor popup, 0x464D68 art) vs the R card may differ. First free experiment: R card on tile 0x1a4 in the M10 state (no write), plus the compact popup on the same cell. (unverified)

### 1d. Step list (cheap -> test-only)
A. No-write reads (all natural states already exist):
 1. M10 fortress state: WK/{original,candidate}/fortress_continue_25/step_23.ss0; reuse fortress_cards.py with items [('1a4',10,4),('1a5',..)], pipeline `loadstate; keys 32; frames 180; keys 0; frames 60; w16 030034F0 <4H>; frames 120; shot; keys 256; frames 3; keys 0; frames 60; shot`. 0x1a4 cells: (10,4),(11,4),(12,4).
 2. Volcano state (WK volcano_entry.py/volcano_continue.py/volcano_cards.py; legacy save, provenance (unverified)): cells (10,5),(11,5),(12,5),(10,7),(12,7),(13,7) for type 9 tiles.
 3. Laser: laser maps need a state; c1 has work.sav+run.json (run.json lists route, read it) - load work.sav in each ROM, reach battle, read 0x0201E340 to confirm 27x14, cursor to (6,3), R. run15 map 28x28 from w2b6e (route (unverified)).
 4. Compact popup (small cursor label) is what the 0x464D68 art feeds: it appears as the cursor lands, no R needed (shot after `frames 30` following the cursor write).
B. Test-only RAM write (label as CHEAT, keep apart from normal evidence). On any battle state with known w (read u16 @0x0201E340 via `dumpmem 0201E340 4 f`, or use the table above):
 - addr_type = 0x0201F772 + y*w + x ; addr_tile = 0x02003012 + 2*(y*w+x) ; copy @ 0x0201ED62 + 2*(y*w+x).
 - `w8 <addr_type> <code>` with code: lake 09, cannon 15 (or 1a/1b for the "generic" variants), laser 19, A laser 1e (also 1d factory, 1f impassable as sanity). Optionally also `w16 <addr_tile> <tile>` + copy with a tile that exists (e.g. 0x181 laser, 0x183 cannon, 0x1a4 lake-ish) so the display matches.
 - Then cursor write `w16 030034F0 <x*16,y*16,x,y>`, `keys 256`, `frames 3`, `keys 0`, `frames 30..60`, `shot`; also shot before R for the popup. Use scan_cards.py structure (per-ROM loadstate, row?? .ss0 from WK/candidate/maps and WK/original/maps; same writes to both ROMs).
 - If the card still does not change, the card caches at map load: set cursor elsewhere then back, or write before load via `loadstate` of a state saved before entering the battle (unverified). Check by reading dump 0x0201F772 after R.
 - Rows 20 (16x12) and 23 (19x19) of War Room are the quickest states (WK/*/maps/row20.ss0 etc., rows 6-28 exist for both ROMs).
Facing question ("each facing"): 4 cannon types 15,16,17,18 = tiles 0x182..0x185 (probably 4 directions/states, prior card text identical = mini cannon); 0x1a/0x1b also map to lab18. The generic キャノン card may simply not exist separately - the table gives the same label for all six types. (unverified)

## 2. Own-HQ-captured loss dialogue (campaign)
- CSV (data/translation_for_import.csv, address sorted, Part 2 text = 0xA0xxxx-0xA3xxxx): best candidate = the 14-day HQ-defense mission block A16A19..A1716A: `A16E05 本部を守りきるんだ！`, `A16DE6 １４日が終わるまで`, loss lines `A1703C ああ、守りきれなかった・・・` (group g_00A1703C in data/dialogue_groups.json, ids 11981/11982), `A1705C キャハハハハ。`, `A17075 道がせまくなってるとこで守ればいいのに…`, `A1716A もう一度だけがんばってください！`. Matching mission-hint rows 10199-10200 (A3435F-A3437F `このマップは、とにかく１４日間 本部を守りぬくのよ！`). Mission number (unverified; title candidates A2D73C 「守るべきもの」 idx 116 of the title table, A2D5.. list).
- Other HQ-related lines: A1774A `本部にたどり着けば` (reach-own-HQ mission, title A2D6D0 「あの森をこえて」), A177C5 `本部を占領されねえよう`, A17834 `突破された！？` (these are win-side), A221AF/A221D1 city-loss variant (`右上の都市10個を占領されたら、こちらの負け`), A0EDDB/A0F4DD/A14242/A1CE97/A1D06F generic defeat lines (not HQ-specific; unverified).
- Fastest enemy reach: no mission verified. Mission with an enemy next to HQ (reach/defense missions above) is the target; otherwise cheat route like prior: put an enemy unit on own HQ via unit coordinate write then native end-turn + Capture (prior used `w8 02022882 0107` Free Battle blue infantry; `w8 020225D6 0e09` M7 enemy unit; records at EWRAM 0x02022580.., type byte 0x020225A4; record stride/field layout (unverified)). Caveat: AI must choose to capture; prior HQ test made the second side human.
- Saves available: output/qa/part2_2026-10-06/anchor_m10_day6/game.sav (M10 D6), part2_2026-09-23/round8_m7_live (M7), round13_m8_cold_live (M8), round5/4_m6_live (M6), part2_2026-09-28 round16..23_m8*, part2_2026-09-30 m8_victory_*, part2_2026-10-07/m11_* (+cheat_m11_effc = cheat), part2_v9_rowfit_20261012 (M28 variants), P2/round6_final_sram_copy.sav (Free Battle sha ece0b0c8..), P2/sweep2_m7_day2_{original,candidate}_input.sav (M7 Day2 sha 6a13b53b..), P2/sweep3b_war_records_populated_final_candidate/victory.sav (War Room). Mission of the defense map: none of these is verified to be the 14-day defense mission (unverified); find by scanning saves' running mission or checking hint text on entry.
- Steps: (i) pick save, ROM-bound cold boot with `--read-only-save`; (ii) enter mission, record the shown win/loss text and day limit; (iii) cheat: enemy infantry onto own HQ (label CHEAT) or play natural; (iv) capture -> shot sequence of loss dialogue (A1703C ..) both ROMs.

## 3. Hidden COs (natural unlock)
- Roster builder: thumb fn 0x083451A4. ROM CO list at 0x0881C820 = `01 02 04 00 0f 80 | 03 05 10 81 | 06 07 12 83 | 08 09 11 82 | 0b 0c 0d 0e 0a 84 | ff` (army groups; high bit = group header). For each id it calls 0x0833D02C and, if nonzero, appends id to IWRAM 0x03005A70 and ++ count at 0x03005AD0+army. (verified static)
- **Availability bit: bit (id&7) of byte EWRAM 0x02027EBC + 0x2D + (id>>3)** (fn 0x0833D02C). Hidden: id 0x0F (Hachi) = byte 0x02027EEA bit7 (mask 0x80); id 0x0A (Sturm/Helboze per sweep note) = 0x02027EEA bit2 (mask 0x04). Normal 17 = 4/3/3/3/4, hidden make 5/3/3/3/5. (verified static; SRAM offset of the persisted mirror and unlock writer (War Shop purchase with campaign points? Hachi runs the "Wars Shop", A2D8E0) are (unverified))
- Prior evidence: P2/sweep3b_co_hidden_table.py wrote `w8 03005A70 0f|0a` into the built roster (RAM substitution, both ROMs, captures in sweep3b_co_hidden_table_{candidate,original}); co select state P2/sweep3b_co_select_diff/co_select.ss0; BP at 0x0837DC4E hit in the UI draw (sweep3b_co_bp).
- Ready test-only steps: before entering CO select (build happens on entry) `w8 02027EEA <old|0x84>` (read old byte first with dumpmem) or use the existing purchased-save setup (sweep2_co_*_input.sav, "same purchased-save setup"); then open CO select, RIGHT/UP-DOWN to army 0/4, shot select + R profile. Natural unlock condition (shop price / mission clear) is not in repo (unverified) -> external question.

## 4. Cable (link) battle
- tools/mgba_link_harness.c (VERIFY-4b, single-threaded deterministic SIO driver, two cores) HAS native multiplayer + Normal-32 transfer when run with the real BIOS `--bios temp/bios/gba_bios.bin` (exists, sha fd254772...) and client slot `-`: usage `temp/release_C/verify4b/mgba_link_harness --bios temp/bios/gba_bios.bin HOST_ROM - LOG`. Binary is x86-64 ELF (exists). Commands: frames/framesc/frames1, keys PLAYER MASK, shot/syncshot PLAYER FILE, link on|off, savestate/loadstate PLAYER FILE, dumpmem/w16/w32 PLAYER ..., sio/siotrace/status (tools/mgba_link_harness.c:5-23).
- Evidence it works: docs/screenshots/verify4_2026-10-15/part2_onepak_native_link.json (b35: host cold LINK*MODE -> MultiBoot -> P2 send -> client day-1 banner, exit 0) and docs/screenshots/canon8_2026-10-18/linked_clients.json + temp/release_C/canon8/link/part2/{transfer,day_banner}/receipt.json (b39 ROM 7e00df.., full command transcript incl. host_end.ss0/client_end.ss0 states, xfer_multi=448 after link on). The FAILED 2026-10-23 attempt (SWEEP3_REPORT row H; docs/fail.md:1676) used HLE (no BIOS): xfer_multi=0. So use BIOS mode.
- This is the Single-Pak (one cartridge + MultiBoot client) cable battle. Two-cartridge (Multi-Pak) mode: harness setup_core(players[1], rom, mb ...) supports a client MB or empty; a second real cartridge on player 1 is not an advertised option (unverified).
- emucap (MCP): single emulator per connection (Mesen2 GBA); no link-cable/two-core support described in its tool docs (unverified; not tried). mgba-qt exists at /usr/bin/mgba-qt (multi-window lockstep link, GUI, unverified here).
- Steps: (1) for each ROM (original + candidate) run the canon8 transfer route (receipt route inputs) with `--bios`; (2) save host_end/client_end .ss0 (they are ROM-bound: regenerate for the 20261026 gate, b39 states cannot be reused); (3) `link on`, step to map select/rules/battle start with frames+keys per PLAYER, `syncshot` both players; (4) compare original vs candidate; battle UI and day banner are what is untested beyond the day-1 banner.

## Constraints noted
- CLAUDE.md: temp/ only for scratch; keep cheats labelled; don't reuse savestates across ROM; heavy emulator jobs 1 at a time with memcap/nice; B-team protected strings unchanged.

## Questions for research-external
1. In AW2 (GBA, Japan) what does the cursor/R terrain card show for terrain type 9 (lake?) vs black-hole "impassable"; what are the 4 cannon variants and "Hレーザー"? Do type 0x1e/0x19 tiles exist in any campaign map?
2. How are Hachi and the second hidden CO unlocked natively (shop points, mission clears)?
3. Does the AW2 Japan ROM implement a 2-pak link battle that mGBA can lockstep (mgba-qt multiplayer)?

RECEIPT: model=sonnet effort=medium role=research-internal
