# Editor gate acceptance fixture

Run from the repository root. The fixture executes the pinned final ROM bytes in Unicorn and asserts register, branch, and write behavior for 140 cases.

## Dependency and ROM

Install Unicorn 2.1.4 into the ignored local directory:

```sh
python3 -m pip install --target temp/gate_pydeps unicorn==2.1.4 --disable-pip-version-check
```

The fixture requires `output/game_wars_korean_gate_r3_0126.gba` with SHA-256 `4fd453daf1ac0d065ecd322fa71943e7ee53e69ba7abfd3984fd9e41c2db210d`. To rebuild it, provide the verified, unmodified Japanese source ROM at `original/Game Boy Wars Advance 1+2 (Japan).gba`, then run:

```sh
python3 -B tools/build_korean_full.py --base 'original/Game Boy Wars Advance 1+2 (Japan).gba' --out output/game_wars_korean_gate_r3_0126.gba --no-sync-outputs
sha256sum output/game_wars_korean_gate_r3_0126.gba
```

The source ROM is not included. Its documented SHA-256 begins `a8ad7c7d` and ends `3831c`; verify its full digest against the project's source record before rebuilding. The rebuild was not run in this worktree because the source ROM is absent. The fixture refuses a ROM whose full digest differs from its pin.

## Rerun on 2026-10-26

```sh
PYTHONPATH=temp/gate_pydeps python3 -B tools/gate_thumb_fixture.py temp/gate_thumb_results.json
```

Exit code: **0**. Output: `PASS 140 real Thumb cases, ROM 4fd453daf1ac0d065ecd322fa71943e7ee53e69ba7abfd3984fd9e41c2db210d, evidence temp/gate_thumb_results.json`. Runtime Unicorn version: `2.1.4`. The output JSON is temporary; archived `thumb_cases.json` is the prior acceptance case summary with assertion-based register checks, not a complete register/write trace.

See [REPORT.md](REPORT.md) for the bounded acceptance result and [INDEX.md](INDEX.md) for checksums of retained evidence. The representative PNGs and JSON are archived here; full VRAM dumps, SAVs, ROMs, and process logs are excluded.
