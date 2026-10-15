# VERIFY-2 Part 1 compact help natural-route probes

ROM `output/game_wars_korean_full.gba` SHA-256 `7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a`.

Run each separately: `memcap -n aw-kor-verify2 -- nice -n 15 python3 tools/scene_routes/verify2_part1_help/probe.py F_help_sweep` and the same command with `F7BE_b2`. Each cold boots from a copied cartridge save, replays the recorded native inputs, watches the seven compact help pointer-table entries corresponding to the 11 synthetic-only windows, and captures menu screenshots. The source saves were migrated from an older release ROM; classify the routes `cheat_tainted`. No cross-ROM savestate or code injection is used.

`F_help_sweep` visits the shop, campaign, VS, and communication menus; `F7BE_b2` reaches the native VS-continue help. Both recorded a positive help-row read but zero reads of all seven target entry starts. Raw logs/receipts are under `temp/release_C/verify2_part1_help/<route>/`. SHA-bound captures and code/address mapping are in `docs/screenshots/verify2_2026-10-15/part1_help_route_coverage.json`. No target window was promoted to natural-route status.

Static boundary: `FUN_08B4AF08` indexes the help pointer table at `0x08DFAAB8` with the current code's low seven bits. `FUN_08B3ED10` emits menu codes from 20-byte nodes, filtering them via the callback at node `+4`. The root tree at `0x08DEFFC4` does not list codes 0, 5, or 6; a detached node table at `0x08DF01A4` contains codes 16–19, and no exact ROM pointer to its start was found. These observations do not prove the target windows globally unreachable because other menu initialization paths may exist.
