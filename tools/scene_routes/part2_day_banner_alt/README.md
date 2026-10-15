# Part 2 alternate day sheets — VERIFY-1 static route diagnosis

Target ROM: `output/game_wars_korean_full.gba`, SHA-256 `7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a`.

**Runtime status: (unverified).** No active screenshot is registered for any of the eight alternate ROM offsets. The normal host result route uses `0x45EC74` (b32r5 `temp/release_C/w2b6f_scene28_extended/emulator.log.gz`: `SWI: 11 r0: 0845EC74`). Its result frame matches all four decoded `0x45EC74` glyph cells at score 1.0. Each alternate `작전` cell also matches those two visible cells at score 1.0 because the patched art is byte-identical; a screenshot template match alone cannot identify the source sheet.

## Where the eight sheets reside

| Main `일째개시` | Separate `작전` | Containing embedded image/payload | Sheet offsets from base |
|---|---|---|---|
| `0x92DF84` | `0x92EB5C` | `0x90DC7C..0x9463FC` | `+0x20308`, `+0x20EE0` |
| `0x966C0C` | `0x9677E4` | `0x9463FC..0x97ECA0` | `+0x20810`, `+0x213E8` |
| `0x99F4B0` | `0x9A0088` | `0x97ECA0..0x9B7544` | `+0x20810`, `+0x213E8` |
| `0x9D7D54` | `0x9D892C` | `0x9B7544..0x9EFDE8` | `+0x20810`, `+0x213E8` |

The last three embedded images are byte-identical for their full `0x388A4` length and begin with GBA headers. The first payload is `0x38780` bytes; its SHA-256 is `c3bdbbb635c04e68a0ecdaa465132dd436d6524c89f737aa9134d6b4e053a649` (`temp/release_C/verify1_multiboot/client0.bin`, copied only for static analysis). The four main streams decompress to 7168 bytes each, and the four word streams to 1024 bytes each. All six localized glyph cells in every pair are byte-identical to the corresponding `0x45EC74` cells. `PYTHONPATH=tools python3 -m unittest tools.test_part2_battle_day_banner -v` passed 2 tests.

## Loader path and limits

- The address `0x0838B454` is **BIOS MultiBoot** (`SWI 0x25`, confirmed by the installed mGBA `GBA_SWI_MULTI_BOOT` definition), not the LZ77 decompressor. `0x0838B450` is `SWI 0x11`, as recorded for `0x45EC74` in the b32r5 host route.
- Host table `0x08391400` contains `0x0890DC7C` and `0x089463FC` as adjacent payload bounds. Host function around `0x08333980..0x08333A00` configures transfer state, waits for a successful client/link status, and DMA-copies `[0x0890DC7C, 0x089463FC)` to EWRAM `0x02000000`. Exact mode-menu trigger and the role of the three later copies are (unverified).
- In that copied client payload, Ghidra at `0x0200E4D8` shows two decompressor calls with source pointers at `0x0200E5B0 → 0x02020308` (the copied `0x92DF84` sheet) and `0x0200E5B8 → 0x02020EE0` (the copied `0x92EB5C` sheet). The other three byte-identical images contain the analogous rebased pointers `0x02020810` and `0x020213E8` at relative `+0xE8C4/+0xE8CC`. This demonstrates a client-side banner loader, not an observed client frame.
- No exact 32-bit host ROM pointer to any of the eight alternate asset addresses exists. Three inspected b32r5 host logs contain zero `SWI 0x11` hits for all eight offsets. This negative observation is limited to those routes; it is not a proof of dead code.
- Capturing the client banner as actual b32r5 runtime evidence requires a linked client execution path and a source trace. This worker was limited to one emulator at a time, so no linked host/client run was performed. An extracted payload boot would have a different loaded-ROM hash and cannot be registered as a canonical b32r5 frame.

Read-only audit: `python3 temp/release_C/verify1_multiboot/audit.py` → `temp/release_C/verify1_multiboot/audit.json`. This records decompressed hashes, exact pointer counts, and palette-mapped nontransparent pixel scores for the visible reference frame. It does not mark any alternate sheet runtime-proven.

## VERIFY-3 direct client boot boundary

Installed Linux libmGBA is 0.10.5 with `GBALoadMB` and GBA SIO lockstep headers. `temp/release_C/verify3/mgba_mb_probe.c` is an experimental copy of `tools/mgba_harness.c` that loads `temp/release_C/verify1_multiboot/client0.bin` into EWRAM with `AW_MB_FILE`. This extracted program's ARM entry is at byte 0; libmGBA's usual `.mb` entry at byte `0xC0` starts in the middle of code and crashes. The probe sets PC `0x02000000` after reset. Build with `cc -O2 -I/usr/include temp/release_C/verify3/mgba_mb_probe.c -lmgba -o temp/release_C/verify3/mgba_mb_probe`; then run `AW_MB_FILE=temp/release_C/verify1_multiboot/client0.bin memcap -n aw-kor-verify3 -- nice -n 15 temp/release_C/verify3/mgba_mb_probe output/game_wars_korean_full.gba temp/release_C/verify3/mb_entry0.log` with `frames 180`, `shot ...`, `quit` on stdin. It reaches the client `WAIT` screen at frame 180, still waiting at frame 880. Screenshot and hashes: `docs/screenshots/verify3_2026-10-15/part2_extracted_client_wait.json`. This is supplementary extracted-program evidence only; no cartridge link, banner sheet source read, or handshake row read was observed.

The installed libmGBA HLE BIOS does not implement MultiBoot SWI `0x25` (official mGBA 0.10.5 `src/gba/bios.c` default stub), so a canonical single-pak host transfer requires an external BIOS or a correct host-side transfer stub. That path remains (unverified).
