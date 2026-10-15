# VERIFY-4b native one-pak link route (b35)

Needs a real GBA BIOS at `temp/bios/gba_bios.bin` (SHA-256
`fd2547724b505f487e6dcb29ec2ecff3af35a841a77ab2e85fd87350abd36570`, git-ignored;
never copy it into tracked paths). Both cores load it; the client cartridge slot
is empty, so the client boots the BIOS and receives a genuine MultiBoot download.

Build:

```sh
cc -O2 -Wall -Wextra tools/mgba_link_harness.c -lmgba -o temp/release_C/verify4b/mgba_link_harness
```

Route (every step under `memcap -n aw-kor-verify4b -- nice -n 15`):

```sh
V=temp/release_C/verify4b
# cold host -> MODE★SELECT (host only)
python3 tools/scene_routes/verify4_link/bios_nav.py $V/nav1 link:off wait:480 A:2:200 START:2:200 DOWN:2:120 A:2:240 START:2:240 A:2:200 save:$V/nav1/s06.ss0
# 통신 -> LINK★MODE
python3 tools/scene_routes/verify4_link/bios_nav.py $V/nav4 link:off load:$V/nav1/s06.ss0 DOWN:2:40 DOWN:2:40 DOWN:2:40 A:2:180 save:$V/nav4/s01.ss0
# 1팩 대전, wait for idle handshake, START: MultiBoot + P2 payload send -> map select
python3 tools/scene_routes/verify4_link/bios_nav.py $V/link8 link:off load:$V/nav4/s01.ss0 siotrace:sio_trace.log \
  watch:0:08804FC8:8:r:host_watch.log watch:0:0892DF84:4:r:KEEP ... link:on UP:2:60 A:2:400 START:2:10 \
  wait:250 ... dump:1:02000000:0x40000:client_ewram.bin save:$V/link8/host_end.ss0 savec:$V/link8/client_end.ss0
# resume the pair, pick MAP1, capture the client day-1 banner
python3 tools/scene_routes/verify4_link/bios_nav.py $V/link11 link:off load:$V/link8/host_end.ss0 loadc:$V/link8/client_end.ss0 \
  link:on wait:30 A:2:30 wait:110 wait:3 cshot:c00 ... (40 shots, settled banner at c16..c25)
python3 tools/scene_routes/verify4_day_banner/match.py output/game_wars_korean_candidate_20261015_b35.gba $V/link11/c18_p1.png $V/link11/match_c18.json
python3 tools/scene_routes/verify4_link/payload_id.py $V/link8/client_ewram.bin $V/link8/payload_id.json
```

Notes:
- Press START only once the handshake idles at `6202/7202`; START earlier, or
  paired savestates loaded during the handshake, re-initialise the master library.
- Paired savestates after the payload has started (map select) resume correctly.
- Evidence summary: `docs/screenshots/verify4_2026-10-15/part2_onepak_native_link.json`.
