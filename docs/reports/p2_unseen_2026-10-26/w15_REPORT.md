BLOCKED: The valid M7 map's own-HQ Capture route remains unreached. The C12 fallback **did** reach native own-HQ Capture, loss dialogue, failure result, and post screen on both ROMs by CHEAT.

# W15 CHEAT own-HQ loss QA — 2026-10-26

## Outcome and identity

- **C12 fallback: reached, CHEAT.** The original ROM (`a8ad7c7d2a48b4ce…`) and candidate (`01f65b11d0dfa65c…`) each used its own matching emulator state and the read-only W4 map-ID `0x96` save (`fd10ef4da29de722…`). The save has a C12 map with mixed M7 units, so this proves native Capture/result rendering in this constructed state, not natural C12 mission reachability or the M7-specific script.
- **M7: BLOCKED.** On both ROMs, changing all three known copies of the `(2,2)` Black Hole APC (`0x02000458`, `0x020024AA`, `0x020228E0`) to infantry before the Black Hole turn left the target unselectable at the expected cell. Selecting the native APC first, then changing its type, allowed one native move and Wait to `(2,3)` (live record changed); after the next BH/Orange/BH turn cycle, that converted unit remained unselectable. Synchronizing the three copies' coordinates and acted flags did not restore selection. The screen and command evidence is in `entry/`, `select_probe/`, `first_walk/`, `next_turn/`, `cycle_finish/`, `scan_after_walk/`, and `sync_probe/` (original), with the matching core probes in `candidate/`.
- **C12 successful route:** `w8 02023207 01` made Black Hole human controlled. A naturally selectable Black Hole mech at `(0,4)` moved with native D-pad/A/Wait along `(0,2) → (0,1) → (2,1) → (4,1) → (6,1)`. Black Hole and Orange Star turns used native End Turn. The only route terrain cheats were type `01` (plain) at `x=0,y=1..3` and `x=1..5,y=1`; the actual HQ at `(6,1)` kept type/owner byte `0x28` until native Capture changed it to `0x48` on both ROMs. Cursor RAM `0x030034F0` positioned the cursor; movement and both HQ Capture actions were native. No unit teleport or forced result event was used in the successful route.

## Paired screens and every-frame evidence

- [CHEAT capture pair](capture_paired.png): first Capture `20→10`, second Capture `10→0`, native `占領!` / `점령!` banner, and own-HQ-loss dialogue.
- [CHEAT dialogue pair](dialogue_paired.png): the subsequent dialogue pages.
- [CHEAT result/post pair](result_post_paired.png): `作戦失敗` / `작전 실패`, the campaign map after the result, and its next dialogue.
- For **each ROM**, every frame is saved as PNG: `c12_capture1/frame_000..239.png` (240), `c12_capture2/frame_000..419.png` (420), `c12_dialogue_advance/step_0..3_frame_000..179.png` (720), and `c12_post/step_0..7_frame_000..179.png` (1,440). Total: **2,820 frames per ROM**. Each segment has `commands.json` with exact command/reply sequence, ROM/save SHA, exit code, and source-state metadata; `*.ss0` joins the segments. The paired sheets are selected frames; the full sequences are in the per-ROM directories.

## Candidate screen judgment

- The selected candidate screens show legible `점령`, `점령!`, `작전 실패`, and `캠페인`. The sampled dialogue preserves the meaning of the original: `ああ、守りきれなかった…` is `아아, 지켜 내지 못했다…`; the subsequent tactical comments about defending a narrow route and indirect fire are also represented. I saw no residual Japanese, broken Hangul, or clipping in the paired key screens. The full 2,820-frame sequences were captured, but a manual judgment of every individual frame is **(unverified)**.
- C12's mixed save and RAM terrain edits limit gameplay conclusions. Real hardware and unmodified campaign reachability are **(unverified)**. M7's own-HQ-loss-specific script is **(unverified)**.

## Files, checks, and remaining risk

- Added only `temp/unseen_20261026/w15/probe.py`, `make_sheets.py`, `REPORT.md`, paired sheets, per-ROM command/state/frame evidence, and zoom crops. No tracked source edit or commit by this worker.
- Every emulator command was serial under `memcap -n aw-w15 -- nice -n 15 ...`; `memcap` reported `systemd user bus 접근 불가(샌드박스?) — 메모리 상한 없이 대기열만 적용`. CPU temperature was below 80°C before work. Each reported emulator exit code is `0`.
- `python3 temp/unseen_20261026/w15/make_sheets.py` output: `capture_paired.png 4`, `dialogue_paired.png 6`, `result_post_paired.png 3`.
- `python3 -m py_compile temp/unseen_20261026/w15/probe.py temp/unseen_20261026/w15/make_sheets.py` exited `0` with no output. Frame count check output: `frame count checks PASS` (240 + 420 + 720 + 1,440 per ROM).
- Remaining blocker: no native M7 HQ Capture; no claim that C12's mixed map/save is a natural campaign route.

RECEIPT: model=unknown effort=unknown role=code
