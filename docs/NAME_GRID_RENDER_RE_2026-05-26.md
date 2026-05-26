# GBA name grid render findings and patch

Date: 2026-05-26

## Render routine

The name grid is rendered during the name input init path around `0x08B48800`.

Confirmed direct calls:

- `0x08B48910`: `bl 0x08B1311C`, row string `r3 = 0x08DF8C38`, x/y = `6,6`
- `0x08B48920`: `bl 0x08B1311C`, row string `r3 = 0x08DF8C60`, x/y = `6,8`
- `0x08B48930`: `bl 0x08B1311C`, row string `r3 = 0x08DF8C88`, x/y = `6,10`
- `0x08B48940`: `bl 0x08B1311C`, row string `r3 = 0x08DF8CB0`, x/y = `6,12`
- `0x08B48950`: `bl 0x08B1311C`, row string `r3 = 0x08DF8CCC`, x/y = `6,14`
- `0x08B48960`: `bl 0x08B1311C`, row string `r3 = 0x08DF8CE8`, x/y = `6,16`

`0x08B48E50` remains the name preview renderer. It also calls `0x08B1311C`, but it reads from `obj+0x2c` and draws the top NAME box, not the 6-row grid.

## Why the gaps and symbols appear

The grid layout is not computed from `0x02010CEC` or the older SET1/SET2 tables. It is baked into the six live row strings above.

The string format is:

- `0A 09` prefix
- raw Shift-JIS bytes
- `0A 00 00 00` row terminator/padding

Original examples:

- row1 middle: `83 84 81 40 83 86 81 40 83 88`
  - This is `ヤ`, full-width space, `ユ`, full-width space, `ヨ`.
  - After the current glyph slot patch this becomes visually `f _ g _ h`.
- row3 middle: `83 8F 81 40 83 92 81 40 83 93`
  - This is `ワ`, space, `ヲ`, space, `ン`.
  - After the glyph patch this becomes visually `n _ o _ p`/related gap behavior depending on slot remap.
- row2 right: `81 68 81 4B 81 45 81 49 81 48`
  - This is the visible symbol row under the digits.

So this part is data-driven, not a Thumb branch/coordinate skip.

## Patch implemented

Implemented in `tools/build_korean_full.py`:

- Added `NAME_GRID_ROW_LAYOUTS`.
- Added `_name_grid_row_bytes()`.
- Extended `patch_name_grid()` to patch the six live row strings after the existing base8 table and glyph-slot injection.

New visual layout:

```text
ABCDE abcde 01234
FGHIJ fghij 56789
KLMNO klmno      
PQRST pqrst
UVWXY uvwxy
Z     z
```

The right-side symbol row is replaced with five `0x8140` full-width spaces. The middle area no longer contains `0x8140` holes in the rows that previously had katakana structural gaps.

## Build verification

Command run:

```sh
python3 tools/build_korean_full.py
```

Result:

- Build succeeded.
- Output: `output/game_wars_korean_full.gba`
- Header checksum was recomputed by the build script.

Spot-checked output row bytes:

- `0x08DF8C60` middle is now `83 84 83 86 83 88 83 89 83 8A`
- `0x08DF8C88` right side is now `81 40 81 40 81 40 81 40 81 40`
- `0x08DF8CB0` middle is now `83 93 83 40 83 42 83 44 83 46`
- `0x08DF8CCC` middle is now `83 48 83 62 83 83 83 85 83 87`
- `0x08DF8CE8` middle is now `81 5B 81 40 81 40 81 40 81 40`

## Remaining notes

The cursor/input path still has separate state and lookup logic around `0x08B48EF0..0x08B49336`. This task targeted the render layout verified through BG0 tilemap. I did not change cursor navigation logic because the requested visual fixes are achieved through the live render row data, and changing selection logic has a higher risk of affecting name entry behavior.
