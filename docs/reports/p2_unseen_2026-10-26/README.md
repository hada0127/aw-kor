# Part 2 unseen screens sweep — 2026-10-26

Scratch evidence: `temp/unseen_20261026/` (local). Per-worker reports copied here (paths inside are relative to the temp dir).

| Item | Result |
|---|---|
| Generic cannon / laser terrain card | PASS (CHEAT RAM terrain write) — w1 |
| Hell Laser (type 0x1e) | DEFECT `A레이저` → fixed `헬레이저` in 8d72a6e (compact popup; big card uses B-team `헬 레이저`) — w1, w5 |
| Lake 湖 | Static: type 0x09 → compact label idx 8 reachable in M10 data; live compact/big card not captured — BLOCKED — w4 |
| Campaign own-HQ loss (C12 Two-Week Test, IDs 0x044F..0x0451) | PASS (CHEAT: SRAM map 0x96 + test ROM forcing native loss event); natural HQ capture BLOCKED. Text and following 14-day lines match original page order — w4 |
| Hidden COs Hachi / Hellbouze | PASS (CHEAT unlock bits 0x02027EE7 0x80/0x04 via native roster builder; shop list/description) ; native purchase BLOCKED — w4 |
| Part 2 link (Single-Pak) | PASS menus/waiting/day banner/menus/surrender; English map-select labels are original art. Host freeze after surrender = harness two-core state reload artifact (uninterrupted run reaches 작전성공 + lobby) — w2, w3 |
| Multi-Pak, link CO select, alternate link messages | BLOCKED (harness) |

## Round 2 (cheats allowed, 2026-10-26)

| Item | Result |
|---|---|
| Lake 湖/호수 compact label | PASS (CHEAT; no separate 湖 R-card title exists) — w10 |
| Own-HQ capture loss (C12) | PASS (CHEAT: map 0x96 save + RAM; native move + two native Captures; 점령! banner, loss dialogue, 작전실패, campaign map) — w15 |
| Hidden CO purchase + save + reboot roster | PASS (CHEAT points/flags; native purchase/save) — w6 |
| Multi-Pak link menus → battle start; 9 link waiting messages (live pointers) | PASS — w7, w12 (w7 msg cheat used stale slots; w11/w12 corrected) |
| Multi-Pak result, link CO picker | BLOCKED (surrender input not accepted in Multi-Pak; no separate picker observed) |
| Part 2 LINK MODE newspaper BG | DEFECT since b2 (sequential sheet vs native tilemap at 0x5B5D10/0x5B58E0) — w14; fix pending user choice |
| Link harness | fixed 56f2179 (--rom2, savepair/loadpair) |
