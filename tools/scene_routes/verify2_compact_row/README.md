# `0x804FC8` candidate prompt probes

ROM: `output/game_wars_korean_full.gba`, SHA-256 `7c6f15fad29fab2a4d0a40becaffe06380cb2a4231a77f452e69a42ad611d78a`. Run each script separately, under `memcap -n aw-kor-verify2 -- nice -n 15 python3 tools/scene_routes/verify2_compact_row/<script>`. Use only one emulator at a time.

| Script | Cold boot source | Native screen / positive read control | Output |
|---|---|---|---|
| `probe.py` | No cartridge save | Part 1 name confirm / `0x08D835BC` | `temp/release_C/verify2_compact_name/` |
| `shop_prompt_probe.py` | Copied migrated save from `temp/release_C/rebind1/help/F_help_sweep/game.sav`, SHA `d1210b1d8fe444a3cc84eb8ae272c0076375107f93ce97b37d786f0efc2e9d51` | Part 1 shop buy confirm / `0x08DF8B6A` | `temp/release_C/verify2_compact_shop/` |
| `part2_prompt_probe.py` | Copied migrated save from `temp/release_C/rebind1/runs/C_3p_surrender/game.sav`, SHA `0a964addd4ca5f7f01806b8f38e0b93dd3541e8c2fbb178d0bed7cfadada0d04` | Part 2 surrender confirm / `0x08A34B6C` | `temp/release_C/verify2_compact_part2/` |
| `part1_save_probe.py` | Copied migrated save from `temp/release_C/rebind1/help/F7BE_b2/game.sav`, SHA `f3d143111ee24c7a00e780cd3881f36306b14f4cb523ad65de1655e3a6816cb1` | Part 1 battle save yes/no / VS help `0x08A7BFEE` | `temp/release_C/verify2_compact_part1_save/` |
| `link_client_probe.py` | Copied migrated save from `temp/release_C/rebind1/help/F_help_sweep/game.sav`, SHA `d1210b1d8fe444a3cc84eb8ae272c0076375107f93ce97b37d786f0efc2e9d51` | Part 1 communication menu and cable setup / menu help codes 20 and 22 | `temp/release_C/verify2_compact_link/` |

All copied cartridge saves are conservatively `cheat_tainted`; no cross-ROM savestate is loaded. All five runs exited 0. Target read watches `0x08804FC8..0x08804FCF` were zero, with positive controls and exact frames recorded in `docs/screenshots/verify2_2026-10-15/compact_row_coverage.json`. The cable setup did not establish an actual linked client handshake. Delete confirmation remains untested. This is bounded negative evidence, not a global dead-code proof.
